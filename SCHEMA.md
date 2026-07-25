# 10KAY Database & Data Schema Documentation

This document consolidates all schema definitions (database tables, JSON structures, and code models) for agent reference and consistency.

> **The migrations are the source of truth, not this file.** Columns documented
> here that did not exist in `migrations/` have caused real production failures
> (`subscribers.enabled`, `subscribers.first_name`, `subscribers.topics_subscribed`,
> `email_deliveries.metadata` — every query touching them raised `UndefinedColumn`).
> When code and this document disagree, check `migrations/` and fix whichever is wrong.

## Writing data

**Do not issue INSERT/UPDATE from fetchers, analyzers, generators, publishers or
scripts.** Use `pipeline/db`, which owns every write:

```python
from pipeline.db import connect, transaction, savepoint, FilingRepository, FilingRecord

conn = connect(config.database.url)
result = FilingRepository(conn).upsert(FilingRecord(...))   # idempotent
```

- `pipeline/db/models.py` — typed row contracts that validate before SQL is issued
- `pipeline/db/repositories.py` — one idempotent upsert per table
- `pipeline/db/connection.py` — `transaction()`, `savepoint()`, `read_cursor()`, `ConnectionPool`
- `pipeline/analyzers/synthesis.py` — model response → validated fields

Every repository write is `INSERT ... ON CONFLICT DO UPDATE` against a real
unique index, so re-running any phase is safe. Batch writes wrap each row in a
savepoint: one bad row fails alone instead of aborting the transaction.

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
**Migrations**: 001, 003 (unique index)

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `company_id` | UUID | Foreign key to companies |
| `filing_type` | VARCHAR(10) | "10-K" or "10-Q" |
| `accession_number` | VARCHAR(25) | SEC identifier (**unique**) |
| `filing_date` | DATE | SEC submission date |
| `period_end_date` | DATE | Fiscal period end date |
| `fiscal_year` | INTEGER | Fiscal year of filing |
| `fiscal_quarter` | INTEGER | Quarter (1-4) for 10-Q, NULL for 10-K |
| `edgar_url` | TEXT | EDGAR document URL (NOT NULL) |
| `raw_document_url` | TEXT | S3 path to original filing |
| `status` | VARCHAR(20) | pending → analyzed → generated → published |
| `processed_at` | TIMESTAMPTZ | When processing finished |
| `error_message` | TEXT | Last failure reason |
| `created_at` / `updated_at` | TIMESTAMPTZ | Timestamps |

There is **no** `ticker`, `fiscal_date` or `filed_date` column — join `companies`
for the ticker and use `period_end_date` / `filing_date`.

**Two unique keys**, and a write can collide with either:

| Index | Columns | Collides when |
|-------|---------|---------------|
| `filings_accession_number_key` | `accession_number` | the same filing is re-fetched |
| `idx_filings_unique` | `company_id, filing_type, fiscal_year, COALESCE(fiscal_quarter, 0)` | an **amended** filing brings a new accession for an existing period |

`FilingRepository.upsert()` handles both; the second is why a plain
`ON CONFLICT (accession_number)` is not sufficient.

### `content` Table
**Purpose**: Analyzed and formatted content for each filing

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key (content record ID) |
| `filing_id` | UUID | FK to filings |
| `company_id` | UUID | FK to companies |
| `version` | INTEGER | Content version number |
| `is_current` | BOOLEAN | Whether this is the latest version |
| `slug` | VARCHAR(255) | URL slug (**unique**): "nvda/2025/q3/10-q" |
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

Unique index `idx_content_filing_current` on `filing_id WHERE is_current`
(migration 010) gives `ContentRepository.upsert_analysis()` its conflict target:
one live analysis per filing, superseded versions retained with `is_current = false`.

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
  "sections": [{"title": "...", "content": "..."}],
  "conclusion": "Forward-looking synthesis",
  "model": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
  "tokens": 7104,
  "duration": 3.45,
  "analyzed_at": "2025-11-20T14:03:11",
  "synthesis": {
    "repaired_json": true,
    "missing_fields": ["conclusion"],
    "coerced_fields": [],
    "warnings": ["response truncated at max_tokens"]
  }
}
```

`synthesis` is present only when normalization had to repair or infer something.
Query it to find analyses worth regenerating:

```sql
SELECT slug, key_takeaways->'synthesis' AS issues
FROM content
WHERE is_current AND key_takeaways ? 'synthesis'
ORDER BY created_at DESC;
```

### `subscribers` Table
**Purpose**: Email newsletter subscriber list
**Migrations**: 002, 007_enhance_subscriber_preferences

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `email` | VARCHAR(255) | Email address (unique) |
| `clerk_user_id` | VARCHAR(255) | Clerk auth ID (unique, NULL for email-only) |
| `subscription_tier` | VARCHAR(20) | "free" or "paid" |
| `subscription_status` | VARCHAR(20) | "active", "canceled", "past_due", ... |
| `stripe_customer_id` | VARCHAR(255) | Stripe customer |
| `stripe_subscription_id` | VARCHAR(255) | Stripe subscription |
| `email_enabled` | BOOLEAN | Whether email delivery is on (007) |
| `email_frequency` | VARCHAR(20) | "daily", "weekly", "off" |
| `content_preference` | VARCHAR(20) | "tldr" or "full" (007) |
| `delivery_time` | TIME | Preferred send time (007) |
| `interested_companies` | UUID[] | Company IDs followed; empty/NULL = all |
| `subscribed_at` | TIMESTAMPTZ | Subscription date |
| `unsubscribed_at` | TIMESTAMPTZ | NULL while subscribed |
| `last_email_sent_at` | TIMESTAMPTZ | Last send |

There is **no** `enabled`, `first_name` or `topics_subscribed` column. Use
`email_enabled`, derive a greeting from `email`, and read `interested_companies`.

### `email_deliveries` Table
**Purpose**: Track email sends via Resend API
**Migrations**: 002, 010 (`metadata`)

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `content_id` | UUID | FK to content sent |
| `subscriber_id` | UUID | FK to subscriber (NULL for batch-level records) |
| `status` | VARCHAR(20) | "sent", "delivered", "opened", "clicked", "bounced", "failed" |
| `sent_at` | TIMESTAMPTZ | When sent |
| `resend_email_id` | VARCHAR(255) | Resend API message ID |
| `opened_at` / `clicked_at` | TIMESTAMPTZ | Engagement timestamps |
| `metadata` | JSONB | Channel details — **added in migration 010** |

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
  AND NOT EXISTS (SELECT 1 FROM content c WHERE c.filing_id = f.id AND c.is_current)
ORDER BY f.filing_date DESC
```

The `NOT EXISTS` guard matters: a crash between writing content and updating the
status leaves a filing at `pending` with its analysis already stored, and without
the guard the next run pays Bedrock for it again. Prefer
`FilingRepository.pending()` over hand-writing this.

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
