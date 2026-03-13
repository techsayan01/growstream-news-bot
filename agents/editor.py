"""
Agent 4 — Editorial Review Gate (Priya Sharma, Managing Editor).

Reviews final HTML before publishing. Scores SEO and editorial quality.
Returns approval + actionable feedback for revision loops.
"""

import json
import re

from core.llm import call_llm
from core.retry import with_retry
from core.utils import log, safe_json_parse

_PERSONA = """\
You are Priya Sharma, Managing Editor at GrowStream Media.
Background: 15 years in digital publishing — former senior content strategist at SEMrush,
ex-editor at Forbes Digital. Expert at balancing SEO performance with genuine editorial
quality. You can spot keyword stuffing, thin content, and poor structure instantly.
Approach: You review final articles before they go live. Your job is to catch anything
that would embarrass GrowStream, hurt search rankings, or fail the reader. You are
thorough, fair, and constructive — you give specific, actionable feedback.
"""


@with_retry(max_retries=2, delay=5)
def review_article(
    article_html: str,
    story: dict,
    seo_title: str,
    focus_keyword: str,
    meta_description: str,
    category: dict,
) -> dict | None:
    """
    Editorial quality gate. Reviews the final draft before publishing.

    Returns a dict with:
      approved         bool  — True if the article can publish as-is
      seo_score        int   — 1-10
      quality_score    int   — 1-10
      issues           list  — specific problems found (empty if none)
      rewrites_needed  bool  — True if a rewrite pass is required
      editorial_notes  str   — Actionable feedback for the revision prompt
      priya_note       str   — Short verdict in Priya's voice
    """
    log.info(f"📝 [Agent 4 — Priya Sharma] Editing article for {category['name']}")

    article_preview = re.sub(r"<[^>]+>", " ", article_html)[:6000]

    prompt = f"""{_PERSONA}

Your task: Review this article before it goes live on GrowStream Media.

---
SEO TITLE   : {seo_title}
FOCUS KEYWORD: {focus_keyword}
META DESC   : {meta_description}
CATEGORY    : {category['name']}
SOURCE SUMMARY: {story.get('summary','')[:400]}
KEY FACTS   : {json.dumps(story.get('key_facts', []))}
---

ARTICLE (HTML body):
{article_preview}

Evaluate on TWO axes:

1. SEO (score 1–10):
   - Focus keyword appears 4–6 times naturally (not stuffed)
   - Keyword in first 100 words, at least one H2, and conclusion
   - Meta description 150–155 characters and includes focus keyword
   - Proper heading hierarchy (H2 → H3 → H4)
   - No duplicate headings

2. EDITORIAL QUALITY (score 1–10):
   - MUST include a "15 Sec Read" summary box at the very top
   - MUST include a two-column Winner/Loser box immediately after it
   - MUST include a "Global Market Angles" section with Asia, Europe, US sub-sections
   - MUST include a "The Contrarian Take" section starting with "Here's what nobody's saying..."
   - Highly scannable (bolded key metrics, blockquotes, bullet points over walls of text)
   - Factual consistency with the source summary and key facts
   - Logical narrative flow
   - Editorial voice: sharp, opinionated, first-person — NOT dry or passive
   - No padding, filler phrases, or generic statements
   - FAQ answers are genuinely useful

Return ONLY this JSON (no markdown, no commentary):
{{
  "approved": true,
  "seo_score": 8,
  "quality_score": 9,
  "issues": ["Specific issue 1 if any"],
  "rewrites_needed": false,
  "editorial_notes": "Specific, actionable rewrite instructions if rewrites_needed is true, else empty string.",
  "priya_note": "One sentence verdict in Priya's voice."
}}

Rules:
- Set approved=true ONLY IF both seo_score >= 7 AND quality_score >= 7
- Set rewrites_needed=true if approved=false
- If rewrites_needed, editorial_notes MUST contain specific, actionable instructions"""

    result = safe_json_parse(call_llm("gemini-3.1-pro-preview", 1200, [{"role": "user", "content": prompt}]))
    if not result:
        raise ValueError("Invalid editor response")

    seo_score     = result.get("seo_score", 0)
    quality_score = result.get("quality_score", 0)
    approved      = result.get("approved", False)
    priya_note    = result.get("priya_note", "")
    issues        = result.get("issues", [])

    log.info(
        f"  {'✓ Approved' if approved else '✗ Needs revision'} — "
        f"SEO: {seo_score}/10 | Quality: {quality_score}/10 | {priya_note}"
    )
    for issue in issues:
        log.warning(f"  ⚠ {issue}")

    return result
