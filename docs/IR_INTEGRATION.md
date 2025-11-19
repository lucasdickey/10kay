# Investor Relations Integration Feature

## Overview

The IR Integration feature automatically scrapes and analyzes company investor relations pages to extract press releases, earnings presentations, and other documents published within ±72 hours of SEC filings (10-K/10-Q). This provides additional context and insights for investors.

## Architecture

### Database Schema

Three new tables support this feature:

1. **`ir_pages`** - Tracks investor relations URLs for each company
2. **`ir_documents`** - Stores scraped documents with AI analysis
3. **`ir_filing_links`** - Links IR documents to SEC filings within time windows

See `migrations/008_add_investor_relations_tracking.sql` for the complete schema.

### Data Flow

```
1. Filing Published
   ↓
2. IR Scraper runs for ±72 hour window
   ↓
3. Documents scraped and stored in ir_documents
   ↓
4. IR Analyzer analyzes each document with Claude
   ↓
5. Documents automatically linked to filings
   ↓
6. UI displays related IR updates on filing and ticker pages
```

## Components

### Backend

#### 1. IR Page Scraper (`pipeline/fetchers/ir_scraper.py`)

Scrapes company IR pages using multiple strategies:
- RSS/Atom feed detection and parsing
- HTML content extraction with heuristics
- Date-based filtering (±72 hour windows)
- Content deduplication via SHA256 hashing

**Key Methods:**
- `scrape_ir_page(ir_url, from_date, to_date)` - Main scraping method
- `save_documents(ir_page_id, company_id, ticker, documents)` - Saves to database
- `link_documents_to_filings(company_id, filing_id, filing_date)` - Creates filing links
- `scrape_for_filing(filing_id, company_id, ticker, filing_date)` - Complete workflow

**Usage:**
```python
from pipeline.fetchers import IRPageScraper

scraper = IRPageScraper(config, db_connection, logger)
docs_saved, links_created = scraper.scrape_for_filing(
    filing_id='uuid',
    company_id='uuid',
    ticker='AAPL',
    filing_date=datetime(2024, 11, 1),
    window_hours=72
)
```

#### 2. IR Document Analyzer (`pipeline/analyzers/ir_analyzer.py`)

Analyzes IR documents using Claude AI to extract:
- Concise summary (2-3 sentences)
- Key topics/themes (3-5)
- Salient takeaways for investors (3-5 points)
- Relevance score (0.00-1.00)

**Relevance Scoring:**
- **0.90-1.00**: Highly relevant (earnings results, major announcements)
- **0.70-0.89**: Moderately relevant (guidance updates, strategic info)
- **0.50-0.69**: Somewhat relevant (general news, product updates)
- **0.00-0.49**: Low relevance (routine announcements)

**Key Methods:**
- `analyze_document(ir_document_id)` - Analyze single document
- `save_analysis(result)` - Save analysis to database
- `analyze_pending_documents(limit, company_id)` - Batch analyze pending documents

**Usage:**
```python
from pipeline.analyzers import IRDocumentAnalyzer

analyzer = IRDocumentAnalyzer(config, db_connection, logger)
result = analyzer.analyze_document('document-uuid')
analyzer.save_analysis(result)
```

### API Endpoints

#### 1. Filing IR Documents (`/api/filings/[id]/ir-documents`)

Fetches IR documents linked to a specific filing.

**Response:**
```json
{
  "documents": [
    {
      "id": "uuid",
      "title": "Apple Reports Q1 2024 Results",
      "document_url": "https://...",
      "document_type": "press_release",
      "published_at": "2024-11-01T20:00:00Z",
      "analysis_summary": "Apple reported strong Q1 results...",
      "relevance_score": 0.95,
      "key_topics": ["Earnings Results", "iPhone Sales", "Services Growth"],
      "salient_takeaways": [
        "Revenue beat expectations by 3%",
        "Services revenue up 15% YoY",
        "iPhone 15 driving strong upgrade cycle"
      ],
      "time_delta_hours": -24,
      "window_type": "pre_filing"
    }
  ],
  "count": 1
}
```

#### 2. Company IR Documents (`/api/companies/[ticker]/ir-documents`)

Fetches recent IR documents for a company.

**Query Parameters:**
- `limit` - Number of documents (default: 10)
- `offset` - Pagination offset (default: 0)
- `from_date` - Filter from date (ISO 8601)
- `to_date` - Filter to date (ISO 8601)

**Response:**
```json
{
  "ticker": "AAPL",
  "documents": [...],
  "count": 5,
  "limit": 10,
  "offset": 0
}
```

### UI Components

#### 1. IRDocuments Component (`components/IRDocuments.tsx`)

Displays IR documents on filing detail pages (10-K/10-Q analysis pages).

**Features:**
- Timeline view showing pre/post filing context
- Relevance badges (Highly Relevant, Moderately Relevant, etc.)
- Document type icons
- Key topics tags
- Salient takeaways in highlighted boxes
- External links to original documents

**Usage:**
```tsx
import IRDocuments from '@/components/IRDocuments';

<IRDocuments filingId={filingId} />
```

#### 2. RecentIRUpdates Component (`components/RecentIRUpdates.tsx`)

Displays recent IR updates on company ticker pages.

**Features:**
- Compact card layout
- Document summaries (truncated)
- Key topics (first 3 shown)
- Links to related filings
- "View all" link for full IR updates

**Usage:**
```tsx
import RecentIRUpdates from '@/components/RecentIRUpdates';

<RecentIRUpdates ticker="AAPL" limit={5} />
```

## Setup & Deployment

### 1. Run Database Migrations

