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
│   ├── copy.py             ← AI-generated platform-specific copy (Haiku)
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
# All pipelines go through run.py
python run.py --site growstreammedia --pipeline daily_news
python run.py --site growstreammedia --pipeline hot_takes
python run.py --site growstreammedia --pipeline translated
python run.py --site growstreammedia --pipeline follow_the_money
python run.py --site growstreammedia --pipeline dumbest_move
python run.py --site growstreammedia --pipeline leaderboards

# Social media posting
python run.py --site growstreammedia --pipeline social                                    # process pending queue
python run.py --site growstreammedia --pipeline social --url https://site.com/article/   # force-post a URL

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
| 2 | Dr. Sarah Chen | **Haiku** | Story ranking by market relevance + virality |
| 3 | Marcus Webb | **Haiku** | Fact-check & credibility gate |
| 4 | Priya Sharma | Sonnet | Editorial review (SEO + quality gate) |
| 5 | Jordan Blake | Haiku / Sonnet | Article writing (Haiku draft → Sonnet revision only if scores < 8/8) |

> **Model selection rationale:** Agents 2 and 3 perform structured JSON classification tasks (scoring/approving headlines) that don't need Sonnet's reasoning depth. Agent 4 stays on Sonnet because it reviews full article quality. Agent 5 uses Haiku for the initial draft and only escalates to Sonnet when the editorial score falls below threshold — skipping the most expensive call in most runs.

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

## Publishing to LinkedIn

LinkedIn posts are AI-generated by Jordan Blake (Haiku) with a hook, body, and CTA, then posted via the LinkedIn UGC API. The poster tries your **company page** first, falls back to your **personal profile** if the org post fails.

### Step 1 — Create a LinkedIn Developer App

1. Go to [linkedin.com/developers](https://www.linkedin.com/developers/) and click **Create App**
2. Link the app to your LinkedIn **company page** (required for org posting)
3. Under **Products**, request access to:
   - **Share on LinkedIn** — grants `w_member_social` scope (personal profile posts)
   - **Community Management API** — grants `w_organization_social` scope (company page posts)
4. Under **Auth** → **OAuth 2.0 settings**, add this exact redirect URL:
   ```
   http://localhost:8080/callback
   ```
5. Copy your **Client ID** and **Client Secret** from the Auth tab

### Step 2 — Get your access token

Add your app credentials to `.env`:

```env
LINKEDIN_CLIENT_ID=86abc123...
LINKEDIN_CLIENT_SECRET=xyz456...
```

Then run the one-time OAuth flow:

```bash
python auth/linkedin.py
```

A browser window opens. Sign in to LinkedIn and approve the permissions. On success the terminal prints your token. Copy it into `.env`:

```env
LINKEDIN_ACCESS_TOKEN=AQV...
```

> Tokens expire after ~60 days. Re-run `python auth/linkedin.py` to refresh.

### Step 3 — Find your URNs

**Person URN** (personal profile):

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://api.linkedin.com/v2/userinfo
```

Look for the `"sub"` field and format it as `urn:li:person:<sub>`.

**Org URN** (company page):

Find the numeric ID in your company page URL:
`https://www.linkedin.com/company/12345678/`
Format: `urn:li:organization:12345678`

### Step 4 — Add URNs to `.env`

```env
LINKEDIN_ORG_URN=urn:li:organization:12345678
LINKEDIN_PERSON_URN=urn:li:person:abc123def
```

You only need one URN. If both are set, the company page is tried first with automatic fallback to the personal profile.

### Step 5 — Post to LinkedIn

```bash
# Process the pending queue (articles queued automatically after publishing):
python run.py --site growstreammedia --pipeline social

# Force-post a specific article URL right now:
python run.py --site growstreammedia --pipeline social --url https://growstreammedia.com/your-article/
```

### What gets posted

Each LinkedIn post is structured as:

- **Hook** — 2 scroll-stopping opening lines, no emoji on the first line
- **Body** — 3–4 short paragraphs with a contrarian angle, ends with a discussion question (max 1,200 chars)
- **CTA** — one-line link to the article

The article URL is attached as a LinkedIn article card showing the title and meta description.

### Troubleshooting

| Error | Fix |
|-------|-----|
| `401 Unauthorized` | Token expired — re-run `python auth/linkedin.py` |
| `403 Forbidden` on org post | App missing `w_organization_social` — request the Community Management API product in your developer app settings |
| `LINKEDIN_ACCESS_TOKEN not set` | Add the token to `.env` |
| Post silently skipped | Article already posted to that platform — check the `social_queue` table in the DB |

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
| Per article | ~$0.016 |
| Per day (5 articles) | ~$0.08 |
| Per month | ~$2.40 |

**How costs are minimised:**

- Story ranking and fact-checking run on Haiku (12× cheaper than Sonnet for classification tasks)
- The Sonnet revision pass is skipped when the Haiku draft already scores ≥ 8/8 on SEO + quality
- The editor receives plain text (HTML stripped) capped at 6,000 chars instead of 20,000 chars of raw HTML
- Story picker calls in `hot_takes` and `dumbest_move` run on Haiku
- Social copy generation (LinkedIn, X, Facebook) runs entirely on Haiku
- All SEO metadata (keyword, title, meta description) runs on Haiku

---

## Design Principles

- **Site isolation** — Each `SiteConfig` carries its own WP credentials, feeds, categories, social tokens, and DB path. Two sites never share state.
- **Generic agents** — Agent functions receive feeds/categories as parameters, never importing site-specific globals.
- **Classed publishers & social posters** — `WordPressClient`, `LinkedInPoster`, etc. are instantiated per-site, making it safe to run multiple sites in the same process.
- **Global infrastructure** — `CLAUDE_API_KEY` and `UNSPLASH_API_KEY` are the only truly global values (same API, same billing).
- **Preflight first** — No LLM tokens are spent until all services are confirmed reachable.
- **Right model for the job** — Classification and selection tasks use Haiku; long-form creative writing uses Sonnet. Never use Sonnet where Haiku is sufficient.
