"""
MongoDB database layer.

Call `configure(db_name)` once per run to set the target database.
All DAO functions use the configured database automatically.

Connection is read from MONGODB_URI in the environment.
A module-level PyMongo client is created lazily and reused across threads
(PyMongo MongoClient is thread-safe by design).

Duplicate detection layers
───────────────────────────
Layer 1  is_story_processed(url)         exact URL match in raw_stories
Layer 2  is_headline_seen(fingerprint)   SHA-256 fingerprint across all seen stories
Layer 3  is_headline_duplicate(headline) Jaccard + entity-anchor against
                                          published_articles from last 30 days
Layer 4  WordPressClient.article_exists  WP title search — final safeguard
"""

import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote_plus

from .utils import headline_fingerprint, headline_jaccard, log, normalise_headline

# Load .env so core/db works when imported standalone (e.g. tests, scripts)
try:
    from dotenv import load_dotenv
    for _p in [Path(__file__).parent.parent / ".env",
               Path(__file__).parent.parent / "growstream" / ".env"]:
        if _p.exists():
            load_dotenv(dotenv_path=_p, override=True)
            break
except ImportError:
    pass

# ── Connection ────────────────────────────────────────────────────────────────

_client      = None
_db_name: str = "newsbot"

# Semantic dedup threshold for Layer 3
_SEMANTIC_THRESHOLD = 0.40
_ENTITY_THRESHOLD   = 0.22


def _get_uri() -> str:
    """Return a properly encoded MongoDB URI.

    If MONGODB_URI has unencoded special characters in the password
    (%, (, ), * are common in Atlas auto-generated passwords), this re-encodes
    the password using the raw value from MONGODB_DB_PASSWORD while keeping
    the full host/query string from the original URI intact.
    """
    uri = os.environ.get("MONGODB_URI", "").strip()
    if not uri:
        raise RuntimeError(
            "MONGODB_URI is not set. Add it to your .env file or GitHub Secrets."
        )

    # Parse: scheme://user:pass@host/rest
    m = re.match(r"(mongodb(?:\+srv)?://)([^:@]+):([^@]+)@(.+)", uri)
    if not m:
        return uri  # unusual format — pass through as-is

    scheme, user, raw_pass, host_and_rest = m.groups()

    # Check if the password section has invalid percent-encoding
    # Valid: %XX where both X are hex digits. Invalid: bare %, (, ), *
    has_bare_special = bool(
        re.search(r"%(?![0-9a-fA-F]{2})", raw_pass) or
        any(c in raw_pass for c in "()* ")
    )
    if not has_bare_special:
        return uri  # already clean

    # Re-encode using the raw password from env (strip surrounding quotes)
    raw_password = os.environ.get("MONGODB_DB_PASSWORD", raw_pass).strip("'\"")
    safe_uri = f"{scheme}{quote_plus(user)}:{quote_plus(raw_password)}@{host_and_rest}"
    log.info("  ℹ  MONGODB_URI: password re-encoded (special characters detected)")
    return safe_uri


def _get_client():
    global _client
    if _client is None:
        from pymongo import MongoClient
        _client = MongoClient(_get_uri(), serverSelectionTimeoutMS=10_000)
    return _client


def _db():
    return _get_client()[_db_name]


# ── Bootstrap ─────────────────────────────────────────────────────────────────

def configure(db_name: str) -> None:
    """Set the target database and ensure indexes exist."""
    global _db_name
    _db_name = db_name
    _ensure_indexes()
    log.info(f"  ✓ MongoDB configured: {db_name}")


def _ensure_indexes() -> None:
    from pymongo import ASCENDING, DESCENDING
    db = _db()

    db.raw_stories.create_index("headline_fingerprint")
    db.raw_stories.create_index("processed")
    # _id = url (unique by default)

    db.published_articles.create_index([("published_at", DESCENDING)])
    db.published_articles.create_index("headline_norm")
    # _id = wp_post_id (unique by default)

    db.social_queue.create_index("added_at")
    db.llm_metrics.create_index([("run_date", DESCENDING)])


# ── Story DAOs ────────────────────────────────────────────────────────────────

def store_raw_story(
    guid: str,
    headline: str,
    summary: str,
    source: str,
    pub_date: str,
) -> bool:
    """Insert a story. Returns True if inserted, False if already existed."""
    from pymongo.errors import DuplicateKeyError
    fp = headline_fingerprint(headline)
    try:
        _db().raw_stories.insert_one({
            "_id":                  guid,
            "headline":             headline,
            "headline_fingerprint": fp,
            "summary":              summary,
            "source":               source,
            "published_date":       pub_date,
            "processed":            False,
            "created_at":           datetime.now(timezone.utc),
        })
        return True
    except DuplicateKeyError:
        return False


