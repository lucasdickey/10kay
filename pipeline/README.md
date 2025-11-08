# 10KAY Data Processing Pipeline

Python-based data pipeline for fetching, analyzing, and distributing SEC filing insights.

## Architecture

The pipeline follows a modular, four-phase architecture:

```
┌─────────────┐
│  FETCHERS   │ → Fetch SEC filings from EDGAR
└──────┬──────┘
       ↓
┌─────────────┐
│  ANALYZERS  │ → Analyze with Claude AI (AWS Bedrock)
└──────┬──────┘
       ↓
┌─────────────┐
│ GENERATORS  │ → Generate multi-format content
└──────┬──────┘
       ↓
┌─────────────┐
│ PUBLISHERS  │ → Distribute to subscribers
└─────────────┘
```

### Modules

#### 1. **Fetchers** (`pipeline/fetchers/`)
Fetch SEC filings from EDGAR API and store in S3.

- `base.py` - Abstract `BaseFetcher` class
- `edgar.py` - SEC EDGAR implementation (TODO)

**Key responsibilities:**
- Query SEC EDGAR for latest 10-K/10-Q filings
- Download filing documents (HTML, PDF)
- Upload to S3 (`10kay-filings` bucket)
- Record metadata in `filings` table
- Respect SEC rate limits (10 requests/second)

#### 2. **Analyzers** (`pipeline/analyzers/`)
Analyze filings with Claude AI via AWS Bedrock.

- `base.py` - Abstract `BaseAnalyzer` class
- `claude.py` - Claude 3.5 Sonnet implementation (TODO)

**Key responsibilities:**
- Extract relevant sections from filings
- Build structured prompts for Claude
- Call AWS Bedrock API
- Parse and structure AI responses
- Save analysis to `content` table
- Generate both TLDR (free tier) and deep analysis (paid tier)

#### 3. **Generators** (`pipeline/generators/`)
Transform analysis into multiple distribution formats.

- `base.py` - Abstract `BaseGenerator` class
- `blog.py` - Blog post HTML generator (TODO)
- `email.py` - Email newsletter HTML generator (TODO)
- `social.py` - Twitter/LinkedIn post generator (TODO)

**Key responsibilities:**
- Fetch analyzed content from database
- Apply format-specific templates and styling
- Validate output meets constraints
- Update `content` table with formatted output

#### 4. **Publishers** (`pipeline/publishers/`)
Distribute content to subscribers and social channels.

- `base.py` - Abstract `BasePublisher` class
- `email.py` - Email via Resend API (TODO)
- `social.py` - Twitter/LinkedIn posting (TODO)

**Key responsibilities:**
- Fetch target audience (subscribers)
- Send content through appropriate channel
- Track delivery in `email_deliveries` table
- Handle free vs paid tier access control

### Utilities

- **`utils/config.py`** - Configuration management with typed dataclasses
- **`utils/logging.py`** - Structured logging with database persistence

## Usage

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Ensure .env.local is configured with:
# - DATABASE_URL
# - AWS credentials
# - AWS_S3_FILINGS_BUCKET
# - AWS_S3_AUDIO_BUCKET
# - AWS_BEDROCK_MODEL_ID
```

### Running the Pipeline

The `main.py` orchestrator coordinates all phases:

```bash
# Run full pipeline (all phases)
python3 pipeline/main.py

# Run specific phase
python3 pipeline/main.py --phase fetch
python3 pipeline/main.py --phase analyze
python3 pipeline/main.py --phase generate
python3 pipeline/main.py --phase publish

# Process specific tickers (fetch phase only)
python3 pipeline/main.py --phase fetch --tickers AAPL GOOGL META

# Dry run (validate without sending emails)
python3 pipeline/main.py --phase publish --dry-run

