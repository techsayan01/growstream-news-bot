"""
Agent 2 — Story Ranking (Dr. Sarah Chen, Chief Market Intelligence Analyst).

Scores stories by market relevance and virality, returns the top 5.
"""

import json

from core.llm import get_client
from core.retry import with_retry
from core.utils import log, safe_json_parse

_PERSONA = """\
You are Dr. Sarah Chen, Chief Market Intelligence Analyst at GrowStream Media.
Background: CFA charterholder, 18 years in institutional finance and financial media.
Approach: You evaluate news through the lens of its impact on institutional investors,
CFOs, and finance operations leaders. You are ruthless about relevance — a story must
move markets, change behaviour, or signal a structural shift to merit coverage.
You have zero patience for PR fluff, incremental product updates, or hype without data.
"""


@with_retry(max_retries=3, delay=5)
def rank_stories(stories: list[dict], category: dict) -> list[dict] | None:
    """Rank *stories* and return the top 5 for *category*."""
    log.info(f"📊 [Agent 2 — Dr. Sarah Chen] Ranking {len(stories)} stories for {category['name']}")

    stories_json = json.dumps(
        [{"headline": s["headline"], "summary": s["summary"][:500],
          "source": s["source"], "url": s["url"]} for s in stories],
        indent=2,
    )

    prompt = f"""{_PERSONA}

Your task: Score each story's MARKET TREND RELEVANCE and VIRALITY POTENTIAL (1–10) for the '{category['name']}' section of GrowStream Media.

Scoring criteria:
- Impact on financial markets, institutions, or business strategy
- Relevance to CFOs, investors, and finance professionals
- Timeliness, newsworthiness, and data-backed claims
- Virality potential: likelihood to spark debate or sharing on LinkedIn/Twitter
- Alignment with one of these macro trends:
  AI Infrastructure Boom | Fintech Disruption | Regulatory Crackdown | Investment AI | Banking Transformation

Stories to evaluate:
{stories_json}

Select the TOP 5 best stories in order of relevance/virality. Return ONLY this JSON format (no markdown, no commentary):
{{
  "top_stories": [
    {{
      "headline": "...",
      "summary": "...",
      "source": "...",
      "url": "...",
      "market_trend": "...",
      "market_relevance_score": 9,
      "virality_score": 8,
      "virality_rationale": "High debate potential on Twitter/LinkedIn because...",
      "key_facts": ["fact1", "fact2", "fact3"],
      "sarah_chen_note": "One sentence on why this story wins over the others."
    }}
  ]
}}"""

    response = get_client().messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    result = safe_json_parse(response.content[0].text)
    if not result or "top_stories" not in result or not isinstance(result["top_stories"], list):
        raise ValueError("Invalid ranking response structure")

    top = result["top_stories"]
    log.info(f"  ✓ Ranked top {len(top)} stories for {category['name']}")
    return top