def mark_raw_story_processed(guid: str) -> None:
    _db().raw_stories.update_one(
        {"_id": guid},
        {"$set": {"processed": True}}
    )


def is_story_processed(guid: str) -> bool:
    """Layer 1: exact URL match."""
    doc = _db().raw_stories.find_one({"_id": guid}, {"processed": 1})
    return bool(doc and doc.get("processed"))


def is_headline_seen(fingerprint: str) -> bool:
    """Layer 2: fingerprint match across all seen stories (raw + published)."""
    if _db().raw_stories.find_one({"headline_fingerprint": fingerprint}, {"_id": 1}):
        return True
    return False


def is_headline_duplicate(headline: str, days: int = 30) -> bool:
    """Layer 3: semantic similarity against recently published articles.

    Two-signal check:
    1. Jaccard on normalised token sets >= 0.40
    2. Same primary entity AND Jaccard >= 0.22
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows   = list(_db().published_articles.find(
        {"published_at": {"$gte": cutoff}},
        {"title": 1, "headline_norm": 1},
        limit=200,
    ))
    if not rows:
        return False

    norm    = normalise_headline(headline)
    entities = re.findall(r"\b[A-Z][a-zA-Z]{2,}\b", headline)
    first_entity = entities[0].lower() if entities else ""

    for row in rows:
        past_norm = row.get("headline_norm") or normalise_headline(row.get("title", ""))
        j = headline_jaccard(norm, past_norm)
        if j >= _SEMANTIC_THRESHOLD:
            return True
        if first_entity and first_entity in past_norm and j >= _ENTITY_THRESHOLD:
            return True

    return False


# ── Article DAOs ──────────────────────────────────────────────────────────────

def log_published_article(
    wp_post_id: int,
    title: str,
    focus_keyword: str,
    unsplash_id: str | None = None,
    source_url: str | None = None,
    post_url: str | None = None,
    category: str | None = None,
    article_type: str | None = None,
    seo_score: int | None = None,
    quality_score: int | None = None,
) -> None:
    norm = normalise_headline(title)
    _db().published_articles.replace_one(
        {"_id": wp_post_id},
        {
            "_id":           wp_post_id,
            "title":         title,
            "headline_norm": norm,
            "source_url":    source_url,
            "post_url":      post_url,
            "focus_keyword": focus_keyword,
            "category":      category,
            "article_type":  article_type,
            "seo_score":     seo_score,
            "quality_score": quality_score,
            "unsplash_id":   unsplash_id,
            "published_at":  datetime.now(timezone.utc),
        },
        upsert=True,
    )
    _db().social_queue.update_one(
        {"_id": wp_post_id},
        {"$setOnInsert": {
            "_id":             wp_post_id,
            "linkedin_status": "pending",
            "twitter_status":  "pending",
            "facebook_status": "pending",
            "added_at":        datetime.now(timezone.utc),
        }},
        upsert=True,
    )


def get_recent_articles_for_linking(
    days: int = 60,
    exclude_id: int | None = None,
    limit: int = 20,
) -> list[dict]:
    """Return recently published articles for internal link selection.

    Excludes the article being currently built (exclude_id) and any without
    a post_url (legacy records before post_url was tracked).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    query: dict = {
        "published_at": {"$gte": cutoff},
        "post_url":     {"$exists": True, "$ne": None},
    }
    if exclude_id:
        query["_id"] = {"$ne": exclude_id}

    return list(_db().published_articles.find(
        query,
        {"title": 1, "post_url": 1, "focus_keyword": 1, "category": 1, "article_type": 1},
        sort=[("published_at", -1)],
        limit=limit,
    ))


def is_image_used(unsplash_id: str) -> bool:
    if not unsplash_id:
        return False
    return bool(_db().published_articles.find_one({"unsplash_id": unsplash_id}, {"_id": 1}))


# ── Social queue DAOs ─────────────────────────────────────────────────────────

def get_pending_social_posts() -> list[dict]:
    return list(_db().social_queue.find({
        "$or": [
            {"linkedin_status":  "pending"},
            {"twitter_status":   "pending"},
            {"facebook_status":  "pending"},
        ]
    }))


def update_social_status(wp_post_id: int, platform: str, status: str) -> None:
    if platform not in ("linkedin", "twitter", "facebook"):
        return
    _db().social_queue.update_one(
        {"_id": wp_post_id},
        {"$set": {f"{platform}_status": status}},
    )


# ── LLM metrics ───────────────────────────────────────────────────────────────

def log_llm_usage(
    agent_name: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
) -> None:
    _db().llm_metrics.insert_one({
        "agent_name":          agent_name,
        "input_tokens":        input_tokens,
        "output_tokens":       output_tokens,
        "estimated_cost_usd":  cost_usd,
        "run_date":            datetime.now(timezone.utc),
    })
