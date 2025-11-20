-- Migration 009: Add CUSIP to companies table

ALTER TABLE companies
ADD COLUMN cusip VARCHAR(25) UNIQUE;

CREATE INDEX idx_companies_cusip ON companies(cusip);
