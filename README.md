# 10KAY

**Automated SEC Filing Analysis for Tech Companies**

10KAY delivers strategic insights from 10-K and 10-Q filings, translated into actionable intelligence for tech professionals and operators.

---

## Overview

10KAY automatically fetches, analyzes, and publishes insights from SEC filings (10-Ks and 10-Qs) for tech-oriented Fortune 500 companies and tech-first companies listed on NASDAQ and NYSE. Content is delivered through multiple formats: blog posts, email newsletters, social media summaries, and podcast episodes.

### Target Audience
Tech and startup professionals seeking business strategy insights with a "TBPN meets Bloomberg Media" approach—substantive, data-driven analysis delivered conversationally with actionable takeaways.

### Content Formats

- **Blog Posts**: TLDR (free) + Deep Dive (paid subscription)
- **Email Newsletter**: Daily digest with key insights
- **Social Sharing**: AI-generated tweets and summaries
- **Audio/Podcast**: 5-7 minute audio briefings (Phase 5)

---

## Tech Stack

### Frontend
- **Next.js 15+** with TypeScript and App Router
- **Tailwind CSS** for styling
- **Vercel** for hosting and preview deployments

### Backend & Infrastructure
- **AWS RDS PostgreSQL** for relational data (db.t3.micro)
- **AWS S3** for document and audio storage
- **AWS Bedrock** (Claude Sonnet 4.5) for AI-powered analysis
- **Python 3.11+** for data processing pipeline
- **GitHub Actions** for scheduled filing checks (4x daily)

### Auth & Payments
- **Clerk** for authentication and user management
- **Stripe** for subscription billing

### Email
- **Resend** for transactional emails and newsletters

---

## Project Structure

```
10kay/
├── app/                    # Next.js App Router pages
│   ├── layout.tsx         # Root layout
│   ├── page.tsx           # Homepage
│   └── globals.css        # Global styles
├── components/            # React components
├── lib/                   # Utility functions and configs
├── pipeline/              # Python data processing
│   ├── fetchers/         # SEC EDGAR integration
│   ├── analyzers/        # Claude/Bedrock analysis
│   ├── generators/       # Content generation
│   └── publishers/       # Database and email delivery
├── companies.json         # Tracked companies list (47 companies)
├── .env.local            # Environment variables (gitignored)
├── .env.example          # Environment variable template
└── TECHNICAL_SPEC.md     # Detailed technical specification
```

---

## Tracked Companies

Currently tracking **47 tech companies** including:

**Mega-Cap Tech**: Apple, Microsoft, Google (GOOGL/GOOG), Amazon, Meta, Nvidia, Tesla

**Cloud & SaaS**: Snowflake, Shopify, ServiceNow, Salesforce, Workday

**Semiconductors**: Nvidia, AMD, Intel, Qualcomm, TSM, ASML, Broadcom

**Security**: Palo Alto Networks, CrowdStrike, Zscaler, Okta

**Fintech**: PayPal, Block (Square), Spotify, Uber, DoorDash

**Dev Tools & Platforms**: MongoDB, Atlassian, Unity, Pinterest, Figma

*See `companies.json` for the complete list.*

---

## Getting Started

### Prerequisites

- **Node.js 18+** and npm
- **Python 3.11+**
- **AWS Account** with Bedrock access
- **PostgreSQL** (AWS RDS)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/lucasdickey/10kay.git
   cd 10kay
   ```

2. **Install dependencies**
   ```bash
   # Frontend
   npm install

   # Pipeline
   cd pipeline
   pip install -r requirements.txt
   ```

3. **Configure environment variables**
   ```bash
   cp .env.example .env.local
   # Edit .env.local with your credentials
   ```

4. **Set up the database**
   ```bash
   # Run migrations
   python3 run_migrations.py

   # Seed companies
   python3 seed_companies.py
   ```

5. **Run the development server**
   ```bash
   npm run dev
   ```

   Open [http://localhost:3000](http://localhost:3000)

---

## Environment Variables

Required environment variables (see `.env.example` for template):

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string (AWS RDS) |
| `AWS_ACCESS_KEY_ID` | AWS IAM credentials |
| `AWS_SECRET_ACCESS_KEY` | AWS IAM credentials |
| `AWS_REGION` | AWS region (`us-east-1` or `us-west-2`) |
| `S3_BUCKET_FILINGS` | S3 bucket for PDF storage |
| `S3_BUCKET_AUDIO` | S3 bucket for audio files |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Clerk authentication |
| `CLERK_SECRET_KEY` | Clerk server-side key |
| `STRIPE_SECRET_KEY` | Stripe payments |
| `RESEND_API_KEY` | Email delivery |
| `ELEVENLABS_API_KEY` | Text-to-speech (Phase 5) |

---

## Development Workflow

### Single Production Environment
- **No staging/dev AWS resources** - keep it simple for solo development
- **Testing**: Vercel preview deployments for each branch/PR
- **Deployment**: Merge to `main` → auto-deploy to production
- **Rollback**: Git revert or Vercel instant rollback

### Data Processing Pipeline

The Python pipeline is designed to run 4x daily via GitHub Actions (to be implemented):
- **6:00 AM EST** - Morning check
- **9:00 AM EST** - Mid-morning check
- **12:00 PM EST** - Noon check
- **6:00 PM EST** - Evening check

**Pipeline Flow:**
```
┌─────────────┐
│  FETCHERS   │ → Fetch SEC filings from EDGAR API
└──────┬──────┘   Download documents, upload to S3
       ↓
