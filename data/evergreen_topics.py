"""
Evergreen topic queue — seed data.

Each entry will become a standalone 1500-word explainer article.
Topics are chosen for high search volume + low competition in the
finance/fintech/AI space. Add new topics here as needed.

Run `python data/evergreen_topics.py` to seed/top-up the MongoDB queue.
"""

TOPICS = [
    # ── Fintech Fundamentals ──────────────────────────────────────────────────
    {"slug": "what-is-embedded-finance",
     "topic": "What is Embedded Finance? A Complete Guide for CFOs",
     "keyword": "embedded finance",
     "category": "Fintech Explainers"},

    {"slug": "what-is-open-banking",
     "topic": "What is Open Banking and How Does It Work?",
     "keyword": "open banking",
     "category": "Fintech Explainers"},

    {"slug": "what-is-bnpl",
     "topic": "What is Buy Now Pay Later (BNPL)? Risks and Opportunities",
     "keyword": "buy now pay later BNPL",
     "category": "Fintech Explainers"},

    {"slug": "what-is-a-neobank",
     "topic": "What is a Neobank? How Challenger Banks Are Disrupting Finance",
     "keyword": "neobank challenger bank",
     "category": "Fintech Explainers"},

    {"slug": "what-is-regtech",
     "topic": "What is RegTech? How AI is Automating Compliance",
     "keyword": "regtech compliance automation",
     "category": "Fintech Explainers"},

    {"slug": "what-is-api-banking",
     "topic": "What is API Banking and Why Every CFO Should Care",
     "keyword": "api banking",
     "category": "Fintech Explainers"},

    {"slug": "what-is-a-payment-gateway",
     "topic": "What is a Payment Gateway? How Online Payments Actually Work",
     "keyword": "payment gateway",
     "category": "Fintech Explainers"},

    {"slug": "what-is-digital-wallet",
     "topic": "What is a Digital Wallet? A Finance Professional's Guide",
     "keyword": "digital wallet",
     "category": "Fintech Explainers"},

    {"slug": "what-is-real-time-payments",
     "topic": "What is Real-Time Payments (RTP)? The End of Banking Delays",
     "keyword": "real time payments RTP",
     "category": "Fintech Explainers"},

    {"slug": "what-is-merchant-acquiring",
     "topic": "What is Merchant Acquiring? How Card Payments Reach Your Bank",
     "keyword": "merchant acquiring payments",
     "category": "Fintech Explainers"},

    # ── AI in Finance ─────────────────────────────────────────────────────────
    {"slug": "how-ai-fraud-detection-works",
     "topic": "How AI Fraud Detection Works in Banking",
     "keyword": "AI fraud detection banking",
     "category": "AI in Banking"},

    {"slug": "what-is-robo-advisory",
     "topic": "What is Robo-Advisory? How AI Manages Investments",
     "keyword": "robo advisory AI investing",
     "category": "AI in Banking"},

    {"slug": "how-algorithmic-trading-works",
     "topic": "How Algorithmic Trading Works: A Plain-English Guide",
     "keyword": "algorithmic trading",
     "category": "Investment AI"},

    {"slug": "ai-tools-for-cfos",
     "topic": "Best AI Tools for CFOs in 2026: What Actually Works",
     "keyword": "AI tools for CFOs",
     "category": "AI in Banking"},

    {"slug": "what-is-generative-ai-in-finance",
     "topic": "What is Generative AI in Finance? Use Cases and Risks",
     "keyword": "generative AI finance",
     "category": "AI in Banking"},

    {"slug": "how-ai-credit-scoring-works",
     "topic": "How AI-Powered Credit Scoring Works and Why It Matters",
     "keyword": "AI credit scoring",
     "category": "AI in Banking"},

    {"slug": "what-is-agentic-ai-in-finance",
     "topic": "What is Agentic AI in Finance? The Next Frontier",
     "keyword": "agentic AI finance",
     "category": "AI in Banking"},

    # ── Regulation & Compliance ───────────────────────────────────────────────
    {"slug": "what-is-kyc",
     "topic": "What is KYC (Know Your Customer)? Why Banks Need It",
     "keyword": "KYC know your customer",
     "category": "Regulatory Updates"},

    {"slug": "what-is-psd2",
     "topic": "What is PSD2? Europe's Open Banking Law Explained",
     "keyword": "PSD2 open banking regulation",
     "category": "Regulatory Updates"},

    {"slug": "what-is-aml",
     "topic": "What is AML (Anti-Money Laundering)? A Complete Guide",
     "keyword": "anti money laundering AML",
     "category": "Regulatory Updates"},

    {"slug": "what-is-dora-regulation",
     "topic": "What is DORA? The EU's Digital Operational Resilience Act Explained",
     "keyword": "DORA digital operational resilience",
     "category": "Regulatory Updates"},

    {"slug": "what-is-basel-iii",
     "topic": "What is Basel III? How Global Banking Rules Work",
     "keyword": "Basel III banking regulation",
     "category": "Regulatory Updates"},

    {"slug": "what-is-gdpr-finance",
     "topic": "How GDPR Affects Financial Services: A Practical Guide",
     "keyword": "GDPR financial services",
     "category": "Regulatory Updates"},

    {"slug": "what-is-mica-regulation",
     "topic": "What is MiCA? Europe's Crypto Regulation Explained",
     "keyword": "MiCA crypto regulation Europe",
     "category": "Regulatory Updates"},

    # ── Investment & Markets ──────────────────────────────────────────────────
    {"slug": "what-is-esg-investing",
     "topic": "What is ESG Investing? A CFO's Guide to Sustainable Finance",
     "keyword": "ESG investing sustainable finance",
     "category": "Investment AI"},

    {"slug": "what-is-private-equity",
     "topic": "What is Private Equity? How PE Firms Actually Make Money",
     "keyword": "private equity explained",
     "category": "Investment AI"},

    {"slug": "what-is-venture-debt",
     "topic": "What is Venture Debt? When Startups Borrow Instead of Dilute",
     "keyword": "venture debt startup financing",
     "category": "Investment AI"},

    {"slug": "how-does-ipo-process-work",
     "topic": "How Does an IPO Work? A Finance Professional's Guide",
     "keyword": "IPO process explained",
     "category": "Investment AI"},

    {"slug": "what-is-spac",
     "topic": "What is a SPAC? Special Purpose Acquisition Companies Explained",
     "keyword": "SPAC special purpose acquisition",
     "category": "Investment AI"},

    {"slug": "what-is-financial-inclusion",
     "topic": "What is Financial Inclusion and Why It Matters for Fintech",
     "keyword": "financial inclusion fintech",
     "category": "Fintech Explainers"},

    # ── Banking & Infrastructure ──────────────────────────────────────────────
    {"slug": "what-is-core-banking",
     "topic": "What is Core Banking? Why Banks Are Finally Modernising",
     "keyword": "core banking modernisation",
     "category": "AI in Banking"},

    {"slug": "what-is-cbdc",
     "topic": "What is a CBDC? Central Bank Digital Currencies Explained",
     "keyword": "CBDC central bank digital currency",
     "category": "Fintech Explainers"},

    {"slug": "how-cross-border-payments-work",
     "topic": "How Cross-Border Payments Work (and Why They're Still Slow)",
     "keyword": "cross border payments",
     "category": "Fintech Explainers"},

    {"slug": "what-is-correspondent-banking",
     "topic": "What is Correspondent Banking? How Global Money Moves",
     "keyword": "correspondent banking",
     "category": "Fintech Explainers"},

    {"slug": "what-is-supply-chain-finance",
     "topic": "What is Supply Chain Finance? How CFOs Optimise Working Capital",
     "keyword": "supply chain finance",
     "category": "Fintech Explainers"},

    {"slug": "what-is-invoice-financing",
     "topic": "What is Invoice Financing? A Guide for SME Finance Leaders",
     "keyword": "invoice financing",
     "category": "Fintech Explainers"},

    {"slug": "what-is-banking-as-a-service",
     "topic": "What is Banking as a Service (BaaS)? The Infrastructure Behind Fintech",
     "keyword": "banking as a service BaaS",
     "category": "Fintech Explainers"},

    # ── Emerging Topics ───────────────────────────────────────────────────────
    {"slug": "what-is-defi",
     "topic": "What is DeFi (Decentralised Finance)? Risks and Real Use Cases",
     "keyword": "DeFi decentralised finance",
     "category": "Investment AI"},

    {"slug": "what-is-tokenisation-of-assets",
     "topic": "What is Asset Tokenisation? How Blockchain Changes Investing",
     "keyword": "asset tokenisation blockchain",
     "category": "Investment AI"},

    {"slug": "what-is-insurtech",
     "topic": "What is InsurTech? How AI is Disrupting the Insurance Industry",
     "keyword": "insurtech AI insurance",
     "category": "Fintech Explainers"},

    {"slug": "what-is-wealthtech",
     "topic": "What is WealthTech? The Technology Reshaping Wealth Management",
     "keyword": "wealthtech wealth management technology",
     "category": "Fintech Explainers"},

    {"slug": "how-does-credit-scoring-work",
     "topic": "How Does Credit Scoring Work? FICO, CIBIL and Beyond",
     "keyword": "credit scoring how it works",
     "category": "Fintech Explainers"},
]


if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from core.db import configure, seed_evergreen_topics, get_evergreen_queue_status
    from sites.growstreammedia.config import SITE

    configure(SITE.db_name)
    inserted = seed_evergreen_topics(TOPICS)
    status   = get_evergreen_queue_status()
    print(f"Inserted {inserted} new topics.")
    print(f"Queue: {status['pending']} pending | {status['published']} published | {status['total']} total")
