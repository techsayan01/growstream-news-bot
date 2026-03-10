"""
GrowStream — Auto-Social Pipeline.

Reads the pending social queue from the local DB and auto-posts to:
  - LinkedIn (company page — live)
  - X / Twitter (when credentials are added)
  - Facebook Page (when credentials are added)

Run after main.py: python social.py
Or pass a specific post URL to force post: python social.py https://growstreammedia.com/my-article/
"""

import json
import re
import sys
from datetime import datetime

import requests

from ..config import (
    LINKEDIN_ACCESS_TOKEN,
    LINKEDIN_ORG_URN,
    WP_PASSWORD,
    WP_URL,
    WP_USERNAME,
    get_client,
    log,
    with_retry,
)
from ..db import update_social_status


# ============================================================
# FETCH WORDPRESS POST
# ============================================================

def _get_wp_auth() -> dict:
    import base64
    token = base64.b64encode(f"{WP_USERNAME}:{WP_PASSWORD}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def fetch_post_by_url(post_url: str) -> dict | None:
    try:
        r = requests.get(
            f"{WP_URL}/wp-json/wp/v2/posts",
            headers=_get_wp_auth(),
            params={"link": post_url, "per_page": 1},
            timeout=15,
        )
        r.raise_for_status()
        posts = r.json()
        if not posts:
            log.error(f"  ✗ Post not found: {post_url}")
            return None
        return posts[0]
    except Exception as e:
        log.error(f"  ✗ Could not fetch post: {e}")
        return None


def fetch_post_by_id(post_id: int) -> dict | None:
    try:
        r = requests.get(
            f"{WP_URL}/wp-json/wp/v2/posts/{post_id}",
            headers=_get_wp_auth(),
            timeout=15,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log.error(f"  ✗ Could not fetch post ID {post_id}: {e}")
        return None


# ============================================================
# CRAFT SOCIAL COPY (AI-generated)
# ============================================================

@with_retry(max_retries=3, delay=5)
def _generate_social_copy(post: dict) -> dict:
    """Jordan Blake writes platform-specific social copy for an article."""
    title   = post["title"]["rendered"]
    excerpt = re.sub(r"<[^>]+>", "", post.get("excerpt", {}).get("rendered", ""))[:400]
    url     = post.get("link", "")

    prompt = f"""You are Jordan Blake, GrowStream's sharp, irreverent financial journalist.

Write social copy for this article for THREE platforms. Return ONLY valid JSON with these keys.

Article title: {title}
Article excerpt: {excerpt}
Article URL: {url}

Return this JSON exactly:
{{
  "linkedin": {{
    "hook": "First 2 lines that stop the scroll — bold opinion or surprising stat. NO emojis in first line.",
    "body": "3-4 short paragraphs. Contrarian angle. End with a question to drive comments. Max 1,200 chars.",
    "cta": "One-line CTA with the article link. E.g. 'Full breakdown: {url}'"
  }},
  "twitter_thread": [
    "Tweet 1: The hook — bold claim. Max 240 chars. No hashtags.",
    "Tweet 2: The context. Max 240 chars.",
    "Tweet 3: The contrarian angle. Max 240 chars.",
    "Tweet 4: The takeaway + link: {url}"
  ],
  "facebook": {{
    "text": "Conversational 3-paragraph post. Broader audience tone. End with article link. Max 500 chars."
  }}
}}"""

    r = get_client().messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1200,
        messages=[{"role": "user", "content": prompt}],
    )

    from ..config import safe_json_parse
    result = safe_json_parse(r.content[0].text)
    if not result:
        log.warning("  ⚠ Social copy JSON parse failed — using fallback")
        return _fallback_copy(title, excerpt, url)
    log.info("  ✓ Social copy generated")
    return result


def _fallback_copy(title: str, excerpt: str, url: str) -> dict:
    short = excerpt[:200] if excerpt else title
    return {
        "linkedin": {
            "hook": title,
            "body": short,
            "cta": f"Read more: {url}",
        },
        "twitter_thread": [title, short[:200], url],
        "facebook": {"text": f"{title}\n\n{short[:300]}\n\n{url}"},
    }


# ============================================================
# LINKEDIN PUBLISHER
# ============================================================

@with_retry(max_retries=2, delay=5)
def post_to_linkedin(copy: dict, post: dict, db_row=None) -> str | None:
    if db_row and db_row["linkedin_status"] not in ("pending", "failed"):
        log.info("  ⏭ LinkedIn: not pending — skipping")
        return "already_posted"

    from ..config import LINKEDIN_PERSON_URN

    if not LINKEDIN_ACCESS_TOKEN or LINKEDIN_ACCESS_TOKEN == "your_access_token_here":
        log.error("  ✗ LINKEDIN_ACCESS_TOKEN not set — skipping LinkedIn")
        if db_row: update_social_status(db_row["wp_post_id"], "linkedin", "failed")
        return None

    li = copy.get("linkedin", {})
    text = f"{li.get('hook', '')}\n\n{li.get('body', '')}\n\n{li.get('cta', '')}"
    text = text[:2900]  # LinkedIn hard limit is 3000

    article_url = post.get("link", "")
    title       = re.sub(r"<[^>]+>", "", post["title"]["rendered"])

    authors_to_try = []
    if LINKEDIN_ORG_URN:
        authors_to_try.append(("company page", LINKEDIN_ORG_URN))
    if LINKEDIN_PERSON_URN:
        authors_to_try.append(("personal profile", LINKEDIN_PERSON_URN))

    if not authors_to_try:
        log.error("  ✗ No LinkedIn author URN configured")
        if db_row: update_social_status(db_row["wp_post_id"], "linkedin", "failed")
        return None

    headers = {
        "Authorization":  f"Bearer {LINKEDIN_ACCESS_TOKEN}",
        "Content-Type":   "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }

    for label, author_urn in authors_to_try:
        post_text = text
        if "person" in author_urn and "GrowStream" not in post_text:
            post_text = post_text + "\n\n📍 GrowStream Media | growstreammedia.com"

        payload = {
            "author":          author_urn,
            "lifecycleState":  "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": post_text},
                    "shareMediaCategory": "ARTICLE",
                    "media": [{
                        "status":      "READY",
                        "description": {"text": title[:200]},
                        "originalUrl": article_url,
                        "title":       {"text": title[:200]},
                    }],
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            },
        }

        r = requests.post(
            "https://api.linkedin.com/v2/ugcPosts",
            headers=headers,
            json=payload,
            timeout=20,
        )

        if r.status_code == 201:
            post_id  = r.headers.get("X-RestLi-Id", "unknown")
            post_url = f"https://www.linkedin.com/feed/update/{post_id}/"
            log.info(f"  ✅ LinkedIn published as {label} → {post_url}")
            if db_row: update_social_status(db_row["wp_post_id"], "linkedin", "published")
            return post_url
        elif r.status_code in (401, 403):
            log.warning(f"  ⚠ {label} auth failed ({r.status_code}) — trying next author")
            continue
        else:
            log.error(f"  ✗ LinkedIn failed {r.status_code}: {r.text[:200]}")
            if db_row: update_social_status(db_row["wp_post_id"], "linkedin", "failed")
            return None

    log.error("  ✗ LinkedIn: all author URNs failed.")
    if db_row: update_social_status(db_row["wp_post_id"], "linkedin", "failed")
    return None


