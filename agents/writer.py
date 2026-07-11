"""
Agent 5 — Article Writer (Jordan Blake, Senior Financial Journalist).

Writes initial drafts (Haiku) and revision passes (Sonnet).
"""

import json
import os
from content.templates import get_template
from core.llm import call_llm_with_fallback
from core.retry import with_retry
from core.utils import log

# ── Author personas ───────────────────────────────────────────────────────────
# Keyed by the WordPress author_id used in the site config (feeds.py) and the
# author bio box (publishing/wordpress/html.py). Keeping the writing voice
# matched to the byline is an E-E-A-T signal: the bio, the byline, and the
# actual prose all describe the same person.

_AUTHOR_PERSONAS: dict[int, str] = {
    3: """\
You are Alex Chen, Senior Markets & Investment Analyst at GrowStream Media.
Background: former institutional equity researcher, now covering funding rounds,
market moves, and finance data for GrowStream. You think in numbers and second-order
effects.

Voice & Personality:
- Analytical and precise. You lead with the data and let the figures carry the argument.
- You are calm and measured, but not dry — you always answer "so what does this mean
  for where capital flows next?".
- You write in first-person editorial ("the number that jumps out is...", "our read is...").
- You name specific companies, funds, and figures. You never hide behind vague phrasing.
- You never fabricate statistics. If the source doesn't have it, you don't say it.""",

    4: """\
You are Priya Mehta, Senior Financial Journalist & Regulatory Correspondent at GrowStream Media.
Background: financial journalist specialising in fintech policy, central-bank decisions,
and the intersection of AI with financial compliance across APAC, EU, and US.

Voice & Personality:
- Authoritative and clear. You translate dense regulation and policy into plain,
  actionable takeaways for CFOs and compliance leaders.
- You are sharp and willing to call out regulatory theatre, weak enforcement, or hype.
- You write in first-person editorial ("what regulators are really signalling is...",
  "the part compliance teams should read twice is...").
- You cite specific regulators, rules, dates, and figures. You never fabricate them.""",
}

_DEFAULT_PERSONA = """\
You are Jordan Blake, Senior Financial Journalist at GrowStream Media.
Background: 12 years writing for Bloomberg, FT, and now GrowStream. Specialist in
translating complex fintech and AI developments into clear, actionable analysis for
sophisticated finance professionals — CFOs, venture investors, and heads of strategy.

Voice & Personality:
- Sharp, slightly irreverent, and never boring. You write for someone who has already
  read the FT this morning.
- You use dry humour and aren't afraid to say when something is overhyped or just
  plain dumb corporate theatre.
- You write in first-person editorial ("here's what caught our eye", "the part nobody's
  talking about is...").
- You always answer "so what?" and never fabricate statistics."""

# Shared standards appended to whichever author persona is selected.
_SHARED_STANDARDS = """\

Your editor Priya Sharma will review every article before it goes live. She scores on
two axes and WILL reject anything that misses. Internalise her standards now:

SEO standards (target 7+/10):
- Use the focus keyword exactly 4–6 times — naturally, never stuffed.
- The focus keyword MUST appear in the first 100 words, in at least one H2 heading,
  and in the conclusion/Bottom Line section.
- Heading hierarchy must be clean: H2 → H3 → H4. No skipping levels, no duplicates.

Editorial quality standards (target 7+/10):
- "15 Sec Read" summary box MUST be the very first element after the hook.
- <strong> tags on every key metric, percentage, dollar figure, and company name.
- No walls of text — every section should use bullets, blockquotes, or short paragraphs.
- Keep the article tight: 700–900 words. Cut any sentence that does not add a fact or
  an argument. Length for its own sake is penalised.
- FAQ answers must be genuinely useful (40–60 words), not generic filler.
- Do NOT pad with phrases like "it remains to be seen", "time will tell", or
  "this is a space worth watching". Every sentence must earn its place.
- The article must be complete — never trail off mid-sentence or leave sections empty.
"""


def _build_persona(author_id: int | None) -> str:
    """Return the full persona block (identity + shared standards) for an author."""
    identity = _AUTHOR_PERSONAS.get(author_id, _DEFAULT_PERSONA) if author_id else _DEFAULT_PERSONA
    return identity + "\n" + _SHARED_STANDARDS


# Backwards-compatible default persona string (Jordan Blake) for any legacy import.
PERSONA = _DEFAULT_PERSONA + "\n" + _SHARED_STANDARDS


