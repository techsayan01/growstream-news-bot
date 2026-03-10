"""
GrowStream — Dumbest Move of the Week Pipeline.

Weekly (Sunday) pipeline that picks the most questionable decision in AI finance
and publishes a humorous accountability piece.

Run: python dumbest_move.py
"""

from datetime import datetime

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
from ..seo import generate_meta_description

_WP_CATEGORY_NAME = "Dumbest Move of the Week"
_WP_CATEGORY_SLUG = "dumbest-move"

_ALL_KEYWORDS = [
    "bank", "fintech", "payment", "ai", "fund", "regulation", "sec", "rbi",
    "billion", "million", "ceo", "executive", "company", "startup",
]

_PERSONA = """\
You are Jordan Blake, Senior Financial Journalist at GrowStream Media.
You call out questionable decisions in AI finance with dry humour and accountability journalism.
You are never cruel, always accurate, and occasionally devastating.
"""


@with_retry(max_retries=3, delay=5)
def _pick_dumbest_story(stories: list[dict]) -> dict | None:
    """Sarah Chen picks the story with the most obviously questionable decision."""
    import json
    stories_json = json.dumps(
        [{"index": i, "headline": s["headline"], "summary": s["summary"][:300]}
         for i, s in enumerate(stories[:20])],
        indent=2,
    )
    prompt = f"""\
You are Dr. Sarah Chen. Pick the story where a company, regulator, or executive made
the MOST questionable, misguided, or ironic decision in AI finance this week.

Stories:
{stories_json}

Return ONLY JSON:
{{
  "index": 0,
  "decision_maker": "Company or person who made the questionable decision",
  "what_they_did": "One sentence describing the move",
  "why_questionable": "One sentence on why it's a bad call"
}}"""
    r = get_client().messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    result = safe_json_parse(r.content[0].text)
    if result and "index" in result:
        idx = int(result["index"])
        if 0 <= idx < len(stories):
            story = stories[idx]
            story["_dm_decision_maker"] = result.get("decision_maker", "")
            story["_dm_what"] = result.get("what_they_did", "")
            story["_dm_why"] = result.get("why_questionable", "")
            return story
    return stories[0] if stories else None


@with_retry(max_retries=3, delay=5)
def _write_dumbest_move(story: dict) -> str | None:
    decision_maker = story.get("_dm_decision_maker", "the company involved")
    prompt = f"""{_PERSONA}

Write a 300-400 word humorous but fair accountability piece about this questionable decision.

Use this EXACT structure:

<h2>🏆 This Week's Questionable Move</h2>
One dramatic paragraph introducing {decision_maker} and what they did. Set the scene.

<h2>The Full Story</h2>
2 paragraphs. What happened, who's affected, the context. Facts first, wit second.

<h2>What They Were Probably Thinking</h2>
1 paragraph. Be charitable — explain their likely rationale. Make it human.

<h2>Why It Backfired (or Will)</h2>
1 paragraph. The actual problem with the decision. Stay factual.

<h2>What They Should Have Done Instead</h2>
3 bullet points. Practical alternatives.

<div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 16px; border-radius: 6px;">
  <strong>📊 The Grade: [Give an A-F grade]</strong><br>
  [One sentence verdict]<br>
  <em>Better luck next week.</em>
</div>

Rules:
- Humorous, not cruel. Accountability, not attack.
- Do NOT fabricate any facts — stay within the source material.
- Return ONLY the HTML body.

Story:
Headline: {story['headline']}
Source: {story['source']}
Summary: {story['summary'][:600]}
Decision maker: {decision_maker}
What they did: {story.get('_dm_what', '')}"""

    r = get_client().messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    content = r.content[0].text.strip()
    if content.startswith("```"):
        content = content.split("```", 2)[1]
        if content.startswith("html"):
            content = content[4:]
        content = content.rsplit("```", 1)[0].strip()
    return content


def run() -> None:
    log.info("=" * 60)
    log.info("  GrowStream — Dumbest Move of the Week Pipeline")
    log.info(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')} IST")
    log.info("=" * 60)

    run_preflight(abort_on_failure=True)

    # Fetch from all feeds for a broad net
    all_stories = []
    for slug, feeds in CATEGORY_FEEDS.items():
        all_stories += _fetch_from_feeds(feeds, _ALL_KEYWORDS)
    if not all_stories:
        all_stories = _fetch_from_feeds(FALLBACK_FEEDS, _ALL_KEYWORDS)

    # Deduplicate
    seen, unique = set(), []
    for s in all_stories:
        key = s["headline"][:40].lower()
        if key not in seen:
            seen.add(key)
            unique.append(s)

    log.info(f"  ✓ {len(unique)} stories available for review")

    story = _pick_dumbest_story(unique)
    if not story:
        log.error("  ✗ Could not identify a story")
        return

    log.info(f"  🤔 Selected: '{story['headline'][:60]}...'")
    log.info(f"  Decision maker: {story.get('_dm_decision_maker', 'Unknown')}")

    content = _write_dumbest_move(story)
    if not content:
        log.error("  ✗ Content generation failed")
        return

    week_str = datetime.now().strftime("Week of %B %d, %Y")
    title = f"😬 Dumbest Move of the Week — {week_str}"
    meta = generate_meta_description(title, content, "ai finance accountability")

    category_id = get_or_create_wp_category(_WP_CATEGORY_NAME, _WP_CATEGORY_SLUG)
    used_slugs = get_recent_featured_image_slugs(days=7)
    images = fetch_unsplash_images(["business mistake failure corporate"], "corporate business decision", count=1, used_slugs=used_slugs)

    featured_id = None
    unsplash_id = None
    if images:
        uploaded = upload_image_to_wordpress(images[0], title)
        if uploaded:
            featured_id = uploaded["id"]
            unsplash_id = images[0].get("unsplash_id")

    post_url = publish_to_wordpress(
        title=title,
        html_content=content,
        category_id=category_id,
        featured_image_id=featured_id,
        meta_description=meta,
        focus_keyword="ai finance accountability",
        unsplash_id=unsplash_id,
    )
    if post_url:
        from ..db import mark_raw_story_processed
        mark_raw_story_processed(story["url"])
        log.info(f"  ✅ Dumbest Move LIVE → {post_url}")
    else:
        log.error("  ✗ Publish failed")
