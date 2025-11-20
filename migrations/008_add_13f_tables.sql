-- Migration 008: Add tables for 13F data processing

-- Table to store institutional investment managers
CREATE TABLE institutional_managers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cik VARCHAR(25) UNIQUE NOT NULL,
  name TEXT NOT NULL,
  enabled BOOLEAN DEFAULT true,
  metadata JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_institutional_managers_cik ON institutional_managers(cik);

-- Table to store individual holdings from 13F filings
CREATE TABLE institutional_holdings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  filing_id UUID REFERENCES filings(id) ON DELETE CASCADE,
  company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
  manager_id UUID REFERENCES institutional_managers(id) ON DELETE CASCADE,

  -- Holding details from 13F
  cusip VARCHAR(25) NOT NULL,
  shares INTEGER,
  value_usd NUMERIC(20, 2), -- value in USD

  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_institutional_holdings_filing_id ON institutional_holdings(filing_id);
CREATE INDEX idx_institutional_holdings_company_id ON institutional_holdings(company_id);
CREATE INDEX idx_institutional_holdings_manager_id ON institutional_holdings(manager_id);
CREATE INDEX idx_institutional_holdings_cusip ON institutional_holdings(cusip);

-- Add a column to filings to link to a manager (for 13F filings)
ALTER TABLE filings
ADD COLUMN manager_id UUID REFERENCES institutional_managers(id) ON DELETE CASCADE;

CREATE INDEX idx_filings_manager_id ON filings(manager_id);
