# Earnings Calendar Integration - Setup & Testing

This document explains the new **Finnhub Earnings Calendar** integration, which provides actual company-announced earnings dates instead of estimated dates based on historical patterns.

---

## Overview

Previously, the system estimated upcoming filing dates by:
- Looking at the last filing's period end date
- Adding 42 days for 10-Q or 67 days for 10-K
- Projecting forward in 3-month cycles

**Problem:** Companies like Nvidia announce their exact earnings dates weeks in advance via press releases, but EDGAR only knows about filings *after* they're submitted.

**Solution:** Integrate Finnhub's Earnings Calendar API, which aggregates company IR announcements.

---

## What Changed

### New Components

1. **Database Table:** `scheduled_earnings`
   - Stores company-announced earnings dates from Finnhub
   - Includes fiscal period, EPS/revenue estimates, earnings time (bmo/amc)
   - Migration: `migrations/007_add_scheduled_earnings.sql`

2. **Python Fetcher:** `pipeline/fetchers/earnings_calendar.py`
   - Fetches upcoming earnings from Finnhub API
   - Upserts to `scheduled_earnings` table
   - Rate limited: 60 calls/minute (free tier)

3. **Pipeline Phase:** New `earnings-calendar` phase
   - Runs independently from SEC filing fetch
   - Recommended: Every other day (vs 4x daily for EDGAR)

4. **API Update:** `/api/upcoming-filings`
   - Now queries `scheduled_earnings` first
   - Falls back to estimation for companies without scheduled data
   - Returns `source: 'scheduled' | 'estimated'` for each filing

---

## Setup Instructions

### 1. Get Finnhub API Key

