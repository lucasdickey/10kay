# 10KAY Technical Specification

**Version:** 1.0
**Last Updated:** 2025-11-07
**Project Goal:** Automated analysis and distribution of SEC 10-K/10-Q filings for tech-oriented public companies

---

## Executive Summary

10KAY is a content platform that ingests SEC filings (10-K, 10-Q) from tech-focused public companies, generates insightful analysis via Claude AI, and distributes content across multiple formats (blog, email newsletter, audio podcast). The product serves tech/startup professionals seeking strategic insights and actionable takeaways from financial disclosures.

### Target Audience
Tech and startup operators seeking business strategy insights ("TBPN meets Bloomberg Media") - substantive analysis with conversational tone and dry humor, focused on 10,000-foot takeaways applicable to their work.

---

## Product Requirements Summary

### Scope
- **Companies:** Fortune 500 + tech-first NASDAQ/NYSE companies (~50 companies for MVP, expandable to hundreds)
- **Filing Types:** Both 10-K (annual) and 10-Q (quarterly)
- **Processing Frequency:** 4x daily (6am, 9am, 12pm, 6pm EST)
- **Historical Analysis:** Yes - backfill previous filings to identify significant changes

### Content Formats

#### 1. Blog Posts (Primary)
**Structure:**
- **TLDR/BLUF** (5-7 min read, ~800-1,200 words)
  - Executive Summary (2-3 sentences)
  - Key Takeaways (bullet points)
- **Full Analysis** (total 10-15 min read, ~1,500-2,500 words)
  - Deep Dive Sections (opportunities, risks, strategic shifts)
  - What This Means For You (actionable implications)

**Access:**
- TLDR: Free tier
- Full Analysis: Paid tier only

#### 2. Email Newsletter
- Body contains TLDR section
- Permalink to full blog post
- Auto-delivered upon content generation
- Not editable post-send (blog is canonical)

#### 3. X (Twitter) Posts
- AI-generated draft saved as sharing intent on blog
- "Click to tweet" functionality
- Manual posting (no auto-post for MVP)

#### 4. Audio/Podcast (Phase 5)
- Audio-optimized narration of TLDR (~5-7 min episodes)
- Generated via ElevenLabs voice clone
- Style: NPR "Up First" / WSJ "Tech News Briefing"
- RSS feed for podcast apps

### Business Model
- **Free Tier:** TLDR summaries on website
- **Paid Tier:** Full analysis + email newsletter + podcast (Stripe recurring subscription)

### Content Workflow
1. Auto-publish all AI-generated content immediately
2. Blog posts editable post-publication (canonical source)
3. Newsletter auto-sends with permalink
4. Version tracking on blog posts

---

## Technical Architecture

### Stack Overview

```
┌─────────────────────────────────────────────┐
│           User-Facing Frontend              │
│         Next.js 14+ (App Router)            │
│              Hosted: Vercel                 │
└─────────────────────────────────────────────┘
                    │
                    ├── Auth: Clerk
                    ├── Payments: Stripe
                    └── Database: AWS RDS (PostgreSQL)

┌─────────────────────────────────────────────┐
│          Data Processing Pipeline           │
│      Python + GitHub Actions (Cron)         │
└─────────────────────────────────────────────┘
                    │
                    ├── SEC EDGAR API
                    ├── AWS Bedrock (Claude)
                    ├── AWS S3 (Document Storage)
                    ├── ElevenLabs API (Phase 5)
                    └── AWS RDS (writes)

┌─────────────────────────────────────────────┐
│          Email & Distribution               │
│         Resend (Email Service)              │
└─────────────────────────────────────────────┘
```

### Technology Choices

**Frontend:**
- **Framework:** Next.js 14+ (App Router)
- **Hosting:** Vercel
- **Auth:** Clerk (handles user accounts, sessions)
- **Payments:** Stripe (recurring subscriptions)
- **Styling:** Tailwind CSS

**Backend/Database:**
- **Database:** AWS RDS PostgreSQL (db.t3.micro for dev, db.t3.small for prod)
- **Connection Pooling:** PgBouncer or RDS Proxy (optional, can add later)
- **Access Control:** PostgreSQL Row Level Security policies for free vs paid content
- **Migrations:** Handled via SQL scripts or Prisma/Drizzle ORM

**Data Pipeline:**
- **Language:** Python 3.11+
- **Orchestration:** GitHub Actions (cron schedules)
- **AI Model:** Claude 3.5 Sonnet via AWS Bedrock
- **Document Processing:** PyPDF2 or pdfplumber
- **HTTP Client:** requests or httpx

