-- Migration 007: Enhance Subscriber Preferences
-- Adds additional preference fields for Phase 3.2
-- Run: psql $DATABASE_URL -f migrations/007_enhance_subscriber_preferences.sql

-- Add new preference columns to subscribers table
ALTER TABLE subscribers
  ADD COLUMN IF NOT EXISTS email_enabled BOOLEAN DEFAULT true,
  ADD COLUMN IF NOT EXISTS content_preference VARCHAR(20) DEFAULT 'tldr' CHECK (content_preference IN ('tldr', 'full')),
  ADD COLUMN IF NOT EXISTS delivery_time TIME DEFAULT '08:00:00';

-- Update email_frequency to use enum-like constraint
ALTER TABLE subscribers
  DROP CONSTRAINT IF EXISTS subscribers_email_frequency_check;

ALTER TABLE subscribers
  ADD CONSTRAINT subscribers_email_frequency_check
  CHECK (email_frequency IN ('daily', 'per_filing', 'disabled'));

-- Add indexes for common queries
CREATE INDEX IF NOT EXISTS idx_subscribers_clerk_user_id
  ON subscribers(clerk_user_id) WHERE clerk_user_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_subscribers_email_enabled
  ON subscribers(email_enabled) WHERE email_enabled = true;

CREATE INDEX IF NOT EXISTS idx_subscribers_interested_companies
  ON subscribers USING GIN(interested_companies);

-- Comments for new columns
COMMENT ON COLUMN subscribers.email_enabled IS 'Master toggle for all email notifications';
COMMENT ON COLUMN subscribers.content_preference IS 'Email content type: tldr (free tier) or full (paid tier)';
COMMENT ON COLUMN subscribers.delivery_time IS 'Preferred time for daily digest emails (user timezone assumed EST)';

-- Migration complete
COMMENT ON SCHEMA public IS '10KAY Database - Migration 007 applied: Enhanced subscriber preferences';