┌─────────────┐
│  ANALYZERS  │ → Analyze with Claude Sonnet 4.5 (Bedrock)
└──────┬──────┘   Generate TLDR + deep analysis
       ↓
┌─────────────┐
│ GENERATORS  │ → Generate blog HTML, email HTML
└──────┬──────┘   Format for multiple channels
       ↓
┌─────────────┐
│ PUBLISHERS  │ → Publish to database
└─────────────┘   Send email newsletters via Resend
```

**Manual Execution:**
```bash
# Run full pipeline
python3 pipeline/main.py

# Run specific phase
python3 pipeline/main.py --phase fetch
python3 pipeline/main.py --phase analyze
python3 pipeline/main.py --phase generate
python3 pipeline/main.py --phase publish --dry-run

# Process specific companies
python3 pipeline/main.py --phase fetch --tickers AAPL GOOGL META
```

See `pipeline/README.md` for detailed documentation.

---

## Phased Implementation

### ✅ Phase 0: Foundation (Completed)
- ✅ AWS RDS PostgreSQL database created and configured
- ✅ AWS S3 buckets created (filings, audio)
- ✅ AWS Bedrock access requested (Claude Sonnet 4.5)
- ✅ IAM user with scoped permissions
- ✅ Next.js 15 project initialized with TypeScript
- ✅ Database migrations applied (7 tables, 37 indexes, 3 views)
- ✅ 47 companies seeded into database

### 🔄 Phase 1: Core Content Engine (90% Complete)
- ✅ Python pipeline foundation with base classes
- ✅ SEC EDGAR fetcher implementation (EdgarFetcher)
- ✅ Claude AI analyzer implementation (ClaudeAnalyzer)
- ✅ Blog post HTML generator (BlogGenerator)
- ✅ Email newsletter publisher (EmailPublisher)
- ✅ Main pipeline orchestrator with CLI
- ⏭️ Next.js content display pages
- ⏭️ API routes for frontend-backend integration
- ⏭️ First test run of full pipeline

### Phase 2: Automation (Pending)
- GitHub Actions workflows for 4x daily execution
- Automated filing detection and processing
- Error monitoring and alerting
- Historical data backfill

### Phase 3: User Accounts & Email (Pending)
- Clerk authentication integration
- Subscriber management UI
- Email newsletter delivery via Resend
- Subscription preference management

### Phase 4: Monetization (Pending)
- Stripe subscription integration
- Paywall implementation (free vs paid tiers)
- Payment flow and billing management
- Admin dashboard for metrics

### Phase 5: Audio/Podcast (Pending)
- ElevenLabs TTS integration
- Audio episode generation
- RSS podcast feed
- Podcast distribution

---

## Business Model

### Free Tier
- TLDR summaries (executive summary + key takeaways)
- Public blog post access (preview only)

### Paid Tier ($TBD/month)
- Full analysis (opportunities, risks, strategic shifts, implications)
- Daily email newsletter
- Audio podcast episodes (Phase 5)
- Archive access to all historical analyses

---

## Documentation

### Core Documentation
- **[SCHEMA.md](./SCHEMA.md)** - **⚡ START HERE** - Complete database schema documentation with:
  - Actual vs expected schema mappings
  - JSONB structure definitions
  - Foreign key relationships
  - Known issues and migration path
- **[TECHNICAL_SPEC.md](./TECHNICAL_SPEC.md)** - Original technical specification and architecture
- **[AWS_SETUP.md](./AWS_SETUP.md)** - AWS infrastructure setup guide
- **[IAM_SETUP.md](./IAM_SETUP.md)** - IAM user and permissions configuration

### Schema Validation
Before making code changes that interact with the database, run:
```bash
python3 validate_schema.py
```

This validates that your code's assumptions match the actual database structure.

---

## Contributing

This is a solo project by [Lucas Dickey](https://github.com/lucasdickey), but suggestions and feedback are welcome!

---

## License

Proprietary - All Rights Reserved

---

## Acknowledgments

- **Anthropic Claude Sonnet 4.5** for AI-powered analysis via AWS Bedrock
- **SEC EDGAR** for public company filings data
- **Vercel** for Next.js hosting and deployment
- **AWS** for infrastructure ($100k credits through June 2026)

---

## Contact

**Lucas Dickey**
- GitHub: [@lucasdickey](https://github.com/lucasdickey)
- Twitter: [@lucasdickey4](https://twitter.com/lucasdickey4)
- Website: [lucas.cv](https://lucas.cv)

---

**Built with ❤️ for tech operators who want to understand the business landscape.**
