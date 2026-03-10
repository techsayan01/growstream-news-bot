"""
AI-generated social copy for any article.

Jordan Blake writes platform-specific copy for LinkedIn, X, and Facebook.
"""

import re

from core.llm import get_client
from core.retry import with_retry
from core.utils import log, safe_json_parse


@with_retry(max_retries=3, delay=5)
def generate_social_copy(post: dict) -> dict:
    """Generate platform-specific social copy for a WordPress post dict."""
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
    result = safe_json_parse(r.content[0].text)
    if not result:
        log.warning("  ⚠ Social copy JSON parse failed — using fallback")
        return _fallback_copy(title, excerpt, url)
    log.info("  ✓ Social copy generated")
    return result


def _fallback_copy(title: str, excerpt: str, url: str) -> dict:
    short = excerpt[:200] if excerpt else title
    return {
        "linkedin":      {"hook": title, "body": short, "cta": f"Read more: {url}"},
        "twitter_thread": [title, short[:200], url],
        "facebook":      {"text": f"{title}\n\n{short[:300]}\n\n{url}"},
    }