1. Sign up at [https://finnhub.io/register](https://finnhub.io/register)
2. Navigate to Dashboard → API Key
3. Copy your API key (starts with `c...`)

**Free tier limits:**
- 60 API calls/minute
- 250 API calls/day
- Perfect for <50 companies

### 2. Update Environment Variables

Add to `.env.local`:
```bash
FINNHUB_API_KEY=your_api_key_here
```

### 3. Run Database Migration

```bash
python3 run_migrations.py
```

This creates the `scheduled_earnings` table with:
- Unique constraint on `(company_id, fiscal_year, fiscal_quarter)`
- Indexes on `earnings_date`, `ticker`, `status`
- Foreign keys to `companies` and `filings` tables

### 4. Install Dependencies (if needed)

```bash
pip3 install -r pipeline/requirements.txt
```

---

## Usage Examples

### Fetch Earnings Calendar for All Companies

```bash
python3 pipeline/main.py --phase earnings-calendar
```

**Output:**
```
============================================================
EARNINGS CALENDAR: Fetching Scheduled Dates
============================================================
Fetching earnings calendar for 47 companies
Looking ahead 90 days
✓ Saved 12 scheduled earnings dates
Earnings calendar fetch complete
```

### Fetch for Specific Companies

```bash
python3 pipeline/main.py --phase earnings-calendar --tickers NVDA MSFT AAPL
```

### Check API Response

```bash
curl http://localhost:3000/api/upcoming-filings?days=60&limit=10
```

**Expected Response:**
```json
{
  "success": true,
  "count": 10,
  "daysAhead": 60,
  "filings": [
    {
      "ticker": "NVDA",
      "name": "Nvidia Corporation",
      "filingType": "10-Q",
      "estimatedDate": "2025-11-19T00:00:00.000Z",
      "daysUntil": 3,
      "fiscalPeriod": "Q3 2026",
      "source": "scheduled",
      "earningsTime": "amc",
      "epsEstimate": 0.75,
      "revenueEstimate": 35000000000
    }
  ],
  "metadata": {
    "scheduled": 12,
    "estimated": 35
  }
}
```

---

## Testing with Nvidia Nov 19 Earnings

### Verify Nvidia is Tracked

```bash
# Check companies.json
grep -A 4 "NVDA" companies.json
```

Expected output:
```json
{
  "ticker": "NVDA",
  "name": "Nvidia Corporation",
  "domain": "nvidia.com",
  "enabled": true
}
```

### Fetch Nvidia's Scheduled Date

```bash
python3 pipeline/main.py --phase earnings-calendar --tickers NVDA
```

### Query Database Directly

```sql
SELECT
  ticker,
  earnings_date,
  earnings_time,
  fiscal_quarter,
  fiscal_year,
  eps_estimate,
  revenue_estimate,
  source
FROM scheduled_earnings
WHERE ticker = 'NVDA'
ORDER BY earnings_date DESC;
```

Expected result:
```
 ticker | earnings_date | earnings_time | fiscal_quarter | fiscal_year | eps_estimate | revenue_estimate |  source
--------+---------------+---------------+----------------+-------------+--------------+------------------+---------
 NVDA   | 2025-11-19    | amc           | 3              | 2026        | 0.75         | 35000000000      | finnhub
```

### Verify Frontend Display

1. Start dev server: `npm run dev`
2. Navigate to homepage
3. Check "Upcoming Filings" section
4. Nvidia Q3 2026 should show:
   - Date: November 19, 2025
   - Source: Scheduled (vs. Estimated)
   - Time: After Market Close

---

## Database Schema

```sql
CREATE TABLE scheduled_earnings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id),
    ticker VARCHAR NOT NULL,

    -- Scheduled date info
    earnings_date DATE NOT NULL,
    earnings_time VARCHAR,  -- 'bmo' or 'amc'

    -- Fiscal period
    fiscal_year INTEGER NOT NULL,
    fiscal_quarter INTEGER,  -- 1-4 or NULL for annual

    -- Estimates
    eps_estimate NUMERIC(10, 4),
    revenue_estimate BIGINT,

    -- Lifecycle
    status VARCHAR DEFAULT 'scheduled',
    filing_id UUID REFERENCES filings(id),

    -- Metadata
    source VARCHAR DEFAULT 'finnhub',
    fetched_at TIMESTAMPTZ DEFAULT now(),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),

    UNIQUE(company_id, fiscal_year, fiscal_quarter)
);
```

---

## GitHub Actions Integration (Recommended)

Add to `.github/workflows/earnings-calendar.yml`:

```yaml
name: Fetch Earnings Calendar

on:
  schedule:
    # Run every other day at 6 AM UTC
    - cron: '0 6 */2 * *'
  workflow_dispatch:  # Allow manual trigger

jobs:
  fetch-earnings:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          cd pipeline
          pip install -r requirements.txt

      - name: Fetch earnings calendar
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
          FINNHUB_API_KEY: ${{ secrets.FINNHUB_API_KEY }}
        run: |
          python3 pipeline/main.py --phase earnings-calendar
```

**Required Secrets:**
- `DATABASE_URL`
- `FINNHUB_API_KEY`

---

## Troubleshooting

### Error: "FINNHUB_API_KEY environment variable is required"

**Solution:** Make sure `.env.local` has:
```bash
FINNHUB_API_KEY=your_actual_key
```

### Error: "relation 'scheduled_earnings' does not exist"

**Solution:** Run the migration:
```bash
python3 run_migrations.py
```

### Error: "No module named 'dotenv'"

**Solution:** Install dependencies:
```bash
pip3 install -r pipeline/requirements.txt
```

### No scheduled earnings returned

**Possible causes:**
1. No upcoming earnings in next 90 days → Normal for some companies
2. Finnhub doesn't have data for that ticker → Falls back to estimation
3. API rate limit exceeded → Wait 1 minute and retry

**Check Finnhub directly:**
```bash
curl "https://finnhub.io/api/v1/calendar/earnings?from=2025-11-01&to=2025-12-31&symbol=NVDA&token=YOUR_KEY"
```

---

## API Rate Limits

**Free Tier:**
- 60 calls/minute
- 250 calls/day

**Current Usage:**
- 47 companies = 47 API calls (if fetching per ticker)
- **OR** 1 API call for entire calendar (if no ticker filter)
- Recommended: Fetch entire calendar once per run

**Code automatically:**
- Rate limits to 1 request/second
- Fetches entire calendar if no tickers specified
- Filters to enabled companies in database

---

## Next Steps

1. ✅ Run migration to create table
2. ✅ Add `FINNHUB_API_KEY` to environment
3. ✅ Test with Nvidia: `--phase earnings-calendar --tickers NVDA`
4. ✅ Verify frontend shows "Scheduled" vs "Estimated"
5. 🔄 Set up GitHub Actions for automated fetching
6. 🔄 Monitor API usage to stay within free tier

---

## Questions?

- **Finnhub Docs:** https://finnhub.io/docs/api/earnings-calendar
- **Code:** `pipeline/fetchers/earnings_calendar.py`
- **Migration:** `migrations/007_add_scheduled_earnings.sql`
- **API Route:** `app/api/upcoming-filings/route.ts`
