"""
WordPress REST API client.

Instantiate one WordPressClient per site using credentials from SiteConfig.
All API calls (Application Password auth, category lookup, image upload, post creation) live here.
"""

import json
import time
from datetime import datetime, timedelta, timezone

import requests

from core.db import log_published_article
from core.retry import MAX_RETRIES, REQUEST_TIMEOUT, RETRY_DELAY
from core.utils import log
from publishing.base import Publisher


class WordPressClient(Publisher):
    """WordPress REST API client bound to a single site's credentials.

    Authentication uses WordPress Application Passwords (Basic Auth).
    Generate one at: WP Admin → Users → Profile → Application Passwords.
    Set WP_PASSWORD to the generated password (spaces are fine — WP accepts both).
    No plugin required; works on any WP 5.6+ site.
    """

    def __init__(self, wp_url: str, username: str, password: str, api_key: str = ""):
        self.wp_url   = wp_url.rstrip("/")
        self.username = username
        self.password = password
        self.api_key  = api_key  # preferred; set via WP_API_KEY + mu-plugin

    # ── Authentication ────────────────────────────────────────────────────────

    def _auth_header(self) -> dict:
        """API key header (preferred) or Basic Auth fallback."""
        if self.api_key:
            return {"X-Newsbot-Key": self.api_key}
        import base64
        token = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
        return {"Authorization": f"Basic {token}"}

    # ── Deduplication ─────────────────────────────────────────────────────────

    def article_exists(self, query: str) -> bool:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                r = requests.get(
                    f"{self.wp_url}/wp-json/wp/v2/posts",
                    params={"search": query, "per_page": 1},
                    headers=self._auth_header(),
                    timeout=REQUEST_TIMEOUT,
                )
                r.raise_for_status()
                posts = r.json()
                if posts:
                    log.warning(f"  ⚠ Article matching '{query}' already exists (ID: {posts[0]['id']})")
                    return True
                return False
            except Exception as e:
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
                else:
                    log.error(f"  ✗ Could not check for existing article '{query}': {e}")
        return False

    def get_recent_featured_image_slugs(self, days: int = 7) -> set[str]:
        """Return slugs of featured images used in the last *days* days."""
        cutoff     = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")
        used_slugs: set[str] = set()
        try:
            r = requests.get(
                f"{self.wp_url}/wp-json/wp/v2/posts",
                params={"after": cutoff, "per_page": 50, "_fields": "id,featured_media"},
                headers=self._auth_header(),
                timeout=REQUEST_TIMEOUT,
            )
            r.raise_for_status()
            posts     = r.json()
            media_ids = [p["featured_media"] for p in posts if p.get("featured_media")]
            for mid in media_ids:
                try:
                    mr = requests.get(
                        f"{self.wp_url}/wp-json/wp/v2/media/{mid}?_fields=source_url",
                        headers=self._auth_header(),
                        timeout=REQUEST_TIMEOUT,
                    )
                    mr.raise_for_status()
                    src = mr.json().get("source_url", "")
                    import re
                    slug = re.sub(r"-\d+x\d+$", "", src.split("/")[-1].rsplit(".", 1)[0])
                    if slug:
                        used_slugs.add(slug.lower())
                except Exception:
                    pass
            log.info(f"  🖼  {len(used_slugs)} recent featured image slugs loaded (last {days}d)")
        except Exception as e:
            log.warning(f"  ⚠ Could not fetch recent featured images: {e}")
        return used_slugs

    # ── Category helpers ──────────────────────────────────────────────────────

    def get_category_id(self, slug: str) -> int | None:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                r = requests.get(
                    f"{self.wp_url}/wp-json/wp/v2/categories?slug={slug}",
                    headers=self._auth_header(),
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
                    time.sleep(RETRY_DELAY)
                else:
                    log.error(f"  ✗ Could not fetch category '{slug}': {e}")
        return None

    def get_or_create_category(self, name: str, slug: str) -> int | None:
        cat_id = self.get_category_id(slug)
        if cat_id:
            return cat_id
        try:
            r = requests.post(
                f"{self.wp_url}/wp-json/wp/v2/categories",
                headers={**self._auth_header(), "Content-Type": "application/json"},
                data=json.dumps({"name": name, "slug": slug}),
                timeout=REQUEST_TIMEOUT,
            )
            r.raise_for_status()
            cat_id = r.json().get("id")
            log.info(f"  ✓ Created WP category '{name}' (ID: {cat_id})")
            return cat_id
        except Exception as e:
            log.error(f"  ✗ Could not create WP category '{name}': {e}")
        return None

    # ── Image upload ──────────────────────────────────────────────────────────

    def upload_image(
        self,
        image_data: dict,
        title: str,
        focus_keyword: str = "",
        caption: str = "",
    ) -> dict | None:
        """Upload an image dict to WordPress media library. Returns media info dict."""
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                img_r = requests.get(image_data["url"], timeout=REQUEST_TIMEOUT)
                img_r.raise_for_status()

                safe_title = title.encode("ascii", errors="ignore").decode("ascii")
                filename   = (
                    f"{safe_title[:40].replace(' ', '-').lower()}"
                    f"-{datetime.now().strftime('%H%M%S')}.jpg"
                )
                alt_text = image_data.get("alt") or focus_keyword or title
                if focus_keyword and focus_keyword.lower() not in alt_text.lower():
                    alt_text = f"{focus_keyword} - {alt_text}"
                alt_text = alt_text[:125]

                r = requests.post(
                    f"{self.wp_url}/wp-json/wp/v2/media",
                    headers={
                        **self._auth_header(),
                        "Content-Disposition": f'attachment; filename="{filename}"',
                        "Content-Type": "image/jpeg",
                    },
                    data=img_r.content,
                    timeout=30,
                )

                if r.status_code == 201:
                    media    = r.json()
                    media_id = media["id"]

                    img_caption = caption or (
                        f'Photo by <a href="{image_data.get("photographer_url","#")}" '
                        f'target="_blank" rel="noopener">{image_data.get("photographer","Unsplash")}</a> on '
                        f'<a href="https://unsplash.com" target="_blank" rel="noopener">Unsplash</a>'
                    )
                    try:
                        requests.post(
                            f"{self.wp_url}/wp-json/wp/v2/media/{media_id}",
                            headers={**self._auth_header(), "Content-Type": "application/json"},
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

                elif r.status_code in (401, 403):
                    log.error("  ✗ WordPress auth failed on image upload")
                    return None
                else:
                    log.warning(f"  ⚠ Image upload returned {r.status_code}")

            except Exception as e:
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
                else:
                    log.error(f"  ✗ Image upload failed: {e}")
        return None

    # ── Post publishing ───────────────────────────────────────────────────────

    def publish(
        self,
        title: str,
        html_content: str,
        category_id: int | None = None,
        featured_image_id: int | None = None,
        meta_description: str = "",
        focus_keyword: str = "",
        tags: list | None = None,
        author_id: int | None = None,
        unsplash_id: str | None = None,
        slug: str | None = None,
    ) -> str | None:
        """Publish a post via WordPress REST API. Returns the live URL or None."""
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                payload: dict = {
                    "title":          title,
                    "slug":           slug or "",
                    "content":        html_content,
                    "excerpt":        meta_description,
                    "status":         "publish",
                    "categories":     [category_id] if category_id else [],
                    "featured_media": featured_image_id or 0,
                    "tags":           tags or [],
                    "meta": {
                        "rank_math_focus_keyword": focus_keyword,
                        "rank_math_description":   meta_description,
                        "rank_math_title":         title,
                        "_yoast_wpseo_metadesc":   meta_description,
                        "_yoast_wpseo_focuskw":    focus_keyword,
                    },
                }
                if author_id:
                    payload["author"] = author_id

                r = requests.post(
                    f"{self.wp_url}/wp-json/wp/v2/posts",
                    headers={**self._auth_header(), "Content-Type": "application/json"},
                    data=json.dumps(payload),
                    timeout=30,
                )

                if r.status_code == 201:
                    post_data = r.json()
                    post_id   = post_data.get("id")
                    post_url  = post_data.get("link", "")
                    log_published_article(post_id, title, focus_keyword, unsplash_id)
                    return post_url
                elif r.status_code in (401, 403):
                    log.error(f"  ✗ WordPress auth/permissions error {r.status_code}")
                    return None
                else:
                    log.warning(f"  ⚠ Publish attempt {attempt}: {r.status_code} — {r.text[:100]}")

            except requests.exceptions.Timeout:
                log.warning(f"  ⚠ Publish timeout attempt {attempt}/{MAX_RETRIES}")
            except Exception as e:
                log.warning(f"  ⚠ Publish attempt {attempt}: {e}")

            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)

        log.error("  ✗ Publish failed after all retries")
        return None

    # ── Post fetching (used by social pipeline) ───────────────────────────────

    def fetch_post_by_url(self, post_url: str) -> dict | None:
        try:
            r = requests.get(
                f"{self.wp_url}/wp-json/wp/v2/posts",
                headers=self._auth_header(),
                params={"link": post_url, "per_page": 1},
                timeout=15,
            )
            r.raise_for_status()
            posts = r.json()
            return posts[0] if posts else None
        except Exception as e:
            log.error(f"  ✗ Could not fetch post by URL: {e}")
            return None

    def fetch_post_by_id(self, post_id: int) -> dict | None:
        try:
            r = requests.get(
                f"{self.wp_url}/wp-json/wp/v2/posts/{post_id}",
                headers=self._auth_header(),
                timeout=15,
            )
            r.raise_for_status()
            return r.json()
        except Exception as e:
            log.error(f"  ✗ Could not fetch post ID {post_id}: {e}")
            return None
