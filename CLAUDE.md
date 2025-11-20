# 10kay Project Architecture & Context

**⚠️ SCHEMA REFERENCE**: For complete and up-to-date database schema definitions, JSON structures, Python dataclasses, and common queries, see **[SCHEMA.md](./SCHEMA.md)**. This document provides a single source of truth for all schema definitions across code, database, and data layers.

## Deployment

**Platform:** Vercel
**Command:** `vercel deploy --prod`
**Production URL:** https://10kay-gkolyslg9-lucasdickeys-projects.vercel.app

## Tech Stack

- **Framework:** Next.js 15.5.6
- **Language:** TypeScript
- **Styling:** Tailwind CSS
- **Package Manager:** npm
- **Runtime:** Node.js
- **Database:** PostgreSQL (AWS RDS)
- **AI/LLM:** AWS Bedrock with Claude Sonnet 4.5

## Project Structure

### Key Components
- `components/LatestAnalysesFilter.tsx` - Main dashboard filter for analyses with date range selection
  - Default filter: "Trailing 2 Weeks"
  - Features: Fuzzy search by ticker/company name, sentiment badges, filing information

### Pages
- `app/page.tsx` - Home page with Latest Analyses
- `app/[ticker]` - Individual company analysis page
- `app/[ticker]/[year]/[quarter]/[type]` - Detailed filing analysis
- `app/analysis/[id]` - Analysis detail page
- `app/api/analyses` - API endpoints for analysis data
- `app/api/upcoming-filings` - Upcoming filings endpoint

## Development Notes

- The LatestAnalysesFilter component uses React hooks (useState, useMemo) for state management
- Date range filtering logic is handled by `getDateRangeBoundaries()` function
- Fuzzy search implementation allows flexible ticker and company name matching

---

# 10KAY Data Pipeline Architecture

## Overview

The 10KAY pipeline is a Python-based ETL system that automatically fetches SEC filings, analyzes them with Claude AI, generates multi-format content, and publishes to subscribers. It consists of four main phases that can be run independently or as a complete workflow.

## Pipeline Architecture

### Phase 1: Fetch (SEC EDGAR Integration)
**File:** `pipeline/fetchers/edgar.py`

Fetches latest 10-K and 10-Q filings from SEC EDGAR:

```bash
python3 pipeline/main.py --phase fetch [--tickers AAPL GOOGL ...]
```

**Process:**
1. Convert stock ticker → CIK (Central Index Key) via SEC's company_tickers.json
2. Query SEC EDGAR API for latest filings by type (10-K, 10-Q)
3. Download filing documents (plain text format)
4. Upload to AWS S3 bucket (10kay-filings)
5. Record metadata in PostgreSQL `filings` table with status: `pending`

**Rate Limiting:** SEC requires 10 requests/second max - enforced in code

**Database Schema:**
```
filings table:
- filing_id (UUID)
- ticker (VARCHAR)
- filing_type (10-K, 10-Q)
- fiscal_date (DATE)
- filed_date (DATE)
- raw_document_url (S3 path)
- status (pending → analyzed → generated → published)
- created_at (TIMESTAMP)
```

### Phase 2: Analyze (Claude AI Integration)
**File:** `pipeline/analyzers/claude.py`

Analyzes filings with Claude Sonnet 4.5 via AWS Bedrock:

```bash
python3 pipeline/main.py --phase analyze
```

**Process:**
1. Query database for pending filings
2. Download filing content from S3
3. Extract relevant sections:
   - Business Overview (Item 1)
   - Risk Factors (Item 1A)
   - Management Discussion & Analysis (Item 7)
   - Financial Statements (Item 8)
4. Call Claude via AWS Bedrock API with context-aware prompts
5. Parse AI response into structured JSON
6. Save analysis to PostgreSQL `content` table

