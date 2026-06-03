"""
Evergreen topic queue — seed data.

Each entry will become a standalone 1500-word explainer article.
Topics are chosen for high search volume + low competition in the
finance/fintech/AI space. Add new topics here as needed.

Run `python data/evergreen_topics.py` to seed/top-up the MongoDB queue.
"""

TOPICS = [
    # ── PRIORITY: Exact-match for Google Search Console queries ───────────────
    # These queries are already getting impressions — publish these first
    # to convert impressions → clicks.

    {"slug": "best-ai-billing-providers-usage-based-billing",
     "topic": "Best AI Billing Providers for Usage-Based Billing in 2026",
     "keyword": "AI billing providers usage-based billing",
     "category": "SME & Startup Finance",
     "article_hint": "comparison"},

    {"slug": "usage-based-billing-explained-cfo-guide",
     "topic": "Usage-Based Billing Explained: The Complete CFO Guide",
     "keyword": "usage-based billing",
     "category": "SME & Startup Finance"},

    {"slug": "stripe-revenue-operations-finance-guide",
     "topic": "Stripe Revenue Operations: What Finance Leaders Need to Know",
     "keyword": "stripe revenue operations",
     "category": "SME & Startup Finance"},

    {"slug": "ai-agents-financial-crime-detection",
     "topic": "AI Agents for Financial Crime Detection: How Banks Are Fighting Fraud",
     "keyword": "AI agents financial crime",
     "category": "AI in Banking"},

    {"slug": "agentic-commerce-finance-explained",
     "topic": "What is Agentic Commerce? How AI Agents Are Changing Finance",
     "keyword": "agentic commerce finance",
     "category": "AI in Banking"},

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

    # ── SME & Startup Finance ─────────────────────────────────────────────────
    {"slug": "how-to-raise-series-a",
     "topic": "How to Raise a Series A: What VCs Actually Look For in 2026",
     "keyword": "series A funding",
     "category": "SME & Startup Finance"},

    {"slug": "startup-cash-flow-management",
     "topic": "Startup Cash Flow Management: How to Extend Your Runway",
     "keyword": "startup cash flow management",
     "category": "SME & Startup Finance"},

    {"slug": "what-is-venture-capital",
     "topic": "What is Venture Capital? How VC Funding Actually Works",
     "keyword": "venture capital explained",
     "category": "SME & Startup Finance"},

    {"slug": "startup-valuation-methods",
     "topic": "How Startup Valuation Works: The 5 Methods VCs Use",
     "keyword": "startup valuation methods",
     "category": "SME & Startup Finance"},

    {"slug": "sme-financing-options",
     "topic": "SME Financing Options: Loans, Equity, Grants and Alternatives",
     "keyword": "SME financing options",
     "category": "SME & Startup Finance"},

    {"slug": "what-is-equity-dilution",
     "topic": "What is Equity Dilution? How Startup Founders Protect Ownership",
     "keyword": "equity dilution startup",
     "category": "SME & Startup Finance"},

    {"slug": "fintech-tools-for-startups",
     "topic": "Best Fintech Tools for Startups in 2026: CFO Stack Guide",
     "keyword": "fintech tools for startups",
     "category": "SME & Startup Finance"},

    {"slug": "what-is-revenue-based-financing",
     "topic": "What is Revenue-Based Financing? The Alternative to Giving Up Equity",
     "keyword": "revenue based financing",
     "category": "SME & Startup Finance"},

    {"slug": "cap-table-explained",
     "topic": "Cap Table Explained: What Every Startup Founder Must Know",
     "keyword": "cap table startup",
     "category": "SME & Startup Finance"},

    {"slug": "startup-cfo-responsibilities",
     "topic": "What Does a Startup CFO Actually Do? Roles and Key Metrics",
     "keyword": "startup CFO responsibilities",
     "category": "SME & Startup Finance"},

    {"slug": "how-to-read-term-sheet",
     "topic": "How to Read a Term Sheet: Key Clauses Founders Must Negotiate",
     "keyword": "term sheet startup funding",
     "category": "SME & Startup Finance"},

    {"slug": "sme-working-capital-management",
     "topic": "Working Capital Management for SMEs: Practical CFO Guide",
     "keyword": "working capital management SME",
     "category": "SME & Startup Finance"},

    # ── ESG & Climate Finance ─────────────────────────────────────────────────
    {"slug": "what-is-csrd",
     "topic": "What is CSRD? Europe's New Sustainability Reporting Law Explained",
     "keyword": "CSRD sustainability reporting",
     "category": "ESG & Climate Finance"},

    {"slug": "what-are-green-bonds",
     "topic": "What Are Green Bonds? How Climate Finance Actually Works",
     "keyword": "green bonds climate finance",
     "category": "ESG & Climate Finance"},

    {"slug": "esg-investing-explained",
     "topic": "ESG Investing Explained: Beyond the Buzzword for Finance Professionals",
     "keyword": "ESG investing explained",
     "category": "ESG & Climate Finance"},

    {"slug": "what-is-carbon-credit-market",
     "topic": "What is the Carbon Credit Market? How Companies Trade Emissions",
     "keyword": "carbon credit market",
     "category": "ESG & Climate Finance"},

    {"slug": "esg-reporting-framework-comparison",
     "topic": "GRI vs SASB vs TCFD: Which ESG Reporting Framework Should You Use?",
     "keyword": "ESG reporting framework",
     "category": "ESG & Climate Finance"},

    {"slug": "what-is-net-zero-finance",
     "topic": "What is Net Zero Finance? How Banks Are Funding the Climate Transition",
     "keyword": "net zero finance",
     "category": "ESG & Climate Finance"},

    {"slug": "esg-fund-performance-analysis",
     "topic": "Do ESG Funds Outperform? What the Data Actually Shows",
     "keyword": "ESG fund performance",
     "category": "ESG & Climate Finance"},

    {"slug": "what-is-sustainable-finance-taxonomy",
     "topic": "What is the EU Sustainable Finance Taxonomy? A CFO Explainer",
     "keyword": "EU sustainable finance taxonomy",
     "category": "ESG & Climate Finance"},

    {"slug": "greenwashing-in-finance",
     "topic": "What is Greenwashing in Finance? How Regulators Are Cracking Down",
     "keyword": "greenwashing finance regulation",
     "category": "ESG & Climate Finance"},

    {"slug": "climate-risk-banking",
     "topic": "How Banks Are Managing Climate Risk: Stress Tests and Scenarios",
     "keyword": "climate risk banking",
     "category": "ESG & Climate Finance"},

    # ── PropTech & Real Estate Finance ────────────────────────────────────────
    {"slug": "what-is-proptech",
     "topic": "What is PropTech? How Technology is Transforming Real Estate Finance",
     "keyword": "proptech real estate technology",
     "category": "PropTech & Real Estate"},

    {"slug": "how-reits-work",
     "topic": "How REITs Work: A Finance Professional's Complete Guide",
     "keyword": "REIT explained",
     "category": "PropTech & Real Estate"},

    {"slug": "tokenised-real-estate",
     "topic": "Tokenised Real Estate: How Blockchain is Democratising Property Investment",
     "keyword": "tokenised real estate investment",
     "category": "PropTech & Real Estate"},

    {"slug": "commercial-real-estate-finance",
     "topic": "Commercial Real Estate Finance: Key Metrics Every CFO Must Know",
     "keyword": "commercial real estate finance",
     "category": "PropTech & Real Estate"},

    {"slug": "ai-in-property-valuation",
     "topic": "How AI is Changing Property Valuation and Mortgage Underwriting",
     "keyword": "AI property valuation",
     "category": "PropTech & Real Estate"},

    {"slug": "fractional-property-investment",
     "topic": "What is Fractional Property Investment? The New Way to Buy Real Estate",
     "keyword": "fractional property investment",
     "category": "PropTech & Real Estate"},

    {"slug": "real-estate-debt-instruments",
     "topic": "Real Estate Debt Instruments: Mortgages, CMBS and Private Credit",
     "keyword": "real estate debt instruments",
     "category": "PropTech & Real Estate"},

    {"slug": "proptech-due-diligence",
     "topic": "PropTech Due Diligence: How to Evaluate Real Estate Technology Vendors",
     "keyword": "proptech vendor due diligence",
     "category": "PropTech & Real Estate"},

    # ── Wealth Management ─────────────────────────────────────────────────────
    {"slug": "what-is-family-office",
     "topic": "What is a Family Office? How Ultra-High-Net-Worth Families Manage Wealth",
     "keyword": "family office wealth management",
     "category": "Wealth Management"},

    {"slug": "alternative-investments-explained",
     "topic": "Alternative Investments Explained: Private Equity, Hedge Funds and More",
     "keyword": "alternative investments explained",
     "category": "Wealth Management"},

    {"slug": "ai-in-wealth-management",
     "topic": "How AI is Transforming Wealth Management and Private Banking",
     "keyword": "AI wealth management",
     "category": "Wealth Management"},

    {"slug": "private-banking-vs-wealth-management",
     "topic": "Private Banking vs Wealth Management: What's the Difference?",
     "keyword": "private banking wealth management",
     "category": "Wealth Management"},

    {"slug": "how-hedge-funds-work",
     "topic": "How Hedge Funds Work: Strategies, Fees and What HNIs Need to Know",
     "keyword": "how hedge funds work",
     "category": "Wealth Management"},

    {"slug": "estate-planning-for-hni",
     "topic": "Estate Planning for HNIs: Trusts, Wills and Tax Optimisation",
     "keyword": "estate planning high net worth",
     "category": "Wealth Management"},

    {"slug": "multi-asset-portfolio-strategy",
     "topic": "Multi-Asset Portfolio Strategy: How Institutional Investors Allocate",
     "keyword": "multi asset portfolio strategy",
     "category": "Wealth Management"},

    {"slug": "what-is-discretionary-portfolio-management",
     "topic": "What is Discretionary Portfolio Management? When to Hand Over Control",
     "keyword": "discretionary portfolio management",
     "category": "Wealth Management"},

    {"slug": "offshore-wealth-management",
     "topic": "Offshore Wealth Management: Compliance, Risk and Legitimate Uses",
     "keyword": "offshore wealth management",
     "category": "Wealth Management"},

    {"slug": "impact-investing-explained",
     "topic": "What is Impact Investing? Generating Returns While Doing Good",
     "keyword": "impact investing",
     "category": "Wealth Management"},

    # ── Healthcare Finance ────────────────────────────────────────────────────
    {"slug": "what-is-revenue-cycle-management",
     "topic": "What is Revenue Cycle Management (RCM)? A Hospital CFO Guide",
     "keyword": "revenue cycle management healthcare",
     "category": "Healthcare Finance"},

    {"slug": "ai-in-healthcare-finance",
     "topic": "How AI is Cutting Costs in Hospital Finance and Medical Billing",
     "keyword": "AI healthcare finance",
     "category": "Healthcare Finance"},

    {"slug": "medtech-funding-landscape",
     "topic": "MedTech Funding in 2026: Where the Investment is Going",
     "keyword": "medtech funding investment",
     "category": "Healthcare Finance"},

    {"slug": "hospital-cfo-challenges",
     "topic": "Top 7 Financial Challenges Hospital CFOs Face in 2026",
     "keyword": "hospital CFO financial challenges",
     "category": "Healthcare Finance"},

    {"slug": "value-based-care-finance",
     "topic": "What is Value-Based Care? The Financial Model Replacing Fee-for-Service",
     "keyword": "value based care finance",
     "category": "Healthcare Finance"},

    {"slug": "pharma-pricing-strategy",
     "topic": "Pharma Pricing Strategy: How Drug Prices Are Set and Regulated",
     "keyword": "pharmaceutical pricing strategy",
     "category": "Healthcare Finance"},

    {"slug": "health-insurance-finance-explained",
     "topic": "How Health Insurance Finances Work: Premiums, Claims and Reserves",
     "keyword": "health insurance finance",
     "category": "Healthcare Finance"},

    # ── Crypto & Web3 ─────────────────────────────────────────────────────────
    {"slug": "institutional-bitcoin-strategy",
     "topic": "Bitcoin as a Corporate Treasury Asset: What CFOs Need to Know",
     "keyword": "bitcoin treasury strategy",
     "category": "Crypto & Web3"},

    {"slug": "what-is-mica-crypto-regulation",
     "topic": "What is MiCA? Europe's Crypto Regulation and What it Means for Institutions",
     "keyword": "MiCA crypto regulation",
     "category": "Crypto & Web3"},

    {"slug": "stablecoin-explained-institutional",
     "topic": "Stablecoins Explained for Finance Professionals: USDC, USDT and CBDCs",
     "keyword": "stablecoin institutional finance",
     "category": "Crypto & Web3"},

    {"slug": "crypto-custody-institutional",
     "topic": "Crypto Custody for Institutions: How Banks Safeguard Digital Assets",
     "keyword": "crypto custody institutional",
     "category": "Crypto & Web3"},

    {"slug": "defi-for-institutions",
     "topic": "DeFi for Institutional Investors: Opportunities and Regulatory Risks",
     "keyword": "DeFi institutional investors",
     "category": "Crypto & Web3"},

    {"slug": "crypto-accounting-tax",
     "topic": "Crypto Accounting and Tax: What CFOs Must Know Before Filing",
     "keyword": "crypto accounting tax CFO",
     "category": "Crypto & Web3"},

    {"slug": "tokenisation-of-traditional-assets",
     "topic": "Tokenisation of Traditional Assets: Stocks, Bonds and Beyond",
     "keyword": "tokenisation traditional assets",
     "category": "Crypto & Web3"},

    {"slug": "cbdc-impact-on-banking",
     "topic": "CBDC Impact on Banking: What Central Bank Digital Currencies Mean for Banks",
     "keyword": "CBDC impact banking",
     "category": "Crypto & Web3"},

    {"slug": "blockchain-trade-finance",
     "topic": "How Blockchain is Transforming Trade Finance and Letters of Credit",
     "keyword": "blockchain trade finance",
     "category": "Crypto & Web3"},
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
