"""
news_bot_production.py — compatibility shim.
The codebase has been refactored into the `growstream/` package.
Run `python main.py` or import from `growstream.*` directly.
"""

from growstream.pipeline import run  # noqa: F401

if __name__ == "__main__":
    run()