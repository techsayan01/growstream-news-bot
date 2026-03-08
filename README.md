# GrowStream News Bot

An autonomous multi-agent news bot that researches, writes, edits, and publishes AI finance articles to WordPress — daily, weekly, and monthly.

---

## How It Works

Each pipeline runs a team of five AI agents in sequence:

| Agent | Name | Role | Model |
|---|---|---|---|
| 1 | **Alex Rivera** | RSS Research | — |
| 2 | **Dr. Sarah Chen** | Story Ranking & Picking | Claude Sonnet |
| 3 | **Marcus Webb** | Fact-Check Gate | Claude Sonnet |
| 4 | **Jordan Blake** | Article Writer | Claude Haiku / Sonnet |
| 5 | **Priya Sharma** | SEO & Quality Editor | Claude Sonnet |

---

## Pipelines

### Daily — Main News (`python main.py`)
The flagship pipeline. Runs across 5 WordPress categories: AI in Banking, Fintech News, Investment AI, Regulatory Updates, Tool Reviews.

**Flow per category:**
1. Alex fetches RSS stories → Sarah ranks top 3 → Marcus fact-checks
2. Duplicate check against WordPress (last 7 days by focus keyword)
3. Jordan writes the article → Priya reviews (up to 3 revision passes)
4. Published to WordPress with deduplicated Unsplash hero image

**Every article includes:**
- ⏳ **15 Sec Read** — 3-bullet scannable summary at the top
- 🏆📉 **Winner / Loser Box** — two-column callout naming the story's clear winner and loser
- 🌏🌍🌎 **Global Market Angles** — dedicated Asia / Europe / US sub-sections with named companies & regulators
- 🔄 **The Contrarian Take** — challenges the consensus view
- Blockquotes for key quotes, bolded financial figures, styled Bottom Line box
- FAQ section (3 items)

**Headlines** are generated with a contrarian framing strategy:  
*"Why X Won't Work" / "Everyone's Wrong About X" / "The Real Winner Is..."*

---

### Daily — Hot Takes (`python hot_takes.py`)
One 80–100 word punchy opinion post. No editor review. Just the take.

- Scans all category feeds, Sarah picks the most debate-worthy story
- Jordan writes in tweet energy — bold claim, 2-3 supporting sentences, one quotable line
- Published in a dark-styled callout box to the `hot-takes` category

---

### Daily — Translated for Humans (`python translated.py`)
Skips silently if no regulatory story is found.

Finds stories mentioning: *circular, filing, framework, directive, RBI, SEC, ECB, SEBI...*

Publishes in the format **"We Read [Document] So You Don't Have To"** with sections:
- 📄 What They Said (mocking the bureaucratic tone)
- 🤔 What It Actually Means (plain English + analogy)
- ✅ What You Should Actually Do About It (bullet list)
- 🧐 The Part They Buried (the thing in paragraph 47 that matters)
- ⚡ The Bottom Line

---

### Daily — Follow the Money (`python follow_the_money.py`)
Skips silently if no funding/M&A story is found.

Triggers on: *raised, million, billion, Series A/B/C, acquired, merger, IPO...*

Publishes an investigative-style piece tracing:
- Where the money goes (implied allocation breakdown)
- Who benefits and who doesn't (by name)
- What the deal signals about market direction
- Global ripple effect (Asia / Europe / US paragraphs)

---

### Weekly — Dumbest Move of the Week (`python dumbest_move.py`)
Run on Sundays. Publishes Monday.

Sarah picks the most questionable decision by a company, regulator, or executive from the week's news. Jordan writes a 300–400 word humorous accountability piece with:
- What happened
- What they were probably thinking (charitable reading)
- Why it backfired
- What they should have done instead
- A-F grade + *"Better luck next week."*

---

### Monthly — Leaderboards & Rankings (`python leaderboards.py`)
Run on the 1st of each month.

Auto-selects a rotating topic from 12 themes (AI bank features, funding rounds, regulatory moves, M&A activity, etc.). Publishes a styled **Top 10** ranked list with opinionated commentary per entry and a month-in-one-sentence takeaway.

---

## Setup

### Requirements
```
python 3.11+
pip install -r requirements.txt
```

### Environment Variables
Create a `.env` file:
```env
CLAUDE_API_KEY=your_anthropic_api_key
UNSPLASH_API_KEY=your_unsplash_api_key
WP_URL=https://your-site.com
WP_USERNAME=your_wp_username
WP_PASSWORD=your_wp_application_password
```

### WordPress Setup
- Enable the REST API (on by default in WordPress)
- Generate an **Application Password** under Users → Profile
- The bot will **auto-create** all required categories on first run

---

## Cron Schedule (Recommended)

```cron
# Daily — 6:00 AM IST
0 30 0 * * * cd /path/to/bot && source venv/bin/activate && python main.py
0 45 0 * * * cd /path/to/bot && source venv/bin/activate && python hot_takes.py
0 0 1 * * * cd /path/to/bot && source venv/bin/activate && python translated.py
0 15 1 * * * cd /path/to/bot && source venv/bin/activate && python follow_the_money.py

# Weekly — Every Sunday 11 PM IST (publishes Monday)
0 30 17 * * 0 cd /path/to/bot && source venv/bin/activate && python dumbest_move.py

# Monthly — 1st of month, 4 AM IST
0 30 22 28-31 * * [ "$(date +\%d)" = "01" ] && cd /path/to/bot && source venv/bin/activate && python leaderboards.py
```

---

## Project Structure

```
growstream-news-bot/
├── main.py                        # Daily news entry point
├── hot_takes.py                   # Hot Takes entry point
├── translated.py                  # Translated for Humans entry point
├── follow_the_money.py            # Follow the Money entry point
├── dumbest_move.py                # Dumbest Move entry point
├── leaderboards.py                # Leaderboards entry point
│
├── growstream/
│   ├── agents.py                  # Sarah Chen, Marcus Webb, Priya Sharma
│   ├── config.py                  # Env, logging, retry decorator, JSON utils
│   ├── feeds.py                   # Alex Rivera — RSS feeds & research agent
│   ├── images.py                  # Unsplash image fetching (deduped, shuffled)
│   ├── pipeline.py                # Main daily pipeline orchestrator
│   ├── preflight.py               # Startup checks (API keys, WP connectivity)
│   ├── publisher.py               # WordPress REST API — publish, images, categories
│   ├── seo.py                     # Jordan Blake — writer, SEO title, meta, keyword
│   │
│   └── pipelines/
│       ├── hot_takes.py
│       ├── translated.py
│       ├── follow_the_money.py
│       ├── dumbest_move.py
│       └── leaderboards.py
│
└── .env
```

---

## Content Features

| Feature | Where |
|---|---|
| 15 Sec Read summary box | Every article (top) |
| Winner / Loser callout box | Every article (below summary) |
| Global Market Angles (Asia/EU/US) | Every article |
| The Contrarian Take section | Every article |
| Contrarian headline framing | All SEO titles |
| Sharp editorial voice (Jordan Blake) | All written content |
| Image deduplication (7-day lookback) | All pipelines |
| Article deduplication (focus keyword) | Main pipeline |
| Fallback to Top 3 stories | Main pipeline |
| Auto-create WP categories | All specialist pipelines |
