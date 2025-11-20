-- Add investor_relations_url to companies table
ALTER TABLE companies
ADD COLUMN investor_relations_url TEXT;

-- Create press_releases table
CREATE TABLE press_releases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filing_id UUID NOT NULL REFERENCES filings(id) ON DELETE CASCADE,
    url TEXT NOT NULL UNIQUE,
    title TEXT,
    published_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Add index on filing_id for faster lookups
CREATE INDEX idx_press_releases_on_filing_id ON press_releases(filing_id);
