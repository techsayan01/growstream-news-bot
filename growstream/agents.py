"""
GrowStream — Agents 2, 3, and 4.

Agent 2 — Summary/Ranking  : Dr. Sarah Chen, Chief Market Intelligence Analyst
Agent 3 — Fact-Check        : Marcus Webb, Editorial Director & Head Fact-Checker
Agent 4 — Editor            : Priya Sharma, Managing Editor (quality & SEO gate)
"""

import json

from .config import get_client, log, safe_json_parse, with_retry

# ============================================================
# AGENT PERSONAS
# ============================================================
_PERSONA_SARAH_CHEN = """\
You are Dr. Sarah Chen, Chief Market Intelligence Analyst at GrowStream Media.
Background: CFA charterholder, 18 years in institutional finance and financial media.
Approach: You evaluate news through the lens of its impact on institutional investors,
CFOs, and finance operations leaders. You are ruthless about relevance — a story must
move markets, change behaviour, or signal a structural shift to merit coverage.
You have zero patience for PR fluff, incremental product updates, or hype without data.
"""

_PERSONA_MARCUS_WEBB = """\
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

_PERSONA_PRIYA_SHARMA = """\
You are Priya Sharma, Managing Editor at GrowStream Media.
Background: 15 years in digital publishing — former senior content strategist at SEMrush,
ex-editor at Forbes Digital. Expert at balancing SEO performance with genuine editorial
quality. You can spot keyword stuffing, thin content, and poor structure instantly.
Approach: You review final articles before they go live. Your job is to catch anything
that would embarrass GrowStream, hurt search rankings, or fail the reader. You are
thorough, fair, and constructive — you give specific, actionable feedback.
"""


# ============================================================
# AGENT 2: SUMMARY / RANKING — Dr. Sarah Chen
# ============================================================
@with_retry(max_retries=3, delay=5)
def summary_agent(stories: list[dict], category: dict) -> dict | None:
    """Rank stories and select the single best one for *category*."""
    log.info(f"📊 [Agent 2 — Dr. Sarah Chen] Ranking {len(stories)} stories for {category['name']}")

    stories_json = json.dumps(
        [
            {
                "headline": s["headline"],
                "summary":  s["summary"][:500],
                "source":   s["source"],
                "url":      s["url"],
            }
            for s in stories
        ],
        indent=2,
    )

    prompt = f"""{_PERSONA_SARAH_CHEN}

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

Select the TOP 3 best stories in order of relevance/virality. Return ONLY this JSON format (no markdown, no commentary):
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
        model="claude-sonnet-4-20250514",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    result = safe_json_parse(response.content[0].text)
    if not result or "top_stories" not in result or not isinstance(result["top_stories"], list):
        raise ValueError("Invalid summary response structure")

    top_stories = result["top_stories"]
    log.info(f"  ✓ Ranked top {len(top_stories)} stories for {category['name']}")
    return top_stories



# ============================================================
# AGENT 3: FACT-CHECK — Marcus Webb
# ============================================================
@with_retry(max_retries=3, delay=5)
def factcheck_agent(best_story: dict, category: dict) -> dict | None:
    """Fact-check and approve (or reject) the best story."""
    log.info(f"✅ [Agent 3 — Marcus Webb] Fact-checking for {category['name']}")

    prompt = f"""{_PERSONA_MARCUS_WEBB}

Your task: Review the following story for the '{category['name']}' section of GrowStream Media.
Check for: source credibility, internal consistency, claim verifiability, and suitability
for an audience of finance professionals and institutional investors.

Story:
{json.dumps(best_story, indent=2)}

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


# ============================================================
# AGENT 4: EDITOR — Priya Sharma
# ============================================================
@with_retry(max_retries=2, delay=5)
def editor_agent(
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
      editorial_notes  str   — Actionable feedback for the rewrite prompt
      priya_note       str   — Short verdict in Priya's voice
    """
    log.info(f"📝 [Agent 4 — Priya Sharma] Editing article for {category['name']}")

    # Truncate HTML to stay within token limits (20000 chars is ~5000 tokens, plenty for Sonnet)
    article_preview = article_html[:20000]

    prompt = f"""{_PERSONA_PRIYA_SHARMA}

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
   - MUST include a "15 Sec Read" summary box at the very top (before the first H2)
   - MUST include a two-column Winner/Loser box immediately after the 15 Sec Read block (green for winner, red for loser, with named entities and one punchy sentence each)
   - MUST include a "Global Market Angles" section with sub-sections for Asia, Europe, and the US (with named companies/regulators in each)
   - MUST include a "The Contrarian Take" section starting with "Here's what nobody's saying..."
   - Visual Appeal: Article must be highly scannable (bolded key metrics, blockquotes for quotes, bullet points instead of walls of text)
   - Factual consistency with the source summary and key facts
   - Logical narrative flow (hook → 15 Sec Read → context → analysis → Global Market Angles → Contrarian Take → Bottom Line → FAQ)
   - Editorial voice: sharp, opinionated, and first-person — NOT dry or passive. Penalise generic corporate journalism.
   - Tone: professional but accessible; no jargon without explanation
   - No content padding, filler phrases, or generic statements
   - FAQ answers are genuinely useful, not vague

Return ONLY this JSON (no markdown, no commentary):
{{
  "approved": true,
  "seo_score": 8,
  "quality_score": 9,
  "issues": ["Specific issue 1 if any", "Specific issue 2 if any"],
  "rewrites_needed": false,
  "editorial_notes": "Specific, actionable rewrite instructions if rewrites_needed is true, else empty string.",
  "priya_note": "One sentence verdict in Priya's voice."
}}

Rules:
- Set approved=true ONLY IF both seo_score >= 7 AND quality_score >= 7
- Set rewrites_needed=true if approved=false
- If rewrites_needed, editorial_notes MUST contain specific, actionable instructions"""

    response = get_client().messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}],
    )
    result = safe_json_parse(response.content[0].text)
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
    if issues:
        for issue in issues:
            log.warning(f"  ⚠ {issue}")

    return result