# Adjust log level
python3 pipeline/main.py --log-level DEBUG
```

### Pipeline Phases Explained

#### Phase 1: Fetch
```bash
python3 pipeline/main.py --phase fetch
```

1. Queries enabled companies from database
2. For each company, fetches latest SEC filings
3. Downloads filing documents
4. Uploads to S3
5. Records in `filings` table with status `fetched`

**Output:** New records in `filings` table

#### Phase 2: Analyze
```bash
python3 pipeline/main.py --phase analyze
```

1. Queries pending filings (status=`fetched`, no content)
2. For each filing:
   - Downloads from S3
   - Extracts relevant sections
   - Sends to Claude via Bedrock
   - Parses structured response
3. Saves to `content` table with status `published`

**Output:** New records in `content` table with TLDR + deep analysis

#### Phase 3: Generate
```bash
python3 pipeline/main.py --phase generate
```

1. Queries content without formatted output
2. For each content item:
   - Generates blog post HTML
   - Generates email newsletter HTML
   - Generates Twitter thread
   - Generates LinkedIn post
3. Updates `content` table with formatted output

**Output:** `content` table updated with `blog_html`, `email_html`, etc.

#### Phase 4: Publish
```bash
python3 pipeline/main.py --phase publish
```

1. Queries ready content (has formats, not yet sent)
2. For each content item:
   - Fetches subscriber list
   - Segments by tier (free vs paid)
   - Sends via Resend API
   - Tracks in `email_deliveries` table
3. Updates content metadata with publication status

**Output:** Emails sent, records in `email_deliveries` table

## Scheduled Execution

The pipeline is designed to run on a schedule via GitHub Actions:

```yaml
# .github/workflows/pipeline.yml
name: Data Pipeline
on:
  schedule:
    # Run 4x daily: 6am, 12pm, 6pm, 12am ET
    - cron: '0 11,17,23,5 * * *'  # UTC times
  workflow_dispatch:  # Manual trigger

jobs:
  pipeline:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r pipeline/requirements.txt
      - run: python3 pipeline/main.py
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
```

## Development

### Implementing a Fetcher

1. Create `pipeline/fetchers/edgar.py`
2. Extend `BaseFetcher`
3. Implement abstract methods:
   - `fetch_latest_filings()` - Query SEC EDGAR
   - `download_filing()` - Download document
   - `upload_to_s3()` - Upload to S3
   - `save_to_database()` - Record metadata

Example:
```python
from .base import BaseFetcher, FilingMetadata
import requests

class EdgarFetcher(BaseFetcher):
    def fetch_latest_filings(self, ticker, filing_type=None, limit=10):
        # Query SEC EDGAR API
        # Parse RSS feed or company search results
        # Return list of FilingMetadata
        pass
```

### Implementing an Analyzer

1. Create `pipeline/analyzers/claude.py`
2. Extend `BaseAnalyzer`
3. Implement abstract methods:
   - `fetch_filing_content()` - Download from S3
   - `extract_relevant_sections()` - Parse filing
   - `analyze_filing()` - Call Bedrock
   - `save_to_database()` - Save results

Example:
```python
from .base import BaseAnalyzer, AnalysisResult
import boto3

class ClaudeAnalyzer(BaseAnalyzer):
    def __init__(self, config, db_connection=None, logger=None):
        super().__init__(config, db_connection, logger)
        self.bedrock = boto3.client('bedrock-runtime')

    def analyze_filing(self, filing_id, analysis_type):
        # Fetch content
        # Build prompt
        # Call Bedrock invoke_model()
        # Parse response
        # Return AnalysisResult
        pass
```

### Testing

```bash
# Run tests
pytest pipeline/

# Test specific module
pytest pipeline/fetchers/test_edgar.py

# Test with coverage
pytest --cov=pipeline
```

## Error Handling

All phases include comprehensive error handling:

- **Retries**: Automatic retry with exponential backoff (configurable)
- **Logging**: All errors logged to stdout and `processing_logs` table
- **Graceful degradation**: Errors on individual items don't stop the batch
- **Database transactions**: Failed operations are rolled back

## Monitoring

Check pipeline health:

```sql
-- Recent processing logs
SELECT * FROM processing_logs
ORDER BY created_at DESC
LIMIT 100;

-- Pending filings
SELECT * FROM pending_filings;

-- Failed operations
SELECT * FROM processing_logs
WHERE level IN ('error', 'critical')
AND created_at > NOW() - INTERVAL '24 hours';
```

## Next Steps

**Phase 1 (Current):** Base classes ✅
- [x] BaseFetcher
- [x] BaseAnalyzer
- [x] BaseGenerator
- [x] BasePublisher
- [x] Configuration management
- [x] Logging utilities
- [x] Main orchestrator

**Phase 2:** Concrete implementations
- [ ] EdgarFetcher
- [ ] ClaudeAnalyzer
- [ ] BlogGenerator
- [ ] EmailPublisher
- [ ] GitHub Actions workflow

**Phase 3:** Advanced features
- [ ] Audio generation
- [ ] Podcast RSS feed
- [ ] Social media posting
- [ ] Webhook notifications

---

**Last Updated:** 2025-01-07