**Email:**
- **Service:** Resend
- **Templates:** React Email (JSX-based email templates)

**Storage:**
- **Documents (PDF filings):** AWS S3 (bucket: `10kay-filings`)
- **Audio Files:** AWS S3 (bucket: `10kay-audio`) or Vercel Blob (Phase 5)
- **Blog content:** Stored in RDS PostgreSQL as text/markdown

**Future/Optional:**
- Analyst call transcripts (Phase 2+, provider TBD)
- AWS SES migration (when Resend limits hit)
- RDS Proxy for connection pooling (when scaling to hundreds of concurrent users)

**Why AWS-Heavy Architecture:**
- Maximizes usage of $100k AWS credits (expires June 2026)
- Unified ecosystem: RDS + S3 + Bedrock + (optionally) SES all on same account
- Cost-effective: ~$0 effective cost during validation phase
- Extensible: Easy to add Lambda, CloudFront, etc. if needed

---

## Database Schema

### Core Tables

#### `companies`
```sql
CREATE TABLE companies (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ticker VARCHAR(10) UNIQUE NOT NULL,
  name TEXT NOT NULL,
  exchange VARCHAR(10), -- 'NASDAQ', 'NYSE'
  sector TEXT,
  enabled BOOLEAN DEFAULT true,
  added_at TIMESTAMPTZ DEFAULT NOW(),
  metadata JSONB -- flexible field for additional data
);

CREATE INDEX idx_companies_ticker ON companies(ticker);
CREATE INDEX idx_companies_enabled ON companies(enabled);
```

#### `filings`
```sql
CREATE TABLE filings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
  filing_type VARCHAR(10) NOT NULL, -- '10-K', '10-Q'
  accession_number VARCHAR(25) UNIQUE NOT NULL, -- SEC identifier
  filing_date DATE NOT NULL,
  period_end_date DATE,
  fiscal_year INTEGER,
  fiscal_quarter INTEGER, -- NULL for 10-K

  -- Document storage
  edgar_url TEXT NOT NULL,
  raw_document_url TEXT, -- S3 URL

  -- Processing status
  status VARCHAR(20) DEFAULT 'pending', -- pending, processing, completed, failed
  processed_at TIMESTAMPTZ,
  error_message TEXT,

  -- Metadata
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_filings_company ON filings(company_id);
CREATE INDEX idx_filings_date ON filings(filing_date DESC);
CREATE INDEX idx_filings_status ON filings(status);
CREATE UNIQUE INDEX idx_filings_unique ON filings(company_id, filing_type, fiscal_year, fiscal_quarter);
```

#### `content`
```sql
CREATE TABLE content (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  filing_id UUID REFERENCES filings(id) ON DELETE CASCADE,
  company_id UUID REFERENCES companies(id) ON DELETE CASCADE,

  -- Content versions
  version INTEGER DEFAULT 1,
  is_current BOOLEAN DEFAULT true,

  -- Generated content
  executive_summary TEXT NOT NULL,
  key_takeaways JSONB NOT NULL, -- array of bullet points
  deep_dive_opportunities TEXT,
  deep_dive_risks TEXT,
  deep_dive_strategy TEXT,
  implications TEXT,

  -- Social/email content
  tweet_draft TEXT,
  email_subject TEXT,
  email_preview TEXT,

  -- Audio (Phase 5)
  audio_script TEXT,
  audio_url TEXT,
  audio_duration_seconds INTEGER,

  -- Publishing
  published_at TIMESTAMPTZ,
  slug VARCHAR(255) UNIQUE,

  -- Metadata
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  created_by VARCHAR(50) DEFAULT 'ai', -- 'ai' or user_id for manual edits

  -- SEO
  meta_description TEXT,
  meta_keywords TEXT[]
);

CREATE INDEX idx_content_filing ON content(filing_id);
CREATE INDEX idx_content_company ON content(company_id);
CREATE INDEX idx_content_published ON content(published_at DESC);
CREATE INDEX idx_content_current ON content(is_current) WHERE is_current = true;
```

