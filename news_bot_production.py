"""
GrowStream Media — Multi-Agent News System (Production Ready)
=============================================================
Agent 1: Research Agent   — FREE RSS feeds with retry
Agent 2: Summary Agent    — Claude Sonnet ranks by market trend
Agent 3: Fact-Check Agent — Claude Sonnet verifies + selects best
Image Agent              — Unsplash free API (3 images per article)
Publisher                — Claude Haiku rewrites + posts to WordPress

Cost: ~$3.50/month | Output: 5 articles/day, 1 per category
Error handling: Retries, fallbacks, graceful degradation
"""

import anthropic
import feedparser
import requests
import json
import os
import base64
import random
import time
import logging
from datetime import datetime
from functools import wraps

# ============================================================
# LOGGING SETUP
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f"growstream_{datetime.now().strftime('%Y%m%d')}.log")
    ]
)
log = logging.getLogger("GrowStream")

# ============================================================
# CONFIGURATION
# ============================================================
CLAUDE_API_KEY   = os.environ.get("CLAUDE_API_KEY", "")
UNSPLASH_API_KEY = os.environ.get("UNSPLASH_API_KEY", "")
WP_URL           = "https://growstreammedia.com"
WP_USERNAME      = os.environ.get("WP_USERNAME", "newsbot")
WP_PASSWORD      = os.environ.get("WP_PASSWORD", "")

# Retry settings
MAX_RETRIES     = 3
RETRY_DELAY     = 5   # seconds between retries
REQUEST_TIMEOUT = 15  # seconds for HTTP requests

# Validate required env vars on startup
def validate_config():
    missing = []
    if not CLAUDE_API_KEY:   missing.append("CLAUDE_API_KEY")
    if not UNSPLASH_API_KEY: missing.append("UNSPLASH_API_KEY")
    if not WP_USERNAME:      missing.append("WP_USERNAME")
    if not WP_PASSWORD:      missing.append("WP_PASSWORD")
    if missing:
        log.error(f"Missing environment variables: {', '.join(missing)}")
        raise EnvironmentError(f"Missing required config: {', '.join(missing)}")
    log.info("✓ Configuration validated")

client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)

