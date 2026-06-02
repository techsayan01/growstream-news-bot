"""
Hot Takes Pipeline — 80-100 word punchy daily opinion piece.

Scans all feeds, picks the most provocative story, publishes fast.
No editor review. No revision loop. Just the take.
"""

from datetime import datetime

from agents.researcher import fetch_from_feeds
from content.images import fetch_unsplash_images
from content.seo import generate_focus_keyword, generate_tags
from core.llm import call_llm
from core.retry import with_retry
from core.utils import clean_meta_text, log, safe_json_parse, strip_emojis
from pipelines.base import Pipeline
from publishing.wordpress.client import WordPressClient
from sites.base import SiteConfig

_WP_CATEGORY_NAME = "Hot Takes"
_WP_CATEGORY_SLUG = "hot-takes"

_ALL_KEYWORDS = [
    "bank", "fintech", "payment", "ai", "fund", "invest", "regulation",
    "raised", "billion", "million", "crypto", "fraud", "merger", "IPO",
]

_PERSONA = """\
You are Jordan Blake, Senior Financial Journalist at GrowStream Media.
You are sharp, irreverent, and never boring. You have hot opinions and you say them out loud.
"""


@with_retry(max_retries=3, delay=5)
def _pick_story(stories: list[dict]) -> dict | None:
    import json
    prompt = f"""\
You are Dr. Sarah Chen. Pick the SINGLE story most likely to provoke debate or strong emotion:

{json.dumps([{"headline": s["headline"], "summary": s["summary"][:300]} for s in stories[:20]], indent=2)}

Return ONLY JSON:
{{
  "index": 0,
  "reason": "One sentence on why this is the most provocative story."
}}"""
    result = safe_json_parse(call_llm("gemini-2.5-flash", 200, [{"role": "user", "content": prompt}]))
    if result and "index" in result:
        idx = int(result["index"])
        if 0 <= idx < len(stories):
            log.info(f"  ✓ Story picked: {result.get('reason','')}")
            return stories[idx]
    return stories[0] if stories else None


@with_retry(max_retries=3, delay=5)
def _write_hot_take(story: dict) -> str | None:
    prompt = f"""{_PERSONA}

Write an 80-100 word hot take on this story. Rules:
- State your opinion in sentence 1. Make it bold.
- Back it up in 2-3 punchy sentences. Use specific names/numbers where possible.
- End with one quotable one-liner.
- Write in first-person editorial voice.
- No intro, no fluff. Tweet energy but with a brain.
- No emojis anywhere.
- Format as a single <p> paragraph — no headings, no lists.
- Return ONLY the HTML <p> tag.

Story:
Headline: {story['headline']}
Summary: {story['summary'][:500]}"""

    import re as _md
    content = call_llm("gemini-2.5-flash", 300, [{"role": "user", "content": prompt}]).strip()

    # Convert residual markdown formatting to HTML
    content = _md.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', content)
    content = _md.sub(r'\*(.+?)\*',     r'<em>\1</em>',         content)
    content = _md.sub(r'_(.+?)_',       r'<em>\1</em>',         content)

    if not content.startswith("<p"):
        content = f"<p>{content}</p>"
    return content


@with_retry(max_retries=2, delay=5)
def _write_context(story: dict, focus_keyword: str) -> str:
    """Write a 150-200 word 'Why This Matters' context section.

    Adds SEO substance below the punchy hot take to protect against
    Google's thin-content penalty while keeping the format distinct.
    """
    prompt = f"""\
You are Jordan Blake, Senior Financial Journalist at GrowStream Media.

Write a 150-200 word "Why This Matters" context section for finance professionals.
This sits BELOW a punchy hot take opinion paragraph — so this section should be
factual and analytical, not opinionated. Complement, don't repeat.

Rules:
- Use 2 short paragraphs
- Include the focus keyword "{focus_keyword}" once naturally
- Mention concrete market context, trends, or figures from the source
- No emojis. No markdown. Plain HTML only: <p> tags.
- Do NOT repeat what the hot take already said
- Return ONLY the two <p> tags, nothing else

Story:
Headline: {story['headline']}
Summary: {story['summary'][:600]}"""

    import re as _md
    text = call_llm("gemini-2.5-flash", 400, [{"role": "user", "content": prompt}]).strip()
    text = _md.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = _md.sub(r'\*(.+?)\*',     r'<em>\1</em>',         text)
    if not text.startswith("<p"):
        text = f"<p>{text}</p>"
    return text


