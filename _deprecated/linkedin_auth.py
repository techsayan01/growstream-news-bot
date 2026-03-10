"""
GrowStream — LinkedIn OAuth 2.0 Authorization Code Flow Helper.

Runs a one-time local OAuth flow to get a valid LinkedIn access token with
the right scopes for posting (w_member_social / w_organization_social).

Prerequisites:
  1. In your LinkedIn Developer app settings, add this Redirect URL:
       http://localhost:8080/callback
  2. Ensure LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET are set in .env or .zshrc.

Usage:
    python linkedin_auth.py

After completion, copy the printed access token into your .env / .zshrc as:
    LINKEDIN_ACCESS_TOKEN=<token>
"""

import http.server
import os
import secrets
import threading
import urllib.parse
import webbrowser

import requests

# Load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path="growstream/.env", override=False)
except ImportError:
    pass

CLIENT_ID     = os.environ.get("LINKEDIN_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("LINKEDIN_CLIENT_SECRET", "")
REDIRECT_URI  = "http://localhost:8080/callback"

# Scopes needed:
#   openid + profile + email  → /v2/userinfo (verify token works)
#   w_member_social           → post as personal profile (UGC Posts API)
#   w_organization_social     → post as company page (UGC Posts API)
SCOPES = "openid profile email w_member_social"


# ── OAuth callback server ──────────────────────────────────────────────────

_auth_code: str | None = None
_state_received: str | None = None
_server_ready = threading.Event()
_code_received = threading.Event()


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        global _auth_code, _state_received
        parsed = urllib.parse.urlparse(self.path)
        params = dict(urllib.parse.parse_qsl(parsed.query))

        _auth_code = params.get("code")
        _state_received = params.get("state")

        if _auth_code:
            body = b"<h2>Authorization successful! You can close this tab.</h2>"
        else:
            error = params.get("error_description", params.get("error", "unknown"))
            body = f"<h2>Authorization failed: {error}</h2>".encode()

        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        _code_received.set()

    def log_message(self, fmt, *args):
        pass  # silence request logs


def _start_server():
    server = http.server.HTTPServer(("localhost", 8080), _CallbackHandler)
    _server_ready.set()
    server.handle_request()   # handle exactly one request then stop
    server.server_close()


# ── Main flow ──────────────────────────────────────────────────────────────

def main():
    if not CLIENT_ID or not CLIENT_SECRET:
        print("ERROR: LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET must be set.")
        print("  Add them to growstream/.env or export them in your shell.")
        return

    # Start the local callback server in a background thread
    t = threading.Thread(target=_start_server, daemon=True)
    t.start()
    _server_ready.wait()

    state = secrets.token_urlsafe(16)

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
    print("  GrowStream — LinkedIn OAuth Authorization")
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

    # Exchange code for access token
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

    print("\n✅ Access token obtained!")
    print(f"   Expires in: {expires_in // 86400} days\n")

    # Quick verification
    me = requests.get(
        "https://api.linkedin.com/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    if me.status_code == 200:
        info = me.json()
        print(f"   Verified as: {info.get('name', info.get('sub', 'unknown'))}")
    else:
        print(f"   Note: /v2/userinfo returned {me.status_code} (token may still work for posting)")

    print("\n──────────────────────────────────────────────")
    print("  Add to your .env file (or export in .zshrc):")
    print("──────────────────────────────────────────────")
    print(f"\nexport LINKEDIN_ACCESS_TOKEN={access_token}\n")
    print("Then re-source your shell:  source ~/.zshrc")
    print("──────────────────────────────────────────────\n")


if __name__ == "__main__":
    main()
