# News Bot — Multi-Site Multi-Agent Content Automation

An autonomous AI publishing system that sources, researches, writes, edits, and publishes articles using a team of 5 specialized Claude agents. Designed to run for **multiple websites** with full segregation of site configs, social posting, and pipeline types.

---

## Architecture Overview

```
run.py                      ← Unified CLI entry point (--site, --pipeline)
├── sites/                  ← One sub-package per website
│   ├── base.py             ← SiteConfig dataclass
│   └── growstreammedia/
│       ├── config.py       ← Credentials + SiteConfig instance
│       └── feeds.py        ← RSS feeds + content categories
├── agents/                 ← AI agent logic (generic, reusable across sites)
│   ├── researcher.py       ← Agent 1: RSS fetching (Alex Rivera)
│   ├── ranker.py           ← Agent 2: Story ranking (Dr. Sarah Chen)
│   ├── factchecker.py      ← Agent 3: Credibility gate (Marcus Webb)
│   ├── writer.py           ← Agent 5: Article writing (Jordan Blake)
│   └── editor.py           ← Agent 4: Editorial review (Priya Sharma)
├── content/                ← Content utilities
│   ├── images.py           ← Unsplash image fetching + deduplication
│   └── seo.py              ← Focus keyword, SEO title, meta description
├── publishing/             ← Publishing targets
│   └── wordpress/
│       ├── client.py       ← WordPress REST API client (per-site instance)
│       └── html.py         ← HTML builder + JSON-LD schema markup
├── social/                 ← Social media posting
│   ├── base.py             ← Abstract SocialPoster interface
│   ├── copy.py             ← AI-generated platform-specific copy
│   ├── linkedin.py         ← LinkedIn (company page + personal profile)
│   ├── twitter.py          ← Twitter/X thread poster
│   └── facebook.py         ← Facebook Page poster
├── pipelines/              ← Post type pipelines
│   ├── base.py             ← Abstract Pipeline base class
│   ├── daily_news.py       ← Main 5-category daily pipeline
│   ├── hot_takes.py        ← 80-100 word punchy opinion pieces
│   ├── translated.py       ← Regulatory plain-English translations
│   ├── follow_the_money.py ← Investment/funding analysis
│   ├── dumbest_move.py     ← Weekly accountability piece (Sundays)
│   ├── leaderboards.py     ← Monthly Top 10 rankings (1st of month)
│   └── social.py           ← Social media queue processor
├── core/                   ← Shared infrastructure
│   ├── llm.py              ← Anthropic client singleton + cost tracking
│   ├── db.py               ← SQLite database layer (per-site path)
│   ├── retry.py            ← @with_retry decorator
│   └── utils.py            ← Logging, safe_json_parse
├── auth/
│   └── linkedin.py         ← LinkedIn OAuth 2.0 authorization flow
├── preflight.py            ← Pre-flight health checks (takes SiteConfig)
└── data/                   ← Per-site SQLite databases (gitignored)
    └── growstreammedia.db
```

---

## Quick Start

### 1. Install dependencies

```bash
python -m venv venv
source venv/bin/activate
pip install anthropic feedparser requests httpx python-dotenv json-repair
```

### 2. Configure credentials

Create `.env` in the project root:

```env
# Required (global)
CLAUDE_API_KEY=sk-ant-...
UNSPLASH_API_KEY=...

# Required (GrowStream Media site)
WP_URL=https://growstreammedia.com
WP_USERNAME=newsbot
WP_PASSWORD=your-app-password

# Optional — LinkedIn social posting
LINKEDIN_CLIENT_ID=...
LINKEDIN_CLIENT_SECRET=...
LINKEDIN_ACCESS_TOKEN=...
LINKEDIN_ORG_URN=urn:li:organization:...
LINKEDIN_PERSON_URN=urn:li:person:...

# Optional — Twitter/X
TWITTER_API_KEY=...
TWITTER_API_SECRET=...
TWITTER_ACCESS_TOKEN=...
TWITTER_ACCESS_SECRET=...

# Optional — Facebook
FB_PAGE_ID=...
FB_PAGE_ACCESS_TOKEN=...
```

### 3. Run

```bash
# Full CLI
python run.py --site growstreammedia --pipeline daily_news

# Shortcut aliases (backward-compatible)
python main.py            # daily_news
python hot_takes.py
python translated.py
python follow_the_money.py
python dumbest_move.py
python leaderboards.py
python social.py                               # process pending queue
python social.py https://site.com/article/    # force-post a URL

# Developer flags
python run.py --site growstreammedia --pipeline daily_news --skip-preflight
```

---

## Adding a New Website

### Step 1 — Create the site package

```bash
mkdir -p sites/mynewsite
touch sites/mynewsite/__init__.py
```

### Step 2 — `sites/mynewsite/feeds.py`

```python
CATEGORY_FEEDS = {
    "my-category": ["https://rss.example.com/feed/"],
}
FALLBACK_FEEDS = ["https://rss.example.com/all/"]
CATEGORIES = [
    {
        "slug":        "my-category",
        "name":        "My Category",
        "keywords":    ["keyword1", "keyword2"],
        "image_style": "technology business",
        "author_id":   1,
    },
]
```

