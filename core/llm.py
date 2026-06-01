"""
LLM client layer — Google Gemini only.

Unified router:  call_llm(model, max_tokens, messages) → str
                 call_llm_with_fallback(models, max_tokens, messages) → str

Call `init_client(db_log_fn)` once at startup to wire in DB cost logging.
"""

import inspect
import os
import threading
import time as _time
from pathlib import Path

from .utils import log

# Load .env from project root or legacy growstream/.env
try:
    from dotenv import load_dotenv
    for _p in [Path(__file__).parent.parent / ".env",
               Path(__file__).parent.parent / "growstream" / ".env"]:
        if _p.exists():
            load_dotenv(dotenv_path=_p, override=True)
            break
except ImportError:
    pass

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Gemini pricing ($ per 1M tokens)
_GEMINI_PRICING: dict[str, tuple[float, float]] = {
    "gemini-2.5-pro":   (1.25, 10.0),
    "gemini-2.5-flash": (0.15, 0.60),
    "gemini-2.0-flash": (0.10, 0.40),
}

# Per-model RPM limits (free tier). Enforced proactively to avoid 429s.
_GEMINI_RPM: dict[str, int] = {
    "gemini-2.5-pro":   5,
    "gemini-2.5-flash": 10,
    "gemini-2.0-flash": 15,
}
_GEMINI_LAST_CALL: dict[str, float] = {}  # model → last call timestamp
_GEMINI_RATE_LOCK = threading.Lock()      # serialises calls across threads

_db_log_fn = None   # set by init_client()


def init_client(db_log_fn=None) -> None:
    """Store the DB log fn for cost tracking."""
    global _db_log_fn
    _db_log_fn = db_log_fn


# ── Gemini ────────────────────────────────────────────────────────────────────

_gemini_client = None


def get_gemini_client():
    """Return the shared Gemini client, lazily creating it if needed.

    Auth priority:
      1. Service account file (GOOGLE_APPLICATION_CREDENTIALS) — uses OAuth2.
      2. API key (GEMINI_API_KEY) — uses AI Studio endpoint.
    """
    global _gemini_client
    if _gemini_client is None:
        try:
            from google import genai
            sa_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
            if sa_path and os.path.exists(sa_path):
                from google.oauth2 import service_account
                credentials = service_account.Credentials.from_service_account_file(
                    sa_path,
                    scopes=["https://www.googleapis.com/auth/cloud-platform"],
                )
                _gemini_client = genai.Client(credentials=credentials)
            else:
                _gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        except ImportError:
            raise RuntimeError(
                "google-genai package not installed. Run: pip install google-genai"
            )
    return _gemini_client


# ── Unified router ────────────────────────────────────────────────────────────

def call_llm(model: str, max_tokens: int, messages: list[dict]) -> str:
    """Call Gemini and return the text response.

    Args:
        model:      e.g. "gemini-2.5-flash" or "gemini-2.5-pro"
        max_tokens: maximum output tokens
        messages:   list of {"role": "user"|"assistant", "content": "..."}

    Returns:
        The model's text response as a plain string.
    """
    caller_name = "unknown"
    try:
        for frame_info in inspect.stack()[1:5]:
            func = frame_info.function
            if func not in ("call_llm",):
                caller_name = func
                break
    except Exception:
        pass

    return _call_gemini(model, max_tokens, messages, caller_name)


def call_llm_with_fallback(models: list[str], max_tokens: int, messages: list[dict]) -> str:
    """Try each model in sequence, falling back on quota/rate-limit errors.

    Args:
        models:     Ordered list of model IDs to try, e.g.
                    ["gemini-2.5-pro", "gemini-2.5-flash"]
        max_tokens: Maximum output tokens.
        messages:   list of {"role": "user"|"assistant", "content": "..."}
    """
    last_err: Exception | None = None
    for model in models:
        try:
            return call_llm(model, max_tokens, messages)
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                log.warning(f"  ⚠ {model} quota exhausted — trying next model…")
                last_err = e
                continue
            raise  # non-quota error — don't swallow it
    raise last_err  # type: ignore[misc]


def _call_gemini(model: str, max_tokens: int, messages: list[dict], caller_name: str) -> str:
    """Internal: call Gemini and log usage to DB."""
    import re
    from google.genai import types

    # Proactive rate limiting — serialise across threads and space calls
    # to stay within per-model RPM quota.
    with _GEMINI_RATE_LOCK:
        rpm     = _GEMINI_RPM.get(model, 5)
        min_gap = 60.0 / rpm
        last    = _GEMINI_LAST_CALL.get(model, 0.0)
        gap     = _time.time() - last
        if gap < min_gap:
            _time.sleep(min_gap - gap)
        _GEMINI_LAST_CALL[model] = _time.time()

    # Flatten messages into a single prompt
    prompt = "\n\n".join(m["content"] for m in messages if m.get("role") == "user")

    client = get_gemini_client()

    # Gemini 2.5 Flash uses thinking tokens that count against max_output_tokens.
    # Disable thinking for calls where the budget is tight to avoid truncation.
    try:
        thinking_cfg = types.ThinkingConfig(thinking_budget=0) if "flash" in model else None
    except AttributeError:
        thinking_cfg = None

    _MAX_QUOTA_RETRIES = 4
    response = None
    for _attempt in range(1, _MAX_QUOTA_RETRIES + 1):
        try:
            cfg = types.GenerateContentConfig(
                max_output_tokens=max_tokens,
                **({"thinking_config": thinking_cfg} if thinking_cfg is not None else {}),
            )
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=cfg,
            )
            _GEMINI_LAST_CALL[model] = _time.time()
            break
        except Exception as e:
            err_str = str(e)
            is_quota = "429" in err_str or "RESOURCE_EXHAUSTED" in err_str
            is_daily = "PerDay" in err_str
            if is_quota and is_daily:
                raise
            if is_quota and _attempt < _MAX_QUOTA_RETRIES:
                match = re.search(r"retryDelay['\"]:\s*['\"](\d+)", err_str)
                wait = int(match.group(1)) + 2 if match else 35
                log.warning(f"  ⚠ Gemini rate limit — waiting {wait}s (attempt {_attempt}/{_MAX_QUOTA_RETRIES - 1})…")
                _time.sleep(wait)
                _GEMINI_LAST_CALL[model] = _time.time()
            else:
                raise

    text = response.text or ""

    # Log cost to DB
    if _db_log_fn:
        try:
            usage   = response.usage_metadata
            in_tok  = getattr(usage, "prompt_token_count", 0) or 0
            out_tok = getattr(usage, "candidates_token_count", 0) or 0

            cost_in, cost_out = 0.0, 0.0
            for prefix, rates in _GEMINI_PRICING.items():
                if model.startswith(prefix):
                    cost_in, cost_out = rates
                    break

            cost = (in_tok / 1_000_000.0 * cost_in) + (out_tok / 1_000_000.0 * cost_out)
            _db_log_fn(caller_name, in_tok, out_tok, cost)
        except Exception as e:
            log.warning(f"  ⚠ Gemini metrics logging failed: {e}")

    return text
