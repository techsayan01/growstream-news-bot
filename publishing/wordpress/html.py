"""
HTML builder for WordPress posts.

Assembles the final post HTML with JSON-LD schema markup, trend badge,
and inline Unsplash images interleaved after the first and second H2 tags.
"""

from datetime import datetime


def build_html(
    content: str,
    images: list[dict],
    story: dict,
    focus_keyword: str = "",
    meta_description: str = "",
    publisher_name: str = "GrowStream Media",
    publisher_url: str = "https://growstreammedia.com",
) -> str:
    """Assemble the final post HTML with schema markup, badge, and inline images."""
    trend    = story.get("market_trend", "AI & Finance")
    pub_date = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+00:00")
    headline = story.get("headline", "")

    schema = f"""<script type="application/ld+json">
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

    badge = f'<p><strong>📈 {trend}</strong></p>\n<hr/>\n'

    def img_block(img: dict, is_hero: bool = False) -> str:
        alt = img.get("alt") or focus_keyword or "finance AI news"
        if focus_keyword and focus_keyword.lower() not in alt.lower():
            alt = f"{focus_keyword} {alt}"
        alt          = alt[:125]
        caption_text = (
            f'{focus_keyword.title() if focus_keyword else "Finance AI"} — '
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

    # Interleave inline images after the 1st and 2nd H2 tags
    html  = schema + badge
    parts = content.split("<h2>")
    for i, part in enumerate(parts):
        if i == 0:
            html += part
        else:
            html += "<h2>" + part
            if i == 1 and len(images) > 1:
                html += img_block(images[1])
            elif i == 2 and len(images) > 2:
                html += img_block(images[2])

    return html