# ============================================================
# RETRY DECORATOR
# ============================================================
def with_retry(max_retries=MAX_RETRIES, delay=RETRY_DELAY, fallback=None):
    """Decorator: retry a function up to max_retries times with delay."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(1, max_retries + 1):
                try:
                    result = func(*args, **kwargs)
                    if result is not None:
                        return result
                    raise ValueError("Function returned None")
                except Exception as e:
                    last_error = e
                    if attempt < max_retries:
                        log.warning(f"  ⚠ {func.__name__} attempt {attempt}/{max_retries} failed: {e}. Retrying in {delay}s...")
                        time.sleep(delay)
                    else:
                        log.error(f"  ✗ {func.__name__} failed after {max_retries} attempts: {e}")
            return fallback() if callable(fallback) else fallback
        return wrapper
    return decorator


def safe_json_parse(raw_text):
    """Safely parse JSON from Claude response, stripping markdown if needed."""
    text = raw_text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.startswith("json"):
            text = text[4:]
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError as e:
        log.error(f"JSON parse error: {e} | Raw: {text[:200]}")
        return None


# ============================================================
# RSS FEEDS — mapped per category (all free)
# ============================================================
CATEGORY_FEEDS = {
    "ai-in-banking": [
        "https://www.finextra.com/rss/channel.aspx?channel=ai",
        "https://www.bankingtech.com/feed/",
        "https://feeds.feedburner.com/venturebeat/SZYF",
        "https://www.pymnts.com/feed/",
    ],
    "fintech-news": [
        "https://techcrunch.com/category/fintech/feed/",
        "https://www.finextra.com/rss/headlines.aspx",
        "https://www.pymnts.com/feed/",
        "https://feeds.reuters.com/reuters/businessNews",
    ],
    "investment-ai": [
        "https://feeds.bloomberg.com/markets/news.rss",
        "https://feeds.reuters.com/reuters/businessNews",
        "https://feeds.feedburner.com/venturebeat/SZYF",
        "https://www.investing.com/rss/news.rss",
    ],
    "regulatory-updates": [
        "https://feeds.reuters.com/reuters/businessNews",
        "https://www.finextra.com/rss/channel.aspx?channel=regulation",
        "https://feeds.bloomberg.com/markets/news.rss",
        "https://techcrunch.com/feed/",
    ],
    "tool-reviews": [
        "https://feeds.feedburner.com/venturebeat/SZYF",
        "https://techcrunch.com/feed/",
        "https://www.artificialintelligence-news.com/feed/",
        "https://feeds.reuters.com/reuters/technologyNews",
    ],
}

# Fallback feeds used if primary feeds return nothing
FALLBACK_FEEDS = [
    "https://techcrunch.com/feed/",
    "https://feeds.reuters.com/reuters/businessNews",
    "https://feeds.feedburner.com/venturebeat/SZYF",
]

# ============================================================
# CATEGORIES
# ============================================================
CATEGORIES = [
    {
        "slug": "ai-in-banking",
        "name": "AI in Banking",
        "keywords": ["bank", "banking", "financial institution", "credit", "loan", "ai", "machine learning"],
        "image_style": "banking technology finance digital",
    },
    {
        "slug": "fintech-news",
        "name": "Fintech News",
        "keywords": ["fintech", "payment", "neobank", "digital wallet", "startup", "funding", "raised"],
        "image_style": "fintech mobile payment startup technology",
    },
    {
        "slug": "investment-ai",
        "name": "Investment AI",
        "keywords": ["invest", "stock", "portfolio", "hedge fund", "trading", "market", "fund", "ai"],
        "image_style": "stock market investment trading data analytics",
    },
    {
        "slug": "regulatory-updates",
        "name": "Regulatory Updates",
        "keywords": ["regulation", "sec", "rbi", "compliance", "policy", "law", "regulatory", "ban"],
        "image_style": "regulation law compliance government policy",
    },
    {
        "slug": "tool-reviews",
        "name": "Tool Reviews",
        "keywords": ["tool", "platform", "software", "app", "launch", "product", "release", "ai"],
        "image_style": "software technology product interface dashboard",
    },
]


# ============================================================
# AGENT 1: RESEARCH AGENT — Free RSS feeds
# ============================================================
def research_agent(category):
    """Pull latest stories from RSS feeds. Falls back to generic feeds if needed."""
    log.info(f"🔍 [Agent 1] Fetching RSS for: {category['name']}")

    feeds = CATEGORY_FEEDS[category["slug"]]
    stories = _fetch_from_feeds(feeds, category["keywords"])

    # Fallback: if too few stories, try generic feeds
    if len(stories) < 3:
        log.warning(f"  ⚠ Only {len(stories)} stories found. Trying fallback feeds...")
        fallback_stories = _fetch_from_feeds(FALLBACK_FEEDS, category["keywords"])
        stories = stories + fallback_stories

    if not stories:
        log.error(f"  ✗ No stories found for {category['name']} from any feed")
        return None

    # Deduplicate and shuffle
    seen, unique = set(), []
    for s in stories:
        key = s["headline"][:40].lower()
        if key not in seen:
            seen.add(key)
            unique.append(s)

    random.shuffle(unique)
    result = unique[:10]
    log.info(f"  ✓ {len(result)} unique stories found")
    return result


def _fetch_from_feeds(feeds, keywords):
    """Helper: fetch and filter stories from a list of RSS feeds."""
    stories = []
    for feed_url in feeds:
        try:
            feed = feedparser.parse(feed_url)
            if feed.bozo:  # feedparser marks malformed feeds
                log.warning(f"  ⚠ Malformed feed: {feed_url[:50]}")
                continue
            for entry in feed.entries[:8]:
                title   = entry.get("title", "").strip()
                summary = (entry.get("summary") or entry.get("description") or "").strip()
                link    = entry.get("link", "")
                if not title or not summary or len(summary) < 80:
                    continue
                text = (title + " " + summary).lower()
                if not any(kw in text for kw in keywords):
                    continue
                stories.append({
                    "headline": title,
                    "summary":  summary[:1500],
                    "url":      link,
                    "source":   feed.feed.get("title", "Unknown"),
                })
        except Exception as e:
            log.warning(f"  ⚠ Feed error ({feed_url[:40]}): {e}")
    return stories


# ============================================================
# AGENT 2: SUMMARY AGENT — Claude Sonnet with retry
# ============================================================
@with_retry(max_retries=3, delay=5)
def summary_agent(stories, category):
    """Score and rank stories by market trend relevance."""
    log.info(f"📊 [Agent 2] Ranking {len(stories)} stories for {category['name']}")

    stories_json = json.dumps([{
        "headline": s["headline"],
        "summary":  s["summary"][:500],
        "source":   s["source"],
        "url":      s["url"],
    } for s in stories], indent=2)

    prompt = f"""You are a financial analyst scoring news for the '{category['name']}' section of GrowStream Media.

