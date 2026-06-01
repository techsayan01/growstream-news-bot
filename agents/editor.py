"""
Agent 4 — Editorial Review Gate (Priya Sharma, Managing Editor).

Reviews final HTML before publishing. Two-stage review:

Stage 1 — Pre-flight (no LLM, instant):
  - Detect unfilled template placeholders like [value] or [Entity Name]
  - Detect truncated articles (no sentence-ending punctuation at end)
  - Check focus keyword presence in the raw HTML

Stage 2 — LLM review (Gemini Pro):
  - Scores SEO and editorial quality against the article-type-specific checklist
  - Reviews raw HTML structure (not stripped text) so it can verify tables,
    callout boxes, and <strong> tag placement
  - Returns approval + actionable revision notes
"""

import json
import os
import re

from content.templates import get_template
from core.llm import call_llm
from core.retry import with_retry
from core.utils import log, safe_json_parse

_PERSONA = """\
You are Priya Sharma, Managing Editor at GrowStream Media.
Background: 15 years in digital publishing — former senior content strategist at SEMrush,
ex-editor at Forbes Digital. Expert at balancing SEO performance with genuine editorial quality.
You review articles in their raw HTML form — you can read HTML tags and verify that
styled boxes, tables, and highlights are correctly populated.
"""

# Regex to catch unfilled template placeholders
_PLACEHOLDER_RE = re.compile(
    r'\[(?:'
    r'KEY STAT OR FIGURE|One-line label|value|Entity Name|entity|label|'
    r'Date|Feature \d+|Competitor \d+|Step \d+ title|Question \d+|'
    r'Asset \d+|Metric|Reported|Estimate|YoY Change|level|'
    r'This Product|price point|pricing model|amount|valuation|investors|round'
    r')[^\]]*\]',
    re.IGNORECASE,
)

_SENTENCE_END = re.compile(r'[.!?">)\]]$')


def _preflight(article_html: str, focus_keyword: str) -> list[str]:
    """Run instant pre-flight checks. Return list of blocking issues (empty = pass)."""
    issues: list[str] = []

    # 1. Unfilled placeholders
    placeholders = _PLACEHOLDER_RE.findall(article_html)
    if placeholders:
        sample = ", ".join(placeholders[:4])
        issues.append(f"Unfilled template placeholders found: {sample}")

    # 2. Truncation check
    plain = re.sub(r"<[^>]+>", "", article_html).strip()
    if plain and not _SENTENCE_END.search(plain[-50:]):
        issues.append("Article appears truncated — does not end with sentence-ending punctuation")

    # 3. Focus keyword presence
    if focus_keyword and focus_keyword.lower() not in article_html.lower():
        issues.append(f"Focus keyword '{focus_keyword}' not found anywhere in the article HTML")

    # 4. Minimum length
    if len(plain) < 500:
        issues.append(f"Article body too short ({len(plain)} chars) — likely a failed generation")

    return issues