#### `subscribers`
```sql
CREATE TABLE subscribers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email VARCHAR(255) UNIQUE NOT NULL,
  clerk_user_id VARCHAR(255) UNIQUE, -- NULL for email-only subscribers

  -- Subscription status
  subscription_tier VARCHAR(20) DEFAULT 'free', -- 'free', 'paid'
  stripe_customer_id VARCHAR(255),
  stripe_subscription_id VARCHAR(255),
  subscription_status VARCHAR(20), -- 'active', 'canceled', 'past_due', etc.

  -- Preferences
  email_frequency VARCHAR(20) DEFAULT 'daily', -- daily, weekly, off
  interested_companies UUID[], -- array of company IDs

  -- Tracking
  subscribed_at TIMESTAMPTZ DEFAULT NOW(),
  unsubscribed_at TIMESTAMPTZ,
  last_email_sent_at TIMESTAMPTZ,

  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_subscribers_email ON subscribers(email);
CREATE INDEX idx_subscribers_clerk ON subscribers(clerk_user_id);
CREATE INDEX idx_subscribers_tier ON subscribers(subscription_tier);
```

#### `email_deliveries`
```sql
CREATE TABLE email_deliveries (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  subscriber_id UUID REFERENCES subscribers(id) ON DELETE CASCADE,
  content_id UUID REFERENCES content(id) ON DELETE CASCADE,

  -- Delivery tracking
  sent_at TIMESTAMPTZ DEFAULT NOW(),
  resend_email_id VARCHAR(255), -- Resend's tracking ID

  -- Engagement
  opened_at TIMESTAMPTZ,
  clicked_at TIMESTAMPTZ,

  status VARCHAR(20) DEFAULT 'sent' -- sent, delivered, opened, clicked, bounced, failed
);

CREATE INDEX idx_email_subscriber ON email_deliveries(subscriber_id);
CREATE INDEX idx_email_content ON email_deliveries(content_id);
CREATE INDEX idx_email_sent ON email_deliveries(sent_at DESC);
```

#### `processing_logs`
```sql
CREATE TABLE processing_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  filing_id UUID REFERENCES filings(id) ON DELETE CASCADE,

  step VARCHAR(50) NOT NULL, -- 'fetch', 'parse', 'analyze', 'publish'
  status VARCHAR(20) NOT NULL, -- 'started', 'completed', 'failed'

  message TEXT,
  metadata JSONB, -- tokens used, timing, etc.

  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_logs_filing ON processing_logs(filing_id);
CREATE INDEX idx_logs_created ON processing_logs(created_at DESC);
```

---

## API Architecture

### Next.js API Routes

#### Public Routes (No Auth)

**`GET /api/content`**
- List recent analyses (TLDR only for free)
- Query params: `?company=AAPL&limit=10&offset=0`
- Response: Paginated list of content

**`GET /api/content/[slug]`**
- Get single analysis
- Returns TLDR for all, full content only if authenticated + paid

**`GET /api/companies`**
- List tracked companies
- Response: Company list with latest filing dates

#### Protected Routes (Clerk Auth Required)

**`GET /api/user/subscription`**
- Get current user's subscription status
- Response: Tier, status, Stripe details

**`POST /api/user/subscribe`**
- Create Stripe Checkout session
- Redirects to Stripe payment flow

**`GET /api/content/[slug]/full`**
- Access full analysis (requires paid tier)
- Enforced via RLS + API check

#### Admin Routes (Future)

**`POST /api/admin/companies`**
- Add/edit companies to track

**`POST /api/admin/reprocess/[filingId]`**
- Manually trigger reprocessing

#### Webhooks

**`POST /api/webhooks/stripe`**
- Handle Stripe subscription events
- Update subscriber tier in database

**`POST /api/webhooks/resend`**
- Track email delivery events (optional)

---

## Data Processing Pipeline

### Pipeline Overview

```
┌──────────────────────┐
│  GitHub Actions      │
│  Cron: 4x daily      │
│  (6am, 9am, 12pm,    │
│   6pm EST)           │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  1. Fetch New        │
│     Filings          │
│  (SEC EDGAR API)     │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  2. Download &       │
│     Parse Documents  │
│  (PDF → Text)        │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  3. Historical       │
│     Context Fetch    │
│  (Previous filings)  │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  4. AI Analysis      │
│  (AWS Bedrock/Claude)│
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  5. Content          │
│     Generation       │
│  (Blog, Email, Tweet)│
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  6. Publish          │
│  (Save to RDS)       │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  7. Email Delivery   │
│  (Resend API)        │
└──────────────────────┘
```

### Python Pipeline Structure