Score each story's MARKET TREND RELEVANCE (1-10) based on:
- Impact on financial markets and businesses
- Relevance to CFOs, investors, finance professionals
- Timeliness and breaking nature

For each story identify the market trend:
AI Infrastructure Boom | Fintech Disruption | Regulatory Crackdown | Investment AI | Banking Transformation

Stories:
{stories_json}

Select the SINGLE BEST story. Return ONLY this JSON object, no markdown:
{{
  "best_story": {{
    "headline": "...",
    "summary": "...",
    "source": "...",
    "url": "...",
    "market_trend": "...",
    "market_relevance_score": 9,
    "key_facts": ["fact1", "fact2", "fact3"]
  }}
}}"""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )
    result = safe_json_parse(response.content[0].text)
    if not result or "best_story" not in result:
        raise ValueError("Invalid summary response structure")

    story = result["best_story"]
    log.info(f"  ✓ Score: {story.get('market_relevance_score','?')}/10 | {story.get('market_trend','')}")
    return result


# ============================================================
# AGENT 3: FACT-CHECK AGENT — Claude Sonnet with retry
# ============================================================
@with_retry(max_retries=3, delay=5)
def factcheck_agent(best_story, category):
    """Verify story and extract image keywords."""
    log.info(f"✅ [Agent 3] Fact-checking for {category['name']}")

    prompt = f"""You are a fact-checking editor at GrowStream Media.

Review this story for the '{category['name']}' section:
{json.dumps(best_story, indent=2)}

Check credibility, internal consistency, and suitability for business professionals.