### Step 3 — `sites/mynewsite/config.py`

```python
import os
from sites.base import SiteConfig
from sites.mynewsite.feeds import CATEGORIES, CATEGORY_FEEDS, FALLBACK_FEEDS

SITE = SiteConfig(
    name="mynewsite",
    display_name="My New Site",
    site_url="https://mynewsite.com",
    wp_url=os.environ.get("MYNEWSITE_WP_URL", "https://mynewsite.com"),
    wp_username=os.environ.get("MYNEWSITE_WP_USERNAME", ""),
    wp_password=os.environ.get("MYNEWSITE_WP_PASSWORD", ""),
    categories=CATEGORIES,
    category_feeds=CATEGORY_FEEDS,
    fallback_feeds=FALLBACK_FEEDS,
    db_path="data/mynewsite.db",
    linkedin_access_token=os.environ.get("MYNEWSITE_LINKEDIN_TOKEN", ""),
)
```

### Step 4 — Register in `run.py`

```python
def _load_sites():
    from sites.growstreammedia.config import SITE as growstreammedia
    from sites.mynewsite.config import SITE as mynewsite
    return {
        "growstreammedia": growstreammedia,
        "mynewsite": mynewsite,
    }
```

### Step 5 — Run

```bash
python run.py --site mynewsite --pipeline daily_news
```

Each site gets its own isolated database at `data/<sitename>.db`. No credentials, feeds, or DB state are shared between sites.

---

## Agent Roles

| Agent | Persona | Model | Role |
|-------|---------|-------|------|
| 1 | Alex Rivera | — | RSS research & story fetching |
| 2 | Dr. Sarah Chen | Sonnet | Story ranking by market relevance + virality |
| 3 | Marcus Webb | Sonnet | Fact-check & credibility gate |
| 4 | Priya Sharma | Sonnet | Editorial review (SEO + quality gate) |
| 5 | Jordan Blake | Haiku / Sonnet | Article writing + revision passes |

---

## Pipeline Types

| Pipeline | Recommended Schedule | Description |
|----------|---------------------|-------------|
| `daily_news` | Daily | 5 full-length articles across all categories |
| `hot_takes` | Daily | 80-100 word punchy opinion piece |
| `translated` | Daily | Plain-English breakdown of regulatory documents |
| `follow_the_money` | Daily | Investigative funding/investment analysis |
| `dumbest_move` | Weekly (Sunday) | Humorous accountability piece |
| `leaderboards` | Monthly (1st) | Top 10 ranked list on rotating monthly theme |
| `social` | Post-publish | LinkedIn / X / Facebook queue processor |

---

## Social Media Architecture

Each platform is a class instantiated with credentials from `SiteConfig`:

```python
# social/linkedin.py
class LinkedInPoster(SocialPoster):
    def __init__(self, access_token, org_urn, person_urn, ...): ...
    def post(self, copy, post, db_row=None): ...

# social/twitter.py
class TwitterPoster(SocialPoster): ...

# social/facebook.py
class FacebookPoster(SocialPoster): ...
```

The `SocialPipeline` instantiates all configured platforms and runs them. Platforms with empty credentials are skipped gracefully.

---

## Database Schema

Each site gets its own SQLite database at `data/<sitename>.db`:

| Table | Purpose |
|-------|---------|
| `raw_stories` | Fetched RSS stories (deduplication by URL) |
| `published_articles` | Published post log + Unsplash image deduplication |
| `social_queue` | Pending / published / failed social posts per platform |
| `llm_metrics` | Token usage and estimated cost per agent call |

---

## LinkedIn OAuth Setup

```bash
python auth/linkedin.py
# Copy the printed LINKEDIN_ACCESS_TOKEN into your .env
```

Tokens expire after ~60 days. Re-run to refresh.

---

## GitHub Actions

Daily schedule via `.github/workflows/news_bot_production.yml` (2:00 AM UTC = 7:30 AM IST):

```yaml
schedule:
  - cron: '0 2 * * *'
```

Required GitHub Secrets: `CLAUDE_API_KEY`, `WP_USERNAME`, `WP_PASSWORD`, `UNSPLASH_API_KEY`

---

## Cost Estimate

| Scope | Approx. Cost |
|-------|-------------|
| Per article | ~$0.03 |
| Per day (5 articles) | ~$0.15 |
| Per month | ~$4.50 |

---

## Design Principles

- **Site isolation** — Each `SiteConfig` carries its own WP credentials, feeds, categories, social tokens, and DB path. Two sites never share state.
- **Generic agents** — Agent functions receive feeds/categories as parameters, never importing site-specific globals.
- **Classed publishers & social posters** — `WordPressClient`, `LinkedInPoster`, etc. are instantiated per-site, making it safe to run multiple sites in the same process.
- **Global infrastructure** — `CLAUDE_API_KEY` and `UNSPLASH_API_KEY` are the only truly global values (same API, same billing).
- **Preflight first** — No LLM tokens are spent until all services are confirmed reachable.