```
pipeline/
├── main.py                 # Entry point, orchestrates workflow
├── config.py              # Configuration, environment variables
├── requirements.txt       # Python dependencies
│
├── fetchers/
│   ├── __init__.py
│   ├── edgar.py          # SEC EDGAR API client
│   └── documents.py      # Download and parse PDFs
│
├── analyzers/
│   ├── __init__.py
│   ├── bedrock_client.py # AWS Bedrock/Claude interface
│   ├── prompts.py        # AI prompt templates
│   └── historical.py     # Historical comparison logic
│
├── generators/
│   ├── __init__.py
│   ├── blog.py           # Blog post generation
│   ├── email.py          # Email content generation
│   ├── social.py         # Tweet generation
│   └── audio.py          # Audio script generation (Phase 5)
│
├── publishers/
│   ├── __init__.py
│   ├── database.py       # PostgreSQL client (psycopg2 or SQLAlchemy)
│   └── email_sender.py   # Resend integration
│
└── utils/
    ├── __init__.py
    ├── logging.py
    └── retry.py
```

### GitHub Actions Workflow

**`.github/workflows/process-filings.yml`**

```yaml
name: Process SEC Filings

on:
  schedule:
    # 6am EST = 11am UTC (10am UTC in DST)
    - cron: '0 11 * * *'
    # 9am EST = 2pm UTC (1pm UTC in DST)
    - cron: '0 14 * * *'
    # 12pm EST = 5pm UTC (4pm UTC in DST)
    - cron: '0 17 * * *'
    # 6pm EST = 11pm UTC (10pm UTC in DST)
    - cron: '0 23 * * *'
  workflow_dispatch: # Manual trigger

jobs:
  process:
    runs-on: ubuntu-latest
    timeout-minutes: 120 # 2 hours max

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies
        run: |
          cd pipeline
          pip install -r requirements.txt

      - name: Run pipeline
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          AWS_REGION: us-east-1
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_KEY: ${{ secrets.SUPABASE_SERVICE_KEY }}
          RESEND_API_KEY: ${{ secrets.RESEND_API_KEY }}
        run: |
          cd pipeline
          python main.py

      - name: Upload logs
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: processing-logs-${{ github.run_id }}
          path: pipeline/logs/
```

### SEC EDGAR Integration

**Filing Discovery:**
- Use SEC EDGAR Company Search API
- RSS feeds for real-time filing notifications
- Daily query for each tracked company's recent submissions

**Endpoints:**
- Company filings: `https://data.sec.gov/submissions/CIK{cik}.json`
- Document access: `https://www.sec.gov/cgi-bin/viewer?action=view&cik={cik}&accession_number={acc}&xbrl_type=v`

**Rate Limiting:**
- SEC requires User-Agent with contact info
- Max 10 requests/second
- Implement respectful backoff

### AWS Bedrock Integration

**Model:** `anthropic.claude-3-5-sonnet-20241022-v2:0`

**Python Client:**
```python
import boto3
import json

bedrock = boto3.client(
    service_name='bedrock-runtime',
    region_name='us-east-1'
)

def analyze_filing(filing_text, historical_context):
    prompt = generate_analysis_prompt(filing_text, historical_context)

    response = bedrock.invoke_model(
        modelId='anthropic.claude-3-5-sonnet-20241022-v2:0',
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4096,
            "messages": [{
                "role": "user",
                "content": prompt
            }],
            "temperature": 0.7
        })
    )

    return json.loads(response['body'].read())
```

**Token Budget:**
- Input: ~100-150K tokens per 10-K
- Output: ~4K tokens (content generation)
- Cost per analysis: ~$0.50-1.00 with Bedrock credits

---

## AI Prompt Strategy

### Analysis Prompt Template

