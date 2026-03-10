"""
SiteConfig — base dataclass representing one website/publication.

Every field that varies between sites lives here.
Global API keys (CLAUDE_API_KEY, UNSPLASH_API_KEY) are NOT included —
they are read from the environment in their respective modules.
"""

from dataclasses import dataclass, field


@dataclass
class SiteConfig:
    # ── Identity ────────────────────────────────────────────────────────────
    name:         str   # machine-readable slug, e.g. "growstreammedia"
    display_name: str   # human label,           e.g. "GrowStream Media"
    site_url:     str   # canonical site URL,    e.g. "https://growstreammedia.com"

    # ── WordPress publishing ─────────────────────────────────────────────────
    wp_url:      str   # REST API base,          e.g. "https://growstreammedia.com"
    wp_username: str
    wp_password: str   # application password or regular password
    wp_api_key:  str = ""  # if set, uses X-Newsbot-Key header (mu-plugin auth)

    # ── Content sources (site-specific) ─────────────────────────────────────
    categories:     list[dict]        = field(default_factory=list)
    category_feeds: dict[str, list[str]] = field(default_factory=dict)
    fallback_feeds: list[str]         = field(default_factory=list)

    # ── Database ─────────────────────────────────────────────────────────────
    db_path: str = "data/newsbot.db"

    # ── Social: LinkedIn ─────────────────────────────────────────────────────
    linkedin_access_token: str = ""
    linkedin_org_urn:      str = ""
    linkedin_person_urn:   str = ""

    # ── Social: Twitter / X ──────────────────────────────────────────────────
    twitter_api_key:       str = ""
    twitter_api_secret:    str = ""
    twitter_access_token:  str = ""
    twitter_access_secret: str = ""

    # ── Social: Facebook ────────────────────────────────────────────────────
    fb_page_id:           str = ""
    fb_page_access_token: str = ""

    def validate(self) -> None:
        """Raise EnvironmentError if any required field is empty."""
        missing = [
            k for k in ("wp_url", "wp_username", "wp_password")
            if not getattr(self, k)
        ]
        if missing:
            raise EnvironmentError(
                f"Site '{self.name}' is missing required config: {', '.join(missing)}"
            )
