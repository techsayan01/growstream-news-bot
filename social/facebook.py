"""
Facebook Page social posting.

Requires FB_PAGE_ID and FB_PAGE_ACCESS_TOKEN (add to .env when ready).
"""

import requests

from core.db import update_social_status
from core.utils import log
from social.base import SocialPoster


class FacebookPoster(SocialPoster):
    """Posts to a Facebook Page using the Graph API."""

    def __init__(self, page_id: str, page_access_token: str):
        self.page_id           = page_id
        self.page_access_token = page_access_token

    @property
    def platform(self) -> str:
        return "facebook"

    def check_auth(self) -> tuple[bool, str]:
        if not self.page_access_token or not self.page_id:
            return False, "No credentials configured"
        try:
            r = requests.get(
                f"https://graph.facebook.com/v19.0/{self.page_id}",
                params={"fields": "id,name", "access_token": self.page_access_token},
                timeout=10,
            )
            if r.status_code == 200:
                name = r.json().get("name", self.page_id)
                return True, f"Authenticated as '{name}'"
            err = r.json().get("error", {}).get("message", f"HTTP {r.status_code}")
            return False, err[:80]
        except Exception as e:
            return False, str(e)[:60]

    def post(self, copy: dict, post: dict, db_row=None):
        if db_row and db_row["facebook_status"] not in ("pending", "failed"):
            log.info("  ⏭ Facebook: not pending — skipping")
            return "already_posted"

        if not self.page_access_token or not self.page_id:
            log.warning("  ⚠ Facebook credentials not set — skipping FB post")
            return None

        try:
            text = copy.get("facebook", {}).get("text", "")
            r    = requests.post(
                f"https://graph.facebook.com/v19.0/{self.page_id}/feed",
                data={"message": text, "access_token": self.page_access_token},
                timeout=20,
            )
            r.raise_for_status()
            fb_id = r.json().get("id", "")
            log.info(f"  ✅ Facebook published (ID: {fb_id})")
            if db_row:
                update_social_status(db_row["wp_post_id"], "facebook", "published")
            return fb_id
        except Exception as e:
            log.warning(f"  ⚠ Facebook post failed: {e}")
            if db_row:
                update_social_status(db_row["wp_post_id"], "facebook", "failed")
        return None
