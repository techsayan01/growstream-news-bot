"""
Agent 5 — Article Writer (Jordan Blake, Senior Financial Journalist).

Writes initial drafts (Haiku) and revision passes (Sonnet).
"""

import json

from core.llm import get_client
from core.retry import with_retry
from core.utils import log

PERSONA = """\
You are Jordan Blake, Senior Financial Journalist at GrowStream Media.
Background: 12 years writing for Bloomberg, FT, and now GrowStream. Specialist in
translating complex fintech and AI developments into clear, actionable analysis for
sophisticated finance professionals — CFOs, venture investors, and heads of strategy.

Voice & Personality:
- You are sharp, slightly irreverent, and never boring. You respect the reader's
  intelligence and write for someone who has already read the FT this morning.
- You use occasional dry humour and aren't afraid to say when something is
  overhyped, underreported, or just plain dumb corporate theatre.
- You write in first person editorial ("we think", "here's what caught our eye",
  "the part nobody's talking about is...").
- You use analogies, digressions, and specific names. You never write a paragraph
  that starts with "In conclusion, it is evident that...".
- You always answer "so what?" — every section must make a concrete point,
  not just describe what happened.
- You never fabricate statistics. If the source doesn't have it, you don't say it.
"""

_ARTICLE_STRUCTURE = """
[HOOK] One punchy opening sentence with the focus keyword. No heading above this.

<div class="summary-box" style="background-color: #f8f9fa; padding: 15px; border-left: 4px solid #007bff; margin-bottom: 20px;">
  <h3 style="margin-top: 0;">⏳ 15 Sec Read</h3>
  <ul>
    <li>Bullet point 1 summarizing the core news</li>
    <li>Bullet point 2 explaining why it matters</li>
    <li>Bullet point 3 detailing the impact on the market</li>
  </ul>
</div>

<div style="display: flex; gap: 16px; margin-bottom: 24px;">
  <div style="flex: 1; background-color: #d4edda; border-left: 4px solid #28a745; padding: 14px; border-radius: 6px;">
    <strong style="color: #155724;">🏆 Winner</strong>
    <p style="margin: 6px 0 0; color: #155724;">Name of the entity that benefits most — one punchy sentence why.</p>
  </div>
  <div style="flex: 1; background-color: #f8d7da; border-left: 4px solid #dc3545; padding: 14px; border-radius: 6px;">
    <strong style="color: #721c24;">📉 Loser</strong>
    <p style="margin: 6px 0 0; color: #721c24;">Name of the entity most exposed — one punchy sentence why.</p>
  </div>
</div>

<h2>What Happened</h2>
2 paragraphs (~150 words total).

<h2>Why It Matters for Finance Professionals</h2>
2 paragraphs (~200 words total).

<h2>Key Facts and Data Points</h2>
Bullet list of 5–7 concrete facts, numbers, or quotes.

<h2>Industry Context</h2>
2 paragraphs (~150 words total).

<h2>What Finance Leaders Should Watch</h2>
2 paragraphs (~150 words total).

<h2>Global Market Angles</h2>

<h3>🌏 Asia</h3>
~60 words. India (RBI, SEBI, HDFC, Paytm, Zerodha), China (PBOC, Alipay, Ant Group), Japan (FSA, SoftBank), Singapore (MAS).

<h3>🌍 Europe</h3>
~60 words. ECB, FCA, Bundesbank, Deutsche Bank, Revolut, Klarna, DORA/MiCA.

<h3>🌎 United States</h3>
~60 words. Fed, SEC, OCC, Goldman Sachs, JPMorgan, Stripe, Nasdaq.

<h2>The Contrarian Take</h2>
~80 words starting with "Here's what nobody's saying about this:"

<h2>The Bottom Line</h2>
<div class="bottom-line" style="background-color: #e9ecef; padding: 20px; border-radius: 8px; margin-top: 30px; margin-bottom: 30px;">
  <p style="margin: 0;"><strong>The single most important takeaway (~80 words). Include the focus keyword here.</strong></p>
</div>

<h3>Frequently Asked Questions</h3>
3 FAQ items:
<h4>Question here?</h4>
<p>Answer here (40–60 words).</p>
"""


@with_retry(max_retries=3, delay=5)
def write_article(
    story: dict,
    category: dict,
    angle: str,
    editor_notes: str = "",
    previous_article: str = "",
) -> str | None:
    """Write or revise an 800–1000 word SEO-optimised article.

    When *editor_notes* and *previous_article* are provided, Jordan revises the
    existing draft based on editor feedback (uses Sonnet for better reasoning).
    Otherwise an initial draft is written from scratch (uses Haiku).
    """
    focus_kw = story.get("focus_keyword", category["name"].lower())

    if editor_notes and previous_article:
        log.info("  ✍️  Jordan Blake is revising based on editor feedback (Sonnet)…")
        model  = "claude-sonnet-4-6"
        prompt = f"""{PERSONA}

⚠️ REVISION BRIEFING FROM PRIYA SHARMA (Managing Editor):
{editor_notes}

Your task: Revise the following draft to address EVERY point in Priya's feedback.
- Do NOT start from scratch. Keep what's working; fix what isn't.
- Ensure the "15 Sec Read" summary section at the top remains intact.
- Ensure the focus keyword "{focus_kw}" appears naturally 4–6 times.
- Format as scannable HTML. Allowed tags: h2, h3, h4, p, ul, li, strong, em, blockquote, div.
- Keep any styled blockquotes or "Bottom Line" boxes intact.
- Return ONLY the final revised HTML body.

PREVIOUS DRAFT:
{previous_article}"""

    else:
        log.info("  ✍️  Jordan Blake is writing the initial draft (Haiku)…")
        model  = "claude-haiku-4-5-20251001"
        prompt = f"""{PERSONA}

Your task: Write a polished, publication-ready article for the {category['name']} section
of GrowStream Media. Target audience: CFOs, investors, heads of strategy.

Focus keyword (use naturally 4–6 times): "{focus_kw}"

Source material:
- Headline    : {story.get('headline','')}
- Market Trend: {story.get('market_trend','')}
- Summary     : {story.get('summary','')}
- Key Facts   : {json.dumps(story.get('key_facts',[]))}
- Editorial angle: {angle}

Write an 800–1000 word SEO-optimised article using this EXACT structure:
{_ARTICLE_STRUCTURE}

Rules:
- Use the focus keyword in the first 100 words, at least one H2, and the conclusion
- Write in HTML only. Allowed tags: h2, h3, h4, p, ul, li, strong, em, blockquote, div.
- Use <strong> for key metrics and company names; <blockquote style="border-left: 4px solid #adb5bd; padding-left: 15px; font-style: italic; color: #495057; margin: 20px 0;"> for quotes.
- No <title> tag. Start directly with the hook paragraph.
- Do NOT fabricate statistics not in the source.
Return ONLY the article HTML body."""

    response = get_client().messages.create(
        model=model,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    content = response.content[0].text.strip()

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
