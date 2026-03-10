"""Retry decorator for resilient API calls."""

import time
from functools import wraps

from .utils import log

MAX_RETRIES = 3
RETRY_DELAY = 5
REQUEST_TIMEOUT = 15


def with_retry(max_retries: int = MAX_RETRIES, delay: int = RETRY_DELAY, fallback=None):
    """Decorator that retries a function up to *max_retries* times on any exception."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(1, max_retries + 1):
                try:
                    result = func(*args, **kwargs)
                    if result is not None:
                        return result
                    raise ValueError("Function returned None")
                except Exception as e:
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
