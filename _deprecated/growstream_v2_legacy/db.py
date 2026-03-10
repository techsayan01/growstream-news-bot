"""
GrowStream — SQLite Database Layer.

Handles the connection to growstream.db and running the initial schema
on startup. Provides core data access objects (DAOs) for pipelines.
"""

import sqlite3
import threading
from pathlib import Path

from .config import log

DB_PATH = Path(__file__).parent.parent / "growstream.db"

# Thread-local storage since SQLite connections can't be shared across threads easily
_local = threading.local()

def get_db():
    """Get a thread-local SQLite connection with row factory enabled."""
    if not hasattr(_local, "conn"):
        _local.conn = sqlite3.connect(DB_PATH, isolation_level=None) # autocommit
        _local.conn.row_factory = sqlite3.Row
    return _local.conn

def init_db():
    """Initialize the database schema if it doesn't exist."""
    db = get_db()
    
    db.execute("""
        CREATE TABLE IF NOT EXISTS raw_stories (
            id TEXT PRIMARY KEY,
            headline TEXT,
            summary TEXT,
            source TEXT,
            published_date DATETIME,
            processed BOOLEAN DEFAULT 0
        )
    """)
    
    db.execute("""
        CREATE TABLE IF NOT EXISTS published_articles (
            wp_post_id INTEGER PRIMARY KEY,
            title TEXT,
            focus_keyword TEXT,
            unsplash_id TEXT,
            published_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    db.execute("""
        CREATE TABLE IF NOT EXISTS social_queue (
            wp_post_id INTEGER PRIMARY KEY,
            linkedin_status TEXT DEFAULT 'pending' CHECK(linkedin_status IN ('pending', 'published', 'failed')),
            twitter_status TEXT DEFAULT 'pending'  CHECK(twitter_status IN ('pending', 'published', 'failed')),
            facebook_status TEXT DEFAULT 'pending' CHECK(facebook_status IN ('pending', 'published', 'failed')),
            added_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    db.execute("""
        CREATE TABLE IF NOT EXISTS llm_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_name TEXT,
            input_tokens INTEGER,
            output_tokens INTEGER,
            estimated_cost_usd REAL,
            run_date DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

# Initialize schema on first import
init_db()

# ============================================================
# DATA ACCESS DAOs
# ============================================================

def store_raw_story(guid_or_url: str, headline: str, summary: str, source: str, pub_date: str) -> bool:
    """Store a fetched story. Returns True if inserted, False if it already exists."""
    db = get_db()
    try:
        db.execute(
            """INSERT INTO raw_stories (id, headline, summary, source, published_date)
               VALUES (?, ?, ?, ?, ?)""",
            (guid_or_url, headline, summary, source, pub_date)
        )
        return True
    except sqlite3.IntegrityError:
        return False

def mark_raw_story_processed(guid_or_url: str) -> None:
    db = get_db()
    db.execute("UPDATE raw_stories SET processed = 1 WHERE id = ?", (guid_or_url,))

def log_published_article(wp_post_id: int, title: str, focus_keyword: str, unsplash_id: str | None = None) -> None:
    db = get_db()
    # 1. Log the article
    db.execute(
        """INSERT OR REPLACE INTO published_articles (wp_post_id, title, focus_keyword, unsplash_id)
           VALUES (?, ?, ?, ?)""",
        (wp_post_id, title, focus_keyword, unsplash_id)
    )
    # 2. Add to social queue
    db.execute(
        """INSERT OR IGNORE INTO social_queue (wp_post_id) VALUES (?)""",
        (wp_post_id,)
    )

def is_image_used(unsplash_id: str) -> bool:
    """Check if an Unsplash image has EVER been used by the bot."""
    if not unsplash_id:
        return False
    db = get_db()
    cur = db.execute("SELECT 1 FROM published_articles WHERE unsplash_id = ?", (unsplash_id,))
    return cur.fetchone() is not None

def log_llm_usage(agent_name: str, input_tokens: int, output_tokens: int, cost_usd: float) -> None:
    db = get_db()
    db.execute(
        """INSERT INTO llm_metrics (agent_name, input_tokens, output_tokens, estimated_cost_usd)
           VALUES (?, ?, ?, ?)""",
        (agent_name, input_tokens, output_tokens, cost_usd)
    )

def get_pending_social_posts() -> list[sqlite3.Row]:
    db = get_db()
    cur = db.execute('''
        SELECT wp_post_id, linkedin_status, twitter_status, facebook_status 
        FROM social_queue 
        WHERE linkedin_status = 'pending' 
           OR twitter_status = 'pending' 
           OR facebook_status = 'pending'
    ''')
    return cur.fetchall()

def update_social_status(wp_post_id: int, platform: str, status: str) -> None:
    db = get_db()
    col = f"{platform}_status"
    # Parameterized column name isn't directly supported, but since platform is trusted ('linkedin', 'twitter', 'facebook'):
    if platform in ("linkedin", "twitter", "facebook"):
        db.execute(f"UPDATE social_queue SET {col} = ? WHERE wp_post_id = ?", (status, wp_post_id))

def get_recent_raw_stories(days: int = 30) -> list[dict]:
    db = get_db()
    cur = db.execute(f"SELECT id as url, title as headline, summary, source_name as source FROM raw_stories WHERE first_seen >= datetime('now', '-{days} days')")
    return [dict(row) for row in cur.fetchall()]
