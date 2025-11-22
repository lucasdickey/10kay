-- Migration: Add press coverage tracking
-- Purpose: Store financial media articles related to SEC filings (48-hour window)
-- Date: 2025-11-21

-- Table for storing press coverage articles from financial media sources
CREATE TABLE IF NOT EXISTS press_coverage (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  filing_id UUID NOT NULL REFERENCES filings(id) ON DELETE CASCADE,

  -- Article metadata
  source VARCHAR(50) NOT NULL,  -- 'WSJ', 'Bloomberg', 'FT', 'NYT', 'Yahoo Finance', 'AlphaSense'
  headline TEXT NOT NULL,
  url TEXT NOT NULL,
  author VARCHAR(255),
  published_at TIMESTAMPTZ NOT NULL,

  -- Content
  article_snippet TEXT,  -- First few paragraphs or summary
  full_text TEXT,  -- Complete article text (if available)

  -- Analysis scores
  sentiment_score NUMERIC(3, 2),  -- -1.00 to 1.00 scale (bearish to bullish)
  relevance_score NUMERIC(3, 2),  -- 0.00 to 1.00 scale (how related to filing)

  -- Tracking metadata
  scraped_at TIMESTAMPTZ DEFAULT NOW(),
  source_api VARCHAR(50),  -- 'newsapi', 'finnhub', 'direct_scrape', etc.
  metadata JSONB,  -- Flexible field for additional data (tags, categories, etc.)

  -- Ensure no duplicate articles
  UNIQUE(url)
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_press_coverage_filing
  ON press_coverage(filing_id, published_at DESC);

CREATE INDEX IF NOT EXISTS idx_press_coverage_published
  ON press_coverage(published_at DESC);

CREATE INDEX IF NOT EXISTS idx_press_coverage_source
  ON press_coverage(source, published_at DESC);

CREATE INDEX IF NOT EXISTS idx_press_coverage_sentiment
  ON press_coverage(sentiment_score DESC NULLS LAST)
  WHERE sentiment_score IS NOT NULL;

-- Composite index for "articles within 48 hours of filing" queries
CREATE INDEX IF NOT EXISTS idx_press_coverage_filing_timewindow
  ON press_coverage(filing_id, published_at DESC)
  WHERE published_at IS NOT NULL;

-- Comments for documentation
COMMENT ON TABLE press_coverage IS 'Financial press articles related to SEC filings, captured within 48-hour window of filing date';
COMMENT ON COLUMN press_coverage.source IS 'News source identifier (WSJ, Bloomberg, FT, NYT, Yahoo Finance, AlphaSense)';
COMMENT ON COLUMN press_coverage.sentiment_score IS 'AI-analyzed sentiment: -1.00 (bearish) to 1.00 (bullish)';
COMMENT ON COLUMN press_coverage.relevance_score IS 'How relevant article is to the filing: 0.00 (unrelated) to 1.00 (directly about filing)';
COMMENT ON COLUMN press_coverage.article_snippet IS 'First 3-5 paragraphs or executive summary of article';
COMMENT ON COLUMN press_coverage.source_api IS 'Which API or method was used to fetch article (newsapi, finnhub, direct scrape)';
COMMENT ON COLUMN press_coverage.metadata IS 'Additional article metadata: tags, categories, images, related tickers, etc.';
