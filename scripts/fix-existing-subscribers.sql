-- Fix existing subscriber records after migration 007
-- This updates any subscribers with NULL interested_companies to empty array

-- Update NULL interested_companies to empty array
UPDATE subscribers
SET interested_companies = ARRAY[]::uuid[]
WHERE interested_companies IS NULL;

-- Verify the update
SELECT
  email,
  interested_companies,
  email_enabled,
  content_preference,
  delivery_time
FROM subscribers;
