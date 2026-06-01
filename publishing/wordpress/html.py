"""
HTML builder for WordPress posts.

Assembles the final post HTML with:
  - NewsArticle JSON-LD schema
  - FAQPage JSON-LD schema (auto-detected from FAQ sections in the article)
  - Trend badge
  - Inline Unsplash images interleaved after H2 tags
  - Internal links "Related Reading" section
"""

import json
import re
from datetime import datetime


# ── FAQ schema extraction ─────────────────────────────────────────────────────

def _extract_faq_pairs(html: str) -> list[dict]:
    """Extract question/answer pairs from FAQ sections in the article HTML.

    Looks for <h3> or <h4> tags ending with '?' and grabs the following <p>
    as the answer. Limits to 5 pairs to keep schema focused.
    """
    pairs: list[dict] = []

    # Match h3/h4 question + immediately following p answer
    # [^<>]+ ensures no nested tags inside the heading (prevents cross-tag matches)
    pattern = re.compile(
        r'<h[34][^>]*>\s*([^<>]+\?)\s*</h[34]>\s*<p[^>]*>(.*?)</p>',
        re.IGNORECASE | re.DOTALL,
    )
    for m in pattern.finditer(html):
        question = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        answer   = re.sub(r'<[^>]+>', '', m.group(2)).strip()
        # Skip section headers mis-detected as questions (must have 4+ words and end with ?)
        words = question.split()
        if len(words) < 4 or not question.endswith('?'):
            continue
        if question and answer and len(answer) > 20:
            pairs.append({"question": question, "answer": answer})
        if len(pairs) >= 5:
            break

    return pairs


def _faq_schema(pairs: list[dict]) -> str:
    if not pairs:
        return ""
    entities = [
        {
            "@type":          "Question",
            "name":           p["question"],
            "acceptedAnswer": {"@type": "Answer", "text": p["answer"]},
        }
        for p in pairs
    ]
    return f"""<script type="application/ld+json">
{json.dumps({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": entities}, indent=2)}
</script>"""


# ── Internal links section ────────────────────────────────────────────────────

def build_related_section(related_articles: list[dict]) -> str:
    """Build a styled 'Related Reading' section from a list of article dicts.

    Each dict needs: title, post_url, category (optional).
    """
    if not related_articles:
        return ""

    items = ""
    for art in related_articles[:3]:
        title    = art.get("title", "")
        url      = art.get("post_url", "")
        category = art.get("category", "")
        if not title or not url:
            continue
        cat_badge = (
            f'<span style="font-size:0.75em;background:#e9ecef;color:#495057;'
            f'padding:2px 8px;border-radius:12px;margin-left:8px;">{category}</span>'
            if category else ""
        )
        items += (
            f'<li style="padding:8px 0;border-bottom:1px solid #dee2e6;">'
            f'<a href="{url}" style="color:#0056b3;text-decoration:none;font-weight:500;">'
            f'{title}</a>{cat_badge}</li>\n'
        )

    if not items:
        return ""

    return f"""
<div style="background:#f8f9fa;border:1px solid #dee2e6;border-radius:8px;padding:20px 24px;margin:32px 0;">
  <h3 style="margin-top:0;font-size:1em;text-transform:uppercase;letter-spacing:1px;color:#6c757d;">Related Reading</h3>
  <ul style="list-style:none;margin:0;padding:0;">
{items}  </ul>
</div>"""


# ── Main builder ──────────────────────────────────────────────────────────────

def build_html(
    content: str,
    images: list[dict],
    story: dict,
    focus_keyword: str = "",
    meta_description: str = "",
    publisher_name: str = "GrowStream Media",
    publisher_url: str = "https://growstreammedia.com",
    related_articles: list[dict] | None = None,
) -> str:
    """Assemble the final post HTML.

    Args:
        content:          LLM-generated article HTML body.
        images:           Unsplash image dicts (index 0 = hero, 1+ = inline).
        story:            Story dict with headline, market_trend, etc.
        focus_keyword:    SEO focus keyword.
        meta_description: Used in NewsArticle schema.
        publisher_name:   Site display name.
        publisher_url:    Site URL.
        related_articles: List of recently published article dicts for internal links.
    """
    trend    = story.get("market_trend", "AI & Finance")
    pub_date = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+00:00")
    headline = story.get("headline", "")

    # ── NewsArticle schema ────────────────────────────────────────────────────
    news_schema = f"""<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "NewsArticle",
  "headline": "{headline[:110].replace('"', '\\"')}",
  "description": "{meta_description[:160].replace('"', '\\"')}",
  "datePublished": "{pub_date}",
  "dateModified": "{pub_date}",
  "publisher": {{
    "@type": "Organization",
    "name": "{publisher_name}",
    "url": "{publisher_url}"
  }},
  "keywords": "{focus_keyword}, {trend}, AI finance, fintech"
}}
</script>"""

    # ── FAQPage schema (auto-extracted) ───────────────────────────────────────
    faq_pairs  = _extract_faq_pairs(content)
    faq_schema = _faq_schema(faq_pairs)

    # ── Trend badge ───────────────────────────────────────────────────────────
    badge = f'<p><strong>{trend}</strong></p>\n<hr/>\n'

    # ── Inline image helper ───────────────────────────────────────────────────
    def img_block(img: dict, is_hero: bool = False) -> str:
        alt = img.get("alt") or focus_keyword or "finance AI news"
        if focus_keyword and focus_keyword.lower() not in alt.lower():
            alt = f"{focus_keyword} {alt}"
        alt          = alt[:125]
        caption_text = (
            f'{focus_keyword.title() if focus_keyword else "Finance"} — '
            f'Photo by <a href="{img.get("photographer_url","#")}" target="_blank" rel="noopener">'
            f'{img.get("photographer","Unsplash")}</a> via '
            f'<a href="https://unsplash.com" target="_blank" rel="noopener">Unsplash</a>'
        )
        size_attr = 'width="1200" height="630"' if is_hero else 'width="800" height="450"'
        loading   = "eager" if is_hero else "lazy"
        return (
            f'<figure style="margin:28px 0;">'
            f'<img src="{img["url"]}" alt="{alt}" title="{alt}" '
            f'{size_attr} loading="{loading}" decoding="async" '
            f'style="width:100%;height:auto;border-radius:8px;display:block;"/>'
            f'<figcaption style="font-size:13px;color:#666;margin-top:8px;line-height:1.4;">'
            f'{caption_text}'
            f'</figcaption></figure>\n'
        )

    # ── Interleave images after H2 tags ───────────────────────────────────────
    body  = ""
    parts = content.split("<h2>")
    for i, part in enumerate(parts):
        if i == 0:
            body += part
        else:
            body += "<h2>" + part
            if i == 1 and len(images) > 1:
                body += img_block(images[1])
            elif i == 2 and len(images) > 2:
                body += img_block(images[2])

    # ── Related Reading section ───────────────────────────────────────────────
    related_section = build_related_section(related_articles or [])

    return news_schema + faq_schema + badge + body + related_section
