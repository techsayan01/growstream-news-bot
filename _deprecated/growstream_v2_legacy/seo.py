"""
GrowStream — SEO module.
Writer persona: Jordan Blake, Senior Financial Journalist.
Handles article writing and all SEO metadata generation.
"""

import json

from .config import get_client, log, with_retry

# ============================================================
# WRITER PERSONA
# ============================================================
_PERSONA_JORDAN_BLAKE = """\
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

_PERSONA_SEO_SPECIALIST = """\
You are an expert SEO strategist with 10+ years optimising financial and B2B content.
You extract keywords and write metadata that improve click-through rates on Google
while accurately representing the article content. Your meta descriptions are
concise, compelling, and always end with a subtle call-to-action.
"""


# ============================================================
# FOCUS KEYWORD
# ============================================================
@with_retry(max_retries=2, delay=3, fallback=lambda: "")
def generate_focus_keyword(headline: str, category_name: str) -> str:
    """Extract the best 2–4 word SEO focus keyword from the headline."""
    response = get_client().messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=30,
        messages=[
            {
                "role": "user",
                "content": (
                    f"{_PERSONA_SEO_SPECIALIST}\n\n"
                    f"Extract the single best 2–4 word SEO focus keyword from this headline "
                    f"for the '{category_name}' finance section. "
                    f"Headline: {headline}. "
                    f"Return ONLY the keyword phrase, lowercase, no quotes, no punctuation."
                ),
            }
        ],
    )
    return response.content[0].text.strip().lower()


# ============================================================
# SEO TITLE
# ============================================================
@with_retry(max_retries=2, delay=3, fallback=lambda: "Untitled Article")
def generate_seo_title(headline: str, market_trend: str) -> str:
    """Generate a contrarian, opinionated SEO headline under 65 characters."""
    response = get_client().messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=150,
        messages=[
            {
                "role": "user",
                "content": (
                    f"{_PERSONA_SEO_SPECIALIST}\n\n"
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
                ),
            }
        ],
    )
    return response.content[0].text.strip()


# ============================================================
# META DESCRIPTION
# ============================================================
@with_retry(max_retries=2, delay=3, fallback=lambda: "")
def generate_meta_description(title: str, content: str, focus_keyword: str) -> str:
    """Generate a 150–155 character meta description with the focus keyword."""
    log.info("  📝 Generating meta description…")
    response = get_client().messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=100,
        messages=[
            {
                "role": "user",
                "content": (
                    f"{_PERSONA_SEO_SPECIALIST}\n\n"
                    f"Write a meta description of EXACTLY 150–155 characters for this article. "
                    f"Must include the keyword '{focus_keyword}' naturally. "
                    f"Must be compelling and end with a call to action. "
                    f"Title: {title}. "
                    f"Return ONLY the meta description — no quotes, no labels."
                ),
            }
        ],
    )
    desc = response.content[0].text.strip()
    if len(desc) > 160:
        desc = desc[:157] + "..."
    return desc


# ============================================================
# ARTICLE WRITER — Jordan Blake
# ============================================================
@with_retry(max_retries=3, delay=5)
def rewrite_article(
    story: dict,
    category: dict,
    angle: str,
    editor_notes: str = "",
    previous_article: str = "",
) -> str | None:
    """
    Write an 800–1000 word SEO-optimised article as Jordan Blake.

    *editor_notes* and *previous_article* — if provided, Jordan will revise
    the existing draft based on Priya Sharma's feedback instead of writing
    from scratch.
    """
    focus_kw = story.get("focus_keyword", category["name"].lower())

    if editor_notes and previous_article:
        # REVISION PASS (Uses Sonnet for better reasoning)
        log.info("  ✍️  Jordan Blake is revising the article based on feedback (using Sonnet)…")
        model = "claude-sonnet-4-20250514"
        prompt = f"""{_PERSONA_JORDAN_BLAKE}

⚠️ REVISION BRIEFING FROM PRIYA SHARMA (Managing Editor):
{editor_notes}

Your task: You must revise the following draft to address EVERY point in Priya's feedback. 
- Do NOT start from scratch. Keep the good parts of the existing article.
- Focus specifically on fixing the issues she highlighted (e.g., SEO keyword spacing, tone, missing facts).
- Ensure the "15 Sec Read" summary section at the top remains intact.
- Ensure the focus keyword "{focus_kw}" is used naturally 4-6 times.
- Format the output as highly scannable HTML. Allowed tags: h2, h3, h4, p, ul, li, strong, em, blockquote, div.
- Keep any styled blockquotes or "Bottom Line" summary boxes intact.
- Return ONLY the final revised HTML body.

