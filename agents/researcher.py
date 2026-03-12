"""
Agent 1 — Research (Alex Rivera).

Fetches and filters RSS stories for a given category.
Feed URLs and fallback feeds are supplied by the caller (from SiteConfig),
keeping this module site-agnostic.
"""

import feedparser

from core.db import is_story_processed, store_raw_story
from core.utils import log


def research_agent(
    category: dict,
    category_feeds: dict[str, list[str]],
    fallback_feeds: list[str],
) -> list[dict] | None:
    """Fetch, filter, and deduplicate stories for *category*.

    Args:
        category:       Category dict with keys slug, name, keywords, image_style.
        category_feeds: Mapping of category slug → list of RSS feed URLs.
        fallback_feeds: Backup feed URLs used when primary feeds return < 3 stories.
    """
    log.info(f"🔍 [Agent 1] Fetching RSS for: {category['name']}")
    feeds   = category_feeds.get(category["slug"], [])
    stories = _fetch_from_feeds(feeds, category["keywords"])

    if len(stories) < 3:
        log.warning(f"  ⚠ Only {len(stories)} stories — trying fallback feeds")
        stories += _fetch_from_feeds(fallback_feeds, category["keywords"])

    if not stories:
        log.error(f"  ✗ No stories found for {category['name']}")
        return None

    # Deduplicate by first 40 chars of headline and skip already-processed URLs
    seen, unique = set(), []
    for s in stories:
        key = s["headline"][:40].lower()
        if key not in seen and not is_story_processed(s["url"]):
            seen.add(key)
            unique.append(s)

    # Sort by summary length (richer summaries → better article candidates)
    unique.sort(key=lambda s: len(s.get("summary", "")), reverse=True)
    result = unique[:10]
    log.info(f"  ✓ {len(result)} unique stories found")
    return result or None


def fetch_from_feeds(feeds: list[str], keywords: list[str]) -> list[dict]:
    """Public alias used by pipelines that fetch stories without a category."""
    return _fetch_from_feeds(feeds, keywords)


def _fetch_from_feeds(feeds: list[str], keywords: list[str]) -> list[dict]:
    """Parse RSS feed URLs and return stories matching *keywords*."""
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
                pub_date = entry.get("published", "")
                store_raw_story(link, title, summary[:1500], feed.feed.get("title", "Unknown"), pub_date)
                stories.append({
                    "headline": title,
                    "summary":  summary[:1500],
                    "url":      link,
                    "source":   feed.feed.get("title", "Unknown"),
                })
        except Exception as e:
            log.warning(f"  ⚠ Feed error ({feed_url[:40]}): {e}")
    return stories
