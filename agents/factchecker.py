"""
Agent 3 — Fact-Check Gate (Marcus Webb, Editorial Director).

Approves or rejects a story for credibility before writing begins.
"""

import json

from core.llm import get_client
from core.retry import with_retry
from core.utils import log, safe_json_parse

_PERSONA = """\
You are Marcus Webb, Editorial Director and Head Fact-Checker at GrowStream Media.
Background: 22 years in journalism — ex-Reuters financial correspondent, ex-FT editor.
Approach: You verify every claim against the source material. You reject stories with
vague attribution, inflated numbers, or misleading framing. You are protective of
GrowStream's credibility above all else.

Crucially: Because GrowStream is an aggregator, we frequently rely on secondary reporting
(e.g., Finextra summarizing an FT report). You MUST accept reputable secondary sources as
long as they clearly attribute the original reports. Do NOT reject stories merely because
they are summaries, industry commentary, or secondary reports, provided the underlying
claims are logically sound.
"""


@with_retry(max_retries=3, delay=5)
def factcheck_story(story: dict, category: dict) -> dict | None:
    """Fact-check *story* and return an approval dict, or None on failure."""
    log.info(f"✅ [Agent 3 — Marcus Webb] Fact-checking for {category['name']}")

    prompt = f"""{_PERSONA}

Your task: Review the following story for the '{category['name']}' section of GrowStream Media.
Check for: source credibility, internal consistency, claim verifiability, and suitability
for an audience of finance professionals and institutional investors.

Story:
{json.dumps(story, indent=2)}

Return ONLY this JSON (no markdown, no commentary):
{{
  "approved": true,
  "credibility_score": 8,
  "fact_check_notes": "One concise sentence on the story's credibility.",
  "marcus_webb_verdict": "One sentence in Marcus's voice — why he approves or rejects.",
  "suggested_angle": "Specific editorial angle for the GrowStream finance audience.",
  "image_keywords": ["keyword1", "keyword2", "keyword3", "keyword4"],
  "story": {{ ...all original story fields preserved here... }}
}}"""

    response = get_client().messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
    )
    result = safe_json_parse(response.content[0].text)
    if not result:
        raise ValueError("Invalid fact-check response")

    approved = result.get("approved", False)
    score    = result.get("credibility_score", "?")
    verdict  = result.get("marcus_webb_verdict", "")
    log.info(
        f"  {'✓ Approved' if approved else '✗ Rejected'} — "
        f"Credibility: {score}/10 | {verdict}"
    )
    return result
