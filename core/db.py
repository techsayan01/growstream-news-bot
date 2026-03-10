"""
SQLite database layer.

Call `configure(db_path)` once per run to point at the correct site database.
All DAO functions use the configured path automatically.
"""

import sqlite3
import threading
from pathlib import Path

from .utils import log

_db_path: str = "data/newsbot.db"
_local = threading.local()


def configure(db_path: str) -> None:
    """Set the database file path and initialise the schema."""
    global _db_path
    _db_path = db_path
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    _init_schema()
    log.info(f"  ✓ Database configured: {db_path}")


def _get_db() -> sqlite3.Connection:
    """Return a thread-local connection, creating one if needed."""
    if not hasattr(_local, "conn") or getattr(_local, "db_path", None) != _db_path:
        _local.conn    = sqlite3.connect(_db_path, isolation_level=None)  # autocommit
        _local.conn.row_factory = sqlite3.Row
        _local.db_path = _db_path
    return _local.conn


def _init_schema() -> None:
    db = _get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS raw_stories (
            id             TEXT PRIMARY KEY,
            headline       TEXT,
            summary        TEXT,
            source         TEXT,
            published_date DATETIME,
            processed      BOOLEAN DEFAULT 0
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS published_articles (
            wp_post_id   INTEGER PRIMARY KEY,
            title        TEXT,
            focus_keyword TEXT,
            unsplash_id  TEXT,
            published_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS social_queue (
            wp_post_id       INTEGER PRIMARY KEY,
            linkedin_status  TEXT DEFAULT 'pending'
                CHECK(linkedin_status  IN ('pending','published','failed')),
            twitter_status   TEXT DEFAULT 'pending'
                CHECK(twitter_status   IN ('pending','published','failed')),
            facebook_status  TEXT DEFAULT 'pending'
                CHECK(facebook_status  IN ('pending','published','failed')),
            added_at         DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS llm_metrics (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_name         TEXT,
            input_tokens       INTEGER,
            output_tokens      INTEGER,
            estimated_cost_usd REAL,
            run_date           DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)


# ── Story DAOs ──────────────────────────────────────────────────────────────

def store_raw_story(guid: str, headline: str, summary: str, source: str, pub_date: str) -> bool:
    """Insert a story. Returns True if inserted, False if it already existed."""
    try:
        _get_db().execute(
            "INSERT INTO raw_stories (id, headline, summary, source, published_date) VALUES (?,?,?,?,?)",
            (guid, headline, summary, source, pub_date),
        )
        return True
    except sqlite3.IntegrityError:
        return False


def mark_raw_story_processed(guid: str) -> None:
    _get_db().execute("UPDATE raw_stories SET processed = 1 WHERE id = ?", (guid,))


def is_story_processed(guid: str) -> bool:
    cur = _get_db().execute("SELECT processed FROM raw_stories WHERE id = ?", (guid,))
    row = cur.fetchone()
    return bool(row and row["processed"])


# ── Article DAOs ─────────────────────────────────────────────────────────────

def log_published_article(wp_post_id: int, title: str, focus_keyword: str, unsplash_id: str | None = None) -> None:
    db = _get_db()
    db.execute(
        "INSERT OR REPLACE INTO published_articles (wp_post_id, title, focus_keyword, unsplash_id) VALUES (?,?,?,?)",
        (wp_post_id, title, focus_keyword, unsplash_id),
    )
    db.execute("INSERT OR IGNORE INTO social_queue (wp_post_id) VALUES (?)", (wp_post_id,))


def is_image_used(unsplash_id: str) -> bool:
    if not unsplash_id:
        return False
    cur = _get_db().execute("SELECT 1 FROM published_articles WHERE unsplash_id = ?", (unsplash_id,))
    return cur.fetchone() is not None


# ── Social queue DAOs ─────────────────────────────────────────────────────────

def get_pending_social_posts() -> list[sqlite3.Row]:
    cur = _get_db().execute("""
        SELECT wp_post_id, linkedin_status, twitter_status, facebook_status
        FROM social_queue
        WHERE linkedin_status = 'pending'
           OR twitter_status  = 'pending'
           OR facebook_status = 'pending'
    """)
    return cur.fetchall()


def update_social_status(wp_post_id: int, platform: str, status: str) -> None:
    if platform not in ("linkedin", "twitter", "facebook"):
        return
    col = f"{platform}_status"
    _get_db().execute(f"UPDATE social_queue SET {col} = ? WHERE wp_post_id = ?", (status, wp_post_id))


# ── LLM metrics ──────────────────────────────────────────────────────────────

def log_llm_usage(agent_name: str, input_tokens: int, output_tokens: int, cost_usd: float) -> None:
    _get_db().execute(
        "INSERT INTO llm_metrics (agent_name, input_tokens, output_tokens, estimated_cost_usd) VALUES (?,?,?,?)",
        (agent_name, input_tokens, output_tokens, cost_usd),
    )
