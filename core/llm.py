"""
LLM client layer — Anthropic (Claude) + Google (Gemini).

Anthropic client:  get_client() → used by agents that call .messages.create()
Gemini client:     get_gemini_client() → used by call_llm() internally
Unified router:    call_llm(model, max_tokens, messages) → str
                   Routes to Anthropic for "claude-*", Google for "gemini-*".

Call `init_client(db_log_fn)` once at startup to wire in DB cost logging.
"""

import inspect
import os
import threading
import time as _time
from pathlib import Path

import anthropic

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

CLAUDE_API_KEY  = os.environ.get("CLAUDE_API_KEY", "")
GEMINI_API_KEY  = os.environ.get("GEMINI_API_KEY", "")

# Gemini 2.5 Flash pricing ($ per 1M tokens)
_GEMINI_PRICING: dict[str, tuple[float, float]] = {
    "gemini-3.1-pro-preview": (1.25, 10.0),
    "gemini-2.5-flash": (0.15, 0.60),
    "gemini-2.5-pro":   (1.25, 10.0),
    "gemini-2.0-flash": (0.10, 0.40),
}

# Per-model RPM limits (free tier). Enforced proactively to avoid 429s.
_GEMINI_RPM: dict[str, int] = {
    "gemini-3.1-pro-preview": 5,
    "gemini-2.5-pro":         5,
    "gemini-2.5-flash":       10,
    "gemini-2.0-flash":       15,
}
_GEMINI_LAST_CALL: dict[str, float] = {}  # model → last call timestamp
_GEMINI_RATE_LOCK = threading.Lock()      # serialises calls across threads

_db_log_fn = None   # set by init_client()


# ── Anthropic ─────────────────────────────────────────────────────────────────

class MessagesWrapper:
    def __init__(self, original_messages, db_log_fn=None):
        self._original = original_messages
        self._db_log_fn = db_log_fn

    def create(self, **kwargs):
        response = self._original.create(**kwargs)
        if self._db_log_fn:
            try:
                caller_name = "unknown"
                for frame_info in inspect.stack()[1:5]:
                    func = frame_info.function
                    if func not in ("create", "wrapper"):
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

                in_tok  = response.usage.input_tokens
                out_tok = response.usage.output_tokens
                cost    = (in_tok / 1_000_000.0 * cost_in) + (out_tok / 1_000_000.0 * cost_out)
                self._db_log_fn(caller_name, in_tok, out_tok, cost)
            except Exception as e:
                log.warning(f"  ⚠ LLM metrics logging failed: {e}")
        return response


class ClientWrapper:
    def __init__(self, original_client, db_log_fn=None):
        self._original = original_client
        self.messages  = MessagesWrapper(original_client.messages, db_log_fn)

    def __getattr__(self, name):
        return getattr(self._original, name)


_client: ClientWrapper | None = None


def init_client(db_log_fn=None) -> None:
    """(Re-)initialize the singleton Anthropic client and store the DB log fn."""
    global _client, _db_log_fn
    _db_log_fn = db_log_fn
    raw = anthropic.Anthropic(api_key=CLAUDE_API_KEY, timeout=60.0, max_retries=2)
    _client = ClientWrapper(raw, db_log_fn)


def get_client() -> ClientWrapper:
    """Return the shared Anthropic client, lazily creating it if needed."""
    global _client
    if _client is None:
        init_client()
    return _client


# ── Gemini ────────────────────────────────────────────────────────────────────

_gemini_client = None


def get_gemini_client():
    """Return the shared Gemini client, lazily creating it if needed."""
    global _gemini_client
    if _gemini_client is None:
        try:
            from google import genai
            _gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        except ImportError:
            raise RuntimeError(
                "google-genai package not installed. Run: pip install google-genai"
            )
    return _gemini_client


# ── Unified router ────────────────────────────────────────────────────────────

def call_llm(model: str, max_tokens: int, messages: list[dict]) -> str:
    """Call Claude or Gemini based on model prefix, return the text response.

    Args:
        model:      e.g. "gemini-2.5-flash" or "claude-sonnet-4-6"
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

    if model.startswith("gemini"):
        return _call_gemini(model, max_tokens, messages, caller_name)

    # Fallback: Anthropic
    response = get_client().messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=messages,
    )
    return response.content[0].text


def call_llm_with_fallback(models: list[str], max_tokens: int, messages: list[dict]) -> str:
    """Try each model in sequence, falling back on quota/rate-limit errors.

    Args:
        models:     Ordered list of model IDs to try, e.g.
                    ["gemini-2.5-pro", "gemini-2.5-flash", "claude-haiku-4-5-20251001"]
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

    # Flatten messages into a single prompt (Gemini supports multi-turn but
    # all our calls are single-turn user prompts)
    prompt = "\n\n".join(m["content"] for m in messages if m.get("role") == "user")

    client = get_gemini_client()
    _MAX_QUOTA_RETRIES = 4
    response = None
    for _attempt in range(1, _MAX_QUOTA_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(max_output_tokens=max_tokens),
            )
            _GEMINI_LAST_CALL[model] = _time.time()
            break
        except Exception as e:
            err_str = str(e)
            is_quota = "429" in err_str or "RESOURCE_EXHAUSTED" in err_str
            is_daily = "PerDay" in err_str
            if is_quota and is_daily:
                # Daily limit exhausted — no point retrying, let fallback chain handle it
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

            # Match on longest prefix
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
