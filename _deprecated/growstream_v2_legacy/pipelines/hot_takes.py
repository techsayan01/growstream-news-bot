"""
GrowStream — Hot Takes Pipeline.

Publishes a single 80-100 word punchy opinion post daily.
Scans all category feeds, picks the most provocative story, and publishes fast.
No editor review. No hero image. Just the take.

Run: python hot_takes.py
"""

from datetime import datetime

import anthropic

from ..config import get_client, log, safe_json_parse, with_retry
from ..feeds import CATEGORY_FEEDS, FALLBACK_FEEDS, _fetch_from_feeds
from ..images import fetch_unsplash_images
from ..preflight import run_preflight
from ..publisher import (
    get_or_create_wp_category,
    get_recent_featured_image_slugs,
    publish_to_wordpress,
    upload_image_to_wordpress,
)

_WP_CATEGORY_NAME = "Hot Takes"
_WP_CATEGORY_SLUG = "hot-takes"

_ALL_KEYWORDS = [
    "bank", "fintech", "payment", "ai", "fund", "invest", "regulation",
    "raised", "billion", "million", "crypto", "fraud", "merger", "IPO",
]

_PERSONA = """\
You are Jordan Blake, Senior Financial Journalist at GrowStream Media.
You are sharp, irreverent, and never boring. You have hot opinions and you say them out loud.
"""


@with_retry(max_retries=3, delay=5)
def _pick_story(stories: list[dict]) -> dict | None:
    """Have Dr. Sarah Chen pick the single most share-worthy story for a hot take."""
    import json
    prompt = f"""\
You are Dr. Sarah Chen, Chief Market Intelligence Analyst at GrowStream Media.
Pick the SINGLE story from this list that is most likely to provoke debate, disagreement, or strong emotion:

{json.dumps([{"headline": s["headline"], "summary": s["summary"][:300]} for s in stories[:20]], indent=2)}

Return ONLY JSON:
{{
  "index": 0,
  "reason": "One sentence on why this is the most provocative story."
}}"""
    r = get_client().messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    result = safe_json_parse(r.content[0].text)
    if result and "index" in result:
        idx = int(result["index"])
        if 0 <= idx < len(stories):
            log.info(f"  ✓ Story picked: {result.get('reason','')}")
            return stories[idx]
    return stories[0] if stories else None


@with_retry(max_retries=3, delay=5)
def _write_hot_take(story: dict) -> str | None:
    """Jordan Blake writes an 80-100 word hot take on the story."""
    prompt = f"""{_PERSONA}

Write an 80-100 word hot take on this story. Rules:
- State your opinion in sentence 1. Make it bold.
- Back it up in 2-3 punchy sentences. Use specific names/numbers where possible.
- End with one quotable one-liner.
- Write in first-person editorial voice ("we think", "here's the thing").
- No intro, no fluff. Tweet energy but with a brain.
- Format as a single <p> paragraph — no headings, no lists.
- Return ONLY the HTML <p> tag.

Story:
Headline: {story['headline']}
Summary: {story['summary'][:500]}"""

    r = get_client().messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    content = r.content[0].text.strip()
    if not content.startswith("<p"):
        content = f"<p>{content}</p>"
    return content


def run() -> None:
    log.info("=" * 60)
    log.info("  GrowStream — Hot Takes Pipeline")
    log.info(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')} IST")
    log.info("=" * 60)

    run_preflight(abort_on_failure=True)

    # Collect stories from all feeds
    all_stories: list[dict] = []
    for slug, feeds in CATEGORY_FEEDS.items():
        all_stories += _fetch_from_feeds(feeds, _ALL_KEYWORDS)
    if len(all_stories) < 3:
        all_stories += _fetch_from_feeds(FALLBACK_FEEDS, _ALL_KEYWORDS)

    if not all_stories:
        log.error("  ✗ No stories found for Hot Takes")
        return

    # Deduplicate
    seen, unique = set(), []
    for s in all_stories:
        key = s["headline"][:40].lower()
        if key not in seen:
            seen.add(key)
            unique.append(s)

    log.info(f"  ✓ {len(unique)} unique stories across all feeds")

    story = _pick_story(unique)
    if not story:
        log.error("  ✗ Could not pick a story")
        return

    log.info(f"  📰 '{story['headline'][:60]}...'")

    content = _write_hot_take(story)
    if not content:
        log.error("  ✗ Hot take generation failed")
        return

    # Wrap in a styled callout box
    today = datetime.now().strftime("%B %d, %Y")
    title = f"🔥 Hot Take: {story['headline'][:50]}"
    html = f"""
<div style="background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color: #fff; padding: 30px; border-radius: 12px; margin-bottom: 24px;">
  <p style="font-size: 0.85em; text-transform: uppercase; letter-spacing: 2px; color: #a0aec0; margin-top: 0;">GrowStream Hot Take · {today}</p>
  {content}
  <p style="margin-bottom: 0; font-size: 0.8em; color: #718096;">Source: <a href="{story.get('url', '#')}" style="color: #90cdf4;" target="_blank" rel="noopener">{story.get('source', 'Unknown')}</a></p>
</div>
"""

    category_id = get_or_create_wp_category(_WP_CATEGORY_NAME, _WP_CATEGORY_SLUG)
    used_slugs = get_recent_featured_image_slugs(days=7)
    images = fetch_unsplash_images(["finance opinion editorial"], "finance editorial dark", count=1, used_slugs=used_slugs)

    featured_id = None
    unsplash_id = None
    if images:
        uploaded = upload_image_to_wordpress(images[0], title)
        if uploaded:
            featured_id = uploaded["id"]
            unsplash_id = images[0].get("unsplash_id")

    post_url = publish_to_wordpress(
        title=title,
        html_content=html,
        category_id=category_id,
        featured_image_id=featured_id,
        meta_description=f"GrowStream's hot take on: {story['headline'][:120]}",
        focus_keyword="hot take finance",
        unsplash_id=unsplash_id,
    )
    if post_url:
        from ..db import mark_raw_story_processed
        mark_raw_story_processed(story["url"])
        log.info(f"  ✅ Hot Take LIVE → {post_url}")
    else:
        log.error("  ✗ Hot Take publish failed")
