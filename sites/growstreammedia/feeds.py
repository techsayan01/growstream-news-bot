"""
GrowStream Media — RSS feed catalogue and category definitions.

Segments:
  - AI in Banking
  - Fintech News
  - Investment AI
  - Regulatory Updates
  - Tool Reviews
  - SME & Startup Finance     ← NEW
  - ESG & Climate Finance     ← NEW
  - PropTech & Real Estate    ← NEW
  - Wealth Management         ← NEW
  - Healthcare Finance        ← NEW
  - Crypto & Web3             ← NEW
"""

# ── Shared source pools ───────────────────────────────────────────────────────

_FINEXTRA_ALL        = "https://www.finextra.com/rss/headlines.aspx"
_FINEXTRA_AI         = "https://www.finextra.com/rss/channel.aspx?channel=ai"
_FINEXTRA_BANKING    = "https://www.finextra.com/rss/channel.aspx?channel=banking"
_FINEXTRA_PAYMENTS   = "https://www.finextra.com/rss/channel.aspx?channel=payments"
_FINEXTRA_REGULATION = "https://www.finextra.com/rss/channel.aspx?channel=regulation"
_FINEXTRA_RESEARCH   = "https://www.finextra.com/rss/channel.aspx?channel=research"

_TECHCRUNCH          = "https://techcrunch.com/feed/"
_TECHCRUNCH_FINTECH  = "https://techcrunch.com/category/fintech/feed/"
_TECHCRUNCH_STARTUP  = "https://techcrunch.com/category/startups/feed/"
_VENTUREBEAT         = "https://feeds.feedburner.com/venturebeat/SZYF"
_PYMNTS              = "https://www.pymnts.com/feed/"
_AI_NEWS             = "https://www.artificialintelligence-news.com/feed/"

# Markets & investment
_MARKETWATCH         = "https://feeds.marketwatch.com/marketwatch/topstories/"
_SEEKING_ALPHA       = "https://seekingalpha.com/feed.xml"
_REUTERS_BIZ         = "https://feeds.reuters.com/reuters/businessNews"
_REUTERS_TECH        = "https://feeds.reuters.com/reuters/technologyNews"
_REUTERS_HEALTH      = "https://feeds.reuters.com/reuters/healthNews"

# Research & data
_CBINSIGHTS          = "https://www.cbinsights.com/research/feed/"
_PYMNTS_RESEARCH     = "https://www.pymnts.com/category/research-and-data/feed/"

# Regulatory
_FCA_NEWS            = "https://www.fca.org.uk/news/rss.xml"
_CFPB_NEWS           = "https://www.consumerfinance.gov/feed/"
_SEC_PRESS           = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=&dateb=&owner=include&count=20&search_text=&output=atom"

# SME & Startup
_ENTREPRENEUR        = "https://www.entrepreneur.com/latest.rss"
_INC_MAGAZINE        = "https://www.inc.com/rss/"
_STARTUPNATION       = "https://startupnation.com/feed/"
_SIFTED              = "https://sifted.eu/feed/"
_CRUNCHBASE_NEWS     = "https://news.crunchbase.com/feed/"

# ESG & Climate Finance
_GREENBIZ            = "https://www.greenbiz.com/feeds/news"
_ESG_TODAY           = "https://www.esgtoday.com/feed/"
_RESPONSIBLE_INVESTOR = "https://www.responsible-investor.com/feed/"
_CLIMATEACTION       = "https://www.climateaction.org/feed"

# PropTech & Real Estate Finance
_PROPMODO            = "https://propmodo.com/feed/"
_BUILTIN_PROPTECH    = "https://builtin.com/rss.xml"
_THEREALDEAL         = "https://therealdeal.com/feed/"
_BISNOW              = "https://www.bisnow.com/rss"

# Wealth Management & HNI
_FAMILY_WEALTH       = "https://www.familywealthreport.com/rss/"
_WEALTHMANAGEMENT    = "https://www.wealthmanagement.com/rss.xml"
_FINANCIAL_PLANNING  = "https://www.financial-planning.com/feed"
_BARRONS             = "https://www.barrons.com/xml/rss/3_7006.xml"

# Healthcare Finance
_MODERNHEALTHCARE    = "https://www.modernhealthcare.com/rss/news.xml"
_HEALTHCAREFINANCE   = "https://www.healthcarefinancenews.com/rss.xml"
_MEDCITYNEWS         = "https://medcitynews.com/feed/"
_BECKERSHOSPITAL     = "https://www.beckershospitalreview.com/rss/finance-rss.xml"

# Crypto & Web3
_COINDESK            = "https://www.coindesk.com/arc/outboundfeeds/rss/"
_COINTELEGRAPH       = "https://cointelegraph.com/rss"
_DECRYPT             = "https://decrypt.co/feed"
_THEBLOCK            = "https://www.theblock.co/rss.xml"


