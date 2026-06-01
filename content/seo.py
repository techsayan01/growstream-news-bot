"""
SEO metadata generation — focus keyword, SEO title, meta description, tags.

Uses the SEO Specialist persona (quick Flash calls).
"""

import json

from core.llm import call_llm
from core.retry import with_retry
from core.utils import log, safe_json_parse

_PERSONA_SEO = """\
You are an expert SEO strategist with 10+ years optimising financial and B2B content.
You extract keywords and write metadata that improve click-through rates on Google
while accurately representing the article content. Your meta descriptions are
concise, compelling, and always end with a subtle call-to-action.
"""


@with_retry(max_retries=2, delay=3, fallback=lambda: "")
def generate_focus_keyword(headline: str, category_name: str) -> str:
    """Extract the best 2–4 word SEO focus keyword from the headline."""
    return call_llm("gemini-2.5-flash", 30, [{"role": "user", "content": (
        f"{_PERSONA_SEO}\n\n"
        f"Extract the single best 2–4 word SEO focus keyword from this headline "
        f"for the '{category_name}' finance section. "
        f"Headline: {headline}. "
        f"Return ONLY the keyword phrase, lowercase, no quotes, no punctuation."
    )}]).strip().lower()


@with_retry(max_retries=2, delay=3, fallback=lambda: "Untitled Article")
def generate_seo_title(headline: str, market_trend: str) -> str:
    """Generate a contrarian, opinionated SEO headline under 65 characters."""
    return call_llm("gemini-2.5-flash", 150, [{"role": "user", "content": (
        f"{_PERSONA_SEO}\n\n"
        f"Create ONE contrarian, opinionated SEO headline under 65 characters.\n"
        f"Rules:\n"
        f"- Challenge the consensus or argue against the obvious take\n"
        f"- Use provocative framing ('Why X Won't Work', 'The Real Winner Is...', "
        f"'Everyone's Wrong About X', 'X Is Not What You Think')\n"
        f"- Include a power word that sparks curiosity or debate\n"
        f"- Must be under 65 characters\n"
        f"- Do NOT use clickbait that misrepresents the story\n"
        f"Original headline: {headline}.\n"
        f"Market trend: {market_trend}.\n"
        f"Return ONLY the headline, no quotes."
    )}]).strip()


@with_retry(max_retries=2, delay=3, fallback=lambda: "")
def generate_meta_description(title: str, content: str, focus_keyword: str) -> str:
    """Generate a 150–155 character meta description with the focus keyword."""
    log.info("  📝 Generating meta description…")
    desc = call_llm("gemini-2.5-flash", 100, [{"role": "user", "content": (
        f"{_PERSONA_SEO}\n\n"
        f"Write a meta description of EXACTLY 150–155 characters for this article. "
        f"Must include the keyword '{focus_keyword}' naturally. "
        f"Must be compelling and end with a call to action. "
        f"Title: {title}. "
        f"Return ONLY the meta description — no quotes, no labels."
    )}]).strip()
    if len(desc) > 160:
        desc = desc[:157] + "..."
    return desc


@with_retry(max_retries=2, delay=3, fallback=list)
def generate_tags(
    headline: str,
    focus_keyword: str,
    market_trend: str,
    named_entities: list[str] | None = None,
) -> list[str]:
    """Generate 6–10 WordPress tags for the article.

    Returns a list of lowercase tag strings ready to pass to the WP API.
    Tags cover: topic keywords, company names, macro trends, and article type signals.
    """
    entities_hint = ""
    if named_entities:
        entities_hint = f"Named entities in the article: {', '.join(named_entities[:8])}. Include the most important ones as tags."

    raw = call_llm("gemini-2.5-flash", 150, [{"role": "user", "content": (
        f"{_PERSONA_SEO}\n\n"
        f"Generate 6–10 WordPress tags for this finance article.\n"
        f"Headline: {headline}\n"
        f"Focus keyword: {focus_keyword}\n"
        f"Market trend: {market_trend}\n"
        f"{entities_hint}\n\n"
        f"Rules:\n"
        f"- Tags must be specific and searchable (e.g. 'fintech funding', 'gemini ai', 'rbi regulation')\n"
        f"- Include the focus keyword as one tag\n"
        f"- Include the market trend as one tag\n"
        f"- All lowercase, no special characters\n"
        f"- No generic tags like 'news', 'finance', 'article'\n"
        f"Return ONLY a JSON array of strings: [\"tag1\", \"tag2\", ...]"
    )}])

    tags = safe_json_parse(raw)
    if isinstance(tags, list):
        return [str(t).lower().strip() for t in tags if t][:10]
    return []
