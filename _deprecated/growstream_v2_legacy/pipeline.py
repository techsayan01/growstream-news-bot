"""
GrowStream — Main pipeline orchestrator.

Pipeline order:
  1. research_agent  (Alex Rivera — RSS sourcing)
  2. summary_agent   (Dr. Sarah Chen — market ranking)
  3. factcheck_agent (Marcus Webb — credibility gate)
  4. rewrite_article (Jordan Blake — article writing)
  5. editor_agent    (Priya Sharma — SEO & quality gate, optional rewrite)
  6. publish         (WordPress)
"""

from datetime import datetime

from .agents import editor_agent, factcheck_agent, summary_agent
from .config import log
from .feeds import CATEGORIES, research_agent
from .images import fetch_unsplash_images
from .preflight import run_preflight
from .publisher import (
    article_exists,
    build_html,
    get_recent_featured_image_slugs,
    get_wp_category_id,
    publish_to_wordpress,
    upload_image_to_wordpress,
)
from .seo import (
    generate_focus_keyword,
    generate_meta_description,
    generate_seo_title,
    rewrite_article,
)


def run() -> None:
    log.info("=" * 60)
    log.info("  GrowStream Media — Multi-Agent News Bot v2")
    log.info(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')} IST")
    log.info("  Agents: Alex Rivera · Dr. Sarah Chen · Marcus Webb")
    log.info("          Jordan Blake · Priya Sharma")
    log.info("  RSS feeds → Sonnet analysis → Haiku writing → Sonnet editing")
    log.info("  Est. cost: ~$0.15/day | ~$4.50/month")
    log.info("=" * 60)

    # ── Pre-flight: verify all services before spending any tokens ──
    run_preflight(abort_on_failure=True)

    published = 0
    skipped   = 0
    results: list[dict] = []

    # Load recently-used featured image slugs once so all 5 categories avoid repeats
    log.info("  🔍 Loading recently-used featured image slugs from WordPress…")
    used_image_slugs: set[str] = get_recent_featured_image_slugs(days=7)

    for category in CATEGORIES:
        log.info(f"\n{'─' * 50}")
        log.info(f"📂 {category['name'].upper()}")
        log.info(f"{'─' * 50}")

        try:
            # ── Step 1: Research (Alex Rivera) ──────────────────
            stories = research_agent(category)
            if not stories:
                skipped += 1
                continue

            # ── Step 2: Summary / Ranking (Dr. Sarah Chen) ──────
            top_stories = summary_agent(stories, category)
            if not top_stories:
                skipped += 1
                continue

            story_published = False

            # Evaluate each of the top choices in order until one passes
            for rank, best_story in enumerate(top_stories, start=1):
                log.info(f"\n  ========================================")
                log.info(f"  Attempting Top Story #{rank} for {category['name']}")
                log.info(f"  ========================================")

                # ── Step 3: Fact-Check (Marcus Webb) ────────────────
                factcheck = factcheck_agent(best_story, category)
                if not factcheck or not factcheck.get("approved"):
                    log.warning(f"  ⚠ Story #{rank} not approved by Marcus, skipping to next")
                    continue

                story        = factcheck.get("story", best_story)
                angle        = factcheck.get("suggested_angle", "")
                img_keywords = factcheck.get("image_keywords", category["image_style"].split())

                # ── SEO prep ────────────────────────────────────────
                focus_keyword = generate_focus_keyword(story.get("headline", ""), category["name"])
                story["focus_keyword"] = focus_keyword
                log.info(f"  🔑 Focus keyword: {focus_keyword}")

                if article_exists(focus_keyword):
                    log.warning(f"  ⚠ Skipping Topic #{rank} — already published recently")
                    continue

                # ── Images ──────────────────────────────────────────
                images = fetch_unsplash_images(img_keywords, category["image_style"], used_slugs=used_image_slugs)

                # ── Step 4: Write (Jordan Blake) ────────────────────
                content = rewrite_article(story, category, angle)
                if not content:
                    log.warning(f"  ⚠ Story #{rank} writing failed, skipping to next")
                    continue

                # ── SEO metadata ────────────────────────────────────
                seo_title = generate_seo_title(
                    story.get("headline", ""),
                    story.get("market_trend", category["name"]),
                )
                log.info(f"  📰 {seo_title}")

                meta_description = generate_meta_description(seo_title, content, focus_keyword)
                log.info(f"  📋 Meta: {meta_description[:60]}…")

                # ── Step 5: Editorial review loop (Priya Sharma) ────
                MAX_EDITORIAL_RETRIES = 3
                editorial = None
                is_approved = False

                for edit_round in range(1, MAX_EDITORIAL_RETRIES + 2):  # +2: initial + retries
                    editorial = editor_agent(
                        content, story, seo_title, focus_keyword, meta_description, category
                    )

                    if not editorial:
                        log.error("  ✗ Editor agent failed to return a valid result — aborting publication")
                        break

                    if editorial.get("approved"):
                        is_approved = True
                        if edit_round > 1:
                            log.info(f"  ✅ Priya approved on revision {edit_round - 1}")
                        break

                    # Not approved — check if we have retries left
                    if edit_round <= MAX_EDITORIAL_RETRIES:
                        seo_s = editorial.get("seo_score", "?")
                        qua_s = editorial.get("quality_score", "?")
                        log.info(
                            f"  🔄 Revision {edit_round}/{MAX_EDITORIAL_RETRIES} — "
                            f"SEO: {seo_s}/10 | Quality: {qua_s}/10 — Jordan is rewriting…"
                        )
                        notes = editorial.get("editorial_notes", "")
                        issues = editorial.get("issues", [])
                        if issues:
                            notes += "\n\nSpecific Issues to Fix:\n- " + "\n- ".join(issues)

                        revised = rewrite_article(
                            story, category, angle,
                            editor_notes=notes,
                            previous_article=content,
                        )
                        if revised:
                            content = revised
                            meta_description = generate_meta_description(
                                seo_title, content, focus_keyword
                            )
                        else:
                            log.warning("  ⚠ Rewrite returned empty — aborting publication")
                            break

                if not is_approved:
                    seo_s = editorial.get("seo_score", "?") if editorial else "?"
                    qua_s = editorial.get("quality_score", "?") if editorial else "?"
                    log.warning(
                        f"  🚫 Priya's standards not met after {MAX_EDITORIAL_RETRIES} revisions "
                        f"(SEO: {seo_s}/10 | Quality: {qua_s}/10) — skipping to next candidate"
                    )
                    continue

                # ── Publish to WordPress ────────────────────────────
                html = build_html(content, images, story, focus_keyword, meta_description)
                category_id = get_wp_category_id(category["slug"])

                featured_id = None
                unsplash_id = None
                if images:
                    log.info("  ⬆️  Uploading hero image…")
                    uploaded = upload_image_to_wordpress(images[0], seo_title, focus_keyword=focus_keyword)
                    if uploaded:
                        featured_id = uploaded["id"]
                        unsplash_id = images[0].get("unsplash_id")
                        log.info(f"  ✓ Hero image ID: {featured_id}")

                log.info("  🚀 Publishing…")
                post_url = publish_to_wordpress(
                    seo_title, html, category_id, featured_id,
                    meta_description=meta_description,
                    focus_keyword=focus_keyword,
                    author_id=category.get("author_id"),
                    unsplash_id=unsplash_id,
                )

                if post_url:
                    from .db import mark_raw_story_processed
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
                    break  # Break out of top_stories loop since we published one

            if not story_published:
                log.warning(f"  ✗ Exhausted all {len(top_stories)} top stories for {category['name']}")
                skipped += 1

        except Exception as e:
            log.error(f"  ✗ Unexpected error in {category['name']}: {e}", exc_info=True)
            skipped += 1
            continue

    # ── Summary ─────────────────────────────────────────────────
    log.info(f"\n{'=' * 60}")
    log.info(f"  COMPLETED — {published}/5 published | {skipped}/5 skipped")
    log.info(f"{'=' * 60}")
    for r in results:
        log.info(
            f"  [{r['category']}] Relevance:{r['score']}/10 | Viral:{r['virality']}/10 "
            f"| SEO:{r['seo_score']}/10 | Quality:{r['quality_score']}/10 "
            f"| 📸{r['images']} imgs"
        )
        log.info(f"    {r['title'][:55]}…")
        log.info(f"    🔗 {r['url']}")
    log.info("=" * 60)

    if published == 0:
        raise SystemExit("No articles published — check logs for details")
