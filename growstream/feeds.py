"""
GrowStream — Agent 1: Research.
Fetches and filters RSS stories for each category.
"""

import random

import feedparser

from .config import log

# ============================================================
# RSS FEED CATALOGUE
# ============================================================
CATEGORY_FEEDS: dict[str, list[str]] = {
    "ai-in-banking": [
        "https://www.finextra.com/rss/channel.aspx?channel=ai",
        "https://feeds.feedburner.com/venturebeat/SZYF",
        "https://www.pymnts.com/feed/",
        "https://techcrunch.com/feed/",
    ],
    "fintech-news": [
        "https://techcrunch.com/category/fintech/feed/",
        "https://www.finextra.com/rss/headlines.aspx",
        "https://www.pymnts.com/feed/",
        "https://feeds.feedburner.com/venturebeat/SZYF",
    ],
    "investment-ai": [
        "https://feeds.feedburner.com/venturebeat/SZYF",
        "https://techcrunch.com/feed/",
        "https://www.pymnts.com/feed/",
        "https://www.finextra.com/rss/headlines.aspx",
    ],
    "regulatory-updates": [
        "https://www.finextra.com/rss/channel.aspx?channel=regulation",
        "https://techcrunch.com/feed/",
        "https://www.pymnts.com/feed/",
        "https://feeds.feedburner.com/venturebeat/SZYF",
    ],
    "tool-reviews": [
        "https://feeds.feedburner.com/venturebeat/SZYF",
        "https://techcrunch.com/feed/",
        "https://www.artificialintelligence-news.com/feed/",
        "https://www.pymnts.com/feed/",
    ],
}

FALLBACK_FEEDS: list[str] = [
    "https://techcrunch.com/feed/",
    "https://feeds.feedburner.com/venturebeat/SZYF",
    "https://www.pymnts.com/feed/",
]

# ============================================================
# CATEGORY DEFINITIONS
# ============================================================
CATEGORIES: list[dict] = [
    {
        "slug":        "ai-in-banking",
        "name":        "AI in Banking",
        "keywords":    ["bank", "banking", "financial institution", "credit", "loan", "ai", "machine learning"],
        "image_style": "banking technology finance digital",
        "author_id":   3,  # Alex Chen — AI & Banking
    },
    {
        "slug":        "fintech-news",
        "name":        "Fintech News",
        "keywords":    ["fintech", "payment", "neobank", "digital wallet", "startup", "funding", "raised"],
        "image_style": "fintech mobile payment startup technology",
        "author_id":   4,  # Priya Mehta — Fintech & Regulatory
    },
    {
        "slug":        "investment-ai",
        "name":        "Investment AI",
        "keywords":    ["invest", "stock", "portfolio", "hedge fund", "trading", "market", "fund", "ai"],
        "image_style": "stock market investment trading data analytics",
        "author_id":   3,  # Alex Chen — Investment AI
    },
    {
        "slug":        "regulatory-updates",
        "name":        "Regulatory Updates",
        "keywords":    ["regulation", "sec", "rbi", "compliance", "policy", "law", "regulatory", "ban"],
        "image_style": "regulation law compliance government policy",
        "author_id":   4,  # Priya Mehta — Regulatory
    },
    {
        "slug":        "tool-reviews",
        "name":        "Tool Reviews",
        "keywords":    ["tool", "platform", "software", "app", "launch", "product", "release", "ai"],
        "image_style": "software technology product interface dashboard",
        "author_id":   3,  # Alex Chen — Tool Reviews
    },
]


# ============================================================
# AGENT 1: RESEARCH
# ============================================================
def research_agent(category: dict) -> list[dict] | None:
    """Fetch, filter, and deduplicate stories from RSS for *category*."""
    log.info(f"🔍 [Agent 1] Fetching RSS for: {category['name']}")
    feeds   = CATEGORY_FEEDS[category["slug"]]
    stories = _fetch_from_feeds(feeds, category["keywords"])

    if len(stories) < 3:
        log.warning(f"  ⚠ Only {len(stories)} stories — trying fallback feeds")
        stories += _fetch_from_feeds(FALLBACK_FEEDS, category["keywords"])

    if not stories:
        log.error(f"  ✗ No stories found for {category['name']}")
        return None

    # Deduplicate by first 40 chars of headline
    seen, unique = set(), []
    for s in stories:
        key = s["headline"][:40].lower()
        if key not in seen:
            seen.add(key)
            unique.append(s)

    random.shuffle(unique)
    result = unique[:10]
    log.info(f"  ✓ {len(result)} unique stories found")
    return result


def _fetch_from_feeds(feeds: list[str], keywords: list[str]) -> list[dict]:
    """Parse a list of RSS feed URLs and return matching stories."""
    stories: list[dict] = []
    for feed_url in feeds:
        try:
            feed = feedparser.parse(feed_url)
            if feed.bozo:
                log.warning(f"  ⚠ Malformed feed: {feed_url[:50]}")
                continue
            for entry in feed.entries[:8]:
                title   = entry.get("title", "").strip()
                summary = (entry.get("summary") or entry.get("description") or "").strip()
                link    = entry.get("link", "")
                if not title or not summary or len(summary) < 80:
                    continue
                text = (title + " " + summary).lower()
                if not any(kw in text for kw in keywords):
                    continue
                stories.append({
                    "headline": title,
                    "summary":  summary[:1500],
                    "url":      link,
                    "source":   feed.feed.get("title", "Unknown"),
                })
        except Exception as e:
            log.warning(f"  ⚠ Feed error ({feed_url[:40]}): {e}")
    return stories
