# 10KAY Database & Data Schema Documentation

This document consolidates all schema definitions (database tables, JSON structures, and code models) for agent reference and consistency.

## Core Tables

### `companies` Table
**Purpose**: Company master data linked to SEC filings

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `ticker` | VARCHAR(10) | Stock ticker symbol (unique) |
| `name` | TEXT | Company legal name |
| `exchange` | VARCHAR(10) | Stock exchange (NYSE, NASDAQ, etc.) |
| `sector` | TEXT | Industry sector classification |
| `enabled` | BOOLEAN | Whether to include in pipeline runs |
| `added_at` | TIMESTAMPTZ | When record created |
| `metadata` | JSONB | Additional company data |

### `filings` Table
**Purpose**: SEC filing records (10-K, 10-Q) with processing status

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `company_id` | UUID | Foreign key to companies |
| `ticker` | VARCHAR(10) | Denormalized ticker for convenience |
| `filing_type` | VARCHAR(10) | "10-K" or "10-Q" |
| `fiscal_year` | INTEGER | Fiscal year of filing |
| `fiscal_quarter` | INTEGER | Quarter (1-4) for 10-Q, null for 10-K |
| `fiscal_date` | DATE | Fiscal period end date |
| `filed_date` | DATE | SEC submission date |
| `raw_document_url` | TEXT | S3 path to original filing |
| `status` | VARCHAR(20) | Pipeline status: pending → analyzed → generated → published |
| `created_at` | TIMESTAMPTZ | Record creation timestamp |
| `updated_at` | TIMESTAMPTZ | Last update timestamp |

### `content` Table
**Purpose**: Analyzed and formatted content for each filing

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key (content record ID) |
| `filing_id` | UUID | FK to filings |
| `company_id` | UUID | FK to companies |
| `version` | INTEGER | Content version number |
| `is_current` | BOOLEAN | Whether this is the latest version |
| `slug` | VARCHAR | URL slug (unique): "nvda/2025/q3/10-q" |
| `executive_summary` | TEXT | TLDR summary (2-3 sentences) |
| `key_takeaways` | JSONB | Structured analysis metadata |
| `deep_dive_opportunities` | TEXT | Opportunities section |
| `deep_dive_risks` | TEXT | Risk factors section |
| `deep_dive_strategy` | TEXT | Strategy section |
| `implications` | TEXT | Strategic implications |
| `blog_html` | TEXT | Formatted HTML for blog post |
| `email_html` | TEXT | Email newsletter HTML |
| `published_at` | TIMESTAMPTZ | When published to subscribers |
| `created_at` | TIMESTAMPTZ | When analysis created |
| `updated_at` | TIMESTAMPTZ | When last updated |

### key_takeaways JSONB Structure
```json
{
  "headline": "NVIDIA's Data Center Dominance Drives 62% Revenue Growth",
  "points": ["Point 1", "Point 2", "Point 3"],
  "metrics": {
    "revenue": "$57.0B (+62% YoY, +34% QoQ) with Data Center driving growth",
    "net_income": "$31.9B (+65% YoY) with 56% margin",
    "rd_spend": "$4.7B (+39% YoY) at 8.3% of revenue",
    "gross_margin": "73.4% (+180bps YoY) on mix and pricing",
    "operating_margin": "63.2% (+890bps YoY) showing leverage"
  },
  "sentiment": 0.8,
  "bull_case": "Dominant AI infrastructure position with expanding margins",
  "bear_case": "Data center constraints may delay customer deployments",
  "model": "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
  "tokens": 7104,
  "duration": 3.45
}
```

### `subscribers` Table
**Purpose**: Email newsletter subscriber list

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `email` | VARCHAR | Email address (unique) |
| `first_name` | VARCHAR | Subscriber first name |
| `subscription_tier` | VARCHAR | "free" or "paid" |
| `enabled` | BOOLEAN | Whether subscribed |
| `topics_subscribed` | JSONB | Array of tickers subscribed to |
| `created_at` | TIMESTAMPTZ | Subscription date |

### `email_deliveries` Table
**Purpose**: Track email sends via Resend API

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `content_id` | UUID | FK to content sent |
| `subscriber_id` | UUID | FK to subscriber |
| `status` | VARCHAR | "sent", "bounced", "complained" |
| `sent_at` | TIMESTAMPTZ | When sent |
| `resend_email_id` | VARCHAR | Resend API message ID |
| `metadata` | JSONB | Additional delivery data |

---

## Code Data Structures

### AnalysisResult Dataclass
**File**: `pipeline/analyzers/base.py`

```python
@dataclass
class AnalysisResult:
    filing_id: str
    
    # TLDR content (free tier)
    tldr_headline: str
    tldr_summary: str
    tldr_key_points: List[str]
    
    # Deep analysis (paid tier)
    deep_headline: Optional[str] = None
    deep_intro: Optional[str] = None
    deep_sections: Optional[List[Dict[str, str]]] = None
    deep_conclusion: Optional[str] = None
    
    # Metadata
    key_metrics: Optional[Dict[str, Any]] = None
    sentiment_score: Optional[float] = None  # -1.0 to 1.0
    bull_case: Optional[str] = None
    bear_case: Optional[str] = None
    risk_factors: Optional[List[str]] = None
    opportunities: Optional[List[str]] = None
    
    # AI metadata
    model_version: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    analysis_duration_seconds: Optional[float] = None
```

---

## Pipeline Data Flow

```
SEC EDGAR Filing
    ↓
Phase 1: FETCH
    • Downloads filing from SEC
    • Stores in S3
    • Creates filings row (status: pending)
    ↓
Phase 2: ANALYZE
    • Extracts text sections from filing
    • Calls Claude via AWS Bedrock
    • Returns AnalysisResult
    • Saves to content table
    ↓
Phase 3: GENERATE
    • Transforms analysis to HTML
    • Updates blog_html, email_html
    ↓
Phase 4: PUBLISH
    • Gets subscribers from database
    • Filters by tier (free/paid)
    • Sends via Resend API
    ↓
Subscriber Inboxes
```

---

## Key Details

### Financial Metrics Extraction
- **Plain Text Filings**: Searches for "ITEM X" headers, extracts 15,000 chars
- **HTML/XBRL Filings**: Uses `_extract_html_tables()`, extracts 30,000 chars with proper structure ✓

### Slug Format
```
{ticker}/{fiscal_year}/{period}/{filing_type}
Examples: "nvda/2025/q3/10-q", "aapl/2024/fy/10-k"
```

### Tier-Based Distribution
- **Free tier**: tldr_headline, tldr_summary, tldr_key_points only
- **Paid tier**: Full deep_headline, deep_sections, deep_conclusion

---

## Common Queries

### Get pending analyses
```sql
SELECT f.id, f.filing_type, f.fiscal_year
FROM filings f
WHERE f.status = 'pending'
ORDER BY f.filed_date DESC
```

### Get ready-to-publish content
```sql
SELECT c.id, c.slug
FROM content c
WHERE c.blog_html IS NOT NULL AND c.published_at IS NULL
ORDER BY c.created_at DESC
LIMIT 20
```

### Check financial metrics
```sql
SELECT c.slug, c.key_takeaways->'metrics' as financial_metrics
FROM content c
WHERE c.filing_id = '...'
```
