-- Migration 001: Initial Schema
-- Creates core tables for 10KAY application
-- Run: psql $DATABASE_URL -f migrations/001_initial_schema.sql

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Companies table
CREATE TABLE IF NOT EXISTS companies (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ticker VARCHAR(10) UNIQUE NOT NULL,
  name TEXT NOT NULL,
  exchange VARCHAR(10), -- 'NASDAQ', 'NYSE'
  sector TEXT,
  enabled BOOLEAN DEFAULT true,
  added_at TIMESTAMPTZ DEFAULT NOW(),
  metadata JSONB -- flexible field for additional data
);

COMMENT ON TABLE companies IS 'Companies being tracked for SEC filing analysis';
COMMENT ON COLUMN companies.ticker IS 'Stock ticker symbol (e.g., AAPL, MSFT)';
COMMENT ON COLUMN companies.enabled IS 'Whether to actively process filings for this company';

-- Filings table
CREATE TABLE IF NOT EXISTS filings (
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

COMMENT ON TABLE filings IS 'SEC 10-K and 10-Q filings from tracked companies';
COMMENT ON COLUMN filings.accession_number IS 'Unique SEC filing identifier';
COMMENT ON COLUMN filings.status IS 'Processing status: pending, processing, completed, failed';

-- Content table
CREATE TABLE IF NOT EXISTS content (
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

COMMENT ON TABLE content IS 'AI-generated analysis and content from SEC filings';
COMMENT ON COLUMN content.version IS 'Content version number (increments on edits)';
COMMENT ON COLUMN content.is_current IS 'Whether this is the current published version';
COMMENT ON COLUMN content.slug IS 'URL-friendly identifier (e.g., aapl-10-k-2024-q4)';

-- Processing logs table
CREATE TABLE IF NOT EXISTS processing_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  filing_id UUID REFERENCES filings(id) ON DELETE CASCADE,

  step VARCHAR(50) NOT NULL, -- 'fetch', 'parse', 'analyze', 'publish'
  status VARCHAR(20) NOT NULL, -- 'started', 'completed', 'failed'

  message TEXT,
  metadata JSONB, -- tokens used, timing, etc.

  created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE processing_logs IS 'Audit log for filing processing pipeline';
COMMENT ON COLUMN processing_logs.metadata IS 'Additional context: API tokens used, timing, errors';

-- Update timestamp function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers for updated_at
CREATE TRIGGER update_filings_updated_at BEFORE UPDATE ON filings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_content_updated_at BEFORE UPDATE ON content
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Migration complete
COMMENT ON SCHEMA public IS '10KAY Database - Migration 001 applied';
