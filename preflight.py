"""
Pre-flight health checks.

Runs before any LLM call to verify all external services are reachable
and credentials are valid. Aborts early to avoid wasting API tokens.

Checks (in order):
  1. Site config fields present (no network)
  2. Gemini API     — model metadata lookup (no quota consumed)
  3. Unsplash API   — credential validation
  4. WordPress API  — Application Password auth + publish rights
"""

import os
import sys
from dataclasses import dataclass, field

import requests

from core.llm import GEMINI_API_KEY
from core.retry import REQUEST_TIMEOUT
from core.utils import log
from sites.base import SiteConfig

UNSPLASH_API_KEY = os.environ.get("UNSPLASH_API_KEY", "")
PEXELS_API_KEY   = os.environ.get("PEXELS_API_KEY", "")
PIXABAY_API_KEY  = os.environ.get("PIXABAY_API_KEY", "")


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
    if not GEMINI_API_KEY:         missing.append("GEMINI_API_KEY")
    if not UNSPLASH_API_KEY:       missing.append("UNSPLASH_API_KEY")
    if not site.wp_username:       missing.append("WP_USERNAME")
    if not site.wp_password:       missing.append("WP_PASSWORD")
    if missing:
        return CheckResult("Config vars", False, f"Missing: {', '.join(missing)}")
    return CheckResult("Config vars", True, "All present")


def _check_gemini_model(model: str, label: str, fatal: bool) -> CheckResult:
    """Check Gemini model availability AND credit balance via a 1-token generation call."""
    try:
        from core.llm import get_gemini_client
        from google.genai import types
        client = get_gemini_client()
        # Tiny generation call — costs ~1 output token but catches credit exhaustion
        # that models.get() (metadata only) cannot detect.
        client.models.generate_content(
            model=model,
            contents="Hi",
            config=types.GenerateContentConfig(
                max_output_tokens=1,
                thinking_config=types.ThinkingConfig(thinking_budget=0)
                if "flash" in model else None,
            ),
        )
        return CheckResult(label, True, "Reachable")
    except ImportError:
        return CheckResult(label, False, "google-genai not installed")
    except Exception as e:
        err = str(e)
        if "RESOURCE_EXHAUSTED" in err or "prepayment credits" in err or "credits are depleted" in err:
            # Hard stop — no credits means zero articles can publish
            return CheckResult(
                label, False,
                "Prepaid credits depleted — top up at aistudio.google.com",
                fatal=True,
            )
        elif "api_key" in err.lower() or "INVALID_ARGUMENT" in err or "401" in err or "403" in err:
            # Bad key is always fatal — nothing will work
            return CheckResult(label, False, f"Invalid API key: {err[:60]}", fatal=True)
        else:
            # Everything else (429, 500, timeout, connection, model unavailable) is
            # transient — don't abort the run, let the pipeline retry naturally
            return CheckResult(label, False, f"Transient error (will retry): {err[:60]}", fatal=False)


def _check_gemini_quota() -> list[CheckResult]:
    """Check quota for every Gemini model used in the pipeline.

    When NEWSBOT_WRITER=haiku the Gemini writer models are skipped since
    the pipeline won't call them.
    """
    results = []

    if os.environ.get("NEWSBOT_REVIEWER") == "pro":
        results.append(_check_gemini_model("gemini-2.5-pro",   "Gemini reviewer (2.5-pro)  ", fatal=True))
    else:
        results.append(_check_gemini_model("gemini-2.5-flash", "Gemini reviewer (2.5-flash)", fatal=True))

    if os.environ.get("NEWSBOT_WRITER") == "pro":
        results += [
            _check_gemini_model("gemini-2.5-pro",   "Gemini writer   (2.5-pro)  ", fatal=False),
            _check_gemini_model("gemini-2.5-flash",  "Gemini writer fb (2.5-flash)", fatal=False),
        ]
    else:
        results.append(_check_gemini_model("gemini-2.5-flash", "Gemini writer   (2.5-flash)", fatal=True))

    return results



def _check_image_apis() -> CheckResult:
    """Check at least one image API (Unsplash, Pexels, or Pixabay) is available.

    Uses a fallback chain: tries each in order, reports which are working.
    Fatal only if ALL are misconfigured or unreachable.
    """
    available = []
    errors = []

    # Check Unsplash
    if UNSPLASH_API_KEY:
        try:
            r = requests.get(
                "https://api.unsplash.com/search/photos",
                params={"query": "test", "per_page": 1},
                headers={"Authorization": f"Client-ID {UNSPLASH_API_KEY}"},
                timeout=REQUEST_TIMEOUT,
            )
            if r.status_code == 200:
                remaining = r.headers.get("X-Ratelimit-Remaining", "?")
                available.append(f"Unsplash ({remaining} req/hr remaining)")
            elif r.status_code == 401:
                errors.append("Unsplash: Invalid key (401)")
            else:
                errors.append(f"Unsplash: Status {r.status_code}")
        except Exception as e:
            errors.append(f"Unsplash: {str(e)[:40]}")
    else:
        errors.append("Unsplash: No API key configured")

    # Check Pexels
    if PEXELS_API_KEY:
        try:
            r = requests.get(
                "https://api.pexels.com/v1/search",
                params={"query": "test", "per_page": 1},
                headers={"Authorization": PEXELS_API_KEY},
                timeout=REQUEST_TIMEOUT,
            )
            if r.status_code == 200:
                available.append("Pexels (unlimited free)")
            elif r.status_code == 401:
                errors.append("Pexels: Invalid key (401)")
            else:
                errors.append(f"Pexels: Status {r.status_code}")
        except Exception as e:
            errors.append(f"Pexels: {str(e)[:40]}")
    else:
        errors.append("Pexels: No API key configured")

    # Check Pixabay
    if PIXABAY_API_KEY:
        try:
            r = requests.get(
                "https://pixabay.com/api/",
                params={"key": PIXABAY_API_KEY, "q": "test", "per_page": 1},
                timeout=REQUEST_TIMEOUT,
            )
            if r.status_code == 200:
                available.append("Pixabay (unlimited free)")
            elif r.status_code == 401:
                errors.append("Pixabay: Invalid key (401)")
            else:
                errors.append(f"Pixabay: Status {r.status_code}")
        except Exception as e:
            errors.append(f"Pixabay: {str(e)[:40]}")
    else:
        errors.append("Pixabay: No API key configured")

    # Report status
    if available:
        message = f"Available: {', '.join(available)}"
        return CheckResult("Image APIs", True, message, fatal=False)
    else:
        message = "No image API reachable — articles will publish without featured images. Add PEXELS_API_KEY or UNSPLASH_API_KEY to fix."
        return CheckResult("Image APIs", False, message, fatal=False)  # non-fatal: pipeline still runs