```python
ANALYSIS_PROMPT = """
You are a business strategy analyst writing for tech and startup professionals.
Analyze this SEC {filing_type} filing from {company_name} ({ticker}).

AUDIENCE: Tech operators seeking actionable insights for their work
TONE: Substantive but conversational, "TBPN meets Bloomberg Media", dry humor welcomed
FOCUS: Strategic implications, not financial minutiae

{historical_context}

FILING CONTENT:
{filing_text}

Generate a comprehensive analysis with the following structure:

## EXECUTIVE SUMMARY (2-3 sentences)
A high-level encapsulation of the most critical takeaways.

## KEY TAKEAWAYS (5-7 bullet points)
The most important insights that readers should walk away with.

## OPPORTUNITIES
What's working? What new markets, products, or strategies show promise?

## RISKS & CHALLENGES
What are the headwinds? Regulatory concerns? Competitive threats? Execution risks?

## STRATEGIC SHIFTS
How has the company's strategy evolved? What's new in this filing vs historical?
{historical_comparison_instructions}

## WHAT THIS MEANS FOR YOU
Direct, actionable implications for someone building or operating in tech:
- If you're building in [relevant space]...
- If you're a [role type]...
- Broader industry patterns to watch...

REQUIREMENTS:
- TLDR section (Executive Summary + Key Takeaways): 800-1,200 words
- Full analysis: 1,500-2,500 words total
- Use concrete examples and data points from the filing
- Avoid generic business jargon
- Include specific page/section references when making claims
- Highlight surprising or non-obvious insights

Return your analysis as JSON:
{{
  "executive_summary": "...",
  "key_takeaways": ["...", "..."],
  "opportunities": "...",
  "risks": "...",
  "strategic_shifts": "...",
  "implications": "...",
  "meta_description": "...", // SEO description, 150-160 chars
  "meta_keywords": ["...", "..."]
}}
"""

HISTORICAL_CONTEXT_TEMPLATE = """
HISTORICAL CONTEXT:
Previous filing ({prev_filing_type}, {prev_date}):
- Revenue: {prev_revenue}
- Key risks highlighted: {prev_risks}
- Strategic priorities: {prev_priorities}

Focus on CHANGES: What's new, what's emphasized differently, what's been de-emphasized?
"""

TWEET_PROMPT = """
Based on this analysis, create a compelling tweet (280 chars max) that:
1. Hooks the reader with the most surprising insight
2. Teases the full analysis
3. Uses thread-worthy format if needed (1/3 style)

Tone: Sharp, insightful, slightly provocative. No emoji spam.

Analysis:
{executive_summary}
{key_takeaways}

Return as JSON:
{{
  "tweet": "..."
}}
"""

AUDIO_SCRIPT_PROMPT = """
Convert this TLDR into a 5-7 minute audio script for narration.

STYLE: NPR "Up First" / WSJ "Tech News Briefing"
- Conversational but authoritative
- Smooth transitions, natural spoken flow
- No bullet points - rewrite as narrative
- Include natural pauses and emphasis cues [PAUSE], [EMPHASIS]

Original TLDR:
{tldr_content}

Return as JSON:
{{
  "audio_script": "...",
  "estimated_duration_seconds": 360
}}
"""
```

---

## Content Generation Flow

### Blog Post Structure

**URL Pattern:** `10kay.xyz/{company-ticker}/{filing-type}-{year}-q{quarter}`
- Example: `10kay.xyz/aapl/10-k-2024`
- Example: `10kay.xyz/nvda/10-q-2024-q2`

**Blog Post Layout:**

```
┌─────────────────────────────────────┐
│  HEADER                             │
│  - Company logo                     │
│  - Filing type & date               │
│  - "Published: X hours ago"         │
│  - "Updated: X hours ago" (if edited)│
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│  SHARE BAR                          │
│  [Tweet This] [Email] [Copy Link]   │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│  TL;DR (FREE)                       │
│  ✓ Executive Summary                │
│  ✓ Key Takeaways                    │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│  PAYWALL (if not subscribed)        │
│  "Subscribe to read the full        │
│   analysis..."                      │
│  [Subscribe Now]                    │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│  DEEP DIVE (PAID)                   │
│  ✓ Opportunities                    │
│  ✓ Risks & Challenges               │
│  ✓ Strategic Shifts                 │
│  ✓ What This Means For You          │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│  FOOTER                             │
│  - Source filing link               │
│  - Related analyses                 │
│  - Audio player (Phase 5)           │
└─────────────────────────────────────┘
```

### Email Template Structure

**Subject Line:** `{Company Name} {Filing Type}: {Hook from Executive Summary}`

**Email Body:**
```
Hi {subscriber_name},

{Company Name} just filed their {filing_type} for {period}.
Here's what matters:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 EXECUTIVE SUMMARY

{executive_summary}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 KEY TAKEAWAYS

• {takeaway_1}
• {takeaway_2}
• {takeaway_3}
...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[Read Full Analysis →]
({permalink})

Want to dig into opportunities, risks, and what this means for
your work? The full breakdown is on the blog.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Delivered by 10KAY
Update preferences | Unsubscribe
```

---

## Implementation Phases

### Phase 0: Foundation (Day 1 Morning)
**Goal:** Project scaffolding and basic infrastructure

**Tasks:**
- [ ] Initialize Next.js project with TypeScript
- [ ] Set up AWS RDS PostgreSQL database (db.t3.micro)
- [ ] Create database schema (run migrations)
- [ ] Set up Python pipeline structure
- [ ] Configure environment variables
- [ ] Basic Next.js layout and homepage

**Deliverable:** Empty but deployable Next.js app + database ready

---

### Phase 1: Core Content Engine (Day 1 Afternoon - Day 2 Morning)
**Goal:** Generate first analysis (manual process, automated later)

