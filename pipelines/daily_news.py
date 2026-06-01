"""
Daily News Pipeline — 5-category multi-agent publishing run.

Orchestrates all 5 agents (research → rank → fact-check → write → edit → publish)
for each content category defined in the site config. Categories run in parallel
(ThreadPoolExecutor, max 3 concurrent) to cut total wall-clock time by ~3–4×.
"""

import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import json as _json

from agents.classifier import classify_story
from agents.editor import review_article
from agents.factchecker import factcheck_story
from agents.ranker import rank_stories
from agents.researcher import research_agent
from agents.writer import write_article
from content.images import fetch_unsplash_images
from content.seo import generate_focus_keyword, generate_meta_description, generate_seo_title, generate_tags
from core.db import get_recent_articles_for_linking, mark_raw_story_processed
from core.llm import call_llm
from core.utils import log, safe_json_parse


def _pick_related_articles(headline: str, focus_keyword: str, category: str) -> list[dict]:
    """Use Gemini Flash to pick the 3 most relevant published articles for internal linking."""
    candidates = get_recent_articles_for_linking(days=60)
    if not candidates:
        return []

    candidate_list = _json.dumps(
        [{"index": i, "title": a["title"], "category": a.get("category", ""),
          "keyword": a.get("focus_keyword", "")}
         for i, a in enumerate(candidates)],
        indent=2,
    )

    prompt = f"""You are an SEO editor. Pick the 3 most topically relevant articles for internal linking.

Current article:
- Headline: {headline}
- Focus keyword: {focus_keyword}
- Category: {category}

Candidate articles:
{candidate_list}

Return ONLY a JSON array of 3 indexes (most relevant first): [2, 7, 1]
Choose articles that cover related but distinct topics — avoid picking articles that are about the exact same story."""

    try:
        raw    = call_llm("gemini-2.5-flash", 60, [{"role": "user", "content": prompt}])
        result = safe_json_parse(raw)
        if isinstance(result, list):
            return [candidates[i] for i in result[:3] if isinstance(i, int) and i < len(candidates)]
    except Exception:
        pass

    # Fallback: return 3 most recent from same category
    same_cat = [a for a in candidates if a.get("category") == category]
    return (same_cat or candidates)[:3]
from pipelines.base import Pipeline
from publishing.wordpress.client import WordPressClient
from publishing.wordpress.html import build_html
from sites.base import SiteConfig

# Sentence-ending punctuation. If the stripped article doesn't end with one of
# these, it was almost certainly cut off mid-sentence by the LLM.
_SENTENCE_END = re.compile(r'[.!?">)\]]$')


def _is_truncated(html: str) -> bool:
    """Return True if the article appears to be cut off mid-sentence."""
    text = re.sub(r"<[^>]+>", "", html).strip()
    return not bool(_SENTENCE_END.search(text))


