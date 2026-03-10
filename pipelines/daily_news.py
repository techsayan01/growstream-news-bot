"""
Daily News Pipeline — 5-category multi-agent publishing run.

Orchestrates all 5 agents (research → rank → fact-check → write → edit → publish)
for each content category defined in the site config.
"""

from datetime import datetime

from agents.editor import review_article
from agents.factchecker import factcheck_story
from agents.ranker import rank_stories
from agents.researcher import research_agent
from agents.writer import write_article
from content.images import fetch_unsplash_images
from content.seo import generate_focus_keyword, generate_meta_description, generate_seo_title
from core.db import mark_raw_story_processed
from core.utils import log
from pipelines.base import Pipeline
from publishing.wordpress.client import WordPressClient
from publishing.wordpress.html import build_html
from sites.base import SiteConfig


class DailyNewsPipeline(Pipeline):
    """Runs the full 5-agent daily news pipeline for all site categories."""

    def __init__(self, site: SiteConfig):
        super().__init__(site)
        self.wp = WordPressClient(site.wp_url, site.wp_username, site.wp_password, site.wp_api_key)

    def run(self) -> None:
        log.info("=" * 60)
        log.info(f"  {self.site.display_name} — Multi-Agent News Bot v3")
        log.info(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        log.info("  Agents: Alex Rivera · Dr. Sarah Chen · Marcus Webb")
        log.info("          Jordan Blake · Priya Sharma")
        log.info("  Est. cost: ~$0.15/day | ~$4.50/month")
        log.info("=" * 60)

        published = 0
        skipped   = 0
        results: list[dict] = []

        log.info("  🔍 Loading recently-used featured image slugs from WordPress…")
        used_image_slugs: set[str] = self.wp.get_recent_featured_image_slugs(days=7)

        for category in self.site.categories:
            log.info(f"\n{'─' * 50}")
            log.info(f"📂 {category['name'].upper()}")
            log.info(f"{'─' * 50}")

            try:
                # Step 1: Research
                stories = research_agent(category, self.site.category_feeds, self.site.fallback_feeds)
                if not stories:
                    skipped += 1
                    continue

                # Step 2: Rank
                top_stories = rank_stories(stories, category)
                if not top_stories:
                    skipped += 1
                    continue

                story_published = False

                for rank, best_story in enumerate(top_stories, start=1):
                    log.info(f"\n  ═══ Attempting Top Story #{rank} for {category['name']} ═══")

                    # Step 3: Fact-check
                    factcheck = factcheck_story(best_story, category)
                    if not factcheck or not factcheck.get("approved"):
                        log.warning(f"  ⚠ Story #{rank} rejected by Marcus — skipping")
                        continue

                    story        = factcheck.get("story", best_story)
                    angle        = factcheck.get("suggested_angle", "")
                    img_keywords = factcheck.get("image_keywords", category["image_style"].split())

                    # SEO prep
                    focus_keyword = generate_focus_keyword(story.get("headline", ""), category["name"])
                    story["focus_keyword"] = focus_keyword
                    log.info(f"  🔑 Focus keyword: {focus_keyword}")

                    if self.wp.article_exists(focus_keyword):
                        log.warning(f"  ⚠ Skipping #{rank} — already published recently")
                        continue

                    # Images
                    images = fetch_unsplash_images(img_keywords, category["image_style"], used_slugs=used_image_slugs)

                    # Step 4: Write
                    content = write_article(story, category, angle)
                    if not content:
                        log.warning(f"  ⚠ Story #{rank} writing failed — skipping")
                        continue

                    # SEO metadata
                    seo_title = generate_seo_title(
                        story.get("headline", ""),
                        story.get("market_trend", category["name"]),
                    )
                    log.info(f"  📰 {seo_title}")

                    meta_description = generate_meta_description(seo_title, content, focus_keyword)
                    log.info(f"  📋 Meta: {meta_description[:60]}…")

                    # Step 5: Editorial review loop
                    MAX_REVISIONS = 3
                    editorial     = None
                    is_approved   = False

                    for edit_round in range(1, MAX_REVISIONS + 2):
                        editorial = review_article(
                            content, story, seo_title, focus_keyword, meta_description, category
                        )
                        if not editorial:
                            log.error("  ✗ Editor failed — aborting publication")
                            break

                        if editorial.get("approved"):
                            is_approved = True
                            if edit_round > 1:
                                log.info(f"  ✅ Priya approved on revision {edit_round - 1}")
                            break

                        if edit_round <= MAX_REVISIONS:
                            seo_s = editorial.get("seo_score", "?")
                            qua_s = editorial.get("quality_score", "?")
                            log.info(
                                f"  🔄 Revision {edit_round}/{MAX_REVISIONS} — "
                                f"SEO: {seo_s}/10 | Quality: {qua_s}/10 — Jordan is rewriting…"
                            )
                            notes = editorial.get("editorial_notes", "")
                            issues = editorial.get("issues", [])
                            if issues:
                                notes += "\n\nSpecific Issues:\n- " + "\n- ".join(issues)
                            revised = write_article(story, category, angle, editor_notes=notes, previous_article=content)
                            if revised:
                                content = revised
                                meta_description = generate_meta_description(seo_title, content, focus_keyword)
                            else:
                                log.warning("  ⚠ Rewrite returned empty — aborting")
                                break

                    if not is_approved:
                        seo_s = editorial.get("seo_score", "?") if editorial else "?"
                        qua_s = editorial.get("quality_score", "?") if editorial else "?"
                        log.warning(
                            f"  🚫 Priya's standards not met after {MAX_REVISIONS} revisions "
                            f"(SEO: {seo_s}/10 | Quality: {qua_s}/10) — skipping"
                        )
                        continue

                    # Build HTML & publish
                    html = build_html(
                        content, images, story, focus_keyword, meta_description,
                        publisher_name=self.site.display_name,
                        publisher_url=self.site.site_url,
                    )
                    category_id = self.wp.get_category_id(category["slug"])

                    featured_id = None
                    unsplash_id = None
                    if images:
                        log.info("  ⬆️  Uploading hero image…")
                        uploaded = self.wp.upload_image(images[0], seo_title, focus_keyword=focus_keyword)
                        if uploaded:
                            featured_id = uploaded["id"]
                            unsplash_id = images[0].get("unsplash_id")
                            log.info(f"  ✓ Hero image ID: {featured_id}")

                    log.info("  🚀 Publishing…")
                    post_url = self.wp.publish(
                        seo_title, html, category_id, featured_id,
                        meta_description=meta_description,
                        focus_keyword=focus_keyword,
                        author_id=category.get("author_id"),
                        unsplash_id=unsplash_id,
                    )

                    if post_url:
                        mark_raw_story_processed(story["url"])
                        seo_score     = editorial.get("seo_score", "?") if editorial else "?"
                        quality_score = editorial.get("quality_score", "?") if editorial else "?"
                        log.info(f"  ✅ LIVE → {post_url}")
                        log.info(f"  📊 SEO: {seo_score}/10 | Quality: {quality_score}/10")
                        published += 1
                        story_published = True
                        results.append({
                            "category":      category["name"],
                            "title":         seo_title,
                            "url":           post_url,
                            "trend":         story.get("market_trend", ""),
                            "score":         story.get("market_relevance_score", "?"),
                            "virality":      story.get("virality_score", "?"),
                            "seo_score":     seo_score,
                            "quality_score": quality_score,
                            "images":        len(images),
                        })
                        break

                if not story_published:
                    log.warning(f"  ✗ Exhausted all {len(top_stories)} candidates for {category['name']}")
                    skipped += 1

            except Exception as e:
                log.error(f"  ✗ Unexpected error in {category['name']}: {e}", exc_info=True)
                skipped += 1
                continue

        # Summary
        log.info(f"\n{'=' * 60}")
        log.info(f"  COMPLETED — {published}/{len(self.site.categories)} published | {skipped} skipped")
        log.info(f"{'=' * 60}")
        for r in results:
            log.info(
                f"  [{r['category']}] Relevance:{r['score']}/10 | "
                f"Viral:{r['virality']}/10 | SEO:{r['seo_score']}/10 | "
                f"Quality:{r['quality_score']}/10 | 📸{r['images']} imgs"
            )
            log.info(f"    {r['title'][:55]}…")
            log.info(f"    🔗 {r['url']}")
        log.info("=" * 60)

        if published == 0:
            raise SystemExit("No articles published — check logs for details")


def run(site: SiteConfig) -> None:
    """Convenience entry-point for the daily news pipeline."""
    DailyNewsPipeline(site).run()
