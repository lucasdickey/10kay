# 10KAY Database Schema Documentation

**Last Updated:** 2025-11-08
**Database:** PostgreSQL 15 on AWS RDS
**Connection:** `tenkay-db.c41o8ksoi5bt.us-east-1.rds.amazonaws.com`

---

## Table of Contents
1. [Overview](#overview)
2. [Schema vs Code Mapping](#schema-vs-code-mapping)
3. [Table Definitions](#table-definitions)
4. [JSONB Structures](#jsonb-structures)
5. [Foreign Key Relationships](#foreign-key-relationships)
6. [Known Issues & Migration Path](#known-issues--migration-path)

---

## Overview

The 10KAY database has **10 core tables** (+ 2 planned for Phase 2.5) organized around a filing analysis pipeline:

```
companies (47 tech companies)
    ↓
    ├── ir_pages (investor relations URLs)
    │       ↓
    │       └── ir_documents (scraped IR updates)
    │               ↓
    │               └── ir_filing_links (±72hr window links)
    │                       ↓
    └── filings (SEC 10-K/10-Q documents)
        ↓
        ├── document_embeddings (vector search - Phase 2.5)
        └── content (AI-generated analysis)
                ↓
                ├── analysis_embeddings (vector search - Phase 2.5)
                └── email_deliveries (sent to subscribers)
```

**Critical Schema Mismatch:**
- Database schema is **product-oriented** (executive_summary, tweet_draft, email_subject)
- Pipeline code expects **analysis-oriented** fields (tldr_headline, deep_sections, ai_metadata)
- Current workaround: Map analysis data to product fields + store metadata in JSONB

---

## Schema vs Code Mapping

### How AnalysisResult Maps to content Table

| AnalysisResult Field | Actual Column | Storage Method |
|---------------------|---------------|----------------|
| `tldr_headline` | `key_takeaways` | JSONB: `{headline: "..."}` |
| `tldr_summary` | `executive_summary` | First 500 chars |
| `tldr_key_points` | `key_takeaways` | JSONB: `{points: [...]}` |
| `deep_headline` | `key_takeaways` | JSONB: `{headline: "..."}` |
| `deep_intro` | `executive_summary` | Full text |
| `deep_sections` | `deep_dive_strategy` | Markdown formatted text |
| `deep_conclusion` | `implications` | Direct mapping |
| `opportunities` | `deep_dive_opportunities` | Newline separated |
| `risk_factors` | `deep_dive_risks` | Newline separated |
| `sentiment_score` | `key_takeaways` | JSONB: `{sentiment: 0.7}` |
| `key_metrics` | `key_takeaways` | JSONB: `{metrics: {...}}` |
| `model_version` | `key_takeaways` | JSONB: `{model: "..."}` |
| `prompt_tokens` | `key_takeaways` | JSONB: `{tokens: 1234}` |
| `completion_tokens` | `key_takeaways` | (included in tokens sum) |
| `analysis_duration_seconds` | `key_takeaways` | JSONB: `{duration: 25.3}` |

**Workaround Complexity:** 🔴 HIGH - Requires constant mapping layer

---

## Table Definitions

### 1. companies
Tech companies being tracked (47 currently)

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | UUID | NOT NULL | gen_random_uuid() | Primary key |
| `ticker` | VARCHAR | NOT NULL | - | Stock ticker (UNIQUE) |
| `name` | TEXT | NOT NULL | - | Company name |
| `exchange` | VARCHAR | NULL | - | NASDAQ, NYSE, etc |
| `sector` | TEXT | NULL | - | Technology sector |
| `enabled` | BOOLEAN | NULL | true | Active tracking flag |
| `added_at` | TIMESTAMPTZ | NULL | now() | When added to system |
| `metadata` | JSONB | NULL | - | Additional company data |

**Indexes:**
- PRIMARY KEY on `id`
- UNIQUE on `ticker`

---

### 2. filings
SEC filing documents (10-K, 10-Q)

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | UUID | NOT NULL | gen_random_uuid() | Primary key |
| `company_id` | UUID | NULL | - | FK to companies.id |
| `filing_type` | VARCHAR | NOT NULL | - | "10-K" or "10-Q" |
| `accession_number` | VARCHAR | NOT NULL | - | SEC accession # (UNIQUE) |
| `filing_date` | DATE | NOT NULL | - | Official filing date |
| `period_end_date` | DATE | NULL | - | Financial period end |
| `fiscal_year` | INTEGER | NULL | - | Fiscal year (2025, etc) |
| `fiscal_quarter` | INTEGER | NULL | - | 1-4 for 10-Q, NULL for 10-K |
| `edgar_url` | TEXT | NOT NULL | - | SEC EDGAR page URL |
| `raw_document_url` | TEXT | NULL | - | S3 URL to downloaded HTML |
| `status` | VARCHAR | NULL | 'pending' | pending → analyzed |
| `processed_at` | TIMESTAMPTZ | NULL | - | When analysis completed |
| `error_message` | TEXT | NULL | - | Error if processing failed |
| `created_at` | TIMESTAMPTZ | NULL | now() | Record creation |
| `updated_at` | TIMESTAMPTZ | NULL | now() | Last update |

**Foreign Keys:**
- `company_id` → `companies.id`

**Indexes:**
- PRIMARY KEY on `id`
- UNIQUE on `accession_number`

**Status Flow:** `pending` → `analyzed`

---

### 3. content
AI-generated analysis and content

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | UUID | NOT NULL | gen_random_uuid() | Primary key |
| `filing_id` | UUID | NULL | - | FK to filings.id |
| `company_id` | UUID | NULL | - | FK to companies.id |
| `version` | INTEGER | NULL | 1 | Content version |
| `is_current` | BOOLEAN | NULL | true | Current version flag |
| `executive_summary` | TEXT | NOT NULL | - | **TLDR intro + deep intro** |
| `key_takeaways` | JSONB | NOT NULL | - | **AI metadata + metrics** |
| `deep_dive_opportunities` | TEXT | NULL | - | **Newline-separated opportunities** |
| `deep_dive_risks` | TEXT | NULL | - | **Newline-separated risks** |
| `deep_dive_strategy` | TEXT | NULL | - | **Markdown formatted sections** |
| `implications` | TEXT | NULL | - | **Deep conclusion** |
| `tweet_draft` | TEXT | NULL | - | (Unused - future feature) |
| `email_subject` | TEXT | NULL | - | (Unused - future feature) |
| `email_preview` | TEXT | NULL | - | (Unused - future feature) |
| `audio_script` | TEXT | NULL | - | (Phase 5 - audio generation) |
| `audio_url` | TEXT | NULL | - | (Phase 5 - ElevenLabs) |
| `audio_duration_seconds` | INTEGER | NULL | - | (Phase 5) |
| `published_at` | TIMESTAMPTZ | NULL | - | Publication timestamp |
| `slug` | VARCHAR | NULL | - | URL slug (UNIQUE) |
| `created_at` | TIMESTAMPTZ | NULL | now() | Record creation |
| `updated_at` | TIMESTAMPTZ | NULL | now() | Last update |
| `created_by` | VARCHAR | NULL | 'ai' | Creator identifier |
| `meta_description` | TEXT | NULL | - | SEO meta description |
| `meta_keywords` | ARRAY | NULL | - | SEO keywords |
| `blog_html` | TEXT | NULL | - | **Generated blog post HTML** |
| `email_html` | TEXT | NULL | - | **Generated email HTML** |

**Foreign Keys:**
- `filing_id` → `filings.id`
- `company_id` → `companies.id`

**Indexes:**
- PRIMARY KEY on `id`
- UNIQUE on `slug`
- INDEX on `published_at` WHERE published_at IS NOT NULL

**Notes:**
- No `status` column - use `published_at IS NOT NULL` to check if published
- AI analysis metadata stored in `key_takeaways` JSONB (see below)

---

### 4. subscribers
Newsletter subscribers

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | UUID | NOT NULL | gen_random_uuid() | Primary key |
| `email` | VARCHAR | NOT NULL | - | Email address (UNIQUE) |
| `clerk_user_id` | VARCHAR | NULL | - | Clerk Auth ID |
| `subscription_tier` | VARCHAR | NULL | 'free' | free / paid |
| `stripe_customer_id` | VARCHAR | NULL | - | Stripe customer ID |
| `stripe_subscription_id` | VARCHAR | NULL | - | Stripe subscription ID |
| `subscription_status` | VARCHAR | NULL | - | active / canceled / past_due |
| `email_frequency` | VARCHAR | NULL | 'daily' | daily / weekly / instant |
| `interested_companies` | ARRAY | NULL | - | Array of tickers |
| `subscribed_at` | TIMESTAMPTZ | NULL | now() | Subscription date |
| `unsubscribed_at` | TIMESTAMPTZ | NULL | - | Unsubscribe date |
| `last_email_sent_at` | TIMESTAMPTZ | NULL | - | Last email timestamp |
| `created_at` | TIMESTAMPTZ | NULL | now() | Record creation |
| `updated_at` | TIMESTAMPTZ | NULL | now() | Last update |

**Indexes:**
- PRIMARY KEY on `id`
- UNIQUE on `email`

---

### 5. email_deliveries
Email delivery tracking

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | UUID | NOT NULL | gen_random_uuid() | Primary key |
| `subscriber_id` | UUID | NULL | - | FK to subscribers.id |
| `content_id` | UUID | NULL | - | FK to content.id |
| `sent_at` | TIMESTAMPTZ | NULL | now() | Sent timestamp |
| `resend_email_id` | VARCHAR | NULL | - | Resend API email ID |
| `opened_at` | TIMESTAMPTZ | NULL | - | Email opened timestamp |
| `clicked_at` | TIMESTAMPTZ | NULL | - | Link clicked timestamp |
| `status` | VARCHAR | NULL | 'sent' | sent / delivered / bounced |

**Foreign Keys:**
- `subscriber_id` → `subscribers.id`
- `content_id` → `content.id`

---

### 6. processing_logs
Pipeline execution logs

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | UUID | NOT NULL | gen_random_uuid() | Primary key |
| `filing_id` | UUID | NULL | - | FK to filings.id (nullable for general logs) |
| `step` | VARCHAR | NOT NULL | - | fetch / analyze / generate / publish |
| `status` | VARCHAR | NULL | - | success / error / in_progress (nullable) |
| `message` | TEXT | NULL | - | Log message |
| `metadata` | JSONB | NULL | - | Additional context |
| `created_at` | TIMESTAMPTZ | NULL | now() | Log timestamp |
| `level` | VARCHAR | NULL | - | debug / info / warning / error / critical |

**Foreign Keys:**
- `filing_id` → `filings.id`

---

### 7. schema_migrations
Migration tracking

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | INTEGER | NOT NULL | nextval() | Primary key |
| `migration_name` | VARCHAR | NOT NULL | - | Migration filename |
| `applied_at` | TIMESTAMPTZ | NULL | now() | Application timestamp |

---

### 8. ir_pages
Investor relations page tracking for companies

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | UUID | NOT NULL | gen_random_uuid() | Primary key |
| `company_id` | UUID | NOT NULL | - | FK to companies.id |
| `ticker` | VARCHAR | NOT NULL | - | Denormalized ticker |
| `ir_url` | TEXT | NOT NULL | - | Company IR page URL |
| `ir_url_verified_at` | TIMESTAMPTZ | NULL | - | Last URL verification |
| `scraping_enabled` | BOOLEAN | NULL | true | Enable/disable scraping |
| `scraping_frequency` | VARCHAR | NULL | 'daily' | daily / on_filing / manual |
| `last_scraped_at` | TIMESTAMPTZ | NULL | - | Last scrape timestamp |
| `next_scrape_at` | TIMESTAMPTZ | NULL | - | Scheduled next scrape |
| `scraper_config` | JSONB | NULL | - | Custom scraping rules |
| `status` | VARCHAR | NULL | 'active' | active / paused / failed / not_found |
| `error_message` | TEXT | NULL | - | Last error if failed |
| `consecutive_failures` | INTEGER | NULL | 0 | Failure counter |
| `created_at` | TIMESTAMPTZ | NULL | now() | Record creation |
| `updated_at` | TIMESTAMPTZ | NULL | now() | Last update |

**Foreign Keys:**
- `company_id` → `companies.id`

**Indexes:**
- PRIMARY KEY on `id`
- UNIQUE on `company_id`
- INDEX on `next_scrape_at` WHERE scraping_enabled = true
- GIN INDEX on `scraper_config`

**Purpose:** Store IR page URLs and scraping configuration for each company

---

### 9. ir_documents
Individual documents/updates scraped from IR pages

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | UUID | NOT NULL | gen_random_uuid() | Primary key |
| `ir_page_id` | UUID | NOT NULL | - | FK to ir_pages.id |
| `company_id` | UUID | NOT NULL | - | FK to companies.id |
| `ticker` | VARCHAR | NOT NULL | - | Denormalized ticker |
| `title` | TEXT | NOT NULL | - | Document title |
| `document_url` | TEXT | NOT NULL | - | Document URL |
| `document_type` | VARCHAR | NULL | - | press_release / earnings_presentation / etc |
| `published_at` | TIMESTAMPTZ | NOT NULL | - | Document publish date |
| `scraped_at` | TIMESTAMPTZ | NULL | now() | When scraped |
| `summary` | TEXT | NULL | - | Extracted summary |
| `raw_content` | TEXT | NULL | - | Full scraped content |
| `content_hash` | VARCHAR | NULL | - | SHA256 for deduplication |
| `analyzed_at` | TIMESTAMPTZ | NULL | - | AI analysis timestamp |
| `analysis_summary` | TEXT | NULL | - | AI-generated summary |
| `relevance_score` | NUMERIC(3,2) | NULL | - | 0.00-1.00 relevance |
| `key_topics` | JSONB | NULL | - | Extracted topics/themes |
| `status` | VARCHAR | NULL | 'pending' | pending / analyzed / linked / archived |
| `metadata` | JSONB | NULL | - | Additional data |
| `created_at` | TIMESTAMPTZ | NULL | now() | Record creation |
| `updated_at` | TIMESTAMPTZ | NULL | now() | Last update |

**Foreign Keys:**
- `ir_page_id` → `ir_pages.id`
- `company_id` → `companies.id`

**Indexes:**
- PRIMARY KEY on `id`
- UNIQUE on `(ir_page_id, content_hash)`
- INDEX on `company_id, published_at DESC`
- INDEX on `status`
- INDEX on `scraped_at` WHERE status = 'pending'
- GIN INDEX on `key_topics`

**Purpose:** Track individual IR documents within ±72 hour windows of filings

---

### 10. ir_filing_links
Links between IR documents and SEC filings (many-to-many)

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | UUID | NOT NULL | gen_random_uuid() | Primary key |
| `ir_document_id` | UUID | NOT NULL | - | FK to ir_documents.id |
| `filing_id` | UUID | NOT NULL | - | FK to filings.id |
| `time_delta_hours` | INTEGER | NULL | - | Hours from filing (±72) |
| `window_type` | VARCHAR | NOT NULL | - | pre_filing / post_filing / concurrent |
| `link_type` | VARCHAR | NULL | 'auto' | auto / manual / suggested |
| `relevance_reason` | TEXT | NULL | - | Why linked (AI-generated) |
| `confidence_score` | NUMERIC(3,2) | NULL | - | 0.00-1.00 confidence |
| `show_on_filing_page` | BOOLEAN | NULL | true | Display on 10-K/Q page |
| `show_on_ticker_page` | BOOLEAN | NULL | true | Display on ticker page |
| `display_order` | INTEGER | NULL | 0 | Display ordering |
| `created_at` | TIMESTAMPTZ | NULL | now() | Record creation |
| `created_by` | VARCHAR | NULL | 'system' | system / ai / admin |

**Foreign Keys:**
- `ir_document_id` → `ir_documents.id`
- `filing_id` → `filings.id`

**Indexes:**
- PRIMARY KEY on `id`
- UNIQUE on `(ir_document_id, filing_id)`
- INDEX on `filing_id, display_order` WHERE show_on_filing_page = true

**Purpose:** Link IR documents to filings within ±72 hour windows

---

### 11. document_embeddings (Planned - Phase 2.5)
Vector embeddings for raw SEC filing content (chunked)

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | UUID | NOT NULL | gen_random_uuid() | Primary key |
| `filing_id` | UUID | NULL | - | FK to filings.id |
| `company_id` | UUID | NULL | - | FK to companies.id |
| `chunk_index` | INTEGER | NOT NULL | - | Position in document (0, 1, 2...) |
| `content_text` | TEXT | NOT NULL | - | Original text chunk |
| `token_count` | INTEGER | NULL | - | Tokens in this chunk |
| `embedding` | VECTOR(1024) | NULL | - | Embedding vector (pgvector) |
| `section_type` | VARCHAR | NULL | - | 'business_overview', 'risk_factors', etc. |
| `page_number` | INTEGER | NULL | - | Approximate page in original PDF |
| `embedding_model` | VARCHAR | NULL | 'amazon.titan-embed-text-v2:0' | Embedding model used |
| `created_at` | TIMESTAMPTZ | NULL | now() | Record creation |

**Foreign Keys:**
- `filing_id` → `filings.id`
- `company_id` → `companies.id`

**Indexes:**
- PRIMARY KEY on `id`
- INDEX on `filing_id`
- INDEX on `company_id`
- IVFFLAT INDEX on `embedding` using cosine distance

**Use Cases:**
- Semantic search across raw filing content
- RAG (Retrieval Augmented Generation) for chatbot
- Find similar filing sections across companies

---

### 9. analysis_embeddings (Planned - Phase 2.5)
Vector embeddings for AI-generated analysis sections

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | UUID | NOT NULL | gen_random_uuid() | Primary key |
| `content_id` | UUID | NULL | - | FK to content.id |
| `company_id` | UUID | NULL | - | FK to companies.id |
| `filing_id` | UUID | NULL | - | FK to filings.id |
| `section_name` | VARCHAR | NOT NULL | - | 'executive_summary', 'opportunities', etc. |
| `content_text` | TEXT | NOT NULL | - | The actual analysis text |
| `token_count` | INTEGER | NULL | - | Tokens in this section |
| `embedding` | VECTOR(1024) | NULL | - | Embedding vector (pgvector) |
| `filing_type` | VARCHAR | NULL | - | '10-K' or '10-Q' |
| `fiscal_year` | INTEGER | NULL | - | Fiscal year for filtering |
| `fiscal_quarter` | INTEGER | NULL | - | Fiscal quarter for filtering |
| `ticker` | VARCHAR | NULL | - | Denormalized ticker for easy querying |
| `embedding_model` | VARCHAR | NULL | 'amazon.titan-embed-text-v2:0' | Embedding model used |
| `created_at` | TIMESTAMPTZ | NULL | now() | Record creation |

**Foreign Keys:**
- `content_id` → `content.id`
- `company_id` → `companies.id`
- `filing_id` → `filings.id`

**Indexes:**
- PRIMARY KEY on `id`
- INDEX on `content_id`
- INDEX on `company_id`
- INDEX on `section_name`
- INDEX on `ticker`
- IVFFLAT INDEX on `embedding` using cosine distance

**Use Cases:**
- Find companies with similar strategic profiles
- Cross-company theme analysis
- Compare risk factors, opportunities across companies
- Semantic search within analyzed content

---

## JSONB Structures

### content.key_takeaways

Stores AI analysis metadata and metrics:

```json
{
  "headline": "Apple's Services Growth Offsets Hardware Slowdown",
  "points": [
    "Financial Performance Overview",
    "Services Transformation",
    "Product Innovation Pipeline"
  ],
  "sentiment": 0.7,
  "metrics": {
    "revenue": "$397.3B (+4.2% YoY)",
    "margins": "Gross: 43.8% (+180bps), Operating: 30.4% (+90bps)",
    "growth_indicators": {
      "services_revenue": "$95.4B (+17.8%)",
      "r&d_spend": "$29.8B (+14.3%)",
      "paid_subscriptions": "950M (+125M YoY)"
    }
  },
  "model": "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
  "tokens": 1626,
  "duration": 25.92
}
```

### companies.metadata

Additional company data:

```json
{
  "founded": "1976",
  "employees": 161000,
  "market_cap": "3.5T",
  "ceo": "Tim Cook"
}
```

---

## Foreign Key Relationships

```
companies (1)
    ↓
    ├── ir_pages (1) via company_id
    │       ↓
    │       └── ir_documents (*) via ir_page_id
    │               ↓
    │               └── ir_filing_links (*) via ir_document_id
    │
    ├── filings (*) via company_id
    │       ↓
    │       ├── ir_filing_links (*) via filing_id
    │       ├── content (1) via filing_id
    │       │       ↓
    │       │       ├── email_deliveries (*) via content_id
    │       │       └── analysis_embeddings (*) via content_id
    │       │
    │       ├── processing_logs (*) via filing_id
    │       └── document_embeddings (*) via filing_id
    │
    ├── content (*) via company_id
    ├── document_embeddings (*) via company_id
    └── analysis_embeddings (*) via company_id

subscribers (1)
    ↓
    └── email_deliveries (*) via subscriber_id
```

---

## Known Issues & Migration Path

### Issue #1: Analysis vs Product Field Mismatch

**Problem:** Code expects analysis fields (tldr_headline, deep_sections) but database has product fields (executive_summary, tweet_draft).

**Current Workaround:**
- Store analysis metadata in `key_takeaways` JSONB
- Map deep_sections to `deep_dive_strategy` as markdown
- Split opportunities/risks on newlines

**Recommended Fix:** Add dedicated analysis columns

```sql
-- Migration 007: Add AI Analysis Columns
ALTER TABLE content
ADD COLUMN ai_analysis JSONB,  -- Full structured analysis from Claude
ADD COLUMN analyzed_at TIMESTAMPTZ;

-- Migrate existing data
UPDATE content SET
    ai_analysis = jsonb_build_object(
        'headline', key_takeaways->>'headline',
        'sections', (/* parse from deep_dive_strategy */),
        'metrics', key_takeaways->'metrics',
        'sentiment', key_takeaways->'sentiment'
    ),
    analyzed_at = created_at;
```

**Benefits:**
- Clear separation of concerns
- Easier to re-process/regenerate product content
- Full audit trail of AI analysis
- No lossy mapping

---

### Issue #2: Missing status Column in content

**Problem:** Code assumes `content.status` exists for filtering published content.

**Current Workaround:** Use `WHERE executive_summary IS NOT NULL` or `WHERE published_at IS NOT NULL`

**Recommended Fix:** Add status column

```sql
ALTER TABLE content
ADD COLUMN status VARCHAR DEFAULT 'draft';

-- Options: draft, review, published, archived
CREATE INDEX idx_content_status ON content(status);
```

---

### Issue #3: fiscal_period vs fiscal_quarter Inconsistency

**Problem:**
- Database stores `fiscal_quarter` as INTEGER (1-4, NULL for FY)
- Code expects `fiscal_period` as STRING ("Q1", "Q2", "Q3", "Q4", "FY")

**Current Workaround:** Convert on read:
```python
fiscal_period = f'Q{fiscal_quarter}' if fiscal_quarter else 'FY'
```

**Recommendation:** Keep as-is - integer storage is more efficient, conversion is trivial

---

## Migration History

| # | Filename | Description | Applied |
|---|----------|-------------|---------|
| 001 | initial_schema.sql | Create all tables | ✅ |
| 002 | subscribers.sql | Add subscribers, email_deliveries | ✅ |
| 003 | indexes_and_rls.sql | Add indexes and RLS policies | ✅ |
| 004 | fix_processing_logs.sql | Add level column | ✅ |
| 005 | make_status_nullable.sql | Allow NULL status | ✅ |
| 006 | add_html_columns.sql | Add blog_html, email_html | ✅ |
| 007 | add_scheduled_earnings.sql | Add scheduled_earnings table | ✅ |
| 008 | add_investor_relations_tracking.sql | Add ir_pages, ir_documents, ir_filing_links | 🚀 Ready to apply |
| 009 | add_vector_embeddings.sql | Add document_embeddings, analysis_embeddings tables | 📋 Phase 2.5 |

---

## Best Practices

1. **Always check this document** before writing queries
2. **Use typed queries** with proper column validation
3. **Update this doc** when schema changes
4. **Test migrations** in local Postgres before RDS
5. **Version JSONB schemas** in this doc when changing structure

---

**Questions?** See `migrations/` folder for SQL source of truth.
