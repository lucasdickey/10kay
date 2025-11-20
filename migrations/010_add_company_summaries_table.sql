-- Migration 010: Add company_summaries table for aggregated analysis
CREATE TABLE company_summaries (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id UUID REFERENCES companies(id) ON DELETE CASCADE NOT NULL,
  summary_type VARCHAR(50) NOT NULL, -- e.g., 'INSTITUTIONAL_OWNERSHIP'
  fiscal_year INTEGER NOT NULL,
  fiscal_quarter INTEGER NOT NULL,
  summary_content JSONB,
  generated_at TIMESTAMPTZ DEFAULT NOW(),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_company_summaries_company_id ON company_summaries(company_id);
CREATE INDEX idx_company_summaries_type ON company_summaries(summary_type);
CREATE UNIQUE INDEX idx_company_summaries_unique ON company_summaries(company_id, summary_type, fiscal_year, fiscal_quarter);
