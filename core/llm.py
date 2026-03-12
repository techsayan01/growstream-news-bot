"""
Anthropic client singleton with per-call token usage tracking.

CLAUDE_API_KEY is read from the environment (global across all sites).
Call `init_client(db_log_fn)` once at startup to wire in DB cost logging.
"""

import inspect
import os
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

CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY", "")


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
    """(Re-)initialize the singleton client. Call once at app startup."""
    global _client
    raw = anthropic.Anthropic(api_key=CLAUDE_API_KEY, timeout=60.0, max_retries=2)
    _client = ClientWrapper(raw, db_log_fn)


def get_client() -> ClientWrapper:
    """Return the shared Anthropic client, lazily creating it if needed."""
    global _client
    if _client is None:
        init_client()
    return _client
