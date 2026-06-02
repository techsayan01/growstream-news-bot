"""
Shared logging and JSON utilities.
No env-var reading here — that lives in sites/ or core/llm.py.
"""

import hashlib
import json
import logging
import re
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

# ── Headline normalisation & fingerprinting ───────────────────────────────────

_STOP_WORDS = frozenset({
    "the", "a", "an", "of", "to", "in", "for", "and", "or", "is", "are",
    "its", "by", "on", "at", "with", "as", "be", "has", "have", "says",
    "said", "from", "that", "this", "it", "will", "new", "how", "what",
    "why", "when", "who", "over", "into", "about", "after", "up", "their",
    "than", "but", "not", "was", "were", "been", "would", "could", "should",
})


def normalise_headline(text: str) -> str:
    """Lowercase, strip punctuation/numbers/stopwords — for similarity comparison."""
    text = text.lower()
    text = re.sub(r"[^a-z\s]", " ", text)
    tokens = [t for t in text.split() if t not in _STOP_WORDS and len(t) > 2]
    return " ".join(tokens)


def headline_fingerprint(text: str) -> str:
    """Order-independent SHA-256 fingerprint of a normalised headline.

    Sorting tokens makes "Stripe raises funding" == "funding raises Stripe",
    catching rearranged headlines from different sources.
    Returns first 16 hex chars (64-bit collision space — sufficient for a news bot).
    """
    tokens = sorted(normalise_headline(text).split())
    return hashlib.sha256(" ".join(tokens).encode()).hexdigest()[:16]


def headline_jaccard(a: str, b: str) -> float:
    """Jaccard similarity on normalised token sets (ignores numbers)."""
    na = re.sub(r"\d+", "", normalise_headline(a))
    nb = re.sub(r"\d+", "", normalise_headline(b))
    sa, sb = set(na.split()), set(nb.split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def strip_emojis(text: str) -> str:
    """Remove all Unicode emojis from text. Catches every emoji block."""
    return re.sub(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F9FF"  # transport & map / supplemental
        "\U0001FA00-\U0001FA9F"  # chess, extended-A
        "\U0001FAA0-\U0001FAFF"  # extended-B
        "\U00002600-\U000027BF"  # misc symbols (☀★✓✗✅❌⚡⏳📄🔥 etc.)
        "\U0000FE00-\U0000FE0F"  # variation selectors
        "\U0000200D"             # ZWJ
        "]+",
        "",
        text,
        flags=re.UNICODE,
    )


def clean_meta_text(text: str) -> str:
    """Strip HTML tags, decode entities, normalise quotes for social sharing."""
    import html
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    # Replace curly quotes/apostrophes/dashes with plain ASCII via codepoints
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2026", "...")
    text = text.replace("\u2014", " - ").replace("\u2013", "-")
    text = strip_emojis(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

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