@with_retry(max_retries=2, delay=5)
def review_article(
    article_html: str,
    story: dict,
    seo_title: str,
    focus_keyword: str,
    meta_description: str,
    category: dict,
    article_type: str = "breaking_news",
) -> dict | None:
    """
    Editorial quality gate. Returns a dict with:
      approved         bool  — True if the article can publish as-is
      seo_score        int   — 1-10
      quality_score    int   — 1-10
      issues           list  — specific problems found (empty if none)
      rewrites_needed  bool  — True if a rewrite pass is required
      editorial_notes  str   — Actionable feedback for the revision prompt
      priya_note       str   — Short verdict in Priya's voice
    """
    log.info(
        f"📝 [Agent 4 — Priya Sharma] Reviewing [{article_type}] "
        f"for {category['name']}"
    )

    # ── Stage 1: instant pre-flight ──────────────────────────────────────────
    blocking = _preflight(article_html, focus_keyword)
    if blocking:
        for issue in blocking:
            log.warning(f"  ⚠ Pre-flight: {issue}")
        notes = "Fix these issues:\n" + "\n".join(f"- {i}" for i in blocking)
        return {
            "approved":       False,
            "seo_score":      0,
            "quality_score":  0,
            "issues":         blocking,
            "rewrites_needed": True,
            "editorial_notes": notes,
            "priya_note":     "Pre-flight failed — unfilled placeholders or truncation detected.",
        }

    # ── Stage 2: LLM review on raw HTML ─────────────────────────────────────
    template      = get_template(article_type)
    checklist     = template["editor_checklist"]
    checklist_str = "\n".join(f"   - {item}" for item in checklist)

    # Pass raw HTML (not stripped) so Priya can verify box and table structure.
    # Cap at 10000 chars of HTML — long enough for a full 1200-word article.
    html_for_review = article_html[:10000]
    truncated_note  = " [TRUNCATED FOR REVIEW]" if len(article_html) > 10000 else ""

    # Count keyword occurrences for the SEO check
    kw_count = article_html.lower().count(focus_keyword.lower()) if focus_keyword else 0

    prompt = f"""{_PERSONA}

Review this {article_type.replace('_', ' ').title()} article before it goes live.

METADATA:
  Article type  : {article_type}
  SEO title     : {seo_title}
  Focus keyword : {focus_keyword} (appears {kw_count}× in HTML)
  Meta desc     : {meta_description} ({len(meta_description)} chars)
  Category      : {category['name']}
  Source summary: {story.get('summary', '')[:400]}
  Key facts     : {json.dumps(story.get('key_facts', []))}
  Key figures   : {json.dumps(story.get('key_figures', []))}
  Named entities: {json.dumps(story.get('named_entities', []))}

ARTICLE HTML{truncated_note}:
{html_for_review}

Evaluate on TWO axes:

1. SEO (score 1–10):
   - Focus keyword 4–6 times (currently {kw_count}×) — below 4 or above 6 = deduct points
   - Keyword in first 100 words, at least one <h2>, and conclusion section
   - Meta description 150–155 characters, includes focus keyword
   - Clean heading hierarchy (h2 → h3 → h4), no skipped levels, no duplicates

2. EDITORIAL QUALITY for a {article_type.replace('_', ' ').upper()} article (score 1–10):
   Mandatory elements for this type — deduct 1 point per missing element:
{checklist_str}
   General quality checks:
   - <strong> tags present on key metrics, percentages, dollar figures, company names
   - Styled div boxes and tables are populated with real content (not placeholder text)
   - Facts are consistent with the source summary and key facts/figures provided above
   - No fabricated figures that don't appear in the source material
   - Logical narrative flow — no abrupt topic changes
   - Sharp, opinionated, first-person editorial voice — not dry or corporate-passive
   - No emojis anywhere
   - No padding phrases ("it remains to be seen", "time will tell", "space to watch")
   - FAQ answers genuinely useful, 40–60 words each

Return ONLY this JSON (no markdown):
{{
  "approved": true,
  "seo_score": 8,
  "quality_score": 9,
  "issues": ["Specific issue description if any"],
  "rewrites_needed": false,
  "editorial_notes": "Specific actionable instructions if rewrites needed, else empty string.",
  "priya_note": "One sentence verdict in Priya's voice."
}}

Rules:
- approved=true ONLY if seo_score >= 7 AND quality_score >= 7
- rewrites_needed=true whenever approved=false
- editorial_notes must reference specific HTML elements, headings, or missing sections
- Do not approve an article that contains facts not supported by the source material above"""

    _reviewer_model = (
        "gemini-2.5-pro"
        if os.environ.get("NEWSBOT_REVIEWER") == "pro"
        else "gemini-2.5-flash"
    )
    result = safe_json_parse(
        call_llm(_reviewer_model, 1500, [{"role": "user", "content": prompt}])
    )
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
