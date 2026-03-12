"""
LinkedIn social posting.

Tries company page first, falls back to personal profile.
"""

import re

import requests

from core.db import update_social_status
from core.retry import with_retry
from core.utils import log
from social.base import SocialPoster


class LinkedInPoster(SocialPoster):
    """Posts to LinkedIn as a company page or personal profile."""

    def __init__(
        self,
        access_token:  str,
        org_urn:       str = "",
        person_urn:    str = "",
        display_name:  str = "GrowStream Media",
        site_url:      str = "https://growstreammedia.com",
    ):
        self.access_token = access_token
        self.org_urn      = org_urn
        self.person_urn   = person_urn
        self.display_name = display_name
        self.site_url     = site_url

    @property
    def platform(self) -> str:
        return "linkedin"

    def check_auth(self) -> tuple[bool, str]:
        if not self.access_token or self.access_token == "your_access_token_here":
            return False, "No access token configured"

        def _verify(token: str) -> tuple[bool, str]:
            try:
                r = requests.get(
                    "https://api.linkedin.com/v2/userinfo",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10,
                )
                if r.status_code == 200:
                    name = r.json().get("name", "unknown")
                    return True, f"Authenticated as '{name}'"
                elif r.status_code == 401:
                    return False, "expired"
                elif r.status_code == 403:
                    return False, "Token lacks required scope (403)"
                return False, f"Auth check returned {r.status_code}"
            except Exception as e:
                return False, f"Unreachable: {str(e)[:60]}"

        ok, msg = _verify(self.access_token)
        if ok:
            return True, msg

        if msg == "expired":
            # Try silent auto-refresh before giving up
            log.info("  🔄 LinkedIn token expired — attempting silent refresh…")
            try:
                from auth.linkedin import try_auto_refresh
                new_token = try_auto_refresh()
                if new_token:
                    self.access_token = new_token
                    ok2, msg2 = _verify(new_token)
                    if ok2:
                        log.info("  ✓ LinkedIn token refreshed automatically")
                        return True, msg2 + " (auto-refreshed)"
            except Exception as e:
                log.warning(f"  ⚠ Auto-refresh failed: {e}")
            return False, "Token expired or revoked — run: python auth/linkedin.py --refresh"

        return False, msg

    @with_retry(max_retries=2, delay=5)
    def post(self, copy: dict, post: dict, db_row=None):
        if db_row and db_row["linkedin_status"] not in ("pending", "failed"):
            log.info("  ⏭ LinkedIn: not pending — skipping")
            return "already_posted"

        if not self.access_token or self.access_token == "your_access_token_here":
            log.error("  ✗ LINKEDIN_ACCESS_TOKEN not set — skipping LinkedIn")
            if db_row:
                update_social_status(db_row["wp_post_id"], "linkedin", "failed")
            return None

        li      = copy.get("linkedin", {})
        text    = f"{li.get('hook', '')}\n\n{li.get('body', '')}\n\n{li.get('cta', '')}"
        text    = text[:2900]

        article_url = post.get("link", "")
        title       = re.sub(r"<[^>]+>", "", post["title"]["rendered"])

        authors_to_try = []
        if self.org_urn:
            authors_to_try.append(("company page", self.org_urn))
        if self.person_urn:
            authors_to_try.append(("personal profile", self.person_urn))

        if not authors_to_try:
            log.error("  ✗ No LinkedIn author URN configured")
            if db_row:
                update_social_status(db_row["wp_post_id"], "linkedin", "failed")
            return None

        headers = {
            "Authorization":             f"Bearer {self.access_token}",
            "Content-Type":              "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        }

        for label, author_urn in authors_to_try:
            post_text = text
            if "person" in author_urn and self.display_name not in post_text:
                post_text += f"\n\n📍 {self.display_name} | {self.site_url}"

            payload = {
                "author":         author_urn,
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary":    {"text": post_text},
                        "shareMediaCategory": "ARTICLE",
                        "media": [{
                            "status":      "READY",
                            "description": {"text": title[:200]},
                            "originalUrl": article_url,
                            "title":       {"text": title[:200]},
                        }],
                    }
                },
                "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
            }

            r = requests.post(
                "https://api.linkedin.com/v2/ugcPosts",
                headers=headers,
                json=payload,
                timeout=20,
            )

            if r.status_code == 201:
                post_id  = r.headers.get("X-RestLi-Id", "unknown")
                post_url = f"https://www.linkedin.com/feed/update/{post_id}/"
                log.info(f"  ✅ LinkedIn published as {label} → {post_url}")
                if db_row:
                    update_social_status(db_row["wp_post_id"], "linkedin", "published")
                return post_url
            elif r.status_code in (401, 403):
                log.warning(f"  ⚠ {label} auth failed ({r.status_code}) — trying next author")
                continue
            else:
                log.error(f"  ✗ LinkedIn failed {r.status_code}: {r.text[:200]}")
                if db_row:
                    update_social_status(db_row["wp_post_id"], "linkedin", "failed")
                return None

        log.error("  ✗ LinkedIn: all author URNs failed")
        if db_row:
            update_social_status(db_row["wp_post_id"], "linkedin", "failed")
        return None
