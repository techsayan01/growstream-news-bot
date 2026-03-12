"""
Social Media Queue Pipeline.

Reads pending posts from the DB and dispatches them to LinkedIn, X, and Facebook.
Can also force-post a specific WordPress article URL.
"""

from datetime import datetime

from core.db import get_pending_social_posts
from core.utils import log
from pipelines.base import Pipeline
from publishing.wordpress.client import WordPressClient
from sites.base import SiteConfig
from social.copy import generate_social_copy
from social.facebook import FacebookPoster
from social.linkedin import LinkedInPoster
from social.twitter import TwitterPoster


class SocialPipeline(Pipeline):
    """Posts queued or specified articles to all configured social platforms."""

    def __init__(self, site: SiteConfig):
        super().__init__(site)
        self.wp = WordPressClient(site.wp_url, site.wp_username, site.wp_password, site.wp_api_key)

        self.linkedin = LinkedInPoster(
            access_token=site.linkedin_access_token,
            org_urn=site.linkedin_org_urn,
            person_urn=site.linkedin_person_urn,
            display_name=site.display_name,
            site_url=site.site_url,
        ) if site.linkedin_access_token else None

        self.twitter = TwitterPoster(
            api_key=site.twitter_api_key,
            api_secret=site.twitter_api_secret,
            access_token=site.twitter_access_token,
            access_secret=site.twitter_access_secret,
        ) if site.twitter_api_key else None

        self.facebook = FacebookPoster(
            page_id=site.fb_page_id,
            page_access_token=site.fb_page_access_token,
        ) if site.fb_page_access_token else None

    def run(self, post_url: str | None = None) -> None:
        log.info("=" * 60)
        log.info(f"  {self.site.display_name} — Auto-Social Queue Processor")
        log.info(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        log.info("=" * 60)

        if post_url:
            log.info(f"  🎯 Forcing post of URL: {post_url}")
            post = self.wp.fetch_post_by_url(post_url)
            if post:
                self._process_post(post)
        else:
            pending = get_pending_social_posts()
            if not pending:
                log.info("  ⏭ No pending articles in social queue")
                return
            log.info(f"  📋 Found {len(pending)} pending article(s) in queue")
            for row in pending:
                post = self.wp.fetch_post_by_id(row["wp_post_id"])
                if post:
                    self._process_post(post, row)

    def _process_post(self, post: dict, db_row=None) -> None:
        log.info(f"  ✓ Article: '{post['title']['rendered'][:60]}...'")

        # Auth preflight — only generate AI copy if at least one platform is reachable
        platforms = [
            ("LinkedIn",  self.linkedin),
            ("X",         self.twitter),
            ("Facebook",  self.facebook),
        ]
        viable = []
        for name, poster in platforms:
            if poster is None:
                log.info(f"  ⏭ {name}: not configured")
                continue
            ok, msg = poster.check_auth()
            if ok:
                viable.append(name)
                log.info(f"  ✓ {name}: {msg}")
            else:
                log.warning(f"  ⚠ {name}: {msg} — skipping")

        if not viable:
            log.error("  ✗ No social platforms available — skipping AI copy generation")
            return

        log.info(f"  ✍ Generating social copy for {', '.join(viable)}…")
        copy = generate_social_copy(post)

        log.info("\n  📤 Publishing to platforms…")

        def fmt(res) -> str:
            if res == "already_posted": return "⏭ skipped (already posted)"
            return "✅ published" if res else "✗ failed / skipped"

        li_url = self.linkedin.post(copy, post, db_row) if self.linkedin else None
        tw_ids = self.twitter.post(copy, post, db_row) if self.twitter else None
        fb_id  = self.facebook.post(copy, post, db_row) if self.facebook else None

        if not self.linkedin:
            log.info("  ⏭ LinkedIn: not configured")
        if not self.twitter:
            log.info("  ⏭ X: not configured")
        if not self.facebook:
            log.info("  ⏭ Facebook: not configured")

        log.info("\n  📊 Social publish summary:")
        log.info(f"     LinkedIn : {fmt(li_url)}")
        log.info(f"     X        : {fmt(tw_ids)}")
        log.info(f"     Facebook : {fmt(fb_id)}")
        log.info("-" * 40)


def run(site: SiteConfig, post_url: str | None = None) -> None:
    SocialPipeline(site).run(post_url)