PREVIOUS DRAFT:
{previous_article}"""

    else:
        # INITIAL DRAFT (Uses Haiku with strict structure)
        log.info("  ✍️  Jordan Blake is writing the initial draft (using Haiku)…")
        model = "claude-haiku-4-5-20251001"
        prompt = f"""{_PERSONA_JORDAN_BLAKE}

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
    <p style="margin: 6px 0 0; color: #155724;">Name of the entity that benefits most from this story — and one punchy sentence why.</p>
  </div>
  <div style="flex: 1; background-color: #f8d7da; border-left: 4px solid #dc3545; padding: 14px; border-radius: 6px;">
    <strong style="color: #721c24;">📉 Loser</strong>
    <p style="margin: 6px 0 0; color: #721c24;">Name of the entity most exposed or threatened by this story — and one punchy sentence why.</p>
  </div>
</div>

<h2>What Happened</h2>
2 paragraphs (~150 words total) — the news, who is involved, what changed, key numbers.

<h2>Why It Matters for Finance Professionals</h2>
2 paragraphs (~200 words total) — market implications, business impact, why CFOs/investors should care.

<h2>Key Facts and Data Points</h2>
Bullet list of 5–7 concrete facts, numbers, or quotes from the source material.

<h2>Industry Context</h2>
2 paragraphs (~150 words total) — broader market trend, how this fits the bigger picture.

<h2>What Finance Leaders Should Watch</h2>
2 paragraphs (~150 words total) — forward-looking analysis, risks, opportunities.

<h2>Global Market Angles</h2>
Write 3 short sub-sections (one per region), each ~60 words. Use specific company/regulator names:

<h3>🌏 Asia</h3>
Connect to Asian markets — India (RBI, SEBI, HDFC, Paytm, Zerodha), China (PBOC, Alipay, Ant Group),
Japan (FSA, SoftBank), Singapore (MAS). If a region has limited relevance, explain what Asian finance
leaders should watch for.

<h3>🌍 Europe</h3>
Connect to European markets — ECB, FCA, Bundesbank, Deutsche Bank, Revolut, Klarna, DORA/MiCA regulation.
Focus on regulatory divergence or cross-border impact on EU fintech.

<h3>🌎 United States</h3>
Connect to US markets — Fed, SEC, OCC, Goldman Sachs, JPMorgan, Stripe, Nasdaq. Focus on what the
development signals for Wall Street, Silicon Valley, or US regulatory posture.

<h2>The Contrarian Take</h2>
1 short paragraph (~80 words) — push back on the consensus view.
Format: Start with "Here's what nobody's saying about this:" and challenge the dominant
narrative. Is this overhyped? Is the 'winner' not actually winning? Is the risk being
ignored? This should feel like a smart friend's "okay but actually..." commentary.

<h2>The Bottom Line</h2>
<div class="bottom-line" style="background-color: #e9ecef; padding: 20px; border-radius: 8px; margin-top: 30px; margin-bottom: 30px;">
  <p style="margin: 0;"><strong>The single most important takeaway (~80 words).</strong> Include the focus keyword here.</p>
</div>

<h3>Frequently Asked Questions</h3>
3 FAQ items in this exact format:
<h4>Question here?</h4>
<p>Answer here (40–60 words).</p>

Rules:
- Use the focus keyword naturally in the first 100 words, at least one H2 heading, and the conclusion
- Write in HTML. Allowed tags: h2, h3, h4, p, ul, li, strong, em, blockquote, div.
- Make the article highly scannable and visually engaging:
  - Use <strong> to pop key metrics, financial figures, or company names
  - If explaining a complex concept, use bullet points instead of a large block of text
  - If there is a quote or key analyst insight, use <blockquote style="border-left: 4px solid #adb5bd; padding-left: 15px; font-style: italic; color: #495057; margin: 20px 0;">
- No <title> tag. Start directly with the hook paragraph.
- Professional but accessible tone — no jargon without explanation.
- Do NOT fabricate statistics that are not in the source material.
Return ONLY the article HTML body."""

    response = get_client().messages.create(
        model=model,
        max_tokens=2500,
        messages=[{"role": "user", "content": prompt}],
    )
    content = response.content[0].text.strip()

    # Strip markdown code blocks if the LLM wraps the HTML
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