# ── Category feed mapping ─────────────────────────────────────────────────────

CATEGORY_FEEDS: dict[str, list[str]] = {

    # ── Existing segments ─────────────────────────────────────────────────────

    "ai-in-banking": [
        _FINEXTRA_AI,
        _FINEXTRA_BANKING,
        _AI_NEWS,
        _PYMNTS,
        _VENTUREBEAT,
    ],

    "fintech-news": [
        _TECHCRUNCH_FINTECH,
        _FINEXTRA_PAYMENTS,
        _FINEXTRA_ALL,
        _PYMNTS,
        _CBINSIGHTS,
    ],

    "investment-ai": [
        _MARKETWATCH,
        _REUTERS_BIZ,
        _VENTUREBEAT,
        _CBINSIGHTS,
        _FINEXTRA_RESEARCH,
        _PYMNTS_RESEARCH,
        _SEEKING_ALPHA,
    ],

    "regulatory-updates": [
        _FINEXTRA_REGULATION,
        _FCA_NEWS,
        _CFPB_NEWS,
        _PYMNTS,
        _REUTERS_BIZ,
    ],

    "tool-reviews": [
        _AI_NEWS,
        _VENTUREBEAT,
        _TECHCRUNCH,
        _FINEXTRA_AI,
        _PYMNTS,
    ],

    # ── New segments ──────────────────────────────────────────────────────────

    "sme-startup-finance": [
        _TECHCRUNCH_STARTUP,
        _TECHCRUNCH_FINTECH,
        _CRUNCHBASE_NEWS,
        _SIFTED,
        _INC_MAGAZINE,
        _CBINSIGHTS,
        _PYMNTS,
    ],

    "esg-climate-finance": [
        _ESG_TODAY,
        _GREENBIZ,
        _RESPONSIBLE_INVESTOR,
        _REUTERS_BIZ,
        _FINEXTRA_RESEARCH,
    ],

    "proptech-real-estate": [
        _PROPMODO,
        _THEREALDEAL,
        _TECHCRUNCH,
        _CBINSIGHTS,
        _REUTERS_BIZ,
    ],

    "wealth-management": [
        _WEALTHMANAGEMENT,
        _FINANCIAL_PLANNING,
        _SEEKING_ALPHA,
        _MARKETWATCH,
        _CBINSIGHTS,
        _FINEXTRA_RESEARCH,
    ],

    "healthcare-finance": [
        _MODERNHEALTHCARE,
        _HEALTHCAREFINANCE,
        _MEDCITYNEWS,
        _REUTERS_HEALTH,
        _TECHCRUNCH,
    ],

    "crypto-web3": [
        _COINDESK,
        _COINTELEGRAPH,
        _THEBLOCK,
        _DECRYPT,
        _REUTERS_BIZ,
    ],
}

# ── Regional category sets — which categories run at each publish slot ────────
#
# Each region maps to the categories most relevant to that audience.
# The daily_news pipeline uses this when --region is passed.
#
#   india   → 09:00 IST — RBI/SEBI, Indian fintech, Asian markets
#   london  → 13:30 IST — FCA, ECB, DORA, MiCA, ESG (EU taxonomy)
#   us-east → 18:30 IST — SEC, Fed, US VC, Wall Street, US crypto
#   us-mid  → 20:30 IST — Healthcare, Wealth management, PropTech, broad

REGIONAL_CATEGORIES: dict[str, list[str]] = {
    "india": [
        "fintech-news",         # Indian startup funding rounds, neobanks
        "ai-in-banking",        # RBI AI guidelines, Indian bank tech
        "regulatory-updates",   # RBI, SEBI, IRDAI circulars
        "sme-startup-finance",  # Indian startup ecosystem
        "investment-ai",        # Asian market movers, BSE/NSE signals
    ],
    "london": [
        "regulatory-updates",   # FCA, ECB, PRA, DORA, EU AI Act
        "esg-climate-finance",  # EU taxonomy, CSRD, green bonds
        "crypto-web3",          # MiCA enforcement, EU crypto regulation
        "wealth-management",    # London private banking, family offices
        "fintech-news",         # UK/EU fintech (Revolut, Wise, Monzo)
    ],
    "us-east": [
        "investment-ai",        # SEC filings, Fed moves, Wall Street
        "fintech-news",         # US VC rounds, Stripe, Plaid, Brex
        "sme-startup-finance",  # Silicon Valley funding, Y Combinator
        "regulatory-updates",   # SEC, CFPB, OCC actions
        "crypto-web3",          # SEC crypto enforcement, BTC ETF
    ],
    "us-mid": [
        "healthcare-finance",   # US hospital CFOs, MedTech, pharma
        "wealth-management",    # HNI, family offices, private equity
        "proptech-real-estate", # US CRE, REIT earnings, mortgage rates
        "ai-in-banking",        # US bank AI deployments, JPM/GS tech
        "tool-reviews",         # US fintech SaaS, product launches
    ],
}

