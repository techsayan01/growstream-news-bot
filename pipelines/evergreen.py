"""
Evergreen Pipeline — 1500-word explainer articles on high-search-volume topics.

Unlike the daily news pipeline which chases breaking stories, this pipeline
writes timeless educational content that ranks for months. Two articles per
week compounds into a library of permanent organic traffic.

Flow:
  1. Fetch next pending topic from MongoDB queue
  2. Pull recent RSS articles on the topic for current examples/stats
  3. Write 1500-word explainer using the Explainer template
  4. Editorial review (Priya Sharma)
  5. SEO metadata + tags
  6. Publish → mark topic done
"""

import json
import re
from datetime import datetime

from agents.editor import review_article
from agents.researcher import fetch_from_feeds
from agents.writer import write_article
from content.images import fetch_unsplash_images
from content.seo import generate_focus_keyword, generate_meta_description, generate_seo_title, generate_tags
from core.db import (
    get_evergreen_queue_status,
    get_next_evergreen_topic,
    mark_evergreen_topic_published,
)
from core.utils import log
from pipelines.base import Pipeline
from publishing.wordpress.client import WordPressClient
from publishing.wordpress.html import build_html
from sites.base import SiteConfig

_SENTENCE_END = re.compile(r'[.!?">)\]]$')


def _is_truncated(html: str) -> bool:
    text = re.sub(r"<[^>]+>", "", html).strip()
    return not bool(_SENTENCE_END.search(text))


