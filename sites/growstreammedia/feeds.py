"""
GrowStream Media — RSS feed catalogue and category definitions.

Isolated here so that adding a new site never touches shared agent code.
"""

CATEGORY_FEEDS: dict[str, list[str]] = {
    "ai-in-banking": [
        "https://www.finextra.com/rss/channel.aspx?channel=ai",
        "https://feeds.feedburner.com/venturebeat/SZYF",
        "https://www.pymnts.com/feed/",
        "https://techcrunch.com/feed/",
    ],
    "fintech-news": [
        "https://techcrunch.com/category/fintech/feed/",
        "https://www.finextra.com/rss/headlines.aspx",
        "https://www.pymnts.com/feed/",
        "https://feeds.feedburner.com/venturebeat/SZYF",
    ],
    "investment-ai": [
        "https://feeds.feedburner.com/venturebeat/SZYF",
        "https://techcrunch.com/feed/",
        "https://www.pymnts.com/feed/",
        "https://www.finextra.com/rss/headlines.aspx",
    ],
    "regulatory-updates": [
        "https://www.finextra.com/rss/channel.aspx?channel=regulation",
        "https://techcrunch.com/feed/",
        "https://www.pymnts.com/feed/",
        "https://feeds.feedburner.com/venturebeat/SZYF",
    ],
    "tool-reviews": [
        "https://feeds.feedburner.com/venturebeat/SZYF",
        "https://techcrunch.com/feed/",
        "https://www.artificialintelligence-news.com/feed/",
        "https://www.pymnts.com/feed/",
    ],
}

FALLBACK_FEEDS: list[str] = [
    "https://techcrunch.com/feed/",
    "https://feeds.feedburner.com/venturebeat/SZYF",
    "https://www.pymnts.com/feed/",
]

CATEGORIES: list[dict] = [
    {
        "slug":        "ai-in-banking",
        "name":        "AI in Banking",
        "keywords":    ["bank", "banking", "financial institution", "credit", "loan", "ai", "machine learning"],
        "image_style": "banking technology finance digital",
        "author_id":   3,
    },
    {
        "slug":        "fintech-news",
        "name":        "Fintech News",
        "keywords":    ["fintech", "payment", "neobank", "digital wallet", "startup", "funding", "raised"],
        "image_style": "fintech mobile payment startup technology",
        "author_id":   4,
    },
    {
        "slug":        "investment-ai",
        "name":        "Investment AI",
        "keywords":    ["invest", "stock", "portfolio", "hedge fund", "trading", "market", "fund", "ai"],
        "image_style": "stock market investment trading data analytics",
        "author_id":   3,
    },
    {
        "slug":        "regulatory-updates",
        "name":        "Regulatory Updates",
        "keywords":    ["regulation", "sec", "rbi", "compliance", "policy", "law", "regulatory", "ban"],
        "image_style": "regulation law compliance government policy",
        "author_id":   4,
    },
    {
        "slug":        "tool-reviews",
        "name":        "Tool Reviews",
        "keywords":    ["tool", "platform", "software", "app", "launch", "product", "release", "ai"],
        "image_style": "software technology product interface dashboard",
        "author_id":   3,
    },
]
