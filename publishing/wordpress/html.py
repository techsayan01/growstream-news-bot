"""
HTML builder for WordPress posts.

Assembles the final post HTML with:
  - Newspaper-style typography (drop cap, pull quotes, refined spacing)
  - NewsArticle + FAQPage JSON-LD schema
  - Inline Unsplash images interleaved after H2 tags
  - Internal links "Related Reading" section
  - Branded article footer with separator
"""

import json
import re
from datetime import datetime

from core.utils import strip_emojis


# ── Newspaper style CSS (injected once at top of each article) ────────────────

_NEWSPAPER_STYLE = """<style>
/* GrowStream Newspaper Typography */
.gs-article { font-family: Georgia, 'Times New Roman', serif; line-height: 1.8; color: #1a1a1a; }
.gs-article h2 { font-family: 'Helvetica Neue', Arial, sans-serif; font-size: 1.4em; font-weight: 700;
  color: #0d1b2a; border-bottom: 2px solid #0056b3; padding-bottom: 8px; margin: 36px 0 16px; }
.gs-article h3 { font-family: 'Helvetica Neue', Arial, sans-serif; font-size: 1.15em; font-weight: 600;
  color: #1b3a5c; margin: 24px 0 10px; }
.gs-article h4 { font-family: 'Helvetica Neue', Arial, sans-serif; font-size: 1em; font-weight: 600;
  color: #333; margin: 20px 0 8px; }
.gs-article p { margin: 0 0 16px; font-size: 1.05em; }
.gs-article ul, .gs-article ol { margin: 0 0 16px; padding-left: 1.5em; }
.gs-article li { margin-bottom: 6px; }
.gs-article strong { color: #0d1b2a; }
.gs-article a { color: #0056b3; text-decoration: none; border-bottom: 1px solid #b8daff; }
.gs-article a:hover { border-bottom-color: #0056b3; }

/* Drop cap on first paragraph */
.gs-article > p:first-of-type::first-letter {
  float: left; font-size: 3.2em; line-height: 0.85; font-weight: 700;
  color: #0056b3; margin: 4px 10px 0 0; font-family: Georgia, serif; }

/* Pull quote / blockquote — newspaper style */
.gs-article blockquote {
  border: none; border-left: 4px solid #0056b3; margin: 28px 0; padding: 16px 24px;
  background: #f0f7ff; font-style: italic; font-size: 1.1em; color: #1b3a5c;
  line-height: 1.7; position: relative; }
.gs-article blockquote::before {
  content: open-quote; font-size: 3em; color: #0056b3; opacity: 0.3;
  position: absolute; top: -8px; left: 8px; font-family: Georgia, serif; }

/* Tables — clean newspaper data style */
.gs-article table { border-collapse: collapse; width: 100%; margin: 20px 0; font-family: 'Helvetica Neue', Arial, sans-serif; font-size: 0.92em; }
.gs-article th { background: #0d1b2a; color: #fff; padding: 10px 14px; text-align: left; font-weight: 600; }
.gs-article td { padding: 10px 14px; border-bottom: 1px solid #dee2e6; }
.gs-article tr:nth-child(even) td { background: #f8f9fa; }
</style>
"""


# ── FAQ schema extraction ─────────────────────────────────────────────────────

def _extract_faq_pairs(html: str) -> list[dict]:
    """Extract question/answer pairs from FAQ sections in the article HTML."""
    pairs: list[dict] = []
    # [^<>]+ ensures no nested tags inside the heading
    pattern = re.compile(
        r'<h[34][^>]*>\s*([^<>]+\?)\s*</h[34]>\s*<p[^>]*>(.*?)</p>',
        re.IGNORECASE | re.DOTALL,
    )
    for m in pattern.finditer(html):
        question = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        answer   = re.sub(r'<[^>]+>', '', m.group(2)).strip()
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
    """Build a styled 'Related Reading' section from a list of article dicts."""
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
            f'<li style="padding:10px 0;border-bottom:1px solid #dee2e6;">'
            f'<a href="{url}" style="color:#0056b3;text-decoration:none;'
            f'font-weight:500;font-family:Helvetica Neue,Arial,sans-serif;">'
            f'{title}</a>{cat_badge}</li>\n'
        )

    if not items:
        return ""

    return f"""
<div style="background:#f8f9fa;border-top:3px solid #0056b3;padding:24px 28px;margin:40px 0 0;">
  <h3 style="margin-top:0;font-family:Helvetica Neue,Arial,sans-serif;font-size:0.85em;
    text-transform:uppercase;letter-spacing:2px;color:#6c757d;">Related Reading</h3>
  <ul style="list-style:none;margin:0;padding:0;">
{items}  </ul>
</div>"""


