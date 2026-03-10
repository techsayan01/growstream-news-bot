"""
Shared logging and JSON utilities.
No env-var reading here — that lives in sites/ or core/llm.py.
"""

import json
import logging
from datetime import datetime


def setup_logging(log_name: str = "newsbot") -> logging.Logger:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(f"{log_name}_{datetime.now().strftime('%Y%m%d')}.log"),
        ],
    )
    return logging.getLogger(log_name)


log = setup_logging()


def safe_json_parse(raw_text: str):
    """Strip markdown fences and parse JSON, using json-repair as fallback."""
    text = raw_text.strip()

    # Strip markdown fences
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()

    # Fast path
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Robust path: json-repair
    try:
        from json_repair import repair_json
        repaired = repair_json(text, return_objects=True)
        if repaired:
            return repaired
    except Exception:
        pass

    log.error(f"JSON parse failed (all strategies) | Raw: {text[:200]}")
    return None
