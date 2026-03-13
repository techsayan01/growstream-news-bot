# News Bot — Multi-Site Multi-Agent Content Automation

An autonomous AI publishing system that sources, researches, writes, edits, and publishes articles using a team of 5 specialized AI agents. Designed to run for **multiple websites** with full segregation of site configs, social posting, and pipeline types.

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
│   ├── daily_news.py       ← Main 5-category daily pipeline (parallel)
│   ├── hot_takes.py        ← 80-100 word punchy opinion pieces
│   ├── translated.py       ← Regulatory plain-English translations
│   ├── follow_the_money.py ← Investment/funding analysis
│   ├── dumbest_move.py     ← Weekly accountability piece (Sundays)
│   ├── leaderboards.py     ← Monthly Top 10 rankings (1st of month)
│   └── social.py           ← Social media queue processor
├── core/                   ← Shared infrastructure
│   ├── llm.py              ← Claude + Gemini client layer with cost tracking
│   ├── db.py               ← SQLite database layer (per-site path)
│   ├── retry.py            ← @with_retry decorator
│   └── utils.py            ← Logging, safe_json_parse
├── auth/
│   └── linkedin.py         ← LinkedIn OAuth 2.0 authorization flow
├── preflight.py            ← Pre-flight health checks (Anthropic, Gemini, Unsplash, WP)
└── data/                   ← Per-site SQLite databases (gitignored)
    └── growstreammedia.db
```

---

## Quick Start

### 1. Install dependencies

```bash
python -m venv venv
source venv/bin/activate
pip install anthropic google-genai feedparser requests httpx python-dotenv json-repair
```

### 2. Configure credentials

Create `.env` in the project root:

```env
# Required — Anthropic (fact-check, rank, social copy, SEO metadata)
CLAUDE_API_KEY=sk-ant-...

# Required — Google Gemini (article writing + editorial review)
# Get your API key from https://aistudio.google.com/app/apikey
GEMINI_API_KEY=AIza...

# Required — Unsplash
UNSPLASH_API_KEY=...

# Required — WordPress
WP_URL=https://yoursite.com
WP_USERNAME=newsbot
WP_PASSWORD=your-app-password

# Optional — LinkedIn social posting
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

## Agent Roles

| Agent | Persona | Model | Role |
|-------|---------|-------|------|
| 1 | Alex Rivera | — | RSS research & story fetching |
| 2 | Dr. Sarah Chen | **Haiku** | Story ranking by market relevance + virality |
| 3 | Marcus Webb | **Haiku** | Fact-check & credibility gate |
| 4 | Priya Sharma | **Gemini 3.0 Flash** | Editorial review (SEO + quality gate) |
| 5 | Jordan Blake | **Gemini 2.5 Flash** | Article writing (initial draft + revisions) |

> **Model selection rationale:** Agents 2 and 3 perform structured JSON classification on short inputs — Haiku is sufficient and cheap. Agent 5 uses Gemini 2.5 Flash for full HTML article generation (high output volume, cost-sensitive). Agent 4 uses Gemini 3.0 Flash for editorial review (structured JSON scoring with detailed feedback).

---

## Pipeline Types

| Pipeline | Recommended Schedule | Description |
|----------|---------------------|-------------|
| `daily_news` | Daily | 5 full-length articles across all categories (runs in parallel) |
| `hot_takes` | Daily | 80-100 word punchy opinion piece |
| `translated` | Daily | Plain-English breakdown of regulatory documents |
| `follow_the_money` | Daily | Investigative funding/investment analysis |
| `dumbest_move` | Weekly (Sunday) | Humorous accountability piece |
| `leaderboards` | Monthly (1st) | Top 10 ranked list on rotating monthly theme |
| `social` | Post-publish | LinkedIn / X / Facebook queue processor |

---

## Daily News Pipeline — How It Works

Each run processes all 5 categories **in parallel** (max 3 concurrent threads):

```
For each category (parallel):
  1. Research    — fetch RSS stories matching category keywords
  2. Rank        — score top 5 by market relevance + virality (Haiku)
  3. Dedup       — skip if focus keyword published in last 30 days
  4. Fact-check  — credibility gate (Haiku)
  5. Write       — full HTML article, Gemini 2.5 Flash, up to 4096 tokens
  6. Review loop — Gemini 3.0 Flash scores SEO + quality (max 3 revisions)
     ↳ Truncation pre-check: if article is cut off mid-sentence,
       send directly to rewrite without spending a review call
  7. Publish     — upload image, post to WordPress, queue social
```

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
| `llm_metrics` | Token usage and estimated cost per agent call (both Claude and Gemini) |

---

## GitHub Actions

Daily schedule via `.github/workflows/news_bot_production.yml` (2:00 AM UTC = 7:30 AM IST):

```yaml
schedule:
  - cron: '0 2 * * *'
```

Required GitHub Secrets: `CLAUDE_API_KEY`, `GEMINI_API_KEY`, `WP_USERNAME`, `WP_PASSWORD`, `UNSPLASH_API_KEY`

---

## Cost Estimate

| Agent | Model | Daily tokens (approx.) | Daily cost |
|-------|-------|----------------------|-----------|
| Writer (Agent 5) | Gemini 2.5 Flash | 124K in / 114K out | ~$0.087 |
| Editor (Agent 4) | Gemini 3.0 Flash | 83K in / 23K out | ~$0.026 |
| Ranker + Fact-checker + SEO | Claude Haiku | ~60K in / 30K out | ~$0.055 |
| **Total** | | | **~$0.17/day · ~$5/month** |

**How costs are minimised:**

- Story ranking, fact-checking, and all SEO metadata run on Claude Haiku (cheapest classification model)
- Article writing and editorial review use Gemini 2.5 / 3.0 Flash (93% cheaper than Sonnet for the same tasks)
- Truncation pre-check skips the editorial review call entirely when an article is obviously cut off mid-sentence
- Categories run in parallel — 3 concurrent threads cut wall-clock time from ~25 min to ~8 min without increasing token spend
- Dedup check runs before fact-checking to avoid spending tokens on stories that will be skipped

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

## Design Principles

- **Site isolation** — Each `SiteConfig` carries its own WP credentials, feeds, categories, social tokens, and DB path. Two sites never share state.
- **Generic agents** — Agent functions receive feeds/categories as parameters, never importing site-specific globals.
- **Classed publishers & social posters** — `WordPressClient`, `LinkedInPoster`, etc. are instantiated per-site, making it safe to run multiple sites in the same process.
- **Multi-provider LLM layer** — `core/llm.py` routes `gemini-*` calls to Google and `claude-*` calls to Anthropic via a unified `call_llm()` interface with cost tracking for both.
- **Preflight first** — No LLM tokens are spent until all services (Anthropic, Gemini, Unsplash, WordPress) are confirmed reachable.
- **Right model for the job** — Classification tasks use Haiku; long-form generation uses Gemini Flash. Sonnet is reserved for tasks where quality justifies the cost.
- **Parallel categories** — The daily news pipeline runs all 5 categories concurrently (ThreadPoolExecutor, max 3 workers) to reduce wall-clock time by ~3×.