Return ONLY this JSON object, no markdown:
{{
  "approved": true,
  "credibility_score": 8,
  "fact_check_notes": "One sentence on credibility",
  "suggested_angle": "Specific angle for finance professionals",
  "image_keywords": ["keyword1", "keyword2", "keyword3", "keyword4"],
  "story": {{ ...all original story fields... }}
}}"""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )
    result = safe_json_parse(response.content[0].text)
    if not result:
        raise ValueError("Invalid fact-check response")

    approved = result.get("approved", False)
    score    = result.get("credibility_score", "?")
    log.info(f"  {'✓ Approved' if approved else '✗ Rejected'} — Credibility: {score}/10")
    return result


# ============================================================
# IMAGE AGENT — Unsplash with fallback keywords
# ============================================================
def fetch_unsplash_images(image_keywords, category_style, count=3):
    """Fetch 3 images with fallback to generic finance/tech terms."""
    images = []
    primary_queries = [
        " ".join(image_keywords[:2]),
        image_keywords[2] if len(image_keywords) > 2 else category_style.split()[0],
        category_style.split()[1] if len(category_style.split()) > 1 else image_keywords[0],
    ]
    fallback_queries = ["finance technology", "business data", "digital economy"]

    for i in range(count):
        query   = primary_queries[i] if i < len(primary_queries) else fallback_queries[i]
        image   = _fetch_single_image(query, i)
        if not image:
            log.warning(f"  ⚠ Primary query failed for '{query}', trying fallback")
            image = _fetch_single_image(fallback_queries[i % len(fallback_queries)], i)
        if image:
            images.append(image)

    log.info(f"  📸 {len(images)}/3 images fetched from Unsplash")
    return images


def _fetch_single_image(query, index):
    """Fetch one image from Unsplash with error handling."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(
                "https://api.unsplash.com/search/photos",
                params={"query": query, "per_page": 5,
                        "orientation": "landscape", "content_filter": "high"},
                headers={"Authorization": f"Client-ID {UNSPLASH_API_KEY}"},
                timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            results = response.json().get("results", [])
            if results:
                photo = max(results, key=lambda x: x.get("width", 0))
                # Trigger download (Unsplash API requirement)
                try:
                    requests.get(
                        photo["links"]["download_location"],
                        headers={"Authorization": f"Client-ID {UNSPLASH_API_KEY}"},
                        timeout=5
                    )
                except:
                    pass
                return {
                    "url":              photo["urls"]["regular"],
                    "alt":              photo.get("alt_description") or query,
                    "photographer":     photo["user"]["name"],
                    "photographer_url": photo["user"]["links"]["html"],
                    "is_hero":          index == 0,
                }
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                log.error("  ✗ Unsplash API key invalid or rate limited")
                return None
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
        except Exception as e:
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
            else:
                log.error(f"  ✗ Image fetch failed for '{query}': {e}")
    return None


# ============================================================
# PUBLISHER — Claude Haiku + WordPress REST API
# ============================================================
def get_wp_auth():
    credentials = f"{WP_USERNAME}:{WP_PASSWORD}"
    return {"Authorization": f"Basic {base64.b64encode(credentials.encode()).decode()}"}


def get_wp_category_id(slug):
    """Get WordPress category ID with retry."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(
                f"{WP_URL}/wp-json/wp/v2/categories?slug={slug}",
                headers=get_wp_auth(),
                timeout=REQUEST_TIMEOUT
            )
            r.raise_for_status()
            cats = r.json()
            if cats:
                return cats[0]["id"]
            log.warning(f"  ⚠ Category '{slug}' not found in WordPress")
            return None
        except Exception as e:
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
            else:
                log.error(f"  ✗ Could not fetch category ID for '{slug}': {e}")
    return None


@with_retry(max_retries=3, delay=5)
def rewrite_article(story, category, angle):
    """Rewrite story into polished article using Haiku."""
    log.info(f"  ✍️  Writing article...")
    prompt = f"""You are a senior journalist at GrowStream Media writing for the {category['name']} section.
Target audience: CFOs, investors, finance professionals.

Story:
- Headline: {story.get('headline','')}
- Market Trend: {story.get('market_trend','')}
- Summary: {story.get('summary','')}
- Key Facts: {json.dumps(story.get('key_facts',[]))}
- Angle: {angle}

Write a 300-350 word article:
[HOOK] One punchy opening sentence
[PARAGRAPH 1] The news and why it matters NOW (80 words)
[PARAGRAPH 2] Context and market implications (80 words)
[PARAGRAPH 3] Key facts and data points (80 words)
[WHAT THIS MEANS] Practical takeaway for finance professionals (60 words)

