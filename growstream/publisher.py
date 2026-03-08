"""
GrowStream — WordPress Publisher & HTML builder.
Handles media upload, HTML assembly, and post publishing.
Authentication: JWT Bearer token via /wp-json/jwt-auth/v1/token
"""

import json
import time
from datetime import datetime

import requests

from .config import MAX_RETRIES, REQUEST_TIMEOUT, RETRY_DELAY, WP_PASSWORD, WP_URL, WP_USERNAME, log


# ============================================================
# JWT AUTH
# ============================================================
_jwt_token: str | None = None   # cached for the lifetime of this run


def get_jwt_token() -> str | None:
    """
    Fetch a JWT from WordPress and cache it.
    Returns the token string, or None on failure.
    The token is valid for 7 days; re-fetched for each bot run.
    """
    global _jwt_token
    if _jwt_token:
        return _jwt_token

    try:
        r = requests.post(
            f"{WP_URL}/wp-json/jwt-auth/v1/token",
            json={"username": WP_USERNAME, "password": WP_PASSWORD},
            timeout=REQUEST_TIMEOUT,
        )
        r.raise_for_status()
        _jwt_token = r.json().get("token")
        if _jwt_token:
            log.info("  ✓ JWT token acquired")
        else:
            log.error("  ✗ JWT response had no token field")
    except Exception as e:
        log.error(f"  ✗ Could not fetch JWT token: {e}")

    return _jwt_token


def get_wp_auth() -> dict:
    """Return Authorization header using JWT Bearer token."""
    token = get_jwt_token()
    if token:
        return {"Authorization": f"Bearer {token}"}
    # Should not reach here after a successful preflight, but guard anyway
    raise RuntimeError(
        "WordPress JWT token unavailable. Check WP_USERNAME / WP_PASSWORD env vars "
        "and confirm the JWT Authentication plugin is active on the site."
    )


# ============================================================
# DEDUPLICATION
# ============================================================
def article_exists(title_query: str) -> bool:
    """
    Check if an article with a similar title already exists in WordPress.
    Uses the WordPress REST API search functionality.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(
                f"{WP_URL}/wp-json/wp/v2/posts?search={requests.utils.quote(title_query)}&per_page=1",
                headers=get_wp_auth(),
                timeout=REQUEST_TIMEOUT,
            )
            r.raise_for_status()
            posts = r.json()
            if posts:
                log.warning(f"  ⚠ Article matching '{title_query}' already exists (ID: {posts[0]['id']})")
                return True
            return False
        except Exception as e:
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
            else:
                log.error(f"  ✗ Could not check for existing article '{title_query}': {e}")
    return False


def get_recent_featured_image_slugs(days: int = 7) -> set[str]:
    """
    Return a set of source-URL slugs for featured images used in the last *days* days.
    Used to avoid picking the same Unsplash photo ID two days in a row.
    """
    from datetime import datetime, timedelta, timezone
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")
    used_slugs: set[str] = set()
    try:
        r = requests.get(
            f"{WP_URL}/wp-json/wp/v2/posts",
            params={"after": cutoff, "per_page": 50, "_fields": "id,featured_media"},
            headers=get_wp_auth(),
            timeout=REQUEST_TIMEOUT,
        )
        r.raise_for_status()
        posts = r.json()
        media_ids = [p["featured_media"] for p in posts if p.get("featured_media")]
        for mid in media_ids:
            try:
                mr = requests.get(
                    f"{WP_URL}/wp-json/wp/v2/media/{mid}?_fields=source_url",
                    headers=get_wp_auth(),
                    timeout=REQUEST_TIMEOUT,
                )
                mr.raise_for_status()
                src = mr.json().get("source_url", "")
                # Extract the base filename slug (strip extension, path, and WP size suffix)
                slug = src.split("/")[-1].rsplit(".", 1)[0]
                # Remove WP dimension suffixes like "-1920x1080"
                import re
                slug = re.sub(r"-\d+x\d+$", "", slug)
                if slug:
                    used_slugs.add(slug.lower())
            except Exception:
                pass
        log.info(f"  🖼  {len(used_slugs)} recent featured image slugs loaded (last {days}d)")
    except Exception as e:
        log.warning(f"  ⚠ Could not fetch recent featured images: {e}")
    return used_slugs


# ============================================================
# CATEGORY LOOKUP
# ============================================================
def get_wp_category_id(slug: str) -> int | None:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(
                f"{WP_URL}/wp-json/wp/v2/categories?slug={slug}",
                headers=get_wp_auth(),
                timeout=REQUEST_TIMEOUT,
            )
            r.raise_for_status()
            cats = r.json()
            if cats:
                return cats[0]["id"]
            log.warning(f"  ⚠ Category '{slug}' not found in WordPress")
            return None
        except Exception as e:
            if attempt < MAX_RETRIES:
                import time; time.sleep(RETRY_DELAY)
            else:
                log.error(f"  ✗ Could not fetch category '{slug}': {e}")
    return None


def get_or_create_wp_category(name: str, slug: str) -> int | None:
    """Fetch a WP category by slug, creating it if it doesn't exist."""
    import json as _json
    # 1. Try to find existing
    cat_id = get_wp_category_id(slug)
    if cat_id:
        return cat_id
    # 2. Create it
    try:
        r = requests.post(
            f"{WP_URL}/wp-json/wp/v2/categories",
            headers={**get_wp_auth(), "Content-Type": "application/json"},
            data=_json.dumps({"name": name, "slug": slug}),
            timeout=REQUEST_TIMEOUT,
        )
        r.raise_for_status()
        cat_id = r.json().get("id")
        log.info(f"  ✓ Created WP category '{name}' (ID: {cat_id})")
        return cat_id
    except Exception as e:
        log.error(f"  ✗ Could not create WP category '{name}': {e}")
    return None


