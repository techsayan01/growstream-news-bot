"""
Leaderboards & Rankings Pipeline — monthly Top 10 list (runs on the 1st).
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

_WP_CATEGORY_NAME = "Leaderboards & Rankings"
_WP_CATEGORY_SLUG = "leaderboards"

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
- Identify and rank the top 10 entities (companies, banks, regulators, tools) most prominent in these stories.
- If fewer than 10 distinct entities appear, rank as many as are clearly present.
- Write a 700-900 word article using this structure:

<div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 24px; border-radius: 12px; margin-bottom: 28px;">
  <h2 style="margin-top: 0; color: white;">📊 Top 10 {topic}</h2>
  <p style="margin-bottom: 0; color: #e2d9f3;">[Month Year] Edition · GrowStream Media</p>
</div>

<p>[One opinionated paragraph introducing this month's theme]</p>

For each ranked entry:
<div style="border: 1px solid #dee2e6; border-radius: 8px; padding: 16px; margin-bottom: 16px;">
  <h3 style="margin-top: 0;">#[N] [Entity Name]</h3>
  <p><strong>Why they're on the list:</strong> [1 sentence]</p>
  <p>[2-3 sentences of commentary — specific, opinionated, with data]</p>
  <span style="background: #e9ecef; padding: 4px 10px; border-radius: 20px; font-size: 0.85em;">[Category tag]</span>
</div>

After the list:
<h2>The Month in One Sentence</h2>
[One punchy editorial summary]

Rules:
- Be specific — name real entities, real deals, real numbers where available
- Do NOT invent rankings or data not supported by the stories
- Return ONLY the HTML body"""

    content = call_llm("gemini-2.5-pro", 3000, [{"role": "user", "content": prompt}]).strip()
    if content.startswith("```"):
        content = content.split("```", 2)[1]
        if content.startswith("html"):
            content = content[4:]
        content = content.rsplit("```", 1)[0].strip()
    return content


class LeaderboardsPipeline(Pipeline):
    def __init__(self, site: SiteConfig):
        super().__init__(site)
        self.wp = WordPressClient(site.wp_url, site.wp_username, site.wp_password, site.wp_api_key)

    def run(self) -> None:
        log.info("=" * 60)
        log.info(f"  {self.site.display_name} — Leaderboards & Rankings Pipeline")
        log.info(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        log.info("=" * 60)

        month_index              = (datetime.now().month - 1) % len(_MONTHLY_TOPICS)
        topic_name, topic_keywords = _MONTHLY_TOPICS[month_index]
        log.info(f"  📊 This month's leaderboard: '{topic_name}'")

        all_stories: list[dict] = []
        for feeds in self.site.category_feeds.values():
            all_stories += fetch_from_feeds(feeds, topic_keywords)
        if not all_stories:
            all_stories = fetch_from_feeds(self.site.fallback_feeds, topic_keywords)

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

        month_str   = datetime.now().strftime("%B %Y")
        title       = f"Top 10 {topic_name} — {month_str}"
        focus_kw    = f"{topic_name.lower()} rankings {month_str.lower()}"
        meta        = generate_meta_description(title, content, focus_kw)
        category_id = self.wp.get_or_create_category(_WP_CATEGORY_NAME, _WP_CATEGORY_SLUG)
        used_slugs  = self.wp.get_recent_featured_image_slugs(days=7)
        images      = fetch_unsplash_images(
            [topic_name, "ranking leaderboard chart"], "data chart analytics leaderboard",
            count=1, used_slugs=used_slugs,
        )

        featured_id = None
        unsplash_id = None
        if images:
            uploaded = self.wp.upload_image(images[0], title, focus_keyword=focus_kw)
            if uploaded:
                featured_id = uploaded["id"]
                unsplash_id = images[0].get("unsplash_id")

        tag_names = generate_tags(title, focus_kw, topic_name)
        tag_ids   = self.wp.get_or_create_tags(tag_names)

        post_url = self.wp.publish(
            title=title,
            html_content=content,
            category_id=category_id,
            featured_image_id=featured_id,
            meta_description=meta,
            focus_keyword=focus_kw,
            tags=tag_ids,
            author_id=3,   # Alex Chen — data/rankings content
            unsplash_id=unsplash_id,
        )
        if post_url:
            log.info(f"  ✅ Leaderboard LIVE → {post_url}")
        else:
            log.error("  ✗ Publish failed")


def run(site: SiteConfig) -> None:
    LeaderboardsPipeline(site).run()