class HotTakesPipeline(Pipeline):
    def __init__(self, site: SiteConfig):
        super().__init__(site)
        self.wp = WordPressClient(site.wp_url, site.wp_username, site.wp_password, site.wp_api_key)

    def run(self) -> None:
        log.info("=" * 60)
        log.info(f"  {self.site.display_name} — Hot Takes Pipeline")
        log.info(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        log.info("=" * 60)

        # Collect stories from all category feeds
        all_stories: list[dict] = []
        for feeds in self.site.category_feeds.values():
            all_stories += fetch_from_feeds(feeds, _ALL_KEYWORDS)
        if len(all_stories) < 3:
            all_stories += fetch_from_feeds(self.site.fallback_feeds, _ALL_KEYWORDS)

        if not all_stories:
            log.error("  ✗ No stories found for Hot Takes")
            return

        seen, unique = set(), []
        for s in all_stories:
            key = s["headline"][:40].lower()
            if key not in seen:
                seen.add(key)
                unique.append(s)

        log.info(f"  ✓ {len(unique)} unique stories across all feeds")

        story = _pick_story(unique)
        if not story:
            log.error("  ✗ Could not pick a story")
            return

        log.info(f"  📰 '{story['headline'][:60]}...'")

        content = _write_hot_take(story)
        if not content:
            log.error("  ✗ Hot take generation failed")
            return

        # Generate focus keyword early — needed for context block
        focus_keyword = generate_focus_keyword(story["headline"], "Hot Takes")

        today     = datetime.now().strftime("%B %d, %Y")
        pub_date  = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+00:00")
        import re as _re
        # Strip emojis from LLM-generated content
        content = strip_emojis(content)

        # Title: clean, max 60 chars, keep whole words
        raw_title = f"Hot Take: {story['headline']}"
        if len(raw_title) > 60:
            words, buf = raw_title.split(), ""
            for w in words:
                if len(buf) + len(w) + 1 > 57:
                    break
                buf = (buf + " " + w).strip()
            title = buf + "..."
        else:
            title = raw_title

        # Slug must be clean ASCII
        slug = _re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:80]

        # Context block — adds ~150 words of factual analysis below the opinion
        context = strip_emojis(_write_context(story, focus_keyword))

        # JSON-LD schema
        headline_safe = story['headline'].replace('"', '\\"')[:110]
        meta_text     = _re.sub(r'<[^>]+>', '', content).strip()[:155]
        schema = f"""<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "NewsArticle",
  "headline": "{headline_safe}",
  "description": "{meta_text.replace('"', '\\"')}",
  "datePublished": "{pub_date}",
  "dateModified": "{pub_date}",
  "publisher": {{
    "@type": "Organization",
    "name": "{self.site.display_name}",
    "url": "{self.site.site_url}"
  }},
  "keywords": "{focus_keyword}, fintech, {story.get('source','')}"
}}
</script>"""

        category_id = self.wp.get_or_create_category(_WP_CATEGORY_NAME, _WP_CATEGORY_SLUG)
        used_slugs  = self.wp.get_recent_featured_image_slugs(days=7)
        images      = fetch_unsplash_images(["finance opinion editorial"], "finance editorial dark", count=1, used_slugs=used_slugs)

        featured_id  = None
        unsplash_id  = None
        hero_img_html = ""
        if images:
            uploaded = self.wp.upload_image(images[0], title)
            if uploaded:
                featured_id = uploaded["id"]
                unsplash_id = images[0].get("unsplash_id")
                # Embed image in article body so it shows regardless of theme settings
                img_url  = images[0]["url"]
                img_alt  = f"{focus_keyword} — {story['headline'][:60]}"[:125]
                photographer     = images[0].get("photographer", "Unsplash")
                photographer_url = images[0].get("photographer_url", "https://unsplash.com")
                hero_img_html = (
                    f'<figure style="margin:0 0 24px;">'
                    f'<img src="{img_url}" alt="{img_alt}" title="{img_alt}" '
                    f'width="1200" height="630" loading="eager" decoding="async" '
                    f'style="width:100%;height:auto;border-radius:8px;display:block;"/>'
                    f'<figcaption style="font-size:12px;color:#6c757d;margin-top:6px;">'
                    f'Photo by <a href="{photographer_url}" target="_blank" rel="noopener">{photographer}</a>'
                    f' via <a href="https://unsplash.com" target="_blank" rel="noopener">Unsplash</a>'
                    f'</figcaption></figure>'
                )

        html = schema + hero_img_html + f"""
<div style="background:#f8f9fa;border-left:4px solid #007bff;padding:24px 28px;border-radius:8px;margin-bottom:24px;">
  <p style="font-size:0.8em;text-transform:uppercase;letter-spacing:2px;color:#6c757d;margin-top:0;">{self.site.display_name} Hot Take &middot; {today}</p>
  {content}
  <p style="margin-bottom:0;font-size:0.8em;color:#6c757d;">Source: <a href="{story.get('url','#')}" style="color:#0056b3;" target="_blank" rel="noopener">{story.get('source','Unknown')}</a></p>
</div>
<h2>Why This Matters</h2>
{context}
"""

        tag_names = generate_tags(story["headline"], focus_keyword, "fintech")
        tag_ids       = self.wp.get_or_create_tags(tag_names)

        meta_description = clean_meta_text(content)[:152] + "..."

        post_url = self.wp.publish(
            title=title,
            slug=slug,
            html_content=html,
            category_id=category_id,
            featured_image_id=featured_id,
            meta_description=meta_description,
            focus_keyword=focus_keyword,
            tags=tag_ids,
            author_id=4,   # Priya Mehta — opinion content
            unsplash_id=unsplash_id,
        )
        if post_url:
            from core.db import mark_raw_story_processed
            mark_raw_story_processed(story["url"])
            log.info(f"  ✅ Hot Take LIVE → {post_url}")
        else:
            log.error("  ✗ Hot Take publish failed")


def run(site: SiteConfig) -> None:
    HotTakesPipeline(site).run()