# ============================================================
# IMAGE UPLOAD
# ============================================================
def upload_image_to_wordpress(
    image_data: dict,
    title: str,
    focus_keyword: str = "",
    caption: str = "",
) -> dict | None:
    """Upload a single image to WordPress media library and set SEO metadata."""
    import time

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            img_response = requests.get(image_data["url"], timeout=REQUEST_TIMEOUT)
            img_response.raise_for_status()

            # Strip non-ASCII chars (e.g. emojis) so the filename is latin-1 safe
            safe_title = title.encode("ascii", errors="ignore").decode("ascii")
            filename = (
                f"{safe_title[:40].replace(' ', '-').lower()}"
                f"-{datetime.now().strftime('%H%M%S')}.jpg"
            )

            # Build keyword-rich alt text
            alt_text = image_data.get("alt") or focus_keyword or title
            if focus_keyword and focus_keyword.lower() not in alt_text.lower():
                alt_text = f"{focus_keyword} - {alt_text}"
            alt_text = alt_text[:125]

            response = requests.post(
                f"{WP_URL}/wp-json/wp/v2/media",
                headers={
                    **get_wp_auth(),
                    "Content-Disposition": f'attachment; filename="{filename}"',
                    "Content-Type": "image/jpeg",
                },
                data=img_response.content,
                timeout=30,
            )

            if response.status_code == 201:
                media    = response.json()
                media_id = media["id"]

                img_caption = caption or (
                    f'Photo by <a href="{image_data.get("photographer_url","#")}" '
                    f'target="_blank" rel="noopener">{image_data.get("photographer","Unsplash")}</a> on '
                    f'<a href="https://unsplash.com" target="_blank" rel="noopener">Unsplash</a>'
                )
                try:
                    requests.post(
                        f"{WP_URL}/wp-json/wp/v2/media/{media_id}",
                        headers={**get_wp_auth(), "Content-Type": "application/json"},
                        data=json.dumps({
                            "alt_text":    alt_text,
                            "caption":     img_caption,
                            "title":       title[:80],
                            "description": (
                                f"{focus_keyword} — {title[:100]}"
                                if focus_keyword else title[:100]
                            ),
                        }),
                        timeout=15,
                    )
                except Exception:
                    pass  # Metadata update failure is non-critical

                return {"id": media_id, "url": media["source_url"], "alt": alt_text}

            elif response.status_code == 401:
                log.error("  ✗ WordPress auth failed")
                return None
            else:
                log.warning(f"  ⚠ Image upload {response.status_code}")

        except Exception as e:
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
            else:
                log.error(f"  ✗ Image upload failed: {e}")
    return None


# ============================================================
# HTML BUILDER
# ============================================================
def build_html(
    content: str,
    images: list[dict],
    story: dict,
    focus_keyword: str = "",
    meta_description: str = "",
) -> str:
    """Assemble the final post HTML with schema markup, badge, and inline images."""
    trend    = story.get("market_trend", "AI & Finance")
    pub_date = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+00:00")
    headline = story.get("headline", "")

    # JSON-LD Article schema
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
    "name": "GrowStream Media",
    "url": "https://growstreammedia.com"
  }},
  "keywords": "{focus_keyword}, {trend}, AI finance, fintech"
}}
</script>"""

    # Trend badge
    badge = f'<p><strong>📈 {trend}</strong></p>\n<hr/>\n'

    def img_block(img: dict, is_hero: bool = False) -> str:
        alt = img.get("alt") or focus_keyword or "finance AI news"
        if focus_keyword and focus_keyword.lower() not in alt.lower():
            alt = f"{focus_keyword} {alt}"
        alt = alt[:125]
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

    # Interleave inline images after 1st and 2nd H2 tags
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


# ============================================================
# PUBLISH
# ============================================================
def publish_to_wordpress(
    title: str,
    html_content: str,
    category_id: int | None,
    featured_image_id: int | None,
    meta_description: str = "",
    focus_keyword: str = "",
    tags: list | None = None,
    author_id: int | None = None,
) -> str | None:
    """Publish a post via WordPress REST API. Returns the live URL or None."""
    import time

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            payload: dict = {
                "title":          title,
                "content":        html_content,
                "excerpt":        meta_description,
                "status":         "publish",
                "categories":     [category_id] if category_id else [],
                "featured_media": featured_image_id or 0,
                "tags":           tags or [],
                "meta": {
                    # RankMath SEO
                    "rank_math_focus_keyword": focus_keyword,
                    "rank_math_description":   meta_description,
                    "rank_math_title":         title,
                    # Yoast fallback
                    "_yoast_wpseo_metadesc":   meta_description,
                    "_yoast_wpseo_focuskw":    focus_keyword,
                },
            }
            if author_id:
                payload["author"] = author_id

            response = requests.post(
                f"{WP_URL}/wp-json/wp/v2/posts",
                headers={**get_wp_auth(), "Content-Type": "application/json"},
                data=json.dumps(payload),
                timeout=30,
            )

            if response.status_code == 201:
                return response.json().get("link", "")
            elif response.status_code in [401, 403]:
                log.error(f"  ✗ WordPress auth/permissions error {response.status_code}")
                return None
            else:
                log.warning(
                    f"  ⚠ Publish attempt {attempt}: "
                    f"{response.status_code} — {response.text[:100]}"
                )

        except requests.exceptions.Timeout:
            log.warning(f"  ⚠ Publish timeout attempt {attempt}/{MAX_RETRIES}")
        except Exception as e:
            log.warning(f"  ⚠ Publish attempt {attempt}: {e}")

        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY)

    log.error("  ✗ Publish failed after all retries")
    return None
