"""
Follow the Money Pipeline — investigative trace of funding and investment flows.
"""

from datetime import datetime

from agents.researcher import fetch_from_feeds
from content.images import fetch_unsplash_images
from content.seo import generate_focus_keyword, generate_meta_description, generate_seo_title, generate_tags
from core.llm import call_llm
from core.retry import with_retry
from core.utils import log
from pipelines.base import Pipeline
from publishing.wordpress.client import WordPressClient
from sites.base import SiteConfig

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
2 paragraphs — what this funding will be used for. R&D? Headcount? Acquisition war chest?

<h2>Who Benefits (and Who Doesn't)</h2>
Bullet list — name 3-4 specific entities (companies, sectors, regulators) and one sentence on each.

<h2>What It Signals About the Market</h2>
2 paragraphs — investigative insight. What does this deal reveal about where smart money is moving?

<h2>The Global Ripple Effect</h2>
3 short paragraphs (Asia, Europe, US) — how does this money movement affect each region?

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

    content = call_llm("gemini-2.5-pro", 2500, [{"role": "user", "content": prompt}]).strip()
    if content.startswith("```"):
        content = content.split("```", 2)[1]
        if content.startswith("html"):
            content = content[4:]
        content = content.rsplit("```", 1)[0].strip()
    return content


class FollowTheMoneyPipeline(Pipeline):
    def __init__(self, site: SiteConfig):
        super().__init__(site)
        self.wp = WordPressClient(site.wp_url, site.wp_username, site.wp_password, site.wp_api_key)

    def run(self) -> None:
        log.info("=" * 60)
        log.info(f"  {self.site.display_name} — Follow the Money Pipeline")
        log.info(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        log.info("=" * 60)

        feeds = (
            self.site.category_feeds.get("investment-ai", [])
            + self.site.category_feeds.get("fintech-news", [])
        )
        stories = fetch_from_feeds(feeds, _FUNDING_TRIGGERS)
        if not stories:
            stories = fetch_from_feeds(self.site.fallback_feeds, _FUNDING_TRIGGERS)

        funding_stories = [s for s in stories if _is_funding_story(s)]

        if not funding_stories:
            log.warning("  ⚠ No qualifying funding/M&A stories found today — skipping")
            return

        story    = funding_stories[0]
        log.info(f"  💰 Processing: '{story['headline'][:60]}...'")

        focus_kw  = generate_focus_keyword(story["headline"], "investment ai")
        seo_title = generate_seo_title(story["headline"], "investment funding")
        content   = _write_money_trace(story, focus_kw)

        if not content:
            log.error("  ✗ Content generation failed")
            return

        meta        = generate_meta_description(seo_title, content, focus_kw)
        category_id = self.wp.get_or_create_category(_WP_CATEGORY_NAME, _WP_CATEGORY_SLUG)
        used_slugs  = self.wp.get_recent_featured_image_slugs(days=7)
        images      = fetch_unsplash_images(["money investment finance funding"], "finance investment money", count=1, used_slugs=used_slugs)

        featured_id = None
        unsplash_id = None
        if images:
            uploaded = self.wp.upload_image(images[0], seo_title, focus_keyword=focus_kw)
            if uploaded:
                featured_id = uploaded["id"]
                unsplash_id = images[0].get("unsplash_id")

        tag_names = generate_tags(story["headline"], focus_kw, "investment funding")
        tag_ids   = self.wp.get_or_create_tags(tag_names)

        post_url = self.wp.publish(
            title=f"Follow the Money: {seo_title}",
            html_content=content,
            category_id=category_id,
            featured_image_id=featured_id,
            meta_description=meta,
            focus_keyword=focus_kw,
            tags=tag_ids,
            author_id=3,   # Alex Chen — investment/funding content
            unsplash_id=unsplash_id,
        )
        if post_url:
            from core.db import mark_raw_story_processed
            mark_raw_story_processed(story["url"])
            log.info(f"  ✅ Follow the Money LIVE → {post_url}")
        else:
            log.error("  ✗ Publish failed")


def run(site: SiteConfig) -> None:
    FollowTheMoneyPipeline(site).run()