Rules: Separate paragraphs with blank line. No title. Professional tone.
Return ONLY the article body."""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )
    content = response.content[0].text.strip()
    if len(content) < 100:
        raise ValueError("Article too short — likely a bad response")
    return content


@with_retry(max_retries=2, delay=3, fallback=lambda: "Untitled Article")
def generate_seo_title(headline, market_trend):
    """Generate SEO title with fallback to original headline."""
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=80,
        messages=[{"role": "user", "content":
            f"Create one SEO headline under 65 chars with a power word. "
            f"Original: {headline}. Trend: {market_trend}. Return ONLY the headline."}]
    )
    return response.content[0].text.strip()


def upload_image_to_wordpress(image_data, title):
    """Upload image to WordPress media library with retry."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            img_response = requests.get(image_data["url"], timeout=REQUEST_TIMEOUT)
            img_response.raise_for_status()

            filename = (f"{title[:30].replace(' ','-').lower()}"
                        f"-{datetime.now().strftime('%H%M%S')}.jpg")
            response = requests.post(
                f"{WP_URL}/wp-json/wp/v2/media",
                headers={
                    **get_wp_auth(),
                    "Content-Disposition": f'attachment; filename="{filename}"',
                    "Content-Type": "image/jpeg",
                },
                data=img_response.content,
                timeout=30
            )
            if response.status_code == 201:
                media = response.json()
                return {"id": media["id"], "url": media["source_url"]}
            elif response.status_code == 401:
                log.error("  ✗ WordPress auth failed — check WP_USERNAME and WP_PASSWORD")
                return None
            else:
                log.warning(f"  ⚠ Image upload error {response.status_code}: {response.text[:100]}")
        except Exception as e:
            log.warning(f"  ⚠ Image upload attempt {attempt}/{MAX_RETRIES}: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
    log.error("  ✗ Image upload failed after all retries")
    return None


def build_html(content, images, story):
    """Build article HTML with images at strategic positions."""
    paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
    trend = story.get('market_trend', 'AI & Finance')
    score = story.get('market_relevance_score', 'N/A')

    html = (f'<p><strong>📈 {trend}</strong>'
            f' &nbsp;|&nbsp; <strong>Relevance:</strong> {score}/10</p>\n<hr/>\n')

    def img_block(img):
        return (f'<figure style="margin:24px 0;">'
                f'<img src="{img["url"]}" alt="{img["alt"]}" '
                f'style="width:100%;border-radius:8px;"/>'
                f'<figcaption style="font-size:12px;color:#888;margin-top:6px;">'
                f'Photo by <a href="{img.get("photographer_url","#")}" target="_blank">'
                f'{img.get("photographer","Unsplash")}</a> on Unsplash'
                f'</figcaption></figure>\n')

    for i, para in enumerate(paragraphs):
        html += f"<p>{para}</p>\n"
        if i == 1 and len(images) > 1:
            html += img_block(images[1])
        if i == 3 and len(images) > 2:
            html += img_block(images[2])

    return html


def publish_to_wordpress(title, html_content, category_id, featured_image_id):
    """Publish to WordPress with retry."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.post(
                f"{WP_URL}/wp-json/wp/v2/posts",
                headers={**get_wp_auth(), "Content-Type": "application/json"},
                data=json.dumps({
                    "title":          title,
                    "content":        html_content,
                    "status":         "publish",
                    "categories":     [category_id] if category_id else [],
                    "featured_media": featured_image_id or 0,
                }),
                timeout=30
            )
            if response.status_code == 201:
                return response.json().get("link", "")
            elif response.status_code == 401:
                log.error("  ✗ WordPress auth failed — check credentials")
                return None
            elif response.status_code == 403:
                log.error("  ✗ WordPress permissions denied — newsbot needs Administrator role")
                return None
            else:
                log.warning(f"  ⚠ Publish attempt {attempt}: {response.status_code} {response.text[:100]}")
        except requests.exceptions.Timeout:
            log.warning(f"  ⚠ Publish timeout attempt {attempt}/{MAX_RETRIES}")
        except Exception as e:
            log.warning(f"  ⚠ Publish attempt {attempt}: {e}")

        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY)

    log.error("  ✗ Publish failed after all retries")
    return None


# ============================================================
# MAIN PIPELINE
# ============================================================
def run():
    log.info("="*60)
    log.info("  GrowStream Media — Multi-Agent News Bot")
    log.info(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')} IST")
    log.info("  RSS feeds + Sonnet analysis + Haiku writing")
    log.info("  Est. cost: ~$0.12/day | ~$3.50/month")
    log.info("="*60)

    # Validate config before starting
    try:
        validate_config()
    except EnvironmentError as e:
        log.error(f"Startup failed: {e}")
        return

    published = 0
    skipped   = 0
    results   = []

    for category in CATEGORIES:
        log.info(f"\n{'─'*50}")
        log.info(f"📂 {category['name'].upper()}")
        log.info(f"{'─'*50}")

        try:
            # Agent 1 — RSS Research (free, no retry needed — handles internally)
            stories = research_agent(category)
            if not stories:
                log.warning(f"Skipping {category['name']} — no stories found")
                skipped += 1
                continue

            # Agent 2 — Sonnet Summary (with retry)
            summary = summary_agent(stories, category)
            if not summary:
                log.warning(f"Skipping {category['name']} — summary failed")
                skipped += 1
                continue
            best_story = summary.get("best_story", {})

            # Agent 3 — Sonnet Fact-Check (with retry)
            factcheck = factcheck_agent(best_story, category)
            if not factcheck or not factcheck.get("approved"):
                log.warning(f"Skipping {category['name']} — story not approved")
                skipped += 1
                continue

            story        = factcheck.get("story", best_story)
            angle        = factcheck.get("suggested_angle", "")
            img_keywords = factcheck.get("image_keywords", category["image_style"].split())

            # Image Agent — Unsplash (with fallback)
            images = fetch_unsplash_images(img_keywords, category["image_style"])
            if not images:
                log.warning("  ⚠ No images fetched — publishing without images")

            # Haiku Rewrite (with retry)
            content = rewrite_article(story, category, angle)
            if not content:
                log.warning(f"Skipping {category['name']} — rewrite failed")
                skipped += 1
                continue

            # SEO Title (with fallback to original headline)
            seo_title = generate_seo_title(
                story.get("headline", ""),
                story.get("market_trend", category["name"])
            )
            log.info(f"  📰 {seo_title}")

            # Upload hero image (optional — publish continues even if it fails)
            featured_id = None
            if images:
                log.info(f"  ⬆️  Uploading hero image...")
                uploaded = upload_image_to_wordpress(images[0], seo_title)
                if uploaded:
                    featured_id = uploaded["id"]
                    log.info(f"  ✓ Hero image ID: {featured_id}")
                else:
                    log.warning("  ⚠ Hero image upload failed — publishing without featured image")

            # Build HTML + Publish
            html        = build_html(content, images, story)
            category_id = get_wp_category_id(category["slug"])

            log.info("  🚀 Publishing to WordPress...")
            post_url = publish_to_wordpress(seo_title, html, category_id, featured_id)

            if post_url:
                log.info(f"  ✅ LIVE → {post_url}")
                published += 1
                results.append({
                    "category": category["name"],
                    "title":    seo_title,
                    "url":      post_url,
                    "trend":    story.get("market_trend", ""),
                    "score":    story.get("market_relevance_score", "?"),
                    "images":   len(images),
                })
            else:
                log.error(f"  ✗ Publish failed for {category['name']}")
                skipped += 1

        except Exception as e:
            log.error(f"  ✗ Unexpected error in {category['name']}: {e}", exc_info=True)
            skipped += 1
            continue  # Always move to next category

    # Final report
    log.info(f"\n{'='*60}")
    log.info(f"  COMPLETED — {published}/5 published | {skipped}/5 skipped")
    log.info(f"{'='*60}")
    for r in results:
        log.info(f"  [{r['category']}] Score:{r['score']}/10 | 📸{r['images']} imgs")
        log.info(f"    {r['title'][:55]}...")
        log.info(f"    🔗 {r['url']}")
    log.info("="*60)

    # Exit with error code if nothing published (alerts GitHub Actions)
    if published == 0:
        raise SystemExit("No articles published — check logs for details")


if __name__ == "__main__":
    run()