**Analysis Output Structure:**
```json
{
  "headline": "Executive summary",
  "tldr_summary": "4-6 sentence overview",
  "tldr_key_points": [{"title": "...", "description": "..."}],
  "deep_headline": "Full analysis title",
  "deep_intro": "Introduction paragraphs",
  "deep_sections": [{"title": "...", "content": "..."}],
  "deep_conclusion": "Synthesis",
  "key_metrics": {
    "revenue": "...",
    "net_income": "...",
    "gross_margin": "...",
    "fcf": "..."
  },
  "sentiment_score": 0.5,  // -1 to 1 scale
  "bull_case": "Bullish argument (max 15 words)",
  "bear_case": "Bearish argument (max 15 words)",
  "risk_factors": ["Risk 1", "Risk 2", ...],
  "opportunities": ["Opportunity 1", "Opportunity 2", ...]
}
```

**AI Model Configuration:**
- Model: Claude Sonnet 4.5 (us.anthropic.claude-sonnet-4-5-20250929-v1:0)
- Max Tokens: 4096
- Temperature: 0.7

### Phase 3: Generate (Content Formatting)
**File:** `pipeline/generators/blog.py`

Transforms analyses into styled HTML for web/email:

```bash
python3 pipeline/main.py --phase generate
```

**Outputs:**
- Blog post HTML (responsive, mobile-friendly)
- Email newsletter HTML (Resend-compatible)
- Social media metadata

### Phase 4: Publish (Email Distribution)
**File:** `pipeline/publishers/email.py`

Distributes content to subscribers via Resend API:

```bash
python3 pipeline/main.py --phase publish [--dry-run]
```