FALLBACK_FEEDS: list[str] = [
    _FINEXTRA_ALL,
    _TECHCRUNCH,
    _PYMNTS,
    _MARKETWATCH,
    _REUTERS_BIZ,
    _CRUNCHBASE_NEWS,
    _ESG_TODAY,
]


# ── Category definitions ──────────────────────────────────────────────────────

CATEGORIES: list[dict] = [

    # ── Existing ──────────────────────────────────────────────────────────────

    {
        "slug":                    "ai-in-banking",
        "name":                    "AI in Banking",
        "keywords":                ["bank", "banking", "financial institution", "credit", "loan", "ai", "machine learning"],
        "image_style":             "banking technology finance digital",
        "author_id":               3,
        "preferred_article_types": ["breaking_news", "product_launch", "data_insights"],
    },
    {
        "slug":                    "fintech-news",
        "name":                    "Fintech News",
        "keywords":                ["fintech", "payment", "neobank", "digital wallet", "startup", "funding", "raised"],
        "image_style":             "fintech mobile payment startup technology",
        "author_id":               4,
        "preferred_article_types": ["breaking_news", "funding", "product_launch"],
    },
    {
        "slug":                    "investment-ai",
        "name":                    "Investment AI",
        "keywords":                ["invest", "stock", "portfolio", "hedge fund", "trading", "market", "fund", "ai"],
        "image_style":             "stock market investment trading data analytics",
        "author_id":               3,
        "preferred_article_types": ["market_movers", "data_insights", "funding", "earnings"],
    },
    {
        "slug":                    "regulatory-updates",
        "name":                    "Regulatory Updates",
        "keywords":                ["regulation", "sec", "fca", "rbi", "compliance", "policy", "law", "regulatory", "ban", "fine", "penalty"],
        "image_style":             "regulation law compliance government policy",
        "author_id":               4,
        "preferred_article_types": ["regulatory", "breaking_news"],
    },
    {
        "slug":                    "tool-reviews",
        "name":                    "Tool Reviews",
        "keywords":                ["tool", "platform", "software", "app", "launch", "product", "release", "ai", "feature"],
        "image_style":             "software technology product interface dashboard",
        "author_id":               3,
        "preferred_article_types": ["product_launch", "explainer"],
    },

    # ── New segments ──────────────────────────────────────────────────────────

    {
        "slug":                    "sme-startup-finance",
        "name":                    "SME & Startup Finance",
        "keywords":                ["startup", "founder", "series a", "seed", "venture", "smb", "sme", "small business", "cash flow", "runway", "valuation"],
        "image_style":             "startup office entrepreneur team growth",
        "author_id":               3,
        "preferred_article_types": ["funding", "breaking_news", "data_insights"],
    },
    {
        "slug":                    "esg-climate-finance",
        "name":                    "ESG & Climate Finance",
        "keywords":                ["esg", "sustainability", "green", "climate", "carbon", "net zero", "renewable", "csrd", "taxonomy", "green bond"],
        "image_style":             "sustainability green finance climate energy",
        "author_id":               4,
        "preferred_article_types": ["regulatory", "data_insights", "breaking_news"],
    },
    {
        "slug":                    "proptech-real-estate",
        "name":                    "PropTech & Real Estate",
        "keywords":                ["proptech", "real estate", "reit", "property", "mortgage", "housing", "commercial real estate", "cre", "tokenised property"],
        "image_style":             "real estate property technology building city",
        "author_id":               3,
        "preferred_article_types": ["breaking_news", "data_insights", "product_launch"],
    },
    {
        "slug":                    "wealth-management",
        "name":                    "Wealth Management",
        "keywords":                ["wealth", "hni", "hnwi", "family office", "private bank", "asset management", "portfolio", "alternative investment", "private equity", "hedge fund"],
        "image_style":             "wealth management private banking luxury finance",
        "author_id":               3,
        "preferred_article_types": ["data_insights", "market_movers", "breaking_news"],
    },
    {
        "slug":                    "healthcare-finance",
        "name":                    "Healthcare Finance",
        "keywords":                ["healthcare", "hospital", "pharma", "medtech", "health insurance", "rcm", "revenue cycle", "medical billing", "health system", "biotech"],
        "image_style":             "healthcare hospital medical technology finance",
        "author_id":               4,
        "preferred_article_types": ["breaking_news", "data_insights", "funding"],
    },
    {
        "slug":                    "crypto-web3",
        "name":                    "Crypto & Web3",
        "keywords":                ["bitcoin", "ethereum", "crypto", "blockchain", "defi", "web3", "cbdc", "stablecoin", "nft", "tokenisation", "digital asset", "mica"],
        "image_style":             "cryptocurrency blockchain digital finance technology",
        "author_id":               3,
        "preferred_article_types": ["breaking_news", "regulatory", "market_movers"],
    },
]
