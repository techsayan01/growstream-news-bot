"""
GrowStream — Configuration, logging, shared utilities.
All modules import `log`, env vars, and helpers from here.
"""

import json
import logging
import os
import time
from datetime import datetime
from functools import wraps

import anthropic

# ============================================================
# LOGGING
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f"growstream_{datetime.now().strftime('%Y%m%d')}.log"),
    ],
)
log = logging.getLogger("GrowStream")

# ============================================================
# ENVIRONMENT / CONFIGURATION
# ============================================================
CLAUDE_API_KEY   = os.environ.get("CLAUDE_API_KEY", "")
UNSPLASH_API_KEY = os.environ.get("UNSPLASH_API_KEY", "")
WP_URL           = "https://growstreammedia.com"
WP_USERNAME      = os.environ.get("WP_USERNAME", "newsbot")
WP_PASSWORD      = os.environ.get("WP_PASSWORD", "")

MAX_RETRIES     = 3
RETRY_DELAY     = 5
REQUEST_TIMEOUT = 15


def validate_config() -> None:
    """Raise EnvironmentError if any required env var is missing."""
    missing = []
    if not CLAUDE_API_KEY:   missing.append("CLAUDE_API_KEY")
    if not UNSPLASH_API_KEY: missing.append("UNSPLASH_API_KEY")
    if not WP_USERNAME:      missing.append("WP_USERNAME")
    if not WP_PASSWORD:      missing.append("WP_PASSWORD")
    if missing:
        raise EnvironmentError(f"Missing required config: {', '.join(missing)}")
    log.info("✓ Configuration validated")


# ============================================================
# ANTHROPIC CLIENT — lazy singleton
# ============================================================
_client: anthropic.Anthropic | None = None


def get_client() -> anthropic.Anthropic:
    """Return a shared Anthropic client, created on first call."""
    global _client
    if _client is None:
        _client = anthropic.Anthropic(
            api_key=CLAUDE_API_KEY,
            timeout=60.0,
            max_retries=2,
        )
    return _client


# ============================================================
# RETRY DECORATOR
# ============================================================
def with_retry(max_retries: int = MAX_RETRIES, delay: int = RETRY_DELAY, fallback=None):
    """Decorator that retries a function up to *max_retries* times."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(1, max_retries + 1):
                try:
                    result = func(*args, **kwargs)
                    if result is not None:
                        return result
                    raise ValueError("Function returned None")
                except Exception as e:
                    last_error = e
                    if attempt < max_retries:
                        log.warning(
                            f"  ⚠ {func.__name__} attempt {attempt}/{max_retries} "
                            f"failed: {e}. Retrying in {delay}s …"
                        )
                        time.sleep(delay)
                    else:
                        log.error(
                            f"  ✗ {func.__name__} failed after {max_retries} attempts: {e}"
                        )
            return fallback() if callable(fallback) else fallback
        return wrapper
    return decorator


# ============================================================
# HELPERS
# ============================================================
def safe_json_parse(raw_text: str):
    """Strip markdown fences and parse JSON, using json-repair as fallback.

    LLMs sometimes emit unescaped double quotes, curly/smart quotes, or other
    malformed JSON (especially when headlines contain punctuation). We try
    json.loads first (fast path), then json_repair.repair_json (robust path).
    """
    import re

    text = raw_text.strip()

    # --- Strip markdown fences ---
    if text.startswith("```"):
        parts = text.split("```")
        text  = parts[1] if len(parts) > 1 else text
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()

    # --- Fast path ---
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # --- Robust path: use json-repair ---
    try:
        from json_repair import repair_json
        repaired = repair_json(text, return_objects=True)
        if repaired:
            return repaired
    except Exception:
        pass

    log.error(f"JSON parse failed (all strategies) | Raw: {text[:200]}")
    return None