```bash
# Apply schema changes
psql $DATABASE_URL < migrations/008_add_investor_relations_tracking.sql

# Seed IR page URLs
psql $DATABASE_URL < migrations/009_seed_ir_pages.sql
```

### 2. Integrate with Pipeline

Add IR scraping to the main pipeline (`pipeline/main.py`):

```python
from fetchers import IRPageScraper
from analyzers import IRDocumentAnalyzer

# After filing is processed...
if filing_id:
    # Scrape IR page for this filing
    ir_scraper = IRPageScraper(config, db_connection, logger)
    docs_saved, links_created = ir_scraper.scrape_for_filing(
        filing_id=filing_id,
        company_id=company_id,
        ticker=ticker,
        filing_date=filing_date,
        window_hours=72
    )

    # Analyze IR documents
    if docs_saved > 0:
        ir_analyzer = IRDocumentAnalyzer(config, db_connection, logger)
        analyzed_count = ir_analyzer.analyze_pending_documents(
            limit=docs_saved,
            company_id=company_id
        )
```

### 3. Environment Variables

No new environment variables required. Uses existing:
- `AWS_BEDROCK_MODEL_ID` - Claude model for analysis
- `DATABASE_URL` - PostgreSQL connection
- `CONTACT_EMAIL` - For user agent in scraping

## Usage Patterns

### Scraping Frequency

IR pages have a `scraping_frequency` setting:
- **`on_filing`** (default) - Scrape when new filing is published
- **`daily`** - Scrape every day regardless of filings
- **`manual`** - Only scrape when explicitly triggered

### Error Handling

- Failed scrapes increment `consecutive_failures` counter
- After 5 consecutive failures, status changes to `'failed'`
- Error messages stored in `error_message` field
- Successful scrape resets counter to 0

### Document Types

Automatically classified:
- `press_release` - Press releases and news
- `earnings_presentation` - Earnings slides/presentations
- `webcast` - Earnings call webcasts
- `8k` - Form 8-K references
- `other` - Unclassified documents

## Monitoring & Maintenance

### Check IR Page Status

```sql
SELECT
  ticker,
  status,
  last_scraped_at,
  consecutive_failures,
  error_message
FROM ir_pages
WHERE status != 'active' OR consecutive_failures > 0
ORDER BY consecutive_failures DESC;
```

### Pending Analysis Queue

```sql
SELECT
  COUNT(*) as pending_count,
  ticker,
  MIN(scraped_at) as oldest_document
FROM ir_documents
WHERE status = 'pending'
GROUP BY ticker
ORDER BY pending_count DESC;
```

### Relevance Score Distribution

```sql
SELECT
  CASE
    WHEN relevance_score >= 0.9 THEN 'Highly Relevant'
    WHEN relevance_score >= 0.7 THEN 'Moderately Relevant'
    WHEN relevance_score >= 0.5 THEN 'Somewhat Relevant'
    ELSE 'Low Relevance'
  END as relevance_category,
  COUNT(*) as count,
  AVG(relevance_score) as avg_score
FROM ir_documents
WHERE relevance_score IS NOT NULL
GROUP BY relevance_category
ORDER BY avg_score DESC;
```

## Customization

### Company-Specific Scraping

Some IR pages require custom scraping rules. Add to `ir_pages.scraper_config`:

```sql
UPDATE ir_pages
SET scraper_config = '{
  "rss_feed_url": "https://custom.feed.url/rss",
  "date_selector": ".custom-date-class",
  "title_selector": "h2.press-title",
  "exclude_patterns": ["investor-day", "proxy"]
}'::jsonb
WHERE ticker = 'AAPL';
```

### Adjusting Time Windows

Default ±72 hours can be adjusted per-company:

```python
# Custom 48-hour window
scraper.scrape_for_filing(
    filing_id=filing_id,
    company_id=company_id,
    ticker=ticker,
    filing_date=filing_date,
    window_hours=48  # ±2 days
)
```

## Troubleshooting

### No Documents Found

1. Check IR page URL is correct and accessible
2. Verify `scraping_enabled = true` and `status = 'active'`
3. Check for errors in `error_message` field
4. Manually test IR page scraping:

```python
scraper = IRPageScraper(config, db_connection, logger)
from_date = datetime.now() - timedelta(days=3)
to_date = datetime.now() + timedelta(days=3)
docs = scraper.scrape_ir_page(ir_url, from_date, to_date)
print(f"Found {len(docs)} documents")
```

### Low Relevance Scores

If documents consistently get low relevance scores:
1. Ensure filing context is being passed to analyzer
2. Check document content is being scraped correctly
3. Review Claude prompt in `ir_analyzer._build_analysis_prompt()`

### Missing UI Display

If IR documents don't appear on pages:
1. Verify `show_on_filing_page = true` in `ir_filing_links`
2. Check API endpoints return data
3. Check browser console for errors
4. Verify filing_id is being passed to components

## Future Enhancements

Potential improvements:
- [ ] Audio transcription for earnings call webcasts
- [ ] Semantic search across IR documents
- [ ] Email alerts for high-relevance IR updates
- [ ] Historical IR document backfill
- [ ] Integration with investor calendar (dividends, splits)
- [ ] Automated IR page discovery via common patterns
- [ ] Support for international IR pages (non-English)

## Contributing

When adding new IR scraping strategies:
1. Add to `IRPageScraper` class
2. Update tests in `tests/test_ir_scraper.py`
3. Document new patterns in this file
4. Test with multiple company IR pages

## Support

For issues or questions:
- Check logs in `processing_logs` table
- Review error messages in `ir_pages.error_message`
- Consult schema documentation in `/SCHEMA.md`
