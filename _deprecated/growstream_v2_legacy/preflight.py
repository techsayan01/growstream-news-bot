"""
GrowStream — Pre-flight health checks.
Runs before any LLM call to verify all external services are reachable
and credentials are valid. Aborts early to avoid wasting API tokens.

Checks (in order):
  1. Environment variables (no network)
  2. Anthropic API  — cheapest possible ping (1-token request)
  3. Unsplash API   — unauthenticated stats endpoint
  4. WordPress API  — /wp-json/wp/v2/users/me (auth check)
"""

import sys
from dataclasses import dataclass, field

import requests

from .config import (
    CLAUDE_API_KEY,
    REQUEST_TIMEOUT,
    UNSPLASH_API_KEY,
    WP_PASSWORD,
    WP_URL,
    WP_USERNAME,
    get_client,
    log,
)


# ============================================================
# RESULT TYPE
# ============================================================
@dataclass
class CheckResult:
    name:    str
    ok:      bool
    message: str
    fatal:   bool = True   # If True, a failure aborts the whole run


@dataclass
class PreflightReport:
    results: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(r.ok for r in self.results if r.fatal)

    def add(self, result: CheckResult) -> None:
        self.results.append(result)

    def log_summary(self) -> None:
        log.info("─" * 50)
        log.info("  PRE-FLIGHT CHECKS")
        log.info("─" * 50)
        for r in self.results:
            icon = "✓" if r.ok else ("✗" if r.fatal else "⚠")
            log.info(f"  {icon} {r.name:<25} {r.message}")
        log.info("─" * 50)
        if self.passed:
            log.info("  ✅ All systems go — starting pipeline")
        else:
            log.error("  🚫 Pre-flight failed — aborting to save tokens")
        log.info("─" * 50)


# ============================================================
# INDIVIDUAL CHECKS
# ============================================================
def _check_env() -> CheckResult:
    """Verify all required environment variables are set."""
    missing = []
    if not CLAUDE_API_KEY:   missing.append("CLAUDE_API_KEY")
    if not UNSPLASH_API_KEY: missing.append("UNSPLASH_API_KEY")
    if not WP_USERNAME:      missing.append("WP_USERNAME")
    if not WP_PASSWORD:      missing.append("WP_PASSWORD")

    if missing:
        return CheckResult(
            name="Environment vars",
            ok=False,
            message=f"Missing: {', '.join(missing)}",
        )
    return CheckResult(name="Environment vars", ok=True, message="All present")


def _check_anthropic() -> CheckResult:
    """Ping Anthropic with the smallest possible request (1 output token)."""
    try:
        get_client().messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1,
            messages=[{"role": "user", "content": "ping"}],
        )
        return CheckResult(name="Anthropic API", ok=True, message="Reachable & authenticated")
    except Exception as e:
        err = str(e)
        if "authentication" in err.lower() or "api_key" in err.lower() or "401" in err:
            msg = "Invalid API key"
        elif "rate" in err.lower():
            msg = "Rate limited — try again shortly"
        elif "timeout" in err.lower() or "connection" in err.lower():
            msg = "Network timeout — service may be down"
        else:
            msg = err[:80]
        return CheckResult(name="Anthropic API", ok=False, message=msg)


def _check_unsplash() -> CheckResult:
    """Validate Unsplash credentials with a minimal search request."""
    try:
        r = requests.get(
            "https://api.unsplash.com/search/photos",
            params={"query": "test", "per_page": 1},
            headers={"Authorization": f"Client-ID {UNSPLASH_API_KEY}"},
            timeout=REQUEST_TIMEOUT,
        )
        if r.status_code == 200:
            remaining = r.headers.get("X-Ratelimit-Remaining", "?")
            return CheckResult(
                name="Unsplash API",
                ok=True,
                message=f"Reachable — {remaining} requests remaining today",
                fatal=False,  # Images failing shouldn't block publishing
            )
        elif r.status_code == 401:
            return CheckResult(
                name="Unsplash API",
                ok=False,
                message="Invalid API key (401)",
                fatal=False,
            )
        elif r.status_code == 403:
            return CheckResult(
                name="Unsplash API",
                ok=False,
                message="Rate limit hit or key banned (403)",
                fatal=False,
            )
        else:
            return CheckResult(
                name="Unsplash API",
                ok=False,
                message=f"Unexpected status {r.status_code}",
                fatal=False,
            )
    except Exception as e:
        return CheckResult(
            name="Unsplash API",
            ok=False,
            message=f"Unreachable: {str(e)[:60]}",
            fatal=False,  # Articles still publish without images
        )


