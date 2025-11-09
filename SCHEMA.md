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

The 10KAY database has **7 tables** organized around a filing analysis pipeline:

```
companies (47 tech companies)
    ↓
filings (SEC 10-K/10-Q documents)
    ↓
content (AI-generated analysis)
    ↓
email_deliveries (sent to subscribers)
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
    ├── filings (*) via company_id
    │       ↓
    │       └── content (1) via filing_id
    │               ↓
    │               └── email_deliveries (*) via content_id
    │
    └── content (*) via company_id

subscribers (1)
    ↓
    └── email_deliveries (*) via subscriber_id

filings (1)
    ↓
    └── processing_logs (*) via filing_id
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
| 002 | seed_companies.sql | Load 47 tech companies | ✅ |
| 003 | (skipped) | - | - |
| 004 | fix_processing_logs.sql | Add level column | ✅ |
| 005 | make_status_nullable.sql | Allow NULL status | ✅ |
| 006 | add_html_columns.sql | Add blog_html, email_html | ✅ |
| 007 | (planned) | Add ai_analysis, status columns | ⏳ |

---

## Best Practices

1. **Always check this document** before writing queries
2. **Use typed queries** with proper column validation
3. **Update this doc** when schema changes
4. **Test migrations** in local Postgres before RDS
5. **Version JSONB schemas** in this doc when changing structure

---

**Questions?** See `migrations/` folder for SQL source of truth.