# ============================================================
# X / TWITTER PUBLISHER (stub)
# ============================================================

def post_to_twitter(copy: dict, post: dict, db_row=None) -> list[str] | None:
    if db_row and db_row["twitter_status"] not in ("pending", "failed"):
        log.info("  ⏭ X: not pending — skipping")
        return ["already_posted"]

    try:
        from ..config import (  # type: ignore
            TWITTER_API_KEY, TWITTER_API_SECRET,
            TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET,
        )
    except ImportError:
        log.warning("  ⚠ Twitter credentials not in config — skipping X post")
        return None

    if not locals().get("TWITTER_API_KEY"):
        log.warning("  ⚠ TWITTER_API_KEY not set — skipping X post")
        return None

    try:
        import tweepy
        client = tweepy.Client(
            consumer_key=TWITTER_API_KEY,
            consumer_secret=TWITTER_API_SECRET,
            access_token=TWITTER_ACCESS_TOKEN,
            access_token_secret=TWITTER_ACCESS_SECRET,
        )
        tweets    = copy.get("twitter_thread", [])
        tweet_ids = []
        prev_id   = None
        for tweet in tweets:
            resp = client.create_tweet(
                text=tweet[:280],
                in_reply_to_tweet_id=prev_id,
            )
            prev_id = resp.data["id"]
            tweet_ids.append(prev_id)
        log.info(f"  ✅ X thread published ({len(tweet_ids)} tweets)")
        if db_row: update_social_status(db_row["wp_post_id"], "twitter", "published")
        return tweet_ids
    except Exception as e:
        log.warning(f"  ⚠ X post failed: {e}")
        if db_row: update_social_status(db_row["wp_post_id"], "twitter", "failed")
        return None