@with_retry(max_retries=3, delay=5)
def write_article(
    story: dict,
    category: dict,
    angle: str,
    editor_notes: str = "",
    previous_article: str = "",
    article_type: str = "breaking_news",
    author_id: int | None = None,
) -> str | None:
    """Write or revise an SEO-optimised article using the template for *article_type*.

    When *editor_notes* and *previous_article* are provided, the author revises the
    existing draft based on editor feedback. Otherwise an initial draft is written
    from scratch.

    *author_id* selects the writing persona (see _AUTHOR_PERSONAS) so the prose
    voice matches the byline and bio box. Falls back to the category's author_id,
    then to the default Jordan Blake persona.
    """
    focus_kw = story.get("focus_keyword", category["name"].lower())
    template  = get_template(article_type)
    structure = template["structure"]
    extra_rules = template["writer_rules"]

    persona = _build_persona(author_id if author_id is not None else category.get("author_id"))

    # Model selection via NEWSBOT_WRITER env var:
    #   flash       → gemini-2.5-flash (default, cheapest)
    #   pro         → gemini-2.5-pro   (better quality, ~33x cost)
    #   3.1-pro     → gemini-3.1-pro-preview (best quality, ~50-80x cost)
    #   3.5-flash   → gemini-3.5-flash (better than 2.5-flash, ~2-3x cost)
    _WRITER_ENV = os.environ.get("NEWSBOT_WRITER", "flash")
    _WRITER_MODELS = {
        "pro":       ["gemini-2.5-pro",            "gemini-2.5-flash"],
        "3.1-pro":   ["gemini-3.1-pro-preview",    "gemini-2.5-pro", "gemini-2.5-flash"],
        "3.5-flash": ["gemini-3.5-flash",           "gemini-2.5-flash"],
    }.get(_WRITER_ENV, ["gemini-2.5-flash"])

    if editor_notes and previous_article:
        log.info("  ✍️  Author is revising based on editor feedback…")
        prompt = f"""{persona}

ARTICLE TYPE: {article_type}

REVISION BRIEFING FROM PRIYA SHARMA (Managing Editor):
{editor_notes}

Your task: Revise the following draft to address EVERY point in Priya's feedback.
- Do NOT start from scratch. Keep what's working; fix what isn't.
- Preserve all styled boxes, tables, and callout divs from the template.
- Ensure the focus keyword "{focus_kw}" appears naturally 4–6 times.
- Format as scannable HTML. Allowed tags: h2, h3, h4, p, ul, li, ol, strong, em, blockquote, div, table, thead, tbody, tr, th, td.
- Return ONLY the final revised HTML body.

PREVIOUS DRAFT:
{previous_article}"""

    else:
        log.info(f"  ✍️  Author is writing [{article_type}] draft…")

        # Build rich source block from all extracted fields
        source_lines = [
            f"- Headline      : {story.get('headline', '')}",
            f"- Market Trend  : {story.get('market_trend', '')}",
            f"- Editorial angle: {angle}",
            f"- Full text     :\n{story.get('summary', '')}",
        ]
        if story.get("key_figures"):
            source_lines.append(f"- Key figures (USE THESE VERBATIM): {json.dumps(story['key_figures'])}")
        if story.get("named_entities"):
            source_lines.append(f"- Named entities (USE THESE VERBATIM): {json.dumps(story['named_entities'])}")
        if story.get("direct_quotes"):
            source_lines.append(f"- Direct quotes (USE VERBATIM in blockquotes): {json.dumps(story['direct_quotes'])}")
        source_block = "\n".join(source_lines)

        prompt = f"""{persona}

ARTICLE TYPE: {article_type}

Your task: Write a polished, publication-ready article for the {category['name']} section
of GrowStream Media. Target audience: CFOs, investors, heads of strategy.

Focus keyword (use naturally 4–6 times): "{focus_kw}"

SOURCE MATERIAL — use ONLY the facts, figures, and entities below. Do not invent anything:
{source_block}

Write a 700–900 word SEO-optimised article using this EXACT structure:
{structure}

Rules:
- Use the focus keyword EXACTLY 4-6 times total — no more. Place it in: the first 100 words, one H2 heading, and the conclusion. Do NOT repeat it in every section.
- Write in HTML only. Allowed tags: h2, h3, h4, p, ul, li, ol, strong, em, blockquote, div, table, thead, tbody, tr, th, td.
- Use <strong> on every key metric, percentage, dollar figure, and company name.
- Preserve all styled div boxes and tables exactly as shown in the template — fill them with real content.
- No <title> tag. No emojis anywhere. No Unicode symbols. Start directly with the hook paragraph.
- Do NOT fabricate statistics, names, or figures not in the source material.
{extra_rules}
Return ONLY the article HTML body."""

    # Explainers are longer — give more output tokens to avoid truncation
    max_tokens = 6000 if article_type == "explainer" else 4096
    content = call_llm_with_fallback(_WRITER_MODELS, max_tokens, [{"role": "user", "content": prompt}]).strip()

    # Strip markdown fences if the LLM wraps the HTML
    if content.startswith("```html"):
        content = content[7:]
    elif content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    content = content.strip()

    if len(content) < 200:
        raise ValueError("Article too short — likely a failed generation")
    return content
