-- Migration 010: Data integrity constraints for idempotent writes
--
-- The pipeline is re-run constantly (backfills overlap, GitHub Actions retry,
-- workers crash mid-batch). Every write is now an INSERT ... ON CONFLICT, but
-- ON CONFLICT requires a real unique index to target. This migration adds the
-- missing ones and repairs the data that accumulated without them.
--
-- Run: psql $DATABASE_URL -f migrations/010_data_integrity.sql
-- Safe to run more than once.

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. email_deliveries.metadata
--
-- EmailPublisher.save_delivery_record() has always inserted into a `metadata`
-- column that migration 002 never created, so every delivery record write
-- raised UndefinedColumn and no send was ever tracked.
-- ---------------------------------------------------------------------------
ALTER TABLE email_deliveries
  ADD COLUMN IF NOT EXISTS metadata JSONB;

COMMENT ON COLUMN email_deliveries.metadata IS
  'Channel-specific delivery details (recipient counts, tier, Resend response)';

-- ---------------------------------------------------------------------------
-- 2. One current content row per filing
--
-- content.slug was the only unique key, so re-analyzing a filing either created
-- a duplicate row (when the slug changed) or failed outright (when it did not).
-- A partial unique index on filing_id gives ContentRepository.upsert_analysis()
-- a conflict target while leaving room for superseded versions.
-- ---------------------------------------------------------------------------

-- Retire duplicates first: keep the newest row per filing as the current one.
WITH ranked AS (
  SELECT id,
         ROW_NUMBER() OVER (
           PARTITION BY filing_id
           ORDER BY version DESC, updated_at DESC NULLS LAST, created_at DESC
         ) AS rank
  FROM content
  WHERE is_current
)
UPDATE content c
SET is_current = false
FROM ranked r
WHERE c.id = r.id AND r.rank > 1;

CREATE UNIQUE INDEX IF NOT EXISTS idx_content_filing_current
  ON content (filing_id)
  WHERE is_current;

COMMENT ON INDEX idx_content_filing_current IS
  'Conflict target for ContentRepository.upsert_analysis(); one live analysis per filing';

-- ---------------------------------------------------------------------------
-- 3. scheduled_earnings deduplication for annual periods
--
-- UNIQUE(company_id, fiscal_year, fiscal_quarter) never matched 10-K rows,
-- because in Postgres NULL <> NULL: ON CONFLICT could not fire, so every
-- earnings-calendar run re-inserted the same annual event. COALESCE-ing the
-- quarter to 0 in an expression index makes annual rows deduplicate correctly.
-- ---------------------------------------------------------------------------

DELETE FROM scheduled_earnings a
USING scheduled_earnings b
WHERE a.company_id = b.company_id
  AND a.fiscal_year = b.fiscal_year
  AND COALESCE(a.fiscal_quarter, 0) = COALESCE(b.fiscal_quarter, 0)
  AND (a.fetched_at, a.id) < (b.fetched_at, b.id);

ALTER TABLE scheduled_earnings
  DROP CONSTRAINT IF EXISTS unique_company_fiscal_period;

CREATE UNIQUE INDEX IF NOT EXISTS idx_scheduled_earnings_company_period
  ON scheduled_earnings (company_id, fiscal_year, COALESCE(fiscal_quarter, 0));

COMMENT ON INDEX idx_scheduled_earnings_company_period IS
  'Conflict target for EarningsRepository.upsert_many(); NULL quarter treated as 0';

-- ---------------------------------------------------------------------------
-- 4. Indexes for the queue queries the pipeline runs every cycle
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_filings_status_date
  ON filings (status, filing_date DESC);

CREATE INDEX IF NOT EXISTS idx_content_pending_generation
  ON content (created_at DESC)
  WHERE is_current AND (blog_html IS NULL OR email_html IS NULL);

CREATE INDEX IF NOT EXISTS idx_content_ready_to_publish
  ON content (created_at DESC)
  WHERE is_current AND email_html IS NOT NULL AND published_at IS NULL;

COMMIT;
