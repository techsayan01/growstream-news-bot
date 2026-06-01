"""
SEO metadata generation — focus keyword, SEO title, meta description.

Uses the SEO Specialist persona (quick Haiku calls).
"""

from core.llm import call_llm
from core.retry import with_retry
from core.utils import log

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
