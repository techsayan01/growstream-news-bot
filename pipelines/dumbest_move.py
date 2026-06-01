"""
Dumbest Move of the Week Pipeline — weekly humorous accountability piece (runs Sundays).
"""

import json
from datetime import datetime

from agents.researcher import fetch_from_feeds
from content.images import fetch_unsplash_images
from content.seo import generate_meta_description, generate_tags
from core.llm import call_llm
from core.retry import with_retry
from core.utils import log, safe_json_parse
from pipelines.base import Pipeline
from publishing.wordpress.client import WordPressClient
from sites.base import SiteConfig

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

    result = safe_json_parse(call_llm("gemini-2.5-flash", 300, [{"role": "user", "content": prompt}]))
    if result and "index" in result:
        idx = int(result["index"])
        if 0 <= idx < len(stories):
            story = stories[idx]
            story["_dm_decision_maker"] = result.get("decision_maker", "")
            story["_dm_what"]           = result.get("what_they_did", "")
            story["_dm_why"]            = result.get("why_questionable", "")
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
2 paragraphs. Facts first, wit second.

<h2>What They Were Probably Thinking</h2>
1 paragraph. Be charitable — explain their likely rationale.

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

    content = call_llm("gemini-2.5-pro", 1500, [{"role": "user", "content": prompt}]).strip()
    if content.startswith("```"):
        content = content.split("```", 2)[1]
        if content.startswith("html"):
            content = content[4:]
        content = content.rsplit("```", 1)[0].strip()
    return content


class DumbestMovePipeline(Pipeline):
    def __init__(self, site: SiteConfig):
        super().__init__(site)
        self.wp = WordPressClient(site.wp_url, site.wp_username, site.wp_password, site.wp_api_key)

    def run(self) -> None:
        log.info("=" * 60)
        log.info(f"  {self.site.display_name} — Dumbest Move of the Week Pipeline")
        log.info(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        log.info("=" * 60)

        all_stories: list[dict] = []
        for feeds in self.site.category_feeds.values():
            all_stories += fetch_from_feeds(feeds, _ALL_KEYWORDS)
        if not all_stories:
            all_stories = fetch_from_feeds(self.site.fallback_feeds, _ALL_KEYWORDS)

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

        content = _write_dumbest_move(story)
        if not content:
            log.error("  ✗ Content generation failed")
            return

        week_str    = datetime.now().strftime("Week of %B %d, %Y")
        title       = f"😬 Dumbest Move of the Week — {week_str}"
        meta        = generate_meta_description(title, content, "ai finance accountability")
        category_id = self.wp.get_or_create_category(_WP_CATEGORY_NAME, _WP_CATEGORY_SLUG)
        used_slugs  = self.wp.get_recent_featured_image_slugs(days=7)
        images      = fetch_unsplash_images(["business mistake failure corporate"], "corporate business decision", count=1, used_slugs=used_slugs)

        featured_id = None
        unsplash_id = None
        if images:
            uploaded = self.wp.upload_image(images[0], title)
            if uploaded:
                featured_id = uploaded["id"]
                unsplash_id = images[0].get("unsplash_id")

        tag_names = generate_tags(
            story["headline"], "ai finance accountability", "fintech",
            named_entities=[story.get("_dm_decision_maker", "")]
        )
        tag_ids = self.wp.get_or_create_tags(tag_names)

        post_url = self.wp.publish(
            title=title,
            html_content=content,
            category_id=category_id,
            featured_image_id=featured_id,
            meta_description=meta,
            focus_keyword="ai finance accountability",
            tags=tag_ids,
            author_id=4,   # Priya Mehta — accountability/opinion content
            unsplash_id=unsplash_id,
        )
        if post_url:
            from core.db import mark_raw_story_processed
            mark_raw_story_processed(story["url"])
            log.info(f"  ✅ Dumbest Move LIVE → {post_url}")
        else:
            log.error("  ✗ Publish failed")


def run(site: SiteConfig) -> None:
    DumbestMovePipeline(site).run()
