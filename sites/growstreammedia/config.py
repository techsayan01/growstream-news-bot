"""
GrowStream Media — site configuration.

Reads credentials from environment variables (set in .env or exported in shell).
Import `SITE` wherever a SiteConfig is needed for growstreammedia.
"""

import os
from pathlib import Path

# Load .env (project root takes priority, then legacy growstream/.env)
try:
    from dotenv import load_dotenv
    for _p in [
        Path(__file__).parent.parent.parent / ".env",
        Path(__file__).parent.parent.parent / "growstream" / ".env",
    ]:
        if _p.exists():
            load_dotenv(dotenv_path=_p, override=True)
            break
except ImportError:
    pass

from sites.base import SiteConfig
from sites.growstreammedia.feeds import CATEGORIES, CATEGORY_FEEDS, FALLBACK_FEEDS

SITE = SiteConfig(
    # Identity
    name="growstreammedia",
    display_name="GrowStream Media",
    site_url="https://growstreammedia.com",

    # WordPress
    wp_url=os.environ.get("WP_URL", "https://growstreammedia.com"),
    wp_username=os.environ.get("WP_USERNAME", "newsbot"),
    wp_password=os.environ.get("WP_PASSWORD", ""),
    wp_api_key=os.environ.get("WP_API_KEY", ""),

    # Content sources
    categories=CATEGORIES,
    category_feeds=CATEGORY_FEEDS,
    fallback_feeds=FALLBACK_FEEDS,

    # Database (MongoDB Atlas — db name per site)
    db_name="growstreammedia",

    # LinkedIn
    linkedin_access_token=os.environ.get("LINKEDIN_ACCESS_TOKEN", ""),
    linkedin_org_urn=os.environ.get("LINKEDIN_ORG_URN", "urn:li:organization:105025230"),
    linkedin_person_urn=os.environ.get("LINKEDIN_PERSON_URN", ""),

    # Twitter/X (add credentials to .env when ready)
    twitter_api_key=os.environ.get("TWITTER_API_KEY", ""),
    twitter_api_secret=os.environ.get("TWITTER_API_SECRET", ""),
    twitter_access_token=os.environ.get("TWITTER_ACCESS_TOKEN", ""),
    twitter_access_secret=os.environ.get("TWITTER_ACCESS_SECRET", ""),

    # Facebook (add credentials to .env when ready)
    fb_page_id=os.environ.get("FB_PAGE_ID", ""),
    fb_page_access_token=os.environ.get("FB_PAGE_ACCESS_TOKEN", ""),
)
