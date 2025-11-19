-- Add investor relations tracking tables
-- Enables scraping and linking of company IR page updates to 10-K/10-Q filings
-- Tracks documents published within ±72 hours of filing dates

-- Track company investor relations pages
CREATE TABLE ir_pages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    ticker VARCHAR NOT NULL,  -- Denormalized for performance

    -- IR page URL and configuration
    ir_url TEXT NOT NULL,  -- Company's investor relations page URL
    ir_url_verified_at TIMESTAMPTZ,  -- Last time URL was verified to be working

    -- Scraping configuration
    scraping_enabled BOOLEAN DEFAULT true,
    scraping_frequency VARCHAR DEFAULT 'daily',  -- daily | on_filing | manual
    last_scraped_at TIMESTAMPTZ,
    next_scrape_at TIMESTAMPTZ,

    -- Scraper hints (JSONB for flexibility across different IR page structures)
    scraper_config JSONB,  -- Custom selectors, patterns, or rules for this company

    -- Status tracking
    status VARCHAR DEFAULT 'active',  -- active | paused | failed | not_found
    error_message TEXT,  -- Last error if scraping failed
    consecutive_failures INTEGER DEFAULT 0,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),

    -- One IR page per company
    CONSTRAINT unique_company_ir_page UNIQUE(company_id)
);

-- Track individual documents/updates from IR pages
CREATE TABLE ir_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ir_page_id UUID NOT NULL REFERENCES ir_pages(id) ON DELETE CASCADE,
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    ticker VARCHAR NOT NULL,  -- Denormalized for performance

    -- Document metadata
    title TEXT NOT NULL,  -- Document title from IR page
    document_url TEXT NOT NULL,  -- URL to the actual document
    document_type VARCHAR,  -- press_release | earnings_presentation | webcast | 8k | other

    -- Date information
    published_at TIMESTAMPTZ NOT NULL,  -- When the document was published (from IR page)
    scraped_at TIMESTAMPTZ DEFAULT now(),  -- When we scraped it

    -- Content
    summary TEXT,  -- Extracted summary or description
    raw_content TEXT,  -- Full scraped content
    content_hash VARCHAR,  -- SHA256 hash to detect duplicates

    -- AI Analysis
    analyzed_at TIMESTAMPTZ,
    analysis_summary TEXT,  -- AI-generated summary of key takeaways
    relevance_score NUMERIC(3, 2),  -- 0.00-1.00 relevance score to associated filings
    key_topics JSONB,  -- Array of topics/themes extracted by AI

    -- Status
    status VARCHAR DEFAULT 'pending',  -- pending | analyzed | linked | archived

    -- Metadata
    metadata JSONB,  -- Additional document-specific data
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),

    -- Prevent duplicate documents
    CONSTRAINT unique_ir_document UNIQUE(ir_page_id, content_hash)
);

-- Link IR documents to filings (many-to-many)
-- Documents within ±72 hours of filing date are automatically linked
CREATE TABLE ir_filing_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ir_document_id UUID NOT NULL REFERENCES ir_documents(id) ON DELETE CASCADE,
    filing_id UUID NOT NULL REFERENCES filings(id) ON DELETE CASCADE,

    -- Temporal relationship
    time_delta_hours INTEGER,  -- Hours difference: negative = before filing, positive = after
    window_type VARCHAR NOT NULL,  -- pre_filing | post_filing | concurrent

    -- Link metadata
    link_type VARCHAR DEFAULT 'auto',  -- auto | manual | suggested
    relevance_reason TEXT,  -- Why this document was linked (AI-generated)
    confidence_score NUMERIC(3, 2),  -- 0.00-1.00 confidence in this link

    -- Display control
    show_on_filing_page BOOLEAN DEFAULT true,  -- Whether to display on 10-K/Q page
    show_on_ticker_page BOOLEAN DEFAULT true,  -- Whether to display on ticker page
    display_order INTEGER DEFAULT 0,  -- Order for display (lower = higher priority)

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT now(),
    created_by VARCHAR DEFAULT 'system',  -- system | ai | admin

    -- Prevent duplicate links
    CONSTRAINT unique_ir_filing_link UNIQUE(ir_document_id, filing_id)
);

-- Indexes for common queries

-- IR Pages indexes
CREATE INDEX idx_ir_pages_company ON ir_pages(company_id);
CREATE INDEX idx_ir_pages_ticker ON ir_pages(ticker);
CREATE INDEX idx_ir_pages_next_scrape ON ir_pages(next_scrape_at)
    WHERE scraping_enabled = true AND status = 'active';

-- IR Documents indexes
CREATE INDEX idx_ir_documents_page ON ir_documents(ir_page_id);
CREATE INDEX idx_ir_documents_company ON ir_documents(company_id);
CREATE INDEX idx_ir_documents_ticker ON ir_documents(ticker);
CREATE INDEX idx_ir_documents_published ON ir_documents(published_at DESC);
CREATE INDEX idx_ir_documents_status ON ir_documents(status);
CREATE INDEX idx_ir_documents_type ON ir_documents(document_type);

-- Composite index for finding documents by company and date range
CREATE INDEX idx_ir_documents_company_published ON ir_documents(company_id, published_at DESC);

-- Partial index for pending analysis
CREATE INDEX idx_ir_documents_pending_analysis ON ir_documents(scraped_at)
    WHERE status = 'pending';

-- IR Filing Links indexes
CREATE INDEX idx_ir_filing_links_document ON ir_filing_links(ir_document_id);
CREATE INDEX idx_ir_filing_links_filing ON ir_filing_links(filing_id);
CREATE INDEX idx_ir_filing_links_window ON ir_filing_links(window_type);

-- Composite index for finding links to display
CREATE INDEX idx_ir_filing_links_display ON ir_filing_links(filing_id, display_order)
    WHERE show_on_filing_page = true;

-- GIN indexes for JSONB columns
CREATE INDEX idx_ir_documents_key_topics ON ir_documents USING GIN(key_topics);
CREATE INDEX idx_ir_pages_scraper_config ON ir_pages USING GIN(scraper_config);

-- Comments for documentation
COMMENT ON TABLE ir_pages IS 'Company investor relations page URLs and scraping configuration';
COMMENT ON TABLE ir_documents IS 'Individual documents/updates scraped from company IR pages';
COMMENT ON TABLE ir_filing_links IS 'Links between IR documents and SEC filings (±72 hour window)';

COMMENT ON COLUMN ir_pages.scraper_config IS 'JSON config for page-specific scraping rules (selectors, patterns)';
COMMENT ON COLUMN ir_documents.time_delta_hours IS 'Hours from filing: negative = published before, positive = after';
COMMENT ON COLUMN ir_documents.relevance_score IS 'AI-calculated relevance (0.00-1.00)';
COMMENT ON COLUMN ir_filing_links.window_type IS 'pre_filing (-72 to 0 hours) | post_filing (0 to +72 hours) | concurrent';
COMMENT ON COLUMN ir_filing_links.confidence_score IS 'AI confidence in this link (0.00-1.00)';

-- Record migration
INSERT INTO schema_migrations (migration_name, applied_at)
VALUES ('008_add_investor_relations_tracking.sql', now());
