# Project Memory — News Bot

## Architecture (v3 — current)

Full restructuring from monolithic `growstream/` package to modular multi-site framework.

### Key directories
- `core/` — Shared infrastructure: `llm.py` (Anthropic client), `db.py` (SQLite), `retry.py`, `utils.py`
- `agents/` — 5 AI agents: researcher, ranker, factchecker, writer, editor (generic, no site coupling)
- `content/` — `images.py` (Unsplash) and `seo.py` (SEO metadata)
- `publishing/wordpress/` — `WordPressClient` class + `html.py` builder
- `social/` — `LinkedInPoster`, `TwitterPoster`, `FacebookPoster` classes + AI `copy.py`
- `pipelines/` — 7 pipeline types: daily_news, hot_takes, translated, follow_the_money, dumbest_move, leaderboards, social
- `sites/` — Per-site configs: `sites/base.py` (SiteConfig dataclass), `sites/growstreammedia/` (feeds + config)
- `auth/` — `linkedin.py` OAuth helper
- `preflight.py` — Health checks, takes `SiteConfig` parameter
- `run.py` — Unified CLI (`--site`, `--pipeline`, `--url`, `--skip-preflight`)

### How to add a new site
1. `mkdir -p sites/newsite && touch sites/newsite/__init__.py`
2. Create `sites/newsite/feeds.py` (CATEGORY_FEEDS, FALLBACK_FEEDS, CATEGORIES)
3. Create `sites/newsite/config.py` (SITE = SiteConfig(...))
4. Register in `run.py` `_load_sites()` dict
5. Run: `python run.py --site newsite --pipeline daily_news`

### Startup order (run.py)
1. `configure_db(site.db_path)` — creates data/ dir and schema
2. `init_client(db_log_fn=log_llm_usage)` — init LLM client with DB cost logging
3. `run_preflight(site)` — verify all services
4. `_run_pipeline(...)` — run selected pipeline

### Per-site isolation
- Each site has its own `data/<sitename>.db` SQLite database
- `WordPressClient` is instantiated per-site with site credentials
- Social posters are classes instantiated from SiteConfig fields
- CLAUDE_API_KEY and UNSPLASH_API_KEY are global (env vars, not per-site)

### Legacy
- Old `growstream/` package moved to `_deprecated/growstream_v2_legacy/`
- Root-level `main.py`, `hot_takes.py` etc. are thin shims that call `run.py`

## Stack
- Python 3.11+, Claude API (Haiku + Sonnet), WordPress REST API, Unsplash API, SQLite
- Est. cost: ~$0.15/day for 5 articles
