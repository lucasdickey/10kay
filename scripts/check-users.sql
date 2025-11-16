-- Quick SQL query to check users in database
-- Run with: psql $DATABASE_URL -f scripts/check-users.sql

\echo '═══════════════════════════════════════════════════════'
\echo '  10KAY Database Users Check'
\echo '═══════════════════════════════════════════════════════'
\echo ''

-- Check if subscribers table exists
\echo 'Checking if subscribers table exists...'
SELECT EXISTS (
  SELECT FROM information_schema.tables
  WHERE table_name = 'subscribers'
) AS table_exists;

\echo ''
\echo 'Current subscribers:'
\echo ''

-- Show all subscribers
SELECT
  email,
  clerk_user_id,
  subscription_tier,
  email_frequency,
  subscribed_at,
  CASE
    WHEN clerk_user_id IS NOT NULL THEN '✓ Synced'
    ELSE '✗ Not synced'
  END AS sync_status
FROM subscribers
ORDER BY subscribed_at DESC;

\echo ''
\echo 'Summary:'

-- Summary stats
SELECT
  COUNT(*) as total_subscribers,
  COUNT(clerk_user_id) as synced_with_clerk,
  COUNT(*) - COUNT(clerk_user_id) as not_synced,
  COUNT(*) FILTER (WHERE subscription_tier = 'free') as free_tier,
  COUNT(*) FILTER (WHERE subscription_tier = 'paid') as paid_tier
FROM subscribers;

\echo ''
\echo '═══════════════════════════════════════════════════════'