**Process:**
1. Fetch ready content from database
2. Query subscribers from `subscribers` table
3. Filter by tier: free (TLDR only) vs paid (full analysis)
4. Personalize emails (name tokens, unsubscribe links)
5. Send via Resend API (https://api.resend.com/emails)
6. Record delivery tracking in `email_deliveries` table

**Dry Run Mode:** `--dry-run` flag validates without sending

## Complete Command Reference

### Running Full Pipeline
```bash
# Default: process all enabled companies
python3 pipeline/main.py

# Specific tickers only
python3 pipeline/main.py --phase fetch --tickers AAPL GOOGL META

# With custom log level
python3 pipeline/main.py --log-level DEBUG
```

### Individual Phases
```bash
# Fetch only
python3 pipeline/main.py --phase fetch

# Analyze only
python3 pipeline/main.py --phase analyze

# Generate only
python3 pipeline/main.py --phase generate

# Publish with dry-run
python3 pipeline/main.py --phase publish --dry-run
```

### Parallel Processing
```bash
# Parallel analysis (multiple workers)
python3 analyze_parallel.py --workers 5 --limit 100

# Orchestrated parallel pipeline
python3 orchestrate_parallel.py --analyze-limit 500 --generate-limit 500
```

### Earnings Calendar (Finnhub)
```bash
# Fetch upcoming earnings dates
python3 pipeline/main.py --phase earnings-calendar --tickers AAPL META
```

## Database Schema

**Companies Table**
```sql
CREATE TABLE companies (
  id UUID PRIMARY KEY,
  ticker VARCHAR(10) UNIQUE NOT NULL,
  name TEXT NOT NULL,
  exchange VARCHAR(10),
  sector TEXT,
  enabled BOOLEAN DEFAULT true,
  added_at TIMESTAMPTZ DEFAULT NOW(),
  metadata JSONB
);
```

**Filings Table**
```sql
CREATE TABLE filings (
  filing_id UUID PRIMARY KEY,
  ticker VARCHAR(10) NOT NULL,
  filing_type VARCHAR(10) NOT NULL,  -- '10-K' or '10-Q'
  fiscal_date DATE NOT NULL,
  filed_date DATE NOT NULL,
  raw_document_url TEXT NOT NULL,  -- S3 path
  status VARCHAR(20) DEFAULT 'pending',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  FOREIGN KEY (ticker) REFERENCES companies(ticker)
);
```

**Content Table** (Analysis Results)
```sql
CREATE TABLE content (
  content_id UUID PRIMARY KEY,
  filing_id UUID NOT NULL,
  analysis_type VARCHAR(20),  -- 'tldr' or 'deep'
  headline TEXT,
  summary TEXT,
  key_points JSONB,
  sentiment_score FLOAT,
  bull_case TEXT,
  bear_case TEXT,
  risk_factors TEXT[],
  opportunities TEXT[],
  formatted_html TEXT,
  status VARCHAR(20) DEFAULT 'pending',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  FOREIGN KEY (filing_id) REFERENCES filings(filing_id)
);
```

## Environment Configuration

**Required Variables** (in `.env.local`):
```bash
# Database
DATABASE_URL=postgresql://user:password@host:5432/10kay

# AWS (Bedrock, S3)
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_S3_FILINGS_BUCKET=10kay-filings
AWS_BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0

# Financial Data APIs
FINHUB_API_KEY=your_finnhub_key  # For earnings calendar
CONTACT_EMAIL=your.email@company.com  # Required by SEC EDGAR

# Email Distribution
RESEND_API_KEY=re_...
FROM_EMAIL=newsletter@10kay.com
FROM_NAME=10KAY

# Pipeline Options
DRY_RUN=false
MAX_RETRIES=3
RETRY_DELAY=2.0
```

## Data Flow Diagram

```
SEC EDGAR API
    ↓
┌───────────────────┐
│  PHASE 1: FETCH   │
│ - Get CIK from ticker
│ - Download 10-K/10-Q
│ - Upload to S3
│ - Record in filings table
└────────┬──────────┘
         ↓
    filings table
    (status: pending)
         ↓
┌───────────────────┐
│ PHASE 2: ANALYZE  │
│ - Download from S3
│ - Extract sections
│ - Call Claude/Bedrock
│ - Parse response
│ - Save to content table
└────────┬──────────┘
         ↓
    content table
    (raw analysis)
         ↓
┌───────────────────┐
│ PHASE 3: GENERATE │
│ - Transform to HTML
│ - Create blog format
│ - Create email format
│ - Update content table
└────────┬──────────┘
         ↓
    content table
    (formatted_html)
         ↓
┌───────────────────┐
│ PHASE 4: PUBLISH  │
│ - Get ready content
│ - Fetch subscribers
│ - Filter by tier
│ - Personalize emails
│ - Send via Resend
│ - Track deliveries
└────────┬──────────┘
         ↓
    Subscriber Inboxes
```

## Key Implementation Details

### SEC EDGAR Integration
- Uses official SEC endpoints: `https://www.sec.gov/files/company_tickers.json` (ticker→CIK)
- Fetches from: `https://www.sec.gov/cgi-bin/browse-edgar` (filing discovery)
- Downloads from: `https://www.sec.gov/Archives/edgar/data/{CIK}/{accession}.txt`
- Respects SEC rate limiting: max 10 requests/second

### Claude AI Analysis
- Model: Anthropic Claude Sonnet 4.5 (latest version)
- Delivery: AWS Bedrock cross-region inference
- Prompts: Context-aware based on filing type and company sector
- Outputs: Structured JSON with metrics, sentiment, bull/bear cases

### Email Distribution
- Provider: Resend (https://resend.com)
- Features: Template variables, unsubscribe links, delivery tracking
- Tiers: Free (TLDR only) vs Paid (full deep analysis)

## Running for a New Company

To analyze a new company:

```bash
# 1. Add to companies.json
# 2. Run seed_companies.py to sync database
python3 seed_companies.py

# 3. Fetch latest filings
python3 pipeline/main.py --phase fetch --tickers NEWTICKER

# 4. Analyze
python3 pipeline/main.py --phase analyze

# 5. Generate formats
python3 pipeline/main.py --phase generate

# 6. Test email
python3 pipeline/main.py --phase publish --dry-run

# 7. Publish
python3 pipeline/main.py --phase publish
```

## Troubleshooting

**"FINHUB_API_KEY environment variable is required"**
- Add to .env.local: `FINHUB_API_KEY=demo_key_for_pipeline_config`
- Earnings calendar phase will fail with dummy key, but fetch/analyze/publish work fine

**"SEC rate limit exceeded"**
- The fetcher automatically handles rate limiting
- Wait 100ms between requests per SEC guidelines
- Reduce parallel workers if hitting limits

**"Filing not found in S3"**
- Check that fetch phase completed successfully
- Verify AWS_S3_FILINGS_BUCKET and credentials
- Check filings table status column

**"Claude analysis failed"**
- Verify AWS_BEDROCK_MODEL_ID is correct
- Check AWS credentials and region
- Ensure filing content was downloaded correctly