# ============================================================
# FACEBOOK PUBLISHER (stub)
# ============================================================

def post_to_facebook(copy: dict, post: dict, db_row=None) -> str | None:
    if db_row and db_row["facebook_status"] not in ("pending", "failed"):
        log.info("  ⏭ Facebook: not pending — skipping")
        return "already_posted"

    try:
        from ..config import FB_PAGE_ID, FB_PAGE_ACCESS_TOKEN  # type: ignore
    except ImportError:
        log.warning("  ⚠ Facebook credentials not in config — skipping FB post")
        return None

    if not locals().get("FB_PAGE_ACCESS_TOKEN"):
        log.warning("  ⚠ FB_PAGE_ACCESS_TOKEN not set — skipping Facebook")
        return None

    try:
        text = copy.get("facebook", {}).get("text", "")
        r    = requests.post(
            f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/feed",
            data={"message": text, "access_token": FB_PAGE_ACCESS_TOKEN},
            timeout=20,
        )
        r.raise_for_status()
        fb_id = r.json().get("id", "")
        log.info(f"  ✅ Facebook published (ID: {fb_id})")
        if db_row: update_social_status(db_row["wp_post_id"], "facebook", "published")
        return fb_id
    except Exception as e:
        log.warning(f"  ⚠ Facebook post failed: {e}")
        if db_row: update_social_status(db_row["wp_post_id"], "facebook", "failed")
        return None


# ============================================================
# MAIN RUN
# ============================================================

def _process_post(post: dict, db_row=None) -> None:
    log.info(f"  ✓ Article: '{post['title']['rendered'][:60]}...'")
    log.info("  ✍ Generating social copy…")
    copy = _generate_social_copy(post)

    log.info("\n  📤 Publishing to platforms…")
    li_url = post_to_linkedin(copy, post, db_row)
    tw_ids = post_to_twitter(copy, post, db_row)
    fb_id  = post_to_facebook(copy, post, db_row)

    log.info("\n  📊 Social publish summary:")
    def fmt(res):
        if res == "already_posted": return "⏭ skipped (already posted)"
        if res: return "✅ published"
        return "✗ failed / skipped"

    log.info(f"     LinkedIn : {fmt(li_url)}")
    log.info(f"     X        : {fmt(tw_ids)}")
    log.info(f"     Facebook : {fmt(fb_id)}")
    log.info("-" * 40)


def run(post_url: str | None = None) -> None:
    log.info("=" * 60)
    log.info("  GrowStream — Auto-Social Queue Processor")
    log.info(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')} IST")
    log.info("=" * 60)

    if post_url:
        log.info(f"  🎯 Forcing post of URL: {post_url}")
        post = fetch_post_by_url(post_url)
        if post:
            _process_post(post)
    else:
        from ..db import get_pending_social_posts
        pending = get_pending_social_posts()
        if not pending:
            log.info("  ⏭ No pending articles in social queue")
            return
            
        log.info(f"  📋 Found {len(pending)} pending article(s) in queue")
        for row in pending:
            post = fetch_post_by_id(row["wp_post_id"])
            if post:
                _process_post(post, row)