def _check_wordpress() -> CheckResult:
    """Obtain a JWT token and verify the user has publish rights."""
    try:
        # Step 1 — get JWT token
        r = requests.post(
            f"{WP_URL}/wp-json/jwt-auth/v1/token",
            json={"username": WP_USERNAME, "password": WP_PASSWORD},
            timeout=REQUEST_TIMEOUT,
        )
        if r.status_code in (403, 401):
            data = r.json()
            return CheckResult(
                name="WordPress API",
                ok=False,
                message=f"JWT auth failed: {data.get('message', 'wrong credentials')}",
            )
        if r.status_code != 200:
            return CheckResult(
                name="WordPress API",
                ok=False,
                message=f"JWT endpoint returned {r.status_code} — is the JWT plugin active?",
            )

        token = r.json().get("token")
        if not token:
            return CheckResult(
                name="WordPress API",
                ok=False,
                message="JWT response missing token field",
            )

        auth_header = {"Authorization": f"Bearer {token}"}

        # Step 2 — verify token & check publish rights
        me = requests.get(
            f"{WP_URL}/wp-json/wp/v2/users/me",
            headers=auth_header,
            params={"context": "edit"},
            timeout=REQUEST_TIMEOUT,
        )
        if me.status_code != 200:
            return CheckResult(
                name="WordPress API",
                ok=False,
                message=f"Token acquired but /users/me returned {me.status_code}",
            )
        user = me.json()
        name = user.get("name", "unknown")
        roles_list: list[str] = user.get("roles", [])
        caps = user.get("capabilities", {})
        role_str = (
            ", ".join(roles_list) if roles_list
            else ", ".join(k for k, v in caps.items()
                           if v and k in ("administrator", "editor", "author"))
            or "unknown"
        )

        # Step 3 — confirm publish rights with a private draft test
        test_post = requests.post(
            f"{WP_URL}/wp-json/wp/v2/posts",
            headers={**auth_header, "Content-Type": "application/json"},
            json={"title": "__preflight_check__", "status": "private", "content": "test"},
            timeout=REQUEST_TIMEOUT,
        )

        if test_post.status_code == 201:
            post_id = test_post.json().get("id")
            if post_id:
                requests.delete(
                    f"{WP_URL}/wp-json/wp/v2/posts/{post_id}",
                    headers=auth_header,
                    params={"force": True},
                    timeout=REQUEST_TIMEOUT,
                )
            return CheckResult(
                name="WordPress API",
                ok=True,
                message=f"JWT authenticated as '{name}' (role: {role_str}) — publish rights confirmed",
            )
        elif test_post.status_code in (401, 403):
            return CheckResult(
                name="WordPress API",
                ok=False,
                message=(
                    f"Logged in as '{name}' (role: {role_str}) — cannot create posts ({test_post.status_code}). "
                    f"Fix: WP Admin → Users → Edit '{WP_USERNAME}' → set Role to 'Editor'"
                ),
            )
        else:
            return CheckResult(
                name="WordPress API",
                ok=True,
                message=(
                    f"JWT authenticated as '{name}' (role: {role_str}) — "
                    f"publish test returned {test_post.status_code} (proceeding anyway)"
                ),
            )

    except requests.exceptions.ConnectionError:
        return CheckResult(
            name="WordPress API",
            ok=False,
            message=f"Cannot reach {WP_URL} — site may be down or URL wrong",
        )
    except Exception as e:
        return CheckResult(
            name="WordPress API",
            ok=False,
            message=str(e)[:80],
        )



# ============================================================
# PUBLIC ENTRY POINT
# ============================================================
def run_preflight(abort_on_failure: bool = True) -> PreflightReport:
    """
    Run all pre-flight checks and return a :class:`PreflightReport`.

    If *abort_on_failure* is True (default) and any fatal check fails,
    this function calls ``sys.exit(1)`` before the pipeline starts,
    preventing any LLM tokens from being consumed.
    """
    report = PreflightReport()

    report.add(_check_env())
    # Only run network checks if env vars are present
    if report.passed:
        report.add(_check_anthropic())
        report.add(_check_unsplash())
        report.add(_check_wordpress())

    report.log_summary()

    if abort_on_failure and not report.passed:
        sys.exit(1)

    return report
