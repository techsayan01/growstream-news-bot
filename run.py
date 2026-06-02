"""
Unified CLI entry point for the news bot.

Usage:
    python run.py                                          # growstreammedia daily_news
    python run.py --site growstreammedia --pipeline daily_news
    python run.py --site growstreammedia --pipeline hot_takes
    python run.py --site growstreammedia --pipeline translated
    python run.py --site growstreammedia --pipeline follow_the_money
    python run.py --site growstreammedia --pipeline dumbest_move
    python run.py --site growstreammedia --pipeline leaderboards
    python run.py --site growstreammedia --pipeline social
    python run.py --site growstreammedia --pipeline social --url https://example.com/my-post/

Adding a new site:
    1. Create sites/<sitename>/config.py with a SITE = SiteConfig(...) instance
    2. Create sites/<sitename>/feeds.py with CATEGORIES, CATEGORY_FEEDS, FALLBACK_FEEDS
    3. Register the site in the SITES dict below
    4. Run: python run.py --site <sitename> --pipeline daily_news
"""

import argparse
import sys

from core.db import configure as configure_db
from core.llm import init_client
from preflight import run_preflight
from sites.base import SiteConfig

# ── Site registry ─────────────────────────────────────────────────────────────
# Add new sites here as you create them.

def _load_sites() -> dict[str, SiteConfig]:
    from sites.growstreammedia.config import SITE as growstreammedia
    return {
        "growstreammedia": growstreammedia,
        # "mynewsite": mynewsite_site,   ← add new sites here
    }


# ── Pipeline registry ─────────────────────────────────────────────────────────

_PIPELINE_NAMES = [
    "daily_news",
    "hot_takes",
    "translated",
    "follow_the_money",
    "dumbest_move",
    "leaderboards",
    "evergreen",
    "social",
]


def _run_pipeline(pipeline_name: str, site: SiteConfig, **kwargs) -> None:
    if pipeline_name == "daily_news":
        from pipelines.daily_news import run
        run(site)
    elif pipeline_name == "hot_takes":
        from pipelines.hot_takes import run
        run(site)
    elif pipeline_name == "translated":
        from pipelines.translated import run
        run(site)
    elif pipeline_name == "follow_the_money":
        from pipelines.follow_the_money import run
        run(site)
    elif pipeline_name == "dumbest_move":
        from pipelines.dumbest_move import run
        run(site)
    elif pipeline_name == "leaderboards":
        from pipelines.leaderboards import run
        run(site)
    elif pipeline_name == "evergreen":
        from pipelines.evergreen import run
        run(site)
    elif pipeline_name == "social":
        from pipelines.social import run
        run(site, post_url=kwargs.get("url"))
    else:
        print(f"ERROR: Unknown pipeline '{pipeline_name}'. Choose from: {', '.join(_PIPELINE_NAMES)}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="News Bot — multi-site multi-pipeline content automation"
    )
    parser.add_argument(
        "--site",
        default="growstreammedia",
        help="Site to publish to (default: growstreammedia)",
    )
    parser.add_argument(
        "--pipeline",
        default="daily_news",
        help=f"Pipeline to run (default: daily_news). Options: {', '.join(_PIPELINE_NAMES)}",
    )
    parser.add_argument(
        "--url",
        default=None,
        help="For the social pipeline: force-post a specific article URL",
    )
    parser.add_argument(
        "--writer",
        default="flash",
        choices=["flash", "pro"],
        help=(
            "Writer model. 'flash' (default): gemini-2.5-flash — fast and cheap. "
            "'pro': gemini-2.5-pro → gemini-2.5-flash fallback — higher quality."
        ),
    )
    parser.add_argument(
        "--reviewer",
        default="flash",
        choices=["flash", "pro"],
        help=(
            "Reviewer model. 'flash' (default): gemini-2.5-flash — fast and cheap. "
            "'pro': gemini-2.5-pro — stricter editorial bar."
        ),
    )
    parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Skip pre-flight checks (useful for debugging)",
    )
    args = parser.parse_args()

    import os
    os.environ["NEWSBOT_WRITER"]   = args.writer
    os.environ["NEWSBOT_REVIEWER"] = args.reviewer

    # Load site config
    sites = _load_sites()
    if args.site not in sites:
        print(f"ERROR: Unknown site '{args.site}'. Available: {', '.join(sites)}")
        sys.exit(1)

    site = sites[args.site]

    # Bootstrap infrastructure
    configure_db(site.db_name)
    from core.db import log_llm_usage
    init_client(db_log_fn=log_llm_usage)

    # Pre-flight checks
    if not args.skip_preflight:
        run_preflight(site, abort_on_failure=True)

    # Run the pipeline
    _run_pipeline(args.pipeline, site, url=args.url)


if __name__ == "__main__":
    main()