def _check_wordpress(site: SiteConfig) -> CheckResult:
    """Verify WordPress access with retry (Hostinger can be slow from GHA runners)."""
    _WP_TIMEOUT = 30   # longer than REQUEST_TIMEOUT — WP on shared hosting is slow
    _RETRIES    = 3

    if getattr(site, "wp_api_key", ""):
        auth_header  = {"X-Newsbot-Key": site.wp_api_key}
        method_label = "API key"
    else:
        # Obtain JWT token — retry on timeout/connection errors
        token = None
        last_err = ""
        for attempt in range(1, _RETRIES + 1):
            try:
                r = requests.post(
                    f"{site.wp_url}/wp-json/jwt-auth/v1/token",
                    json={"username": site.wp_username, "password": site.wp_password},
                    timeout=_WP_TIMEOUT,
                )
                if r.status_code in (401, 403):
                    msg = r.json().get("message", "wrong credentials") if r.content else f"HTTP {r.status_code}"
                    return CheckResult("WordPress API", False, f"JWT auth failed: {msg}")
                if r.status_code == 200:
                    token = r.json().get("token")
                    if token:
                        break
                last_err = f"JWT endpoint returned {r.status_code}"
            except requests.exceptions.Timeout:
                last_err = f"Timeout on attempt {attempt}/{_RETRIES}"
                import time; time.sleep(5)
            except requests.exceptions.ConnectionError:
                last_err = f"Cannot reach {site.wp_url}"
                import time; time.sleep(5)
            except Exception as e:
                last_err = str(e)[:80]

        if not token:
            return CheckResult("WordPress API", False, last_err)

        auth_header  = {"Authorization": f"Bearer {token}"}
        method_label = "JWT"
    # Verify auth by checking current user — retry on flaky connections
    for attempt in range(1, _RETRIES + 1):
        try:
            me = requests.get(
                f"{site.wp_url}/wp-json/wp/v2/users/me",
                headers=auth_header,
                params={"context": "edit"},
                timeout=_WP_TIMEOUT,
            )
            if me.status_code in (401, 403):
                return CheckResult(
                    "WordPress API", False,
                    f"Auth rejected ({me.status_code}) — check WP_USERNAME / WP_PASSWORD secrets"
                )
            if me.status_code == 200:
                user     = me.json()
                name     = user.get("name", "unknown")
                roles    = user.get("roles", [])
                role_str = ", ".join(roles) if roles else "unknown"
                return CheckResult(
                    "WordPress API", True,
                    f"[{method_label}] Authenticated as '{name}' (role: {role_str})"
                )
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            if attempt < _RETRIES:
                import time; time.sleep(5)
            else:
                return CheckResult("WordPress API", False,
                    f"Unreachable after {_RETRIES} attempts — Hostinger may be slow")
        except Exception as e:
            return CheckResult("WordPress API", False, str(e)[:80])

    return CheckResult("WordPress API", False, "Unknown error during auth check")


# ── Public entry point ────────────────────────────────────────────────────────

def run_preflight(site: SiteConfig, abort_on_failure: bool = True) -> PreflightReport:
    """Run all pre-flight checks. Calls sys.exit(1) on fatal failure if *abort_on_failure*."""
    report = PreflightReport()
    report.add(_check_config(site))
    if report.passed:
        for result in _check_gemini_quota():
            report.add(result)
        report.add(_check_image_apis())
        report.add(_check_wordpress(site))

    report.log_summary()

    if abort_on_failure and not report.passed:
        # Exit 0 for known recoverable failures (credits depleted, WP temporarily down)
        # so GHA marks the run as Warning rather than Failure.
        # Exit 1 only for hard misconfigurations (wrong API key, missing secrets).
        credit_depleted = any(
            "depleted" in (r.message or "").lower() or "credits" in (r.message or "").lower()
            for r in report.results if not r.ok
        )
        wp_unreachable = any(
            "unreachable" in (r.message or "").lower()
            for r in report.results if not r.ok and r.name == "WordPress API"
        )
        if credit_depleted or wp_unreachable:
            log.warning("  ⚠ Exiting with code 0 — transient issue, not a misconfiguration")
            sys.exit(0)
        sys.exit(1)

    return report