class DailyNewsPipeline(Pipeline):
    """Runs the full 5-agent daily news pipeline for all site categories."""

    def __init__(self, site: SiteConfig):
        super().__init__(site)
        self.wp = WordPressClient(site.wp_url, site.wp_username, site.wp_password, site.wp_api_key)

    def _process_category(
        self,
        category: dict,
        used_image_slugs: set[str],
    ) -> dict | None:
        """Run the full agent pipeline for one category.

        Returns a result dict on success, or None if nothing was published.
        """
        cat_name = category["name"]
        log.info(f"\n{'─' * 50}")
        log.info(f"📂 {cat_name.upper()}")
        log.info(f"{'─' * 50}")

        # Step 1: Research
        stories = research_agent(category, self.site.category_feeds, self.site.fallback_feeds)
        if not stories:
            return None

        # Step 2: Rank
        top_stories = rank_stories(stories, category)
        if not top_stories:
            return None

        for rank, best_story in enumerate(top_stories, start=1):
            if not isinstance(best_story, dict):
                log.warning(f"  ⚠ Story #{rank} is not a dict ({type(best_story).__name__}) — skipping")
                continue

            log.info(f"\n  ═══ Attempting Top Story #{rank} for {cat_name} ═══")

            # Step 3: Dedup check (Layers 3 already ran in researcher;
            # Layer 4 WordPress title search runs here as final safeguard)
            focus_keyword = generate_focus_keyword(best_story.get("headline", ""), cat_name)
            log.info(f"  🔑 Focus keyword: {focus_keyword}")
            if self.wp.article_exists(best_story.get("headline", "")):
                log.warning(f"  ⚠ Skipping #{rank} — Layer 4 WP title match")
                continue

            # Step 4: Fact-check
            factcheck = factcheck_story(best_story, category)
            if not factcheck or not factcheck.get("approved"):
                log.warning(f"  ⚠ Story #{rank} rejected by Marcus — skipping")
                continue

            story        = factcheck.get("story", best_story)
            angle        = factcheck.get("suggested_angle", "")
            img_keywords = factcheck.get("image_keywords", category["image_style"].split())
            story["focus_keyword"] = focus_keyword

            # Step 4b: Classify article type
            article_type = classify_story(story)

            # Images
            images = fetch_unsplash_images(img_keywords, category["image_style"], used_slugs=used_image_slugs)

            # Step 5: Write
            content = write_article(story, category, angle, article_type=article_type)
            if not content:
                log.warning(f"  ⚠ Story #{rank} writing failed — skipping")
                continue

            # SEO metadata
            seo_title = generate_seo_title(
                story.get("headline", ""),
                story.get("market_trend", cat_name),
            )
            log.info(f"  📰 {seo_title}")

            meta_description = generate_meta_description(seo_title, content, focus_keyword)
            log.info(f"  📋 Meta: {meta_description[:60]}…")

            # Step 6: Editorial review loop
            MAX_REVISIONS = 3
            editorial     = None
            is_approved   = False

            for edit_round in range(1, MAX_REVISIONS + 2):
                # Fast pre-check: if article is obviously truncated, skip the
                # editor call and go straight to revision with a fixed note.
                if _is_truncated(content):
                    log.warning(f"  ⚠ Article appears truncated — skipping editor, requesting rewrite")
                    if edit_round <= MAX_REVISIONS:
                        revised = write_article(
                            story, category, angle,
                            editor_notes="The article was cut off mid-sentence. Rewrite it in full, ensuring every section is complete and the article ends with a proper conclusion and FAQ.",
                            previous_article=content,
                            article_type=article_type,
                        )
                        if revised:
                            content = revised
                            meta_description = generate_meta_description(seo_title, content, focus_keyword)
                            continue
                    break

                editorial = review_article(
                    content, story, seo_title, focus_keyword, meta_description, category,
                    article_type=article_type,
                )
                if not editorial:
                    log.error("  ✗ Editor failed — aborting publication")
                    break

                if editorial.get("approved"):
                    is_approved = True
                    if edit_round > 1:
                        log.info(f"  ✅ Priya approved on revision {edit_round - 1}")
                    break

                seo_s = editorial.get("seo_score", 0)
                qua_s = editorial.get("quality_score", 0)
                if seo_s >= 8 and qua_s >= 8:
                    log.info(f"  ✅ Scores high (SEO:{seo_s} Quality:{qua_s}) — overriding approval")
                    is_approved = True
                    break

                if edit_round <= MAX_REVISIONS:
                    log.info(
                        f"  🔄 Revision {edit_round}/{MAX_REVISIONS} — "
                        f"SEO: {seo_s}/10 | Quality: {qua_s}/10 — Jordan is rewriting…"
                    )
                    notes = editorial.get("editorial_notes", "")
                    issues = editorial.get("issues", [])
                    if issues:
                        notes += "\n\nSpecific Issues:\n- " + "\n- ".join(issues)
                    revised = write_article(story, category, angle, editor_notes=notes, previous_article=content, article_type=article_type)
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

            # Generate tags
            tag_names = generate_tags(
                story.get("headline", ""),
                focus_keyword,
                story.get("market_trend", cat_name),
                named_entities=story.get("named_entities"),
            )
            tag_ids = self.wp.get_or_create_tags(tag_names)
            log.info(f"  🏷  Tags: {', '.join(tag_names[:5])}")

            # Select related articles for internal linking
            related = _pick_related_articles(
                story.get("headline", ""), focus_keyword, cat_name
            )

            # Build HTML & publish
            html = build_html(
                content, images, story, focus_keyword, meta_description,
                publisher_name=self.site.display_name,
                publisher_url=self.site.site_url,
                related_articles=related,
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
                tags=tag_ids,
                author_id=category.get("author_id"),
                unsplash_id=unsplash_id,
                source_url=story.get("url"),
                category=cat_name,
                article_type=article_type,
                seo_score=editorial.get("seo_score") if editorial else None,
                quality_score=editorial.get("quality_score") if editorial else None,
            )

            if post_url:
                mark_raw_story_processed(story["url"])
                seo_score     = editorial.get("seo_score", "?") if editorial else "?"
                quality_score = editorial.get("quality_score", "?") if editorial else "?"
                log.info(f"  ✅ LIVE → {post_url}")
                log.info(f"  📊 SEO: {seo_score}/10 | Quality: {quality_score}/10")
                return {
                    "category":      cat_name,
                    "title":         seo_title,
                    "url":           post_url,
                    "trend":         story.get("market_trend", ""),
                    "score":         story.get("market_relevance_score", "?"),
                    "seo_score":     seo_score,
                    "quality_score": quality_score,
                    "images":        len(images),
                }

        log.warning(f"  ✗ Exhausted all {len(top_stories)} candidates for {cat_name}")
        return None

    def run(self) -> None:
        log.info("=" * 60)
        log.info(f"  {self.site.display_name} — Multi-Agent News Bot v3")
        log.info(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        log.info("  Agents: Alex Rivera · Dr. Sarah Chen · Marcus Webb")
        log.info("          Jordan Blake · Priya Sharma")
        log.info("=" * 60)

        log.info("  🔍 Loading recently-used featured image slugs from WordPress…")
        used_image_slugs: set[str] = self.wp.get_recent_featured_image_slugs(days=7)

        results: list[dict] = []
        lock = threading.Lock()

        # Run all categories in parallel (max 3 at a time to respect API rate limits)
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(self._process_category, cat, used_image_slugs): cat
                for cat in self.site.categories
            }
            for future in as_completed(futures):
                cat = futures[future]
                try:
                    result = future.result()
                    if result:
                        with lock:
                            results.append(result)
                except Exception as e:
                    log.error(f"  ✗ Unexpected error in {cat['name']}: {e}", exc_info=True)

        published = len(results)
        skipped   = len(self.site.categories) - published

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