# ── Article footer ────────────────────────────────────────────────────────────

def _build_footer(
    publisher_name: str,
    publisher_url: str,
    source_name: str = "",
    source_url: str = "",
) -> str:
    """Branded end-of-article separator and credit line."""
    source_line = ""
    if source_name and source_url:
        source_line = (
            f'<p style="margin:0 0 6px;font-size:0.85em;color:#6c757d;">'
            f'Source: <a href="{source_url}" target="_blank" rel="noopener" '
            f'style="color:#0056b3;">{source_name}</a></p>'
        )
    elif source_name:
        source_line = (
            f'<p style="margin:0 0 6px;font-size:0.85em;color:#6c757d;">'
            f'Source: {source_name}</p>'
        )

    return f"""
<div style="margin-top:48px;padding-top:24px;border-top:1px solid #dee2e6;">
  <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">
    <div style="width:40px;height:4px;background:#0056b3;border-radius:2px;"></div>
    <span style="font-family:Helvetica Neue,Arial,sans-serif;font-size:0.8em;
      text-transform:uppercase;letter-spacing:2px;color:#6c757d;">End of article</span>
    <div style="flex:1;height:1px;background:#dee2e6;"></div>
  </div>
  {source_line}
  <p style="margin:0;font-size:0.85em;color:#6c757d;font-family:Helvetica Neue,Arial,sans-serif;">
    Published by <a href="{publisher_url}" style="color:#0056b3;text-decoration:none;font-weight:600;">{publisher_name}</a>
    &middot; {datetime.now().strftime('%B %d, %Y')}
  </p>
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
    """Assemble the final post HTML with newspaper styling."""
    trend    = story.get("market_trend", "AI & Finance")
    pub_date = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+00:00")
    headline = story.get("headline", "")

    # ── NewsArticle schema ────────────────────────────────────────────────────
    news_schema = f"""<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "NewsArticle",
  "headline": "{headline[:110].replace('"', '\\\\"')}",
  "description": "{meta_description[:160].replace('"', '\\\\"')}",
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

    # ── Trend badge (newspaper-style section label) ───────────────────────────
    badge = (
        f'<div style="margin-bottom:20px;padding-bottom:10px;'
        f'border-bottom:3px double #0d1b2a;">'
        f'<span style="font-family:Helvetica Neue,Arial,sans-serif;'
        f'font-size:0.8em;text-transform:uppercase;letter-spacing:3px;'
        f'color:#0056b3;font-weight:700;">{strip_emojis(trend)}</span></div>\n'
    )

    # ── Inline image helper ───────────────────────────────────────────────────
    def img_block(img: dict, is_hero: bool = False) -> str:
        alt = img.get("alt") or focus_keyword or "finance AI news"
        if focus_keyword and focus_keyword.lower() not in alt.lower():
            alt = f"{focus_keyword} {alt}"
        alt = alt[:125]
        caption_text = (
            f'{focus_keyword.title() if focus_keyword else "Finance"} | '
            f'Photo by <a href="{img.get("photographer_url","#")}" target="_blank" '
            f'rel="noopener">{img.get("photographer","Unsplash")}</a> via '
            f'<a href="https://unsplash.com" target="_blank" rel="noopener">Unsplash</a>'
        )
        size_attr = 'width="1200" height="630"' if is_hero else 'width="800" height="450"'
        loading   = "eager" if is_hero else "lazy"
        return (
            f'<figure style="margin:32px 0;">'
            f'<img src="{img["url"]}" alt="{alt}" title="{alt}" '
            f'{size_attr} loading="{loading}" decoding="async" '
            f'style="width:100%;height:auto;border-radius:4px;display:block;'
            f'box-shadow:0 2px 8px rgba(0,0,0,0.08);"/>'
            f'<figcaption style="font-family:Helvetica Neue,Arial,sans-serif;'
            f'font-size:0.78em;color:#6c757d;margin-top:8px;line-height:1.4;'
            f'font-style:italic;">'
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

    # ── Related Reading ───────────────────────────────────────────────────────
    related_section = build_related_section(related_articles or [])

    # ── Article footer ────────────────────────────────────────────────────────
    footer = _build_footer(
        publisher_name, publisher_url,
        source_name=story.get("source", ""),
        source_url=story.get("url", ""),
    )

    # ── Assemble ──────────────────────────────────────────────────────────────
    final = (
        news_schema + faq_schema +
        _NEWSPAPER_STYLE +
        '<div class="gs-article">' +
        badge + body + related_section + footer +
        '</div>'
    )
    return strip_emojis(final)
