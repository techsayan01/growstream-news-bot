"""
Agent 0 — Article Type Classifier.

Classifies a story into one of 8 article types so the writer can
pick the appropriate template. Uses a fast Gemini Flash call.

Types:
  breaking_news   — default catch-all for hard news
  data_insights   — surveys, research, benchmark reports
  earnings        — quarterly results, revenue announcements
  product_launch  — new tools, platform updates, feature releases
  funding         — investment rounds, M&A, IPOs
  regulatory      — fines, enforcement, compliance actions
  market_movers   — macro moves, index/stock movements
  explainer       — educational, "what is X", how-to guides
"""

from core.llm import call_llm
from core.utils import log, safe_json_parse

ARTICLE_TYPES = {
    "breaking_news",
    "data_insights",
    "earnings",
    "product_launch",
    "funding",
    "regulatory",
    "market_movers",
    "explainer",
}

_PROMPT = """\
You are a financial news editor. Classify the following story into exactly one article type.

Article types:
- breaking_news   : Hard news, announcements, incidents — default when nothing else fits
- data_insights   : Survey results, research reports, statistics, benchmark studies
- earnings        : Quarterly results, revenue, profit, EPS, guidance
- product_launch  : New product, feature, platform, tool, or service announcement
- funding         : Investment round, M&A deal, acquisition, IPO, valuation
- regulatory      : Fine, enforcement action, compliance ruling, regulatory guidance
- market_movers   : Stock/index movement, macro event, Fed/central bank action
- explainer       : Educational piece, "what is X", how-to, concept guide

Story headline: {headline}
Story summary: {summary}

Return ONLY this JSON (no markdown, no explanation):
{{"type": "<one of the 8 types above>", "confidence": 0.9}}
"""


def classify_story(story: dict) -> str:
    """Return the article type string for *story*. Falls back to 'breaking_news'."""
    headline = story.get("headline", "")
    summary  = story.get("summary", "")[:400]

    prompt = _PROMPT.format(headline=headline, summary=summary)
    try:
        raw    = call_llm("gemini-2.5-flash", 60, [{"role": "user", "content": prompt}])
        result = safe_json_parse(raw)
        if result and isinstance(result, dict):
            article_type = result.get("type", "breaking_news")
            if article_type in ARTICLE_TYPES:
                confidence = result.get("confidence", 0)
                log.info(f"  🏷  Article type: {article_type} (confidence: {confidence})")
                return article_type
    except Exception as e:
        log.warning(f"  ⚠ Classifier failed: {e} — defaulting to breaking_news")

    return "breaking_news"
