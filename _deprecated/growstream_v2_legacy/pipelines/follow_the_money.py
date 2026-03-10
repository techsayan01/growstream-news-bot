"""
GrowStream — Follow the Money Pipeline.

Finds funding/M&A/investment stories and publishes an investigative-style trace
of where the money actually went and what it signals about the market.

Only runs if a funding story is found.
Run: python follow_the_money.py
"""

from datetime import datetime

from ..config import get_client, log, with_retry
from ..feeds import CATEGORY_FEEDS, FALLBACK_FEEDS, _fetch_from_feeds
from ..images import fetch_unsplash_images
from ..preflight import run_preflight
from ..publisher import (
    get_or_create_wp_category,
    get_recent_featured_image_slugs,
    publish_to_wordpress,
    upload_image_to_wordpress,
)
from ..seo import generate_focus_keyword, generate_meta_description, generate_seo_title

_WP_CATEGORY_NAME = "Follow the Money"
_WP_CATEGORY_SLUG = "follow-the-money"

_FUNDING_TRIGGERS = [
    "raised", "funding", "million", "billion", "acquired", "acquisition",
    "merger", "ipo", "investment round", "series a", "series b", "series c",
    "seed round", "venture", "backed", "valued at", "valuation",
]

_PERSONA = """\
You are Jordan Blake, Senior Financial Journalist at GrowStream Media.
You specialise in tracing investment flows — who the real winners are, where money actually lands,
and what a funding announcement signals about the broader market shift.
You connect public dots in ways readers haven't seen before.
"""


def _is_funding_story(story: dict) -> bool:
    text = (story["headline"] + " " + story["summary"]).lower()
    return any(kw in text for kw in _FUNDING_TRIGGERS)


@with_retry(max_retries=3, delay=5)
def _write_money_trace(story: dict, focus_kw: str) -> str | None:
    prompt = f"""{_PERSONA}

Write a 600-800 word investigative analysis tracing this investment/funding story.

Structure (use these exact H2 headings):

<h2>The Deal</h2>
2 paragraphs — who, what, how much, when. Include <strong>the numbers</strong>.

<h2>Where the Money Actually Goes</h2>
2 paragraphs — break down what this funding will be used for. Is it R&D? Headcount? Acquisition war chest?
Be specific about the implied allocation even if not stated.

<h2>Who Benefits (and Who Doesn't)</h2>
Use a bullet list — name 3-4 specific entities (companies, sectors, regulators) and one sentence on each.

<h2>What It Signals About the Market</h2>
2 paragraphs — this is the investigative insight. What does this deal tell us about where smart money
is moving? What trend is being validated or killed?

<h2>The Global Ripple Effect</h2>
3 short paragraphs (one each for Asia, Europe, US) — how does this money movement affect each region?

<h2>The Bottom Line</h2>
<div style="background-color: #e9ecef; padding: 20px; border-radius: 8px;">
  One punchy paragraph. Include the focus keyword "{focus_kw}". What should a CFO/investor do next?
</div>

Rules:
- Do NOT fabricate numbers not in the source
- Use <strong> for all financial figures
- Return ONLY the HTML body

Story:
Headline: {story['headline']}
Source: {story['source']}
URL: {story.get('url', '')}
Summary: {story['summary'][:800]}"""

    r = get_client().messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2500,
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
    log.info("  GrowStream — Follow the Money Pipeline")
    log.info(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')} IST")
    log.info("=" * 60)

    run_preflight(abort_on_failure=True)

    # Fetch from investment + fintech feeds
    feeds = CATEGORY_FEEDS.get("investment-ai", []) + CATEGORY_FEEDS.get("fintech-news", [])
    stories = _fetch_from_feeds(feeds, _FUNDING_TRIGGERS)
    if not stories:
        stories = _fetch_from_feeds(FALLBACK_FEEDS, _FUNDING_TRIGGERS)

    funding_stories = [s for s in stories if _is_funding_story(s)]

    if not funding_stories:
        log.warning("  ⚠ No qualifying funding/M&A stories found today — skipping")
        return

    story = funding_stories[0]
    log.info(f"  💰 Processing: '{story['headline'][:60]}...'")

    focus_kw = generate_focus_keyword(story["headline"], "investment ai")
    seo_title = generate_seo_title(story["headline"], "investment funding")
    content = _write_money_trace(story, focus_kw)

    if not content:
        log.error("  ✗ Content generation failed")
        return

    meta = generate_meta_description(seo_title, content, focus_kw)

    category_id = get_or_create_wp_category(_WP_CATEGORY_NAME, _WP_CATEGORY_SLUG)
    used_slugs = get_recent_featured_image_slugs(days=7)
    images = fetch_unsplash_images(["money investment finance funding"], "finance investment money", count=1, used_slugs=used_slugs)

    featured_id = None
    unsplash_id = None
    if images:
        uploaded = upload_image_to_wordpress(images[0], seo_title, focus_keyword=focus_kw)
        if uploaded:
            featured_id = uploaded["id"]
            unsplash_id = images[0].get("unsplash_id")

    post_url = publish_to_wordpress(
        title=f"💰 Follow the Money: {seo_title}",
        html_content=content,
        category_id=category_id,
        featured_image_id=featured_id,
        meta_description=meta,
        focus_keyword=focus_kw,
        unsplash_id=unsplash_id,
    )
    if post_url:
        from ..db import mark_raw_story_processed
        mark_raw_story_processed(story["url"])
        log.info(f"  ✅ Follow the Money LIVE → {post_url}")
    else:
        log.error("  ✗ Publish failed")