class EvergreenPipeline(Pipeline):
    """Publishes one evergreen explainer article per run."""

    def __init__(self, site: SiteConfig):
        super().__init__(site)
        self.wp = WordPressClient(
            site.wp_url, site.wp_username, site.wp_password, site.wp_api_key
        )

    def run(self) -> None:
        log.info("=" * 60)
        log.info(f"  {self.site.display_name} — Evergreen Pipeline")
        log.info(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        log.info("=" * 60)

        # Step 1: Get next topic
        status = get_evergreen_queue_status()
        log.info(f"  📚 Queue: {status['pending']} pending | {status['published']} published")

        topic = get_next_evergreen_topic()
        if not topic:
            log.warning("  ⚠ No pending topics in queue — add more via data/evergreen_topics.py")
            return

        log.info(f"  📖 Topic: {topic['topic']}")
        keyword  = topic["keyword"]
        category = topic["category"]

        # Step 2: Fetch recent RSS context for current examples and stats
        context_feeds = (
            self.site.category_feeds.get("fintech-news", []) +
            self.site.category_feeds.get("ai-in-banking", [])
        )
        context_stories = fetch_from_feeds(context_feeds, keyword.lower().split())
        context_text = ""
        if context_stories:
            snippets = [
                f"- {s['headline']}: {s['summary'][:200]}"
                for s in context_stories[:5]
            ]
            context_text = "\n".join(snippets)
            log.info(f"  ✓ {len(context_stories)} context articles found for examples")
        else:
            log.info("  ℹ  No recent RSS context — writing from knowledge base")

        # Build story dict for the writer
        story = {
            "headline":   topic["topic"],
            "market_trend": "Fintech Education",
            "summary": (
                f"Educational explainer on {topic['topic']}. "
                f"Target audience: CFOs, finance professionals, institutional investors. "
                f"Recent context:\n{context_text}" if context_text
                else f"Educational explainer on {topic['topic']}. "
                     f"Target audience: CFOs, finance professionals, institutional investors."
            ),
            "key_facts":      [],
            "key_figures":    [],
            "named_entities": [],
            "direct_quotes":  [],
            "focus_keyword":  keyword,
            "url":            "",
            "source":         "GrowStream Media",
        }

        # Step 3: Write
        log.info("  ✍️  Writing explainer…")
        content = write_article(
            story,
            {"name": category, "slug": category.lower().replace(" ", "-")},
            angle=f"Practical guide for finance professionals on {topic['topic']}",
            article_type="explainer",
        )
        if not content:
            log.error("  ✗ Writing failed")
            return

        # Step 4: Editorial review + revision loop
        # Use the pre-defined keyword directly — more accurate than LLM extraction
        focus_keyword    = topic["keyword"]
        seo_title        = topic["topic"]   # explainers use the exact topic as title
        meta_description = generate_meta_description(seo_title, content, focus_keyword)

        MAX_REVISIONS = 2
        is_approved   = False
        editorial     = None

        for edit_round in range(1, MAX_REVISIONS + 2):
            if _is_truncated(content):
                if edit_round <= MAX_REVISIONS:
                    log.warning("  ⚠ Article truncated — requesting rewrite")
                    content = write_article(
                        story,
                        {"name": category, "slug": category.lower().replace(" ", "-")},
                        angle=f"Practical guide for finance professionals on {topic['topic']}",
                        editor_notes="Article was truncated. Rewrite in full ensuring all sections are complete.",
                        previous_article=content,
                        article_type="explainer",
                    ) or content
                    continue
                break

            editorial = review_article(
                content, story, seo_title, focus_keyword, meta_description,
                {"name": category},
                article_type="explainer",
            )
            if not editorial:
                break

            if editorial.get("approved"):
                is_approved = True
                break

            seo_s = editorial.get("seo_score", 0)
            qua_s = editorial.get("quality_score", 0)

            if seo_s >= 8 and qua_s >= 8:
                is_approved = True
                break

            if edit_round <= MAX_REVISIONS:
                notes  = editorial.get("editorial_notes", "")
                issues = editorial.get("issues", [])
                if issues:
                    notes += "\n\nIssues:\n- " + "\n- ".join(issues)
                log.info(f"  🔄 Revision {edit_round}/{MAX_REVISIONS} — SEO:{seo_s} Quality:{qua_s}")
                revised = write_article(
                    story,
                    {"name": category, "slug": category.lower().replace(" ", "-")},
                    angle=f"Practical guide for finance professionals on {topic['topic']}",
                    editor_notes=notes,
                    previous_article=content,
                    article_type="explainer",
                )
                if revised:
                    content = revised
                    meta_description = generate_meta_description(seo_title, content, focus_keyword)

        if not is_approved:
            seo_s = editorial.get("seo_score", "?") if editorial else "?"
            qua_s = editorial.get("quality_score", "?") if editorial else "?"
            log.warning(f"  ⚠ Did not pass review (SEO:{seo_s} Quality:{qua_s}) — publishing anyway")

        # Step 5: Images
        img_query = [keyword, "finance education technology"]
        images    = fetch_unsplash_images(
            img_query, f"{keyword} finance education",
            count=3,
            used_slugs=self.wp.get_recent_featured_image_slugs(days=14),
        )

        # Step 6: Tags + HTML
        tag_names = generate_tags(topic["topic"], focus_keyword, category)
        tag_ids   = self.wp.get_or_create_tags(tag_names)
        log.info(f"  🏷  Tags: {', '.join(tag_names[:5])}")

        html = build_html(
            content, images, story, focus_keyword, meta_description,
            publisher_name=self.site.display_name,
            publisher_url=self.site.site_url,
        )

        # Step 7: Publish
        wp_category_id = self.wp.get_or_create_category(
            category,
            category.lower().replace(" ", "-").replace("&", "and"),
        )

        featured_id = unsplash_id = None
        if images:
            uploaded = self.wp.upload_image(images[0], seo_title, focus_keyword=focus_keyword)
            if uploaded:
                featured_id = uploaded["id"]
                unsplash_id = images[0].get("unsplash_id")

        log.info("  🚀 Publishing…")
        post_url = self.wp.publish(
            title=seo_title,
            html_content=html,
            category_id=wp_category_id,
            featured_image_id=featured_id,
            meta_description=meta_description,
            focus_keyword=focus_keyword,
            tags=tag_ids,
            author_id=3,        # Alex Chen — educational content
            unsplash_id=unsplash_id,
            category=category,
            article_type="explainer",
        )

        if post_url:
            mark_evergreen_topic_published(topic["_id"], post_url)
            seo_score     = editorial.get("seo_score", "?") if editorial else "?"
            quality_score = editorial.get("quality_score", "?") if editorial else "?"
            log.info(f"  ✅ LIVE → {post_url}")
            log.info(f"  📊 SEO:{seo_score}/10 | Quality:{quality_score}/10")
            status = get_evergreen_queue_status()
            log.info(f"  📚 Queue remaining: {status['pending']} topics")
        else:
            log.error("  ✗ Publish failed")


def run(site: SiteConfig) -> None:
    EvergreenPipeline(site).run()
