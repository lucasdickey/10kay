-- Migration 003: Indexes and Row Level Security
-- Adds performance indexes and access control policies
-- Run: psql $DATABASE_URL -f migrations/003_indexes_and_rls.sql

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

-- Companies indexes
CREATE INDEX IF NOT EXISTS idx_companies_ticker ON companies(ticker);
CREATE INDEX IF NOT EXISTS idx_companies_enabled ON companies(enabled) WHERE enabled = true;

-- Filings indexes
CREATE INDEX IF NOT EXISTS idx_filings_company ON filings(company_id);
CREATE INDEX IF NOT EXISTS idx_filings_date ON filings(filing_date DESC);
CREATE INDEX IF NOT EXISTS idx_filings_status ON filings(status);
CREATE INDEX IF NOT EXISTS idx_filings_type ON filings(filing_type);
CREATE UNIQUE INDEX IF NOT EXISTS idx_filings_unique
  ON filings(company_id, filing_type, fiscal_year, COALESCE(fiscal_quarter, 0));

-- Content indexes
CREATE INDEX IF NOT EXISTS idx_content_filing ON content(filing_id);
CREATE INDEX IF NOT EXISTS idx_content_company ON content(company_id);
CREATE INDEX IF NOT EXISTS idx_content_published ON content(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_content_current ON content(is_current) WHERE is_current = true;
CREATE INDEX IF NOT EXISTS idx_content_slug ON content(slug);

-- Subscribers indexes
CREATE INDEX IF NOT EXISTS idx_subscribers_email ON subscribers(email);
CREATE INDEX IF NOT EXISTS idx_subscribers_clerk ON subscribers(clerk_user_id);
CREATE INDEX IF NOT EXISTS idx_subscribers_tier ON subscribers(subscription_tier);
CREATE INDEX IF NOT EXISTS idx_subscribers_status ON subscribers(subscription_status);
CREATE INDEX IF NOT EXISTS idx_subscribers_stripe_customer ON subscribers(stripe_customer_id);

-- Email deliveries indexes
CREATE INDEX IF NOT EXISTS idx_email_subscriber ON email_deliveries(subscriber_id);
CREATE INDEX IF NOT EXISTS idx_email_content ON email_deliveries(content_id);
CREATE INDEX IF NOT EXISTS idx_email_sent ON email_deliveries(sent_at DESC);
CREATE INDEX IF NOT EXISTS idx_email_resend ON email_deliveries(resend_email_id);

-- Processing logs indexes
CREATE INDEX IF NOT EXISTS idx_logs_filing ON processing_logs(filing_id);
CREATE INDEX IF NOT EXISTS idx_logs_created ON processing_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_logs_step_status ON processing_logs(step, status);

-- ============================================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- ============================================================================

-- Enable RLS on content table (enforce paywall)
ALTER TABLE content ENABLE ROW LEVEL SECURITY;

-- Policy: Anyone can read TLDR content (executive_summary, key_takeaways)
-- Full content requires paid subscription
CREATE POLICY content_read_tldr ON content
  FOR SELECT
  USING (true); -- We'll enforce paywall logic in application layer for now

-- Policy: Only system can insert/update content
CREATE POLICY content_write ON content
  FOR ALL
  USING (false)
  WITH CHECK (false);

-- Enable RLS on subscribers table
ALTER TABLE subscribers ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see their own subscriber record
CREATE POLICY subscribers_read_own ON subscribers
  FOR SELECT
  USING (
    clerk_user_id = current_setting('app.current_user_id', true)
    OR email = current_setting('app.current_user_email', true)
  );

-- Policy: Only system can modify subscribers
CREATE POLICY subscribers_write ON subscribers
  FOR ALL
  USING (false)
  WITH CHECK (false);

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Function to check if content should be accessible to user
CREATE OR REPLACE FUNCTION is_content_accessible(
  content_id UUID,
  user_subscription_tier VARCHAR(20)
)
RETURNS BOOLEAN AS $$
BEGIN
  -- Free tier: Only TLDR (we'll handle this in application)
  -- Paid tier: Full content
  -- For now, return true and enforce in app layer
  RETURN true;
END;
$$ LANGUAGE plpgsql;

-- Function to get user's subscription tier from Clerk ID
CREATE OR REPLACE FUNCTION get_user_subscription_tier(
  user_clerk_id VARCHAR(255)
)
RETURNS VARCHAR(20) AS $$
DECLARE
  tier VARCHAR(20);
BEGIN
  SELECT subscription_tier INTO tier
  FROM subscribers
  WHERE clerk_user_id = user_clerk_id
  LIMIT 1;

  RETURN COALESCE(tier, 'free');
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- VIEWS FOR COMMON QUERIES
-- ============================================================================

-- View: Latest content per company
CREATE OR REPLACE VIEW latest_content AS
SELECT DISTINCT ON (company_id)
  c.*,
  co.name AS company_name,
  co.ticker AS company_ticker,
  f.filing_type,
  f.filing_date,
  f.fiscal_year,
  f.fiscal_quarter
FROM content c
JOIN companies co ON c.company_id = co.id
JOIN filings f ON c.filing_id = f.id
WHERE c.is_current = true
  AND c.published_at IS NOT NULL
ORDER BY company_id, c.published_at DESC;

COMMENT ON VIEW latest_content IS 'Most recent published content for each company';

-- View: Recent filings awaiting processing
CREATE OR REPLACE VIEW pending_filings AS
SELECT
  f.*,
  c.name AS company_name,
  c.ticker AS company_ticker
FROM filings f
JOIN companies c ON f.company_id = c.id
WHERE f.status = 'pending'
  AND c.enabled = true
ORDER BY f.filing_date DESC;

COMMENT ON VIEW pending_filings IS 'Filings that need to be processed';

-- View: Subscriber stats
CREATE OR REPLACE VIEW subscriber_stats AS
SELECT
  subscription_tier,
  subscription_status,
  COUNT(*) as count,
  COUNT(CASE WHEN last_email_sent_at > NOW() - INTERVAL '7 days' THEN 1 END) as active_7d
FROM subscribers
WHERE unsubscribed_at IS NULL
GROUP BY subscription_tier, subscription_status;

COMMENT ON VIEW subscriber_stats IS 'Subscriber counts by tier and status';

-- Migration complete
COMMENT ON SCHEMA public IS '10KAY Database - Migration 003 applied';