**Tasks:**
- [ ] Create `companies.json` config with initial 50 companies
- [ ] Build Python script to manually upload a 10-K PDF
- [ ] Implement AWS Bedrock integration
- [ ] Create analysis prompt template
- [ ] Generate first analysis (test with one company)
- [ ] Save content to RDS PostgreSQL
- [ ] Build blog post display page
- [ ] Implement TLDR vs full content split
- [ ] Create tweet draft generation
- [ ] Create email content generation

**Deliverable:** First complete analysis published on website

**Test:** Process AAPL or MSFT's latest 10-K manually

---

### Phase 2: Automation & Pipeline (Day 2 Afternoon)
**Goal:** Automated filing discovery and processing

**Tasks:**
- [ ] Build SEC EDGAR API client
- [ ] Implement filing discovery for tracked companies
- [ ] Automate PDF download and parsing
- [ ] Implement historical filing fetch (for context)
- [ ] Create end-to-end pipeline in `main.py`
- [ ] Set up GitHub Actions workflow (4x daily cron)
- [ ] Add error handling and retry logic
- [ ] Implement processing logs

**Deliverable:** Hands-off daily processing

**Test:** Run pipeline manually, verify it discovers and processes new filings

---

### Phase 3: User Accounts & Email (Day 3 Morning)
**Goal:** Build subscriber base

**Tasks:**
- [ ] Integrate Clerk authentication
- [ ] Create user subscription management pages
- [ ] Integrate Resend for email delivery
- [ ] Build React Email templates
- [ ] Implement subscriber preferences
- [ ] Create email delivery logic in pipeline
- [ ] Build archive/browse interface for past analyses
- [ ] Add Row Level Security policies in PostgreSQL

**Deliverable:** Newsletter delivery working

**Test:** Subscribe yourself, verify email delivery

---

### Phase 4: Monetization (Day 3 Afternoon)
**Goal:** Revenue generation

**Tasks:**
- [ ] Integrate Stripe
- [ ] Create subscription checkout flow
- [ ] Implement Stripe webhook handler
- [ ] Sync subscription status to RDS PostgreSQL
- [ ] Enforce paywall on blog (RLS + UI)
- [ ] Create subscription management UI
- [ ] Add billing portal link
- [ ] Define pricing ($X/month)

**Deliverable:** Paid subscriptions functional

**Test:** Complete a test subscription, verify paywall works

---

### Phase 5: Audio/Podcast (Day 4+)
**Goal:** Audio content distribution

**Tasks:**
- [ ] Integrate ElevenLabs API
- [ ] Create audio script generation prompt
- [ ] Build audio file generation logic
- [ ] Set up audio file storage (Vercel Blob)
- [ ] Create audio player component
- [ ] Generate RSS podcast feed
- [ ] Submit to Apple Podcasts / Spotify
- [ ] Add audio to email notifications

**Deliverable:** Podcast feed live and listenable

---

### Phase 6: Polish & Scale (Ongoing)
**Goal:** Optimization and growth

**Tasks:**
- [ ] SEO optimization (meta tags, sitemap, robots.txt)
- [ ] Add analytics (PostHog, Plausible, or similar)
- [ ] Performance optimization (caching, CDN)
- [ ] Company management admin UI
- [ ] Content editing interface
- [ ] Email preference center
- [ ] A/B testing for email subject lines
- [ ] Cost monitoring dashboard
- [ ] Expand to analyst call transcripts (source TBD)
- [ ] Migrate to AWS SES (when volume justifies)

---

## Configuration Files

### `companies.json`
```json
{
  "companies": [
    {
      "ticker": "AAPL",
      "name": "Apple Inc.",
      "cik": "0000320193",
      "exchange": "NASDAQ",
      "enabled": true
    },
    {
      "ticker": "MSFT",
      "name": "Microsoft Corporation",
      "cik": "0000789019",
      "exchange": "NASDAQ",
      "enabled": true
    }
    // ... 48 more
  ]
}
```

### `.env.example`
```bash
# AWS RDS PostgreSQL
DATABASE_URL=postgresql://username:password@10kay-db.xxxxxx.us-east-1.rds.amazonaws.com:5432/10kay
# Or split into components:
DB_HOST=10kay-db.xxxxxx.us-east-1.rds.amazonaws.com
DB_PORT=5432
DB_NAME=10kay
DB_USER=admin
DB_PASSWORD=your-secure-password

# AWS
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=xxx
AWS_REGION=us-east-1
S3_BUCKET_FILINGS=10kay-filings
S3_BUCKET_AUDIO=10kay-audio

# Clerk
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_...
CLERK_SECRET_KEY=sk_...

# Stripe
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_...
STRIPE_SECRET_KEY=sk_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Resend
RESEND_API_KEY=re_...

# ElevenLabs (Phase 5)
ELEVENLABS_API_KEY=...
ELEVENLABS_VOICE_ID=... # Your voice clone ID

# App Config
NEXT_PUBLIC_APP_URL=https://10kay.xyz
```

