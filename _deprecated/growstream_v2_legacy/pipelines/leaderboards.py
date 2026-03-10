"""
GrowStream — Leaderboards & Rankings Pipeline.

Monthly pipeline (run on the 1st) that aggregates the last 30 days of stories
and publishes a ranked Top 10 list — most active banks, fintechs, or funding rounds.

Run: python leaderboards.py
"""

import json
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

_WP_CATEGORY_NAME = "Leaderboards & Rankings"
_WP_CATEGORY_SLUG = "leaderboards"

# Rotate topic based on the current month
_MONTHLY_TOPICS = [
    ("AI Features Launched by Banks",       ["bank", "ai", "launch", "feature", "announced"]),
    ("Fintech Funding Rounds",              ["raised", "funding", "series", "million", "billion", "seed"]),
    ("AI Finance Tools by Buzz",            ["tool", "platform", "software", "ai", "launch", "product"]),
    ("Regulatory Moves",                    ["regulation", "rbi", "sec", "fca", "ecb", "sebi", "policy"]),
    ("AI in Banking Innovations",           ["bank", "ai", "innovation", "digital", "technology"]),
    ("Fintech Startup Activity",            ["startup", "fintech", "neobank", "payment", "wallet"]),
    ("Investment Deals in AI Finance",      ["invest", "fund", "acquire", "merger", "deal"]),
    ("Compliance & RegTech Moves",          ["compliance", "regtech", "regulation", "audit", "kyc"]),
    ("AI Tools for CFOs",                   ["cfo", "finance", "ai", "tool", "automation", "erp"]),
    ("Global Fintech M&A Activity",         ["merger", "acquisition", "acquired", "deal", "buyout"]),
    ("Banking Transformation Stories",      ["digital bank", "transformation", "modernise", "core banking"]),
    ("AI Fraud & Security Developments",    ["fraud", "security", "scam", "cyber", "risk", "ai"]),
]

_PERSONA = """\
You are Jordan Blake, Senior Financial Journalist at GrowStream Media.
You write ranked lists that finance professionals bookmark and share every month.
Your commentary is sharp, opinionated, and specific — each entry gets a real assessment, not filler.
"""


@with_retry(max_retries=3, delay=5)
def _build_rankings(stories: list[dict], topic: str, keywords: list[str]) -> str | None:
    stories_json = json.dumps(
        [{"headline": s["headline"], "source": s["source"], "summary": s["summary"][:200]}
         for s in stories[:30]],
        indent=2,
    )
    prompt = f"""{_PERSONA}

Based on the following news stories from the past 30 days, create a "Top 10 {topic}" ranking.

Stories:
{stories_json}

Instructions:
- Identify and rank the top 10 entities (companies, banks, regulators, tools) that featured most
  prominently in these stories related to: {topic}
- If fewer than 10 distinct entities appear, rank as many as are clearly present
- Write a 700-900 word article using this structure:

<div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 24px; border-radius: 12px; margin-bottom: 28px;">
  <h2 style="margin-top: 0; color: white;">📊 Top 10 {topic}</h2>
  <p style="margin-bottom: 0; color: #e2d9f3;">[Month Year] Edition · GrowStream Media</p>
</div>

<p>[One opinionated paragraph introducing this month's theme and ranking methodology]</p>

For each ranked entry, use this format:
<div style="border: 1px solid #dee2e6; border-radius: 8px; padding: 16px; margin-bottom: 16px;">
  <h3 style="margin-top: 0;">#[N] [Entity Name]</h3>
  <p><strong>Why they're on the list:</strong> [1 sentence]</p>
  <p>[2-3 sentences of commentary — specific, opinionated, with data from the stories]</p>
  <span style="background: #e9ecef; padding: 4px 10px; border-radius: 20px; font-size: 0.85em;">[Category tag]</span>
</div>

After the list:
<h2>The Month in One Sentence</h2>
[One punchy editorial summary of what this leaderboard reveals about the state of AI finance]

Rules:
- Be specific — name real entities, real deals, real numbers where available
- Do NOT invent rankings or data not supported by the stories
- Return ONLY the HTML body"""

    r = get_client().messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=3000,
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
    log.info("  GrowStream — Leaderboards & Rankings Pipeline")
    log.info(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')} IST")
    log.info("=" * 60)

    run_preflight(abort_on_failure=True)

    # Pick topic for this month
    month_index = (datetime.now().month - 1) % len(_MONTHLY_TOPICS)
    topic_name, topic_keywords = _MONTHLY_TOPICS[month_index]
    log.info(f"  📊 This month's leaderboard: '{topic_name}'")

    # Fetch stories from all feeds
    all_stories = []
    for slug, feeds in CATEGORY_FEEDS.items():
        all_stories += _fetch_from_feeds(feeds, topic_keywords)
    if not all_stories:
        all_stories = _fetch_from_feeds(FALLBACK_FEEDS, topic_keywords)

    # Deduplicate
    seen, unique = set(), []
    for s in all_stories:
        key = s["headline"][:40].lower()
        if key not in seen:
            seen.add(key)
            unique.append(s)

    log.info(f"  ✓ {len(unique)} stories found for ranking")

    if len(unique) < 5:
        log.warning(f"  ⚠ Only {len(unique)} stories — leaderboard may be thin")

    content = _build_rankings(unique, topic_name, topic_keywords)
    if not content:
        log.error("  ✗ Leaderboard generation failed")
        return

    month_str = datetime.now().strftime("%B %Y")
    title = f"Top 10 {topic_name} — {month_str}"
    focus_kw = f"{topic_name.lower()} rankings {month_str.lower()}"
    meta = generate_meta_description(title, content, focus_kw)

    category_id = get_or_create_wp_category(_WP_CATEGORY_NAME, _WP_CATEGORY_SLUG)
    used_slugs = get_recent_featured_image_slugs(days=7)
    images = fetch_unsplash_images([topic_name, "ranking leaderboard chart"], "data chart analytics leaderboard", count=1, used_slugs=used_slugs)

    featured_id = None
    unsplash_id = None
    if images:
        uploaded = upload_image_to_wordpress(images[0], title, focus_keyword=focus_kw)
        if uploaded:
            featured_id = uploaded["id"]
            unsplash_id = images[0].get("unsplash_id")

    post_url = publish_to_wordpress(
        title=title,
        html_content=content,
        category_id=category_id,
        featured_image_id=featured_id,
        meta_description=meta,
        focus_keyword=focus_kw,
        unsplash_id=unsplash_id,
    )
    if post_url:
        log.info(f"  ✅ Leaderboard LIVE → {post_url}")
    else:
        log.error("  ✗ Publish failed")
