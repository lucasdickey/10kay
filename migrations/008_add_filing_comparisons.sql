CREATE TABLE filing_comparisons (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    current_filing_id UUID NOT NULL REFERENCES filings(id),
    previous_filing_id UUID NOT NULL REFERENCES filings(id),
    content JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
