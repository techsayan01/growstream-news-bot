"""
GrowStream Media — RSS feed catalogue and category definitions.

Isolated here so that adding a new site never touches shared agent code.

Feed selection principle: each category gets sources most likely to yield the
article types the classifier will detect there. Generic feeds (TechCrunch,
VentureBeat) appear only where genuinely relevant, not as padding.
"""

# ── Shared source pools ───────────────────────────────────────────────────────

_FINEXTRA_ALL       = "https://www.finextra.com/rss/headlines.aspx"
_FINEXTRA_AI        = "https://www.finextra.com/rss/channel.aspx?channel=ai"
_FINEXTRA_BANKING   = "https://www.finextra.com/rss/channel.aspx?channel=banking"
_FINEXTRA_PAYMENTS  = "https://www.finextra.com/rss/channel.aspx?channel=payments"
_FINEXTRA_REGULATION = "https://www.finextra.com/rss/channel.aspx?channel=regulation"
_FINEXTRA_RESEARCH  = "https://www.finextra.com/rss/channel.aspx?channel=research"

_TECHCRUNCH         = "https://techcrunch.com/feed/"
_TECHCRUNCH_FINTECH = "https://techcrunch.com/category/fintech/feed/"
_VENTUREBEAT        = "https://feeds.feedburner.com/venturebeat/SZYF"
_PYMNTS             = "https://www.pymnts.com/feed/"
_AI_NEWS            = "https://www.artificialintelligence-news.com/feed/"

# Earnings / markets
_MARKETWATCH        = "https://feeds.marketwatch.com/marketwatch/topstories/"
_SEEKING_ALPHA_FIN  = "https://seekingalpha.com/feed.xml"
_REUTERS_BIZ        = "https://feeds.reuters.com/reuters/businessNews"
_REUTERS_TECH       = "https://feeds.reuters.com/reuters/technologyNews"

# Research & data
_CBINSIGHTS         = "https://www.cbinsights.com/research/feed/"
_PYMNTS_RESEARCH    = "https://www.pymnts.com/category/research-and-data/feed/"

# Regulatory bodies (official press release feeds)
_FCA_NEWS           = "https://www.fca.org.uk/news/rss.xml"
_CFPB_NEWS          = "https://www.consumerfinance.gov/feed/"
_SEC_PRESS          = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=&dateb=&owner=include&count=20&search_text=&output=atom"

# ── Category feed mapping ─────────────────────────────────────────────────────

CATEGORY_FEEDS: dict[str, list[str]] = {
    # AI in Banking — product launches, breaking news, occasional data insights
    "ai-in-banking": [
        _FINEXTRA_AI,
        _FINEXTRA_BANKING,
        _AI_NEWS,
        _PYMNTS,
        _VENTUREBEAT,
    ],

    # Fintech News — funding rounds, product launches, breaking news
    "fintech-news": [
        _TECHCRUNCH_FINTECH,
        _FINEXTRA_PAYMENTS,
        _FINEXTRA_ALL,
        _PYMNTS,
        _CBINSIGHTS,
    ],

    # Investment AI — market movers, funding, data insights, earnings signals
    "investment-ai": [
        _MARKETWATCH,
        _REUTERS_BIZ,
        _VENTUREBEAT,
        _CBINSIGHTS,
        _FINEXTRA_RESEARCH,
        _PYMNTS_RESEARCH,
    ],

    # Regulatory Updates — regulatory actions, compliance alerts
    "regulatory-updates": [
        _FINEXTRA_REGULATION,
        _FCA_NEWS,
        _CFPB_NEWS,
        _PYMNTS,
        _REUTERS_BIZ,
    ],

    # Tool Reviews — product launches, explainers
    "tool-reviews": [
        _AI_NEWS,
        _VENTUREBEAT,
        _TECHCRUNCH,
        _FINEXTRA_AI,
        _PYMNTS,
    ],
}

FALLBACK_FEEDS: list[str] = [
    _FINEXTRA_ALL,
    _TECHCRUNCH,
    _PYMNTS,
    _MARKETWATCH,
]

# ── Category definitions ──────────────────────────────────────────────────────
# preferred_article_types: the types the classifier is most likely to see here.
# Informational only — the classifier runs on content, not this list.

CATEGORIES: list[dict] = [
    {
        "slug":                   "ai-in-banking",
        "name":                   "AI in Banking",
        "keywords":               ["bank", "banking", "financial institution", "credit", "loan", "ai", "machine learning"],
        "image_style":            "banking technology finance digital",
        "author_id":              3,
        "preferred_article_types": ["breaking_news", "product_launch", "data_insights"],
    },
    {
        "slug":                   "fintech-news",
        "name":                   "Fintech News",
        "keywords":               ["fintech", "payment", "neobank", "digital wallet", "startup", "funding", "raised"],
        "image_style":            "fintech mobile payment startup technology",
        "author_id":              4,
        "preferred_article_types": ["breaking_news", "funding", "product_launch"],
    },
    {
        "slug":                   "investment-ai",
        "name":                   "Investment AI",
        "keywords":               ["invest", "stock", "portfolio", "hedge fund", "trading", "market", "fund", "ai"],
        "image_style":            "stock market investment trading data analytics",
        "author_id":              3,
        "preferred_article_types": ["market_movers", "data_insights", "funding", "earnings"],
    },
    {
        "slug":                   "regulatory-updates",
        "name":                   "Regulatory Updates",
        "keywords":               ["regulation", "sec", "fca", "rbi", "compliance", "policy", "law", "regulatory", "ban", "fine", "penalty"],
        "image_style":            "regulation law compliance government policy",
        "author_id":              4,
        "preferred_article_types": ["regulatory", "breaking_news"],
    },
    {
        "slug":                   "tool-reviews",
        "name":                   "Tool Reviews",
        "keywords":               ["tool", "platform", "software", "app", "launch", "product", "release", "ai", "feature"],
        "image_style":            "software technology product interface dashboard",
        "author_id":              3,
        "preferred_article_types": ["product_launch", "explainer"],
    },
]
