-- Migration 002: Subscribers and Email Delivery
-- Creates tables for user subscriptions and email tracking
-- Run: psql $DATABASE_URL -f migrations/002_subscribers.sql

-- Subscribers table
CREATE TABLE IF NOT EXISTS subscribers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email VARCHAR(255) UNIQUE NOT NULL,
  clerk_user_id VARCHAR(255) UNIQUE, -- NULL for email-only subscribers

  -- Subscription status
  subscription_tier VARCHAR(20) DEFAULT 'free', -- 'free', 'paid'
  stripe_customer_id VARCHAR(255),
  stripe_subscription_id VARCHAR(255),
  subscription_status VARCHAR(20), -- 'active', 'canceled', 'past_due', etc.

  -- Preferences
  email_frequency VARCHAR(20) DEFAULT 'daily', -- daily, weekly, off
  interested_companies UUID[], -- array of company IDs

  -- Tracking
  subscribed_at TIMESTAMPTZ DEFAULT NOW(),
  unsubscribed_at TIMESTAMPTZ,
  last_email_sent_at TIMESTAMPTZ,

  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE subscribers IS 'Newsletter subscribers and user accounts';
COMMENT ON COLUMN subscribers.clerk_user_id IS 'Clerk authentication user ID (NULL for email-only)';
COMMENT ON COLUMN subscribers.subscription_tier IS 'Access level: free (TLDR only) or paid (full access)';
COMMENT ON COLUMN subscribers.interested_companies IS 'Array of company UUIDs user wants to follow';

-- Email deliveries table
CREATE TABLE IF NOT EXISTS email_deliveries (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  subscriber_id UUID REFERENCES subscribers(id) ON DELETE CASCADE,
  content_id UUID REFERENCES content(id) ON DELETE CASCADE,

  -- Delivery tracking
  sent_at TIMESTAMPTZ DEFAULT NOW(),
  resend_email_id VARCHAR(255), -- Resend's tracking ID

  -- Engagement
  opened_at TIMESTAMPTZ,
  clicked_at TIMESTAMPTZ,

  status VARCHAR(20) DEFAULT 'sent' -- sent, delivered, opened, clicked, bounced, failed
);

COMMENT ON TABLE email_deliveries IS 'Email delivery and engagement tracking';
COMMENT ON COLUMN email_deliveries.resend_email_id IS 'Resend API email ID for webhooks';
COMMENT ON COLUMN email_deliveries.status IS 'Delivery status: sent, delivered, opened, clicked, bounced, failed';

-- Trigger for subscribers updated_at
CREATE TRIGGER update_subscribers_updated_at BEFORE UPDATE ON subscribers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Migration complete
COMMENT ON SCHEMA public IS '10KAY Database - Migration 002 applied';
