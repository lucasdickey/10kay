# Issue #32 Implementation: Company Performance Tracking

## Summary

This implementation adds market cap data and 7-day stock price performance tracking with comparative metrics (aggregate and sector-based benchmarking).

## Features Implemented

### 1. Database Schema
- **New Table**: `company_market_data`
  - Stores daily stock price, market cap, volume, and change percentage
  - Unique constraint on company_id + data_date
  - Indexed for efficient querying
- **Migration**: `migrations/009_add_company_market_data.sql`
- **Run Script**: `scripts/run-migration-009.sh`

### 2. Backend Data Fetcher
- **File**: `pipeline/fetchers/market_data.py`
- **Features**:
  - Fetches stock quotes and company profiles from Finnhub API
  - Combines price data with market cap information
  - Respects Finnhub rate limiting (60 requests/minute)
  - Stores data with upsert logic (updates existing records)

### 3. Pipeline Integration
- **Updated**: `pipeline/main.py`
- **New Phase**: `market-data`
- **Usage**:
  ```bash
  # Fetch market data for all companies
  python3 pipeline/main.py --phase market-data

  # Fetch for specific tickers
  python3 pipeline/main.py --phase market-data --tickers AAPL GOOGL META
  ```

### 4. Performance Calculation Utilities
- **File**: `lib/performance.ts`
- **Functions**:
  - `getCompany7DayPerformance(ticker)` - Get 7-day % change for a company
  - `getAggregate7DayPerformance()` - Get average 7-day change across all companies
  - `getSector7DayPerformance(sector)` - Get average 7-day change for a sector
  - `getAllCompaniesPerformance()` - Get comprehensive performance data for all companies

### 5. API Endpoint
- **Route**: `app/api/company-performance/route.ts`
- **Endpoint**: `GET /api/company-performance`
- **Returns**: JSON with all companies' performance metrics including:
  - Market cap (formatted)
  - 7-day price change %
  - Comparison to aggregate
  - Comparison to sector

### 6. Companies Page
- **Route**: `app/companies/page.tsx`
- **URL**: `/companies`
- **Features**:
  - Grid layout of all tracked companies
  - Market cap display
  - 7-day performance indicators
  - Comparison badges (vs Market, vs Sector)
  - Sector tags
  - Sorted by market cap (descending)
  - Links to individual company pages

### 7. Company Page Enhancement
- **Updated**: `app/[ticker]/page.tsx`
- **New Component**: `components/CompanyPerformanceMetrics.tsx`
- **Features**:
  - Visual performance bars
  - Comparison to market aggregate
  - Comparison to sector average
  - Performance metrics with directional indicators

## Setup Instructions

### 1. Run Database Migration
```bash
./scripts/run-migration-009.sh
```

This creates the `company_market_data` table in PostgreSQL.

### 2. Fetch Initial Market Data
```bash
# Fetch for all enabled companies
python3 pipeline/main.py --phase market-data

# Or for specific tickers
python3 pipeline/main.py --phase market-data --tickers AAPL MSFT GOOGL
```

### 3. Schedule Weekly Updates
Set up a scheduled job (cron, GitHub Actions, etc.) to run:
```bash
python3 pipeline/main.py --phase market-data
```

Recommended: Run weekly (as specified in the issue) to update market cap and track 7-day performance.

## Data Flow

```
Finnhub API
    ↓
MarketDataFetcher (Python)
    ↓
company_market_data table (PostgreSQL)
    ↓
Performance Utilities (TypeScript)
    ↓
API Endpoints & Pages (Next.js)
    ↓
User Interface (React Components)
```

## API Rate Limiting

**Finnhub Free Tier**: 60 API calls/minute

Each company requires:
- 1 call for quote (price, daily change)
- 1 call for company profile (market cap)

**Total**: ~2 calls per company

For 47 companies = ~94 API calls = ~2 minutes to complete

## Performance Calculations

### 7-Day Change
```sql
((current_price - price_7_days_ago) / price_7_days_ago) * 100
```

### Aggregate Performance
Average of all companies' 7-day changes

### Sector Performance
Average of 7-day changes for companies in the same sector

### Comparisons
- **vs Aggregate**: company_change - aggregate_average
- **vs Sector**: company_change - sector_average

## UI Components

### Companies Page (`/companies`)
- **Company Cards**: Show ticker, name, logo, market cap, 7-day change
- **Comparison Badges**: Green (outperforming) / Red (underperforming)
- **Sector Tags**: Industry classification
- **Stats Bar**: Total companies, companies with data, average 7-day change

### Individual Company Page (`/[ticker]`)
- **Performance Metrics Section**:
  - Visual bars for performance
  - Comparison to market
  - Comparison to sector
  - Reference values for context

## Files Created/Modified

### New Files
- `migrations/009_add_company_market_data.sql`
- `scripts/run-migration-009.sh`
- `pipeline/fetchers/market_data.py`
- `lib/performance.ts`
- `app/api/company-performance/route.ts`
- `app/companies/page.tsx`
- `components/CompanyPerformanceMetrics.tsx`

### Modified Files
- `pipeline/main.py` (added market-data phase)
- `app/[ticker]/page.tsx` (added performance metrics display)

## Testing

### Manual Testing Steps

1. **Run Migration**:
   ```bash
   ./scripts/run-migration-009.sh
   ```

2. **Fetch Market Data**:
   ```bash
   python3 pipeline/main.py --phase market-data --tickers AAPL MSFT
   ```

3. **Verify Data in Database**:
   ```sql
   SELECT * FROM company_market_data ORDER BY data_date DESC LIMIT 10;
   ```

4. **Test API Endpoint**:
   ```bash
   curl http://localhost:3000/api/company-performance
   ```

5. **Visit Pages**:
   - Navigate to `/companies`
   - Click on a company card
   - Verify performance metrics appear

### Expected Results
- Companies page shows market cap and 7-day performance
- Individual company pages show detailed performance comparison
- Performance indicators show green (positive) or red (negative) with arrows
- Comparison badges show differences from market and sector averages

## Future Enhancements

1. **Historical Charts**: Add price history charts using Chart.js or similar
2. **More Metrics**: Add volume, P/E ratio, 52-week high/low
3. **Real-time Updates**: WebSocket integration for live price updates
4. **Alerts**: Notify users when companies outperform/underperform significantly
5. **Custom Time Ranges**: Allow users to select 1d, 30d, 90d, 1y performance

## Dependencies

### Python
- `requests` - HTTP client for Finnhub API
- `psycopg2` - PostgreSQL database adapter

### Environment Variables
- `FINHUB_API_KEY` - Finnhub API key (get from https://finnhub.io)
- `DATABASE_URL` - PostgreSQL connection string

## Troubleshooting

### No market data showing
- Check that migration was run successfully
- Verify market-data phase has been executed
- Check Finnhub API key is valid
- Ensure companies have `enabled = true` in database

### Performance metrics show "N/A"
- Need at least 7 days of historical data for comparisons
- Run market-data phase daily for a week to build history

### API rate limit errors
- Free tier allows 60 calls/minute
- Fetcher includes rate limiting (1 second between calls)
- Consider upgrading Finnhub plan for more companies

## Notes

- Market cap is displayed in B (billions), M (millions), or T (trillions)
- Market cap data is pulled from Finnhub's company profile endpoint
- Date of last update is shown on company cards
- Sector information comes from company metadata (existing data)
- Performance metrics gracefully handle missing data (show N/A)
