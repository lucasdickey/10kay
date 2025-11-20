-- Migration: Add company market data tracking
-- Purpose: Store market cap and stock price data for performance tracking
-- Date: 2025-11-20

-- Table for storing daily market data (price, market cap, volume)
CREATE TABLE IF NOT EXISTS company_market_data (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  ticker VARCHAR(10) NOT NULL,

  -- Market data fields
  price NUMERIC(12, 4),  -- Closing price in USD
  market_cap BIGINT,  -- Market capitalization in USD
  volume BIGINT,  -- Trading volume
  change_percent NUMERIC(8, 4),  -- Daily change percentage

  -- Metadata
  data_date DATE NOT NULL,  -- The date this data represents
  fetched_at TIMESTAMPTZ DEFAULT NOW(),
  source VARCHAR(50) DEFAULT 'finnhub',

  -- Ensure one record per company per date
  UNIQUE(company_id, data_date)
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_market_data_company_date
  ON company_market_data(company_id, data_date DESC);

CREATE INDEX IF NOT EXISTS idx_market_data_date
  ON company_market_data(data_date DESC);

CREATE INDEX IF NOT EXISTS idx_market_data_ticker
  ON company_market_data(ticker, data_date DESC);

-- Comments for documentation
COMMENT ON TABLE company_market_data IS 'Daily stock market data for tracked companies including price, market cap, and volume';
COMMENT ON COLUMN company_market_data.price IS 'Closing stock price in USD';
COMMENT ON COLUMN company_market_data.market_cap IS 'Market capitalization in USD';
COMMENT ON COLUMN company_market_data.volume IS 'Trading volume for the day';
COMMENT ON COLUMN company_market_data.change_percent IS 'Daily percentage change';
COMMENT ON COLUMN company_market_data.data_date IS 'The date this market data represents (not when it was fetched)';
