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
from pathlib import Path

import anthropic

# Load .env file if present (from growstream/ directory or project root)
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).parent / ".env"
    load_dotenv(dotenv_path=_env_path, override=False)  # override=False: system vars take priority
except ImportError:
    pass  # python-dotenv not installed — fall back to system env vars only

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
WP_URL           = os.environ.get("WP_URL", "https://growstreammedia.com")
WP_USERNAME      = os.environ.get("WP_USERNAME", "newsbot")
WP_PASSWORD      = os.environ.get("WP_PASSWORD", "")

# LinkedIn
LINKEDIN_CLIENT_ID     = os.environ.get("LINKEDIN_CLIENT_ID", "")
LINKEDIN_CLIENT_SECRET = os.environ.get("LINKEDIN_CLIENT_SECRET", "")
LINKEDIN_ORG_URN       = os.environ.get("LINKEDIN_ORG_URN", "urn:li:organization:105025230")
LINKEDIN_ACCESS_TOKEN  = os.environ.get("LINKEDIN_ACCESS_TOKEN", "")
LINKEDIN_PERSON_URN    = os.environ.get("LINKEDIN_PERSON_URN", "")  # fallback: post as personal profile

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
# ANTHROPIC CLIENT — lazy singleton with token tracking
# ============================================================

class MessagesWrapper:
    def __init__(self, original_messages):
        self._original = original_messages

    def create(self, **kwargs):
        response = self._original.create(**kwargs)
        try:
            from .db import log_llm_usage
            import inspect
            
            # Find the caller's function name inside the pipeline
            caller_name = "unknown"
            for frame_info in inspect.stack()[1:5]:
                mod = frame_info.frame.f_globals.get("__name__", "")
                func = frame_info.function
                if "growstream" in mod and func not in ("create", "wrapper"):
                    caller_name = func
                    break

            model = kwargs.get("model", "")
            if "sonnet" in model:
                cost_in, cost_out = 3.0, 15.0
            elif "haiku" in model:
                cost_in, cost_out = 0.25, 1.25
            elif "opus" in model:
                cost_in, cost_out = 15.0, 75.0
            else:
                cost_in, cost_out = 0.0, 0.0

            in_tok = response.usage.input_tokens
            out_tok = response.usage.output_tokens
            cost_usd = (in_tok / 1_000_000.0 * cost_in) + (out_tok / 1_000_000.0 * cost_out)
            log_llm_usage(caller_name, in_tok, out_tok, cost_usd)
        except Exception as e:
            log.warning(f"  ⚠ LLM metrics logging failed: {e}")

        return response

class ClientWrapper:
    def __init__(self, original_client):
        self._original = original_client
        self.messages = MessagesWrapper(self._original.messages)

    def __getattr__(self, name):
        return getattr(self._original, name)


_client: ClientWrapper | None = None


def get_client() -> ClientWrapper:
    """Return a shared Anthropic client, created on first call."""
    global _client
    if _client is None:
        raw_client = anthropic.Anthropic(
            api_key=CLAUDE_API_KEY,
            timeout=60.0,
            max_retries=2,
        )
        _client = ClientWrapper(raw_client)
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

