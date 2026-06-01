"""
Translated for Humans Pipeline — plain-English breakdown of regulatory documents.
Title format: "We Read [Document] So You Don't Have To"
"""

from datetime import datetime

from agents.researcher import fetch_from_feeds
from content.images import fetch_unsplash_images
from content.seo import generate_meta_description, generate_tags
from core.llm import call_llm
from core.retry import with_retry
from core.utils import log
from pipelines.base import Pipeline
from publishing.wordpress.client import WordPressClient
from sites.base import SiteConfig

_WP_CATEGORY_NAME = "Translated for Humans"
_WP_CATEGORY_SLUG = "translated-for-humans"

_REGULATORY_TRIGGERS = [
    "circular", "filing", "framework", "guidance", "directive",
    "minutes", "amendment", "regulation", "policy", "rulebook",
    "consultation paper", "discussion paper", "white paper",
    "rbi", "sec", "fed ", "ecb ", "fca ", "sebi", "eba", "fsb",
]

_PERSONA = """\
You are Jordan Blake, Senior Financial Journalist at GrowStream Media.
You have a gift for translating bureaucratic jargon into plain English.
You use analogies, sarcasm, and dry humour. You write for smart people who hate wasting time.
"""


def _is_regulatory(story: dict) -> bool:
    text = (story["headline"] + " " + story["summary"]).lower()
    return any(kw in text for kw in _REGULATORY_TRIGGERS)


@with_retry(max_retries=3, delay=5)
def _write_translation(story: dict) -> str | None:
    prompt = f"""{_PERSONA}

Your task: Write a witty, plain-English breakdown of this regulatory story for finance professionals.

Format it EXACTLY like this (use these H2 headings):

<h2>📄 What They Said</h2>
2 sentences summarising the official position in dry regulatory-speak (mock the tone slightly).

<h2>🤔 What It Actually Means</h2>
2-3 paragraphs of plain English. Use a relatable analogy. Make it scannable.

<h2>✅ What You Should Actually Do About It</h2>
3-5 bullet points. Practical, actionable.

<h2>🧐 The Part They Buried</h2>
1 paragraph — the thing buried in paragraph 47 that actually matters.

<h2>⚡ The Bottom Line</h2>
One punchy sentence. No jargon.

Rules:
- Total length: 500-700 words
- Use wit but stay factual — do NOT invent details
- Return ONLY the HTML body

Story:
Headline: {story['headline']}
Source: {story['source']}
Summary: {story['summary'][:800]}"""

    content = call_llm("gemini-2.5-pro", 2000, [{"role": "user", "content": prompt}]).strip()
    if content.startswith("```"):
        content = content.split("```", 2)[1]
        if content.startswith("html"):
            content = content[4:]
        content = content.rsplit("```", 1)[0].strip()
    return content


class TranslatedPipeline(Pipeline):
    def __init__(self, site: SiteConfig):
        super().__init__(site)
        self.wp = WordPressClient(site.wp_url, site.wp_username, site.wp_password, site.wp_api_key)

    def run(self) -> None:
        log.info("=" * 60)
        log.info(f"  {self.site.display_name} — Translated for Humans Pipeline")
        log.info(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        log.info("=" * 60)

        feeds   = self.site.category_feeds.get("regulatory-updates", [])
        stories = fetch_from_feeds(feeds, _REGULATORY_TRIGGERS)
        regulatory_stories = [s for s in stories if _is_regulatory(s)]

        if not regulatory_stories:
            log.warning("  ⚠ No qualifying regulatory stories found today — skipping")
            return

        story = regulatory_stories[0]
        log.info(f"  📋 Processing: '{story['headline'][:60]}...'")

        content = _write_translation(story)
        if not content:
            log.error("  ✗ Translation failed")
            return

        short_headline = story["headline"][:45]
        title          = f"We Read It So You Don't Have To: {short_headline}"

        intro = f"""
<div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 16px; border-radius: 6px; margin-bottom: 24px;">
  <strong>⏱ {self.site.display_name} Translation Service</strong><br>
  We waded through the jargon so you can skip straight to the part that matters.
  Original source: <a href="{story.get('url','#')}" target="_blank" rel="noopener">{story.get('source','Unknown')}</a>
</div>
"""
        full_html = intro + content

        category_id = self.wp.get_or_create_category(_WP_CATEGORY_NAME, _WP_CATEGORY_SLUG)
        used_slugs  = self.wp.get_recent_featured_image_slugs(days=7)
        images      = fetch_unsplash_images(["regulation law document policy"], "regulation law finance", count=1, used_slugs=used_slugs)

        featured_id = None
        unsplash_id = None
        if images:
            uploaded = self.wp.upload_image(images[0], title)
            if uploaded:
                featured_id = uploaded["id"]
                unsplash_id = images[0].get("unsplash_id")

        focus_keyword = "regulatory translation finance"
        meta          = generate_meta_description(title, content, focus_keyword)
        tag_names     = generate_tags(story["headline"], focus_keyword, "regulatory")
        tag_ids       = self.wp.get_or_create_tags(tag_names)

        post_url = self.wp.publish(
            title=title,
            html_content=full_html,
            category_id=category_id,
            featured_image_id=featured_id,
            meta_description=meta,
            focus_keyword=focus_keyword,
            tags=tag_ids,
            author_id=4,   # Priya Mehta — regulatory/explainer content
            unsplash_id=unsplash_id,
        )
        if post_url:
            from core.db import mark_raw_story_processed
            mark_raw_story_processed(story["url"])
            log.info(f"  ✅ Translated for Humans LIVE → {post_url}")
        else:
            log.error("  ✗ Publish failed")


def run(site: SiteConfig) -> None:
    TranslatedPipeline(site).run()
