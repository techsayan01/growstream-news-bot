"""
Agent 1 — Research (Alex Rivera).

Fetches RSS stories, enriches them with full article text, scores freshness
and source reputation, deduplicates semantically, and returns the best
candidates for ranking.
"""

import calendar
import re
import time
from html.parser import HTMLParser

import feedparser
import requests

from core.db import is_headline_duplicate, is_headline_seen, is_story_processed, store_raw_story
from core.retry import REQUEST_TIMEOUT
from core.utils import headline_fingerprint, log, normalise_headline

# ── Source reputation registry ─────────────────────────────────────────────
# Score 1–10. Anything not listed defaults to 4.
_SOURCE_REPUTATION: dict[str, int] = {
    "financial times":                  10,
    "reuters":                          10,
    "bloomberg":                        10,
    "wall street journal":              10,
    "wsj":                              10,
    "the economist":                    10,
    "finextra":                         9,
    "fca":                              9,
    "sec":                              9,
    "cfpb":                             9,
    "consumer financial protection":    9,
    "marketwatch":                      8,
    "cbinsights":                       8,
    "cb insights":                      8,
    "pymnts":                           8,
    "seeking alpha":                    7,
    "techcrunch":                       7,
    "fortune":                          7,
    "cnbc":                             7,
    "venturebeat":                      6,
    "artificialintelligence-news":      5,
    "ai news":                          5,
    "unknown":                          3,
}

# Maximum age to accept for news stories (hours). Evergreen explainers skip this.
_MAX_AGE_HOURS = 72

# Fetch full article text only if summary is shorter than this
_SUMMARY_MIN_CHARS = 400


# ── HTML article extractor ─────────────────────────────────────────────────

class _ArticleExtractor(HTMLParser):
    """Minimal HTMLParser that collects <p> text, skipping nav/footer/script."""

    _SKIP_TAGS = {"script", "style", "nav", "footer", "header", "aside", "form", "figure"}

    def __init__(self):
        super().__init__()
        self._skip_depth = 0
        self._in_p = False
        self._current: list[str] = []
        self.paragraphs: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
        if tag == "p" and not self._skip_depth:
            self._in_p = True
            self._current = []

    def handle_endtag(self, tag):
        if tag in self._SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        if tag == "p":
            if self._in_p and self._current:
                text = " ".join(self._current).strip()
                if len(text) > 50:
                    self.paragraphs.append(text)
            self._in_p = False
            self._current = []

    def handle_data(self, data):
        if self._in_p and not self._skip_depth:
            cleaned = data.strip()
            if cleaned:
                self._current.append(cleaned)


def _extract_article_text(url: str) -> str:
    """Fetch URL and extract readable paragraph text. Returns empty string on failure."""
    try:
        resp = requests.get(
            url,
            timeout=8,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (compatible; GrowStreamBot/1.0; "
                    "+https://growstreammedia.com)"
                ),
                "Accept": "text/html,application/xhtml+xml",
            },
            allow_redirects=True,
        )
        if resp.status_code != 200:
            return ""
        # Ignore non-HTML responses (PDFs, JSON APIs, etc.)
        ct = resp.headers.get("Content-Type", "")
        if "html" not in ct:
            return ""

        parser = _ArticleExtractor()
        parser.feed(resp.text[:150_000])  # cap to avoid huge pages
        text = " ".join(parser.paragraphs)
        # Trim to 3000 chars — enough context without overwhelming the LLM
        return text[:3000].strip()
    except Exception:
        return ""


# ── Freshness scoring ──────────────────────────────────────────────────────

def _freshness_score(published_parsed) -> tuple[float, str]:
    """Return (score 0–10, age_label) from feedparser's published_parsed struct."""
    if not published_parsed:
        return 4.0, "unknown age"
    try:
        pub_ts  = calendar.timegm(published_parsed)
        age_h   = (time.time() - pub_ts) / 3600
        if age_h < 0:
            age_h = 0
        if   age_h <= 6:   score = 10.0
        elif age_h <= 12:  score = 8.5
        elif age_h <= 24:  score = 7.0
        elif age_h <= 48:  score = 5.0
        elif age_h <= 72:  score = 3.0
        else:              score = 1.0
        label = f"{int(age_h)}h ago"
        return score, label
    except Exception:
        return 4.0, "unknown age"


def _source_score(source_name: str) -> int:
    """Return reputation score 1–10 for a source name."""
    name = source_name.lower()
    for key, score in _SOURCE_REPUTATION.items():
        if key in name:
            return score
    return 4


# ── Semantic dedup ─────────────────────────────────────────────────────────

def _normalise(text: str) -> str:
    """Alias for shared normalise_headline — keeps internal calls consistent."""
    return normalise_headline(text)