### `pipeline/requirements.txt`
```
boto3>=1.34.0          # AWS SDK (Bedrock, S3)
requests>=2.31.0       # HTTP client
pydantic>=2.5.0        # Data validation
python-dotenv>=1.0.0   # Environment variables
PyPDF2>=3.0.0          # PDF parsing
psycopg2-binary>=2.9.9 # PostgreSQL adapter
sqlalchemy>=2.0.23     # ORM (optional, for easier queries)
beautifulsoup4>=4.12.0 # HTML parsing (for EDGAR)
lxml>=5.1.0            # XML parsing
retry>=0.9.2           # Retry decorator
```

---

## Cost Estimates

### AWS Bedrock (Claude)
- **Budget:** $100k credits through June 2026
- **Per-filing cost:** ~$0.50-1.00 (varies by length)
- **Monthly volume estimate:**
  - 50 companies × 4 filings/year = 200 filings/year ≈ 17/month
  - 17 filings × $0.75 = **~$13/month** (negligible against budget)
- **Scale to 500 companies:** ~$130/month (still well within budget)

### Resend (Email)
- **Free tier:** 3,000 emails/month
- **Paid:** $20/month for 50,000 emails
- **Estimate:**
  - 100 subscribers × 17 emails/month = 1,700 emails (free tier)
  - 1,000 subscribers = 17,000 emails (still free tier)

### Vercel (Hosting)
- **Free tier:** Sufficient for MVP
- **Pro:** $20/month (needed when scaling past hobby limits)

### Stripe
- **2.9% + $0.30 per transaction**
- **Example:** $10/month subscription = $0.59 fee per subscriber

### AWS RDS PostgreSQL
- **db.t3.micro:** $12-15/month (covered by credits)
- **Storage:** $0.115/GB/month for 20GB = ~$2.30/month (covered by credits)
- **Backups:** First 20GB free
- **Estimate:** ~$0 effective cost with AWS credits

### AWS S3
- **Storage:** $0.023/GB/month (first 50GB)
- **Estimate:** 50 companies × 4 filings × 5MB avg = ~1GB = **~$0.02/month** (covered by credits)

### Total Monthly Operating Cost (MVP - 50 Beta Users)
- **Infrastructure (AWS):** ~$0 (all covered by $100k credits)
- **Out-of-pocket:** ~$0-20/month (Vercel free tier, Resend free tier, Clerk free tier)
- **At 10 paid subscribers:** ~$20-40/month
  - Revenue: $100/month (at $10/mo pricing)
  - Net: ~$60-80/month

---

## Success Metrics

### Technical KPIs
- **Processing success rate:** >95% of filings processed without errors
- **Time to publish:** <2 hours from filing detection to email sent
- **Pipeline uptime:** >99% (GitHub Actions reliability)

### Product KPIs
- **Week 1:** First 10 analyses published
- **Month 1:** 100 free subscribers
- **Month 2:** 10 paid subscribers
- **Month 3:** 50 paid subscribers ($500 MRR)

### Content Quality
- **Email open rate:** >30%
- **Click-through rate:** >10%
- **Time on page:** >3 minutes average
- **Subscriber feedback:** Qualitative reviews

---

## Risk Mitigation

### Technical Risks

**1. SEC Rate Limiting**
- **Mitigation:** Implement respectful delays, cache aggressively, spread requests over time

**2. PDF Parsing Failures**
- **Mitigation:** Multiple parsing libraries (PyPDF2, pdfplumber, fallback to OCR)

**3. Claude Token Limits**
- **Mitigation:** Chunk large documents, summarize sections before analysis

**4. GitHub Actions Timeout**
- **Mitigation:** Process in batches, skip if takes >2 hours, retry in next run

### Business Risks

**1. Content Quality Issues**
- **Mitigation:** Manual review for first 20 analyses, iterate on prompts

**2. Low Subscriber Conversion**
- **Mitigation:** A/B test pricing, add referral incentives, improve TLDR hooks

**3. Deliverability Issues**
- **Mitigation:** Use Resend (good sender reputation), authenticate domain, monitor bounce rates

---

## MVP Simplifications for Beta (50 Concurrent Users)

Given the target of 50 beta users for initial validation, we can make several simplifications to accelerate time-to-value:

### Infrastructure Simplifications

