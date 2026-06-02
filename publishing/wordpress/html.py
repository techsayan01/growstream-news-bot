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

from core.utils import clean_meta_text, strip_emojis


# ── Newspaper style CSS (injected once at top of each article) ────────────────

_NEWSPAPER_STYLE = """<style>
/* GrowStream Media — Brand Newspaper Typography
   Primary brand:  #E53E1A (orange-red — logo, accents, drop cap)
   Link blue:      #2B6CB0 (palette 1)
   Dark blue:      #215387 (palette 2 — headings)
   Near-black:     #1A202C (palette 3 — body text)
   Dark grey:      #2D3748 (palette 4 — subheadings)
   Mid grey:       #4A5568 (palette 5 — secondary text)
   Light grey:     #718096 (palette 6 — captions)
   Off-white:      #EDF2F7 (palette 7 — backgrounds)
   White:          #F7FAFC (palette 8 — alt backgrounds)
*/
.gs-article { font-family: Georgia, 'Times New Roman', serif; line-height: 1.8; color: #1A202C; }
.gs-article h2 { font-family: 'Helvetica Neue', Arial, sans-serif; font-size: 1.4em; font-weight: 700;
  color: #215387; border-bottom: 2px solid #E53E1A; padding-bottom: 8px; margin: 36px 0 16px; }
.gs-article h3 { font-family: 'Helvetica Neue', Arial, sans-serif; font-size: 1.15em; font-weight: 600;
  color: #2D3748; margin: 24px 0 10px; }
.gs-article h4 { font-family: 'Helvetica Neue', Arial, sans-serif; font-size: 1em; font-weight: 600;
  color: #4A5568; margin: 20px 0 8px; }
.gs-article p { margin: 0 0 16px; font-size: 1.05em; }
.gs-article ul, .gs-article ol { margin: 0 0 16px; padding-left: 1.5em; }
.gs-article li { margin-bottom: 6px; }
.gs-article strong { color: #1A202C; }
.gs-article a { color: #2B6CB0; text-decoration: none; border-bottom: 1px solid #b8daff; }
.gs-article a:hover { color: #E53E1A; border-bottom-color: #E53E1A; }

/* Drop cap — brand orange-red */
.gs-article > p:first-of-type::first-letter {
  float: left; font-size: 3.2em; line-height: 0.85; font-weight: 700;
  color: #E53E1A; margin: 4px 10px 0 0; font-family: Georgia, serif; }

/* Pull quote — brand accent border */
.gs-article blockquote {
  border: none; border-left: 4px solid #E53E1A; margin: 28px 0; padding: 16px 24px;
  background: #F7FAFC; font-style: italic; font-size: 1.1em; color: #2D3748;
  line-height: 1.7; position: relative; }
.gs-article blockquote::before {
  content: open-quote; font-size: 3em; color: #E53E1A; opacity: 0.25;
  position: absolute; top: -8px; left: 8px; font-family: Georgia, serif; }

/* Tables — dark header with brand accent */
.gs-article table { border-collapse: collapse; width: 100%; margin: 20px 0;
  font-family: 'Helvetica Neue', Arial, sans-serif; font-size: 0.92em; }
.gs-article th { background: #1A202C; color: #fff; padding: 10px 14px; text-align: left;
  font-weight: 600; border-bottom: 3px solid #E53E1A; }
.gs-article td { padding: 10px 14px; border-bottom: 1px solid #EDF2F7; }
.gs-article tr:nth-child(even) td { background: #F7FAFC; }
</style>
"""


# ── Executive summary (auto-generated for long articles) ──────────────────────