def _overlap(a: str, b: str) -> float:  # used only for within-batch dedup
    """Combined similarity: Jaccard on stripped word sets + first-entity match bonus."""
    # Strip digits before comparison — "1B" and "billion" shouldn't block a match
    na = re.sub(r"\d+", "", _normalise(a))
    nb = re.sub(r"\d+", "", _normalise(b))
    sa, sb = set(na.split()), set(nb.split())
    if not sa or not sb:
        return 0.0
    jaccard = len(sa & sb) / len(sa | sb)

    # If both headlines open with the same capitalized entity (company name),
    # add a bonus — two Stripe headlines on the same day are almost always the same story.
    entities_a = re.findall(r"\b[A-Z][a-zA-Z]{2,}\b", a)
    entities_b = re.findall(r"\b[A-Z][a-zA-Z]{2,}\b", b)
    entity_bonus = 0.0
    if entities_a and entities_b and entities_a[0].lower() == entities_b[0].lower():
        entity_bonus = 0.20

    return min(1.0, jaccard + entity_bonus)


def _semantic_dedup(stories: list[dict], threshold: float = 0.40) -> list[dict]:
    """Remove near-duplicate stories (Jaccard similarity > threshold)."""
    kept: list[dict] = []
    for story in stories:
        if all(_overlap(story["headline"], k["headline"]) < threshold for k in kept):
            kept.append(story)
    return kept


# ── Public interface ───────────────────────────────────────────────────────

def research_agent(
    category: dict,
    category_feeds: dict[str, list[str]],
    fallback_feeds: list[str],
) -> list[dict] | None:
    """Fetch, enrich, filter, and score stories for *category*.

    Returns up to 10 stories sorted by composite score (relevance + freshness
    + source reputation), or None if nothing was found.
    """
    log.info(f"🔍 [Agent 1 — Alex Rivera] Researching: {category['name']}")
    feeds   = category_feeds.get(category["slug"], [])
    stories = _fetch_from_feeds(feeds, category["keywords"])

    if len(stories) < 3:
        log.warning(f"  ⚠ Only {len(stories)} primary stories — trying fallback feeds")
        stories += _fetch_from_feeds(fallback_feeds, category["keywords"])

    if not stories:
        log.error(f"  ✗ No stories found for {category['name']}")
        return None

    # Layer 1: skip already-processed source URLs
    stories = [s for s in stories if not is_story_processed(s["url"])]

    # Layer 3: cross-run semantic dedup against recently published articles
    before = len(stories)
    stories = [s for s in stories if not is_headline_duplicate(s["headline"])]
    skipped = before - len(stories)
    if skipped:
        log.info(f"  ✂  {skipped} stories skipped — too similar to recently published articles")

    # Within-batch dedup (catches same story from multiple feeds in this run)
    stories = _semantic_dedup(stories)

    # Sort by composite score descending, return top 10
    stories.sort(key=lambda s: s["composite_score"], reverse=True)
    result = stories[:10]

    log.info(
        f"  ✓ {len(result)} unique stories | "
        f"top score: {result[0]['composite_score']:.1f} | "
        f"'{result[0]['headline'][:50]}'"
    )
    return result or None


def fetch_from_feeds(feeds: list[str], keywords: list[str]) -> list[dict]:
    """Public alias used by pipelines that fetch stories without a category."""
    return _fetch_from_feeds(feeds, keywords)


def _fetch_from_feeds(feeds: list[str], keywords: list[str]) -> list[dict]:
    """Parse RSS feeds, enrich with full text, and score each story."""
    stories: list[dict] = []
    for feed_url in feeds:
        try:
            feed = feedparser.parse(feed_url, agent="GrowStreamBot/1.0")
            if feed.bozo and not feed.entries:
                log.warning(f"  ⚠ Malformed feed: {feed_url[:60]}")
                continue

            for entry in feed.entries[:15]:
                title   = entry.get("title", "").strip()
                summary = (entry.get("summary") or entry.get("description") or "").strip()
                link    = entry.get("link", "")

                if not title or not link:
                    continue
                # Strip HTML tags from RSS summary
                summary = re.sub(r"<[^>]+>", " ", summary).strip()
                summary = re.sub(r"\s{2,}", " ", summary)

                if len(summary) < 60:
                    continue

                # Keyword filter on title + summary
                text = (title + " " + summary).lower()
                if not any(kw.lower() in text for kw in keywords):
                    continue

                # Freshness
                freshness, age_label = _freshness_score(entry.get("published_parsed"))

                # Source reputation
                source_name  = feed.feed.get("title", "Unknown")
                source_rep   = _source_score(source_name)

                # Composite score pre-LLM (relevance slot is filled by ranker later)
                composite = (freshness * 0.45) + (source_rep * 0.55)

                # Full article fetch if summary is thin
                full_text = ""
                if len(summary) < _SUMMARY_MIN_CHARS:
                    full_text = _extract_article_text(link)

                best_text = full_text if len(full_text) > len(summary) else summary

                # Layer 2: fingerprint check — catches same story from different URLs
                fp = headline_fingerprint(title)
                if is_headline_seen(fp):
                    continue

                store_raw_story(
                    link, title, best_text[:1500],
                    source_name, entry.get("published", "")
                )

                stories.append({
                    "headline":        title,
                    "summary":         best_text[:1500],
                    "url":             link,
                    "source":          source_name,
                    "age_label":       age_label,
                    "freshness_score": round(freshness, 1),
                    "source_score":    source_rep,
                    "composite_score": round(composite, 2),
                    "full_text_fetched": bool(full_text),
                })

        except Exception as e:
            log.warning(f"  ⚠ Feed error ({feed_url[:50]}): {e}")

    return stories