**Database:**
- **Instance:** db.t3.micro RDS (2 vCPU, 1GB RAM) - handles 85 connections easily
- **No connection pooling needed** - Direct connections from Next.js and Python pipeline
- **No read replicas** - Single primary instance is sufficient
- **Simple backups** - Automated daily snapshots (default RDS config)

**Caching:**
- **Skip Redis/caching layer** - PostgreSQL can handle all reads for 50 users
- **Vercel Edge Caching** - Sufficient for static content

**Monitoring:**
- **AWS CloudWatch** - Default metrics (CPU, connections, storage)
- **Skip APM tools** - Not needed for small scale
- **Simple logging** - CloudWatch Logs for errors

### Application Simplifications

**Authentication:**
- **Clerk free tier** - Up to 10,000 MAU (way more than needed)
- **No custom user management UI** - Clerk's built-in components

**Content Delivery:**
- **No CDN beyond Vercel** - Vercel's edge network is sufficient
- **No image optimization pipeline** - Next.js built-in Image component

**Email:**
- **Resend free tier** - 3,000 emails/month (plenty for 50 users × ~20 emails/month = 1,000/month)
- **Simple text-based templates** - React Email basics, no heavy design

**Search:**
- **Skip Algolia/Elasticsearch** - Simple PostgreSQL full-text search or client-side filtering
- **Basic filtering** - Filter by company, filing type, date

### Development Workflow

**Deployment:**
- **Single environment initially** - Production only, test locally
- **Add staging later** - When needed for QA

**Database Migrations:**
- **Simple SQL scripts** - No complex migration framework needed initially
- **Version in git** - Numbered files: `001_initial_schema.sql`, `002_add_indexes.sql`

**Testing:**
- **Manual testing** - You + 5-10 beta users
- **Skip automated E2E tests** - Add when scaling
- **Basic unit tests** - For critical business logic only

### What to Skip for MVP

**Not Needed for 50-User Beta:**
- ❌ Load balancers
- ❌ Auto-scaling
- ❌ RDS Proxy / PgBouncer
- ❌ Multi-region deployment
- ❌ Complex monitoring/alerting (PagerDuty, etc.)
- ❌ A/B testing framework
- ❌ Advanced analytics (Mixpanel, Amplitude)
- ❌ Admin dashboard (use database queries directly)
- ❌ Rate limiting (Vercel handles basic protection)

**Add These Later (Phase 6+):**
- Advanced search/filtering
- User preference  center (beyond basic email on/off)
- Social sharing analytics
- Referral program
- Mobile app
- Advanced SEO (structured data, etc.)

### Recommended MVP Stack Size

```
Infrastructure:
├── RDS: db.t3.micro (1GB RAM, 20GB storage)
├── S3: Standard tier (pay per use, ~pennies)
├── Vercel: Hobby tier → Pro when needed ($20/month)
├── Clerk: Free tier (up to 10K MAU)
└── Resend: Free tier (3K emails/month)

Total effective cost: $0 (AWS credits cover everything)
```

### Scale-Up Trigger Points

Upgrade when you hit:
- **200+ concurrent users** → db.t3.small + consider connection pooling
- **500+ subscribers** → Add staging environment
- **1,000+ subscribers** → Add caching layer (Redis)
- **5,000+ subscribers** → RDS Proxy, load monitoring, auto-scaling

---

## Next Steps

1. **Review and approve** this spec
2. **Provide initial 50 company tickers** for MVP
3. **Set up AWS resources** (RDS, S3 buckets - see AWS_SETUP.md guide)
4. **Set up Vercel/Clerk accounts** (if not already done)
5. **Begin Phase 0 implementation**

---

## Appendix: Example Companies (Starter List)

*You mentioned providing 50 tickers - here are suggested categories to consider:*

**Mega-cap Tech (10)**
AAPL, MSFT, GOOGL, AMZN, META, NVDA, TSLA, NFLX, ADBE, CRM

**Cloud/Infrastructure (10)**
SNOW, DDOG, NET, MDB, TEAM, ZS, CRWD, S, OKTA, FTNT

**Semiconductors (10)**
NVDA, AMD, INTC, QCOM, AVGO, TSM, ASML, MRVL, KLAC, AMAT

**Fintech (5)**
SQ, PYPL, COIN, HOOD, SOFI

**E-commerce/Marketplace (5)**
SHOP, ETSY, EBAY, BABA, MELI

**Emerging Tech (5)**
PLTR, RBLX, U, DASH, ABNB

**Enterprise Software (5)**
NOW, WDAY, ZM, DOCU, HUBS

---

**Document End**
