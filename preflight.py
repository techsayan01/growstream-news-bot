"""
Pre-flight health checks.

Runs before any LLM call to verify all external services are reachable
and credentials are valid. Aborts early to avoid wasting API tokens.

Checks (in order):
  1. Site config fields present (no network)
  2. Anthropic API  — cheapest possible ping (1-token request)
  3. Unsplash API   — credential validation
  4. WordPress API  — Application Password auth + publish rights
"""

import os
import sys
from dataclasses import dataclass, field

import requests

from core.llm import CLAUDE_API_KEY, get_client
from core.retry import REQUEST_TIMEOUT
from core.utils import log
from sites.base import SiteConfig

UNSPLASH_API_KEY = os.environ.get("UNSPLASH_API_KEY", "")


@dataclass
class CheckResult:
    name:    str
    ok:      bool
    message: str
    fatal:   bool = True


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


# ── Individual checks ────────────────────────────────────────────────────────

def _check_config(site: SiteConfig) -> CheckResult:
    missing = []
    if not CLAUDE_API_KEY:         missing.append("CLAUDE_API_KEY")
    if not UNSPLASH_API_KEY:       missing.append("UNSPLASH_API_KEY")
    if not site.wp_username:       missing.append("WP_USERNAME")
    if not site.wp_password:       missing.append("WP_PASSWORD")
    if missing:
        return CheckResult("Config vars", False, f"Missing: {', '.join(missing)}")
    return CheckResult("Config vars", True, "All present")


def _check_anthropic() -> CheckResult:
    try:
        get_client().messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1,
            messages=[{"role": "user", "content": "ping"}],
        )
        return CheckResult("Anthropic API", True, "Reachable & authenticated")
    except Exception as e:
        err = str(e)
        if "authentication" in err.lower() or "api_key" in err.lower() or "401" in err:
            msg = "Invalid API key"
        elif "rate" in err.lower():
            msg = "Rate limited — try again shortly"
        elif "timeout" in err.lower() or "connection" in err.lower():
            msg = "Network timeout"
        else:
            msg = err[:80]
        return CheckResult("Anthropic API", False, msg)


def _check_unsplash() -> CheckResult:
    try:
        r = requests.get(
            "https://api.unsplash.com/search/photos",
            params={"query": "test", "per_page": 1},
            headers={"Authorization": f"Client-ID {UNSPLASH_API_KEY}"},
            timeout=REQUEST_TIMEOUT,
        )
        if r.status_code == 200:
            remaining = r.headers.get("X-Ratelimit-Remaining", "?")
            return CheckResult("Unsplash API", True, f"Reachable — {remaining} requests remaining", fatal=False)
        elif r.status_code == 401:
            return CheckResult("Unsplash API", False, "Invalid API key (401)", fatal=False)
        else:
            return CheckResult("Unsplash API", False, f"Status {r.status_code}", fatal=False)
    except Exception as e:
        return CheckResult("Unsplash API", False, f"Unreachable: {str(e)[:60]}", fatal=False)


def _check_wordpress(site: SiteConfig) -> CheckResult:
    """Verify WordPress access using API key (preferred) or Basic Auth."""
    if getattr(site, "wp_api_key", ""):
        auth_header = {"X-Newsbot-Key": site.wp_api_key}
        method_label = "API key"
    else:
        import base64
        token       = base64.b64encode(f"{site.wp_username}:{site.wp_password}".encode()).decode()
        auth_header = {"Authorization": f"Basic {token}"}
        method_label = "Basic Auth"
    try:
        me = requests.get(
            f"{site.wp_url}/wp-json/wp/v2/users/me",
            headers=auth_header,
            params={"context": "edit"},
            timeout=REQUEST_TIMEOUT,
        )
        if me.status_code in (401, 403):
            return CheckResult(
                "WordPress API", False,
                f"Application Password auth failed ({me.status_code}) — check WP_USERNAME / WP_PASSWORD"
            )
        if me.status_code != 200:
            return CheckResult("WordPress API", False, f"/users/me returned {me.status_code}")

        user     = me.json()
        name     = user.get("name", "unknown")
        roles    = user.get("roles", [])
        role_str = ", ".join(roles) if roles else "unknown"

        test = requests.post(
            f"{site.wp_url}/wp-json/wp/v2/posts",
            headers={**auth_header, "Content-Type": "application/json"},
            json={"title": "__preflight_check__", "status": "private", "content": "test"},
            timeout=REQUEST_TIMEOUT,
        )
        if test.status_code == 201:
            post_id = test.json().get("id")
            if post_id:
                requests.delete(
                    f"{site.wp_url}/wp-json/wp/v2/posts/{post_id}",
                    headers=auth_header,
                    params={"force": True},
                    timeout=REQUEST_TIMEOUT,
                )
            return CheckResult(
                "WordPress API", True,
                f"[{method_label}] Authenticated as '{name}' (role: {role_str}) — publish rights confirmed"
            )
        elif test.status_code in (401, 403):
            return CheckResult(
                "WordPress API", False,
                f"Logged in as '{name}' (role: {role_str}) — cannot create posts ({test.status_code})"
            )
        else:
            return CheckResult(
                "WordPress API", True,
                f"[{method_label}] Authenticated as '{name}' (role: {role_str}) — publish test: {test.status_code}"
            )

    except requests.exceptions.ConnectionError:
        return CheckResult("WordPress API", False, f"Cannot reach {site.wp_url}")
    except Exception as e:
        return CheckResult("WordPress API", False, str(e)[:80])


# ── Public entry point ────────────────────────────────────────────────────────

def run_preflight(site: SiteConfig, abort_on_failure: bool = True) -> PreflightReport:
    """Run all pre-flight checks. Calls sys.exit(1) on fatal failure if *abort_on_failure*."""
    report = PreflightReport()
    report.add(_check_config(site))
    if report.passed:
        report.add(_check_anthropic())
        report.add(_check_unsplash())
        report.add(_check_wordpress(site))

    report.log_summary()

    if abort_on_failure and not report.passed:
        sys.exit(1)

    return report
