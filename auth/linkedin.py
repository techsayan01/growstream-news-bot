"""
LinkedIn OAuth 2.0 Authorization Code Flow Helper.

Runs a one-time local OAuth flow to get a valid access token with the
scopes needed for posting (w_member_social / w_organization_social).
Saves the access token AND refresh token directly into your .env file.

Prerequisites:
  1. In your LinkedIn Developer app settings, add this Redirect URL:
       http://localhost:8080/callback
  2. Set LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET in .env or shell.

Usage:
    # Full browser OAuth (first time or when refresh token has also expired):
    python auth/linkedin.py

    # Silent token refresh (no browser — uses stored LINKEDIN_REFRESH_TOKEN):
    python auth/linkedin.py --refresh

After the first run, both LINKEDIN_ACCESS_TOKEN and LINKEDIN_REFRESH_TOKEN
are written to your .env automatically. Run with --refresh every ~60 days,
or let the social pipeline do it automatically when the token expires.
"""

import argparse
import http.server
import os
import re
import secrets
import threading
import urllib.parse
import webbrowser
from pathlib import Path

import requests

# Load .env
_ENV_PATH: Path | None = None
try:
    from dotenv import load_dotenv
    for _p in [Path(__file__).parent.parent / ".env",
               Path(__file__).parent.parent / "growstream" / ".env"]:
        if _p.exists():
            load_dotenv(dotenv_path=_p, override=True)
            _ENV_PATH = _p
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


# ── .env writer ───────────────────────────────────────────────────────────────

def _update_env(key: str, value: str) -> None:
    """Write or update a key=value line in the .env file."""
    if _ENV_PATH is None or not _ENV_PATH.exists():
        return
    text = _ENV_PATH.read_text()
    pattern = rf"^{re.escape(key)}=.*$"
    replacement = f"{key}={value}"
    if re.search(pattern, text, flags=re.MULTILINE):
        text = re.sub(pattern, replacement, text, flags=re.MULTILINE)
    else:
        text = text.rstrip("\n") + f"\n{replacement}\n"
    _ENV_PATH.write_text(text)


def _save_tokens(access_token: str, refresh_token: str, expires_in: int) -> None:
    """Persist both tokens to .env and print confirmation."""
    _update_env("LINKEDIN_ACCESS_TOKEN", access_token)
    if refresh_token:
        _update_env("LINKEDIN_REFRESH_TOKEN", refresh_token)
    days = expires_in // 86400
    print(f"\n✅ Tokens saved to {_ENV_PATH}")
    print(f"   Access token expires in: {days} days")
    if refresh_token:
        print(f"   Refresh token saved — run 'python auth/linkedin.py --refresh' to renew silently")


# ── Token refresh (no browser) ────────────────────────────────────────────────

def refresh_token_flow() -> bool:
    """Use LINKEDIN_REFRESH_TOKEN to get a new access token silently.
    Updates .env and returns True on success.
    """
    refresh_token = os.environ.get("LINKEDIN_REFRESH_TOKEN", "")
    if not refresh_token:
        print("ERROR: LINKEDIN_REFRESH_TOKEN not set in .env — run without --refresh first.")
        return False
    if not CLIENT_ID or not CLIENT_SECRET:
        print("ERROR: LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET must be set.")
        return False

    print("Refreshing LinkedIn access token…")
    r = requests.post(
        "https://www.linkedin.com/oauth/v2/accessToken",
        data={
            "grant_type":    "refresh_token",
            "refresh_token": refresh_token,
            "client_id":     CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )

    if r.status_code != 200:
        print(f"ERROR: Token refresh failed ({r.status_code}): {r.text}")
        print("Refresh token may have expired. Run 'python auth/linkedin.py' for a new browser flow.")
        return False

    data          = r.json()
    access_token  = data.get("access_token", "")
    new_refresh   = data.get("refresh_token", refresh_token)  # LinkedIn rotates refresh tokens
    expires_in    = data.get("expires_in", 0)

    me = requests.get(
        "https://api.linkedin.com/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    name = me.json().get("name", "unknown") if me.status_code == 200 else "unknown"
    print(f"   Verified as: {name}")

    _save_tokens(access_token, new_refresh, expires_in)
    return True


# ── Browser OAuth flow ────────────────────────────────────────────────────────

class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        global _auth_code, _state_received
        parsed          = urllib.parse.urlparse(self.path)
        params          = dict(urllib.parse.parse_qsl(parsed.query))
        _auth_code      = params.get("code")
        _state_received = params.get("state")

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


def browser_flow() -> None:
    """Full browser-based OAuth flow. Saves tokens to .env on success."""
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
    print("\nOpening browser for LinkedIn authorization…")
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

    data          = r.json()
    access_token  = data.get("access_token", "")
    refresh_token = data.get("refresh_token", "")
    expires_in    = data.get("expires_in", 0)

    me = requests.get(
        "https://api.linkedin.com/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    if me.status_code == 200:
        info = me.json()
        print(f"\n   Verified as: {info.get('name', info.get('sub', 'unknown'))}")

    print("\n──────────────────────────────────────────────")
    _save_tokens(access_token, refresh_token, expires_in)
    print("──────────────────────────────────────────────\n")


# ── Public helper (called by social pipeline for auto-refresh) ────────────────

def try_auto_refresh() -> str | None:
    """Silently refresh the access token using the stored refresh token.
    Returns the new access token on success, None on failure.
    Called by the social pipeline when it detects a stale token.
    """
    refresh_token = os.environ.get("LINKEDIN_REFRESH_TOKEN", "")
    if not refresh_token or not CLIENT_ID or not CLIENT_SECRET:
        return None
    r = requests.post(
        "https://www.linkedin.com/oauth/v2/accessToken",
        data={
            "grant_type":    "refresh_token",
            "refresh_token": refresh_token,
            "client_id":     CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    if r.status_code != 200:
        return None
    data         = r.json()
    access_token = data.get("access_token", "")
    new_refresh  = data.get("refresh_token", refresh_token)
    expires_in   = data.get("expires_in", 0)
    if access_token:
        _save_tokens(access_token, new_refresh, expires_in)
        os.environ["LINKEDIN_ACCESS_TOKEN"] = access_token
        os.environ["LINKEDIN_REFRESH_TOKEN"] = new_refresh
    return access_token or None


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="LinkedIn OAuth token manager")
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Silently refresh using stored LINKEDIN_REFRESH_TOKEN (no browser)",
    )
    args = parser.parse_args()

    if args.refresh:
        ok = refresh_token_flow()
        if not ok:
            raise SystemExit(1)
    else:
        browser_flow()


if __name__ == "__main__":
    main()
