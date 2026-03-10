"""
LinkedIn OAuth 2.0 Authorization Code Flow Helper.

Runs a one-time local OAuth flow to get a valid access token with the
scopes needed for posting (w_member_social / w_organization_social).

Prerequisites:
  1. In your LinkedIn Developer app settings, add this Redirect URL:
       http://localhost:8080/callback
  2. Set LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET in .env or shell.

Usage:
    python -m auth.linkedin
    # or
    python auth/linkedin.py

After completion, copy the printed token into your .env file as:
    LINKEDIN_ACCESS_TOKEN=<token>
"""

import http.server
import os
import secrets
import threading
import urllib.parse
import webbrowser
from pathlib import Path

import requests

# Load .env
try:
    from dotenv import load_dotenv
    for _p in [Path(__file__).parent.parent / ".env",
               Path(__file__).parent.parent / "growstream" / ".env"]:
        if _p.exists():
            load_dotenv(dotenv_path=_p, override=False)
            break
except ImportError:
    pass

CLIENT_ID     = os.environ.get("LINKEDIN_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("LINKEDIN_CLIENT_SECRET", "")
REDIRECT_URI  = "http://localhost:8080/callback"
SCOPES        = "openid profile email w_member_social"

_auth_code:      str | None = None
_state_received: str | None = None
_server_ready  = threading.Event()
_code_received = threading.Event()


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        global _auth_code, _state_received
        parsed              = urllib.parse.urlparse(self.path)
        params              = dict(urllib.parse.parse_qsl(parsed.query))
        _auth_code          = params.get("code")
        _state_received     = params.get("state")

        body = (
            b"<h2>Authorization successful! You can close this tab.</h2>"
            if _auth_code
            else f"<h2>Authorization failed: {params.get('error_description', 'unknown')}</h2>".encode()
        )
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        _code_received.set()

    def log_message(self, fmt, *args):
        pass


def _start_server():
    server = http.server.HTTPServer(("localhost", 8080), _CallbackHandler)
    _server_ready.set()
    server.handle_request()
    server.server_close()


def main():
    if not CLIENT_ID or not CLIENT_SECRET:
        print("ERROR: LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET must be set.")
        return

    t = threading.Thread(target=_start_server, daemon=True)
    t.start()
    _server_ready.wait()

    state    = secrets.token_urlsafe(16)
    auth_url = (
        "https://www.linkedin.com/oauth/v2/authorization?"
        + urllib.parse.urlencode({
            "response_type": "code",
            "client_id":     CLIENT_ID,
            "redirect_uri":  REDIRECT_URI,
            "state":         state,
            "scope":         SCOPES,
        })
    )

    print("\n──────────────────────────────────────────────")
    print("  LinkedIn OAuth Authorization")
    print("──────────────────────────────────────────────")
    print(f"\nOpening browser for LinkedIn authorization…")
    print(f"\nIf the browser doesn't open, visit:\n  {auth_url}\n")
    webbrowser.open(auth_url)

    print("Waiting for LinkedIn to redirect back to localhost:8080 …")
    _code_received.wait(timeout=120)

    if not _auth_code:
        print("\nERROR: No authorization code received (timed out or denied).")
        return

    if _state_received != state:
        print("\nERROR: State mismatch — possible CSRF. Aborting.")
        return

    print("\nExchanging authorization code for access token…")
    r = requests.post(
        "https://www.linkedin.com/oauth/v2/accessToken",
        data={
            "grant_type":    "authorization_code",
            "code":          _auth_code,
            "redirect_uri":  REDIRECT_URI,
            "client_id":     CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )

    if r.status_code != 200:
        print(f"\nERROR: Token exchange failed ({r.status_code}): {r.text}")
        return

    data         = r.json()
    access_token = data.get("access_token", "")
    expires_in   = data.get("expires_in", 0)

    print(f"\n✅ Access token obtained! Expires in: {expires_in // 86400} days\n")

    me = requests.get(
        "https://api.linkedin.com/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    if me.status_code == 200:
        info = me.json()
        print(f"   Verified as: {info.get('name', info.get('sub', 'unknown'))}")

    print("\n──────────────────────────────────────────────")
    print("  Add to your .env file:")
    print("──────────────────────────────────────────────")
    print(f"\nLINKEDIN_ACCESS_TOKEN={access_token}\n")
    print("──────────────────────────────────────────────\n")


if __name__ == "__main__":
    main()
