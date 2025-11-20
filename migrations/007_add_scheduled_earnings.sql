-- Add scheduled_earnings table for tracking company-announced earnings dates
-- Data sourced from Finnhub earnings calendar API
-- This provides actual scheduled dates rather than estimates based on historical patterns

CREATE TABLE IF NOT EXISTS scheduled_earnings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    ticker VARCHAR NOT NULL,  -- Denormalized for performance

    -- Scheduled date info from Finnhub
    earnings_date DATE NOT NULL,
    earnings_time VARCHAR,  -- 'bmo' (before market open) or 'amc' (after market close)

    -- Fiscal period info (consistent with filings table)
    fiscal_year INTEGER NOT NULL,
    fiscal_quarter INTEGER,  -- 1-4 for quarterly, NULL for annual

    -- Finnhub analyst estimates
    eps_estimate NUMERIC(10, 4),  -- Earnings per share estimate
    revenue_estimate BIGINT,  -- Revenue estimate in dollars

    -- Lifecycle tracking
    status VARCHAR DEFAULT 'scheduled',  -- scheduled | completed | cancelled
    filing_id UUID REFERENCES filings(id) ON DELETE SET NULL,  -- Link when actual filing appears

    -- Metadata
    source VARCHAR DEFAULT 'finnhub',  -- Data source
    fetched_at TIMESTAMPTZ DEFAULT now(),  -- When this data was fetched
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),

    -- Prevent duplicate entries for the same company/fiscal period
    CONSTRAINT unique_company_fiscal_period UNIQUE(company_id, fiscal_year, fiscal_quarter)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_scheduled_earnings_date ON scheduled_earnings(earnings_date);
CREATE INDEX IF NOT EXISTS idx_scheduled_earnings_company ON scheduled_earnings(company_id);
CREATE INDEX IF NOT EXISTS idx_scheduled_earnings_ticker ON scheduled_earnings(ticker);

-- Partial index for upcoming earnings only (most common query)
-- Note: Using fixed date instead of CURRENT_DATE because PostgreSQL requires immutable expressions
CREATE INDEX IF NOT EXISTS idx_scheduled_earnings_upcoming ON scheduled_earnings(earnings_date, status)
    WHERE status = 'scheduled';

-- Index for finding filings that match scheduled earnings
CREATE INDEX IF NOT EXISTS idx_scheduled_earnings_filing ON scheduled_earnings(filing_id)
    WHERE filing_id IS NOT NULL;

-- Comments
COMMENT ON TABLE scheduled_earnings IS 'Company-announced earnings dates from Finnhub API';
COMMENT ON COLUMN scheduled_earnings.earnings_time IS 'bmo = before market open, amc = after market close';
COMMENT ON COLUMN scheduled_earnings.status IS 'scheduled = upcoming, completed = filing received, cancelled = date changed';
COMMENT ON COLUMN scheduled_earnings.filing_id IS 'Links to actual SEC filing when it appears';
