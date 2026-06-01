"""
WordPress REST API client.

Instantiate one WordPressClient per site using credentials from SiteConfig.
All API calls (Application Password auth, category lookup, image upload, post creation) live here.
"""

import threading
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
        self.wp_url    = wp_url.rstrip("/")
        self.username  = username
        self.password  = password
        self.api_key   = api_key   # preferred; set via WP_API_KEY + mu-plugin
        self._jwt_token: str | None = None
        self._jwt_lock = threading.Lock()

    # ── Authentication ────────────────────────────────────────────────────────

    def _auth_header(self) -> dict:
        """API key (best) → JWT (fallback) → raises if neither works."""
        if self.api_key:
            return {"X-Newsbot-Key": self.api_key}
        token = self._get_jwt_token()
        if token:
            return {"Authorization": f"Bearer {token}"}
        raise RuntimeError("WordPress auth unavailable — set WP_API_KEY or check WP credentials.")

    def _get_jwt_token(self) -> str | None:
        with self._jwt_lock:
            if self._jwt_token:
                return self._jwt_token
        try:
            r = requests.post(
                f"{self.wp_url}/wp-json/jwt-auth/v1/token",
                json={"username": self.username, "password": self.password},
                timeout=REQUEST_TIMEOUT,
            )
            r.raise_for_status()
            self._jwt_token = r.json().get("token")
            if self._jwt_token:
                log.info("  ✓ JWT token acquired")
            else:
                log.error("  ✗ JWT response missing token field")
        except Exception as e:
            log.error(f"  ✗ JWT auth failed: {e}")
        return self._jwt_token

    # ── Deduplication ─────────────────────────────────────────────────────────

    def article_exists(self, title: str, days: int = 30) -> bool:
        """Layer 4 — final safeguard: search WordPress by title words.

        Searches by the first 5 significant words of the SEO title (not the
        generic focus keyword) so the match is specific enough to avoid false
        positives while still catching exact rewrites.

        Layers 1-3 (URL, fingerprint, semantic) run locally before this is
        called, so this is only reached when those checks pass.
        """
        from core.utils import normalise_headline
        # Use the 5 most distinctive words from the title
        words = normalise_headline(title).split()[:5]
        if not words:
            return False
        query  = " ".join(words)
        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=days)
        ).strftime("%Y-%m-%dT%H:%M:%S")

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                r = requests.get(
                    f"{self.wp_url}/wp-json/wp/v2/posts",
                    params={"search": query, "per_page": 3, "after": cutoff,
                            "_fields": "id,title,link"},
                    headers=self._auth_header(),
                    timeout=REQUEST_TIMEOUT,
                )
                r.raise_for_status()
                posts = r.json()
                if posts:
                    matched = posts[0]
                    log.warning(
                        f"  ⚠ [Layer 4] WordPress title match for '{query}' → "
                        f"ID {matched['id']} | {matched.get('link','')}"
                    )
                    return True
                return False
            except Exception as e:
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
                else:
                    log.error(f"  ✗ Layer 4 dedup check failed: {e}")
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

    def get_or_create_tags(self, tag_names: list[str]) -> list[int]:
        """Convert a list of tag name strings into WordPress tag IDs.

        Creates any tags that don't already exist. Returns a list of IDs.
        """
        tag_ids: list[int] = []
        for name in tag_names:
            if not name:
                continue
            try:
                # Search for existing tag
                r = requests.get(
                    f"{self.wp_url}/wp-json/wp/v2/tags",
                    headers=self._auth_header(),
                    params={"search": name, "per_page": 1},
                    timeout=REQUEST_TIMEOUT,
                )
                r.raise_for_status()
                results = r.json()
                if results:
                    tag_ids.append(results[0]["id"])
                    continue
                # Create new tag
                rc = requests.post(
                    f"{self.wp_url}/wp-json/wp/v2/tags",
                    headers=self._auth_header(),
                    json={"name": name},
                    timeout=REQUEST_TIMEOUT,
                )
                if rc.status_code == 201:
                    tag_ids.append(rc.json()["id"])
                elif rc.status_code == 400:
                    # Tag may exist under a slightly different slug — fetch it
                    data = rc.json()
                    existing_id = data.get("data", {}).get("term_id")
                    if existing_id:
                        tag_ids.append(existing_id)
            except Exception as e:
                log.warning(f"  ⚠ Tag '{name}' skipped: {e}")
        return tag_ids

    def get_or_create_category(self, name: str, slug: str) -> int | None:
        cat_id = self.get_category_id(slug)
        if cat_id:
            return cat_id
        try:
            r = requests.post(
                f"{self.wp_url}/wp-json/wp/v2/categories",
                headers=self._auth_header(),
                json={"name": name, "slug": slug},
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
                            headers=self._auth_header(),
                            json={
                                "alt_text":    alt_text,
                                "caption":     img_caption,
                                "title":       title[:80],
                                "description": (
                                    f"{focus_keyword} - {title[:100]}"
                                    if focus_keyword else title[:100]
                                ),
                            },
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
        source_url: str | None = None,
        category: str | None = None,
        article_type: str | None = None,
        seo_score: int | None = None,
        quality_score: int | None = None,
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
                    headers=self._auth_header(),
                    json=payload,
                    timeout=30,
                )

                if r.status_code == 201:
                    post_data = r.json()
                    post_id   = post_data.get("id")
                    post_url  = post_data.get("link", "")
                    log_published_article(
                        post_id, title, focus_keyword, unsplash_id,
                        source_url=source_url,
                        post_url=post_url,
                        category=category,
                        article_type=article_type,
                        seo_score=seo_score,
                        quality_score=quality_score,
                    )
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