def _build_executive_summary(content: str, headline: str) -> str:
    """Auto-extract key points from article HTML for an executive summary box.

    Only generated for articles over 800 words. Extracts bullet points from:
    1. Text inside the Key Takeaways box (if present)
    2. First sentence of each H2 section
    3. Any stat callout figures

    Returns empty string for short articles.
    """
    plain = re.sub(r'<[^>]+>', ' ', content)
    plain = re.sub(r'\s+', ' ', plain).strip()
    words = len(plain.split())

    if words < 800:
        return ""

    bullets = []

    # Extract first sentence after each H2
    h2_sections = re.split(r'<h2[^>]*>', content)
    for section in h2_sections[1:]:  # skip content before first H2
        # Get heading text
        heading_match = re.match(r'(.*?)</h2>', section, re.S)
        if not heading_match:
            continue
        heading = clean_meta_text(heading_match.group(1)).strip()
        # Skip FAQ, Bottom Line, Related headings
        if any(skip in heading.lower() for skip in ['faq', 'frequently', 'bottom line', 'related']):
            continue
        # Get first sentence after the heading
        after_heading = section[heading_match.end():]
        first_p = re.search(r'<p[^>]*>(.*?)</p>', after_heading, re.S)
        if first_p:
            sentence = clean_meta_text(first_p.group(1))
            # Take first sentence only
            end = re.search(r'[.!?](?:\s|$)', sentence)
            if end:
                sentence = sentence[:end.end()].strip()
            if len(sentence) > 30 and len(sentence) < 200:
                bullets.append(f"<strong>{heading}:</strong> {sentence}")
        if len(bullets) >= 5:
            break

    # Extract stat callout figures
    stats = re.findall(
        r'<span style="font-size:2em[^"]*">([^<]+)</span>',
        content, re.I,
    )
    if stats:
        stat_text = ", ".join(s.strip() for s in stats[:3])
        bullets.insert(0, f"<strong>Key figures:</strong> {stat_text}")

    if len(bullets) < 2:
        return ""

    items = "\n".join(f'    <li style="margin-bottom:10px;line-height:1.5;">{b}</li>' for b in bullets[:6])

    return f"""
<div style="background:#F7FAFC;border:1px solid #EDF2F7;border-top:3px solid #E53E1A;padding:24px 28px;border-radius:0 0 8px 8px;margin:0 0 32px;">
  <h3 style="margin-top:0;font-family:Helvetica Neue,Arial,sans-serif;font-size:0.85em;text-transform:uppercase;letter-spacing:2px;color:#E53E1A;">Executive Summary</h3>
  <p style="margin:0 0 12px;font-size:0.9em;color:#718096;font-family:Helvetica Neue,Arial,sans-serif;">
    {words:,} words &middot; {max(1, words // 250)} min read</p>
  <ul style="margin:0;padding-left:1.2em;color:#1A202C;">
{items}
  </ul>
</div>
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
            f'<span style="font-size:0.75em;background:#F7FAFC;color:#4A5568;'
            f'padding:2px 8px;border-radius:12px;margin-left:8px;'
            f'border:1px solid #EDF2F7;">{category}</span>'
            if category else ""
        )
        items += (
            f'<li style="padding:10px 0;border-bottom:1px solid #EDF2F7;">'
            f'<a href="{url}" style="color:#2B6CB0;text-decoration:none;'
            f'font-weight:500;font-family:Helvetica Neue,Arial,sans-serif;">'
            f'{title}</a>{cat_badge}</li>\n'
        )

    if not items:
        return ""

    return f"""
<div style="background:#EDF2F7;border-top:3px solid #E53E1A;padding:24px 28px;margin:40px 0 0;">
  <h3 style="margin-top:0;font-family:Helvetica Neue,Arial,sans-serif;font-size:0.85em;
    text-transform:uppercase;letter-spacing:2px;color:#4A5568;">Related Reading</h3>
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
            f'<p style="margin:0 0 6px;font-size:0.85em;color:#718096;">'
            f'Source: <a href="{source_url}" target="_blank" rel="noopener" '
            f'style="color:#2B6CB0;">{source_name}</a></p>'
        )
    elif source_name:
        source_line = (
            f'<p style="margin:0 0 6px;font-size:0.85em;color:#718096;">'
            f'Source: {source_name}</p>'
        )

    return f"""
<div style="margin-top:48px;padding-top:24px;border-top:1px solid #EDF2F7;">
  <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">
    <div style="width:40px;height:4px;background:#E53E1A;border-radius:2px;"></div>
    <span style="font-family:Helvetica Neue,Arial,sans-serif;font-size:0.8em;
      text-transform:uppercase;letter-spacing:2px;color:#718096;">End of article</span>
    <div style="flex:1;height:1px;background:#EDF2F7;"></div>
  </div>
  {source_line}
  <p style="margin:0;font-size:0.85em;color:#718096;font-family:Helvetica Neue,Arial,sans-serif;">
    Published by <a href="{publisher_url}" style="color:#2B6CB0;text-decoration:none;font-weight:600;">{publisher_name}</a>
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
        f'border-bottom:3px double #1A202C;">'
        f'<span style="font-family:Helvetica Neue,Arial,sans-serif;'
        f'font-size:0.8em;text-transform:uppercase;letter-spacing:3px;'
        f'color:#E53E1A;font-weight:700;">{strip_emojis(trend)}</span></div>\n'
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

    # ── Executive summary (auto-generated for 800+ word articles) ───────────
    exec_summary = _build_executive_summary(body, headline)

    # ── Assemble ──────────────────────────────────────────────────────────────
    final = (
        news_schema + faq_schema +
        _NEWSPAPER_STYLE +
        '<div class="gs-article">' +
        badge + exec_summary + body + related_section + footer +
        '</div>'
    )
    return strip_emojis(final)
