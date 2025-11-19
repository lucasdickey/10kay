#!/bin/bash
# Helper script to run migration 007

# Load environment variables from .env.local
if [ -f .env.local ]; then
  export $(grep -v '^#' .env.local | xargs)
fi

if [ -z "$DATABASE_URL" ]; then
  echo "❌ ERROR: DATABASE_URL not set"
  echo "Make sure .env.local exists and contains DATABASE_URL"
  exit 1
fi

echo "Running migration 007..."
psql "$DATABASE_URL" -f migrations/007_enhance_subscriber_preferences.sql

if [ $? -eq 0 ]; then
  echo "✅ Migration 007 completed successfully"

  echo ""
  echo "Running fix for existing subscribers..."
  psql "$DATABASE_URL" -f scripts/fix-existing-subscribers.sql

  if [ $? -eq 0 ]; then
    echo "✅ All done! Company selections should now work."
  else
    echo "❌ Fix script failed"
    exit 1
  fi
else
  echo "❌ Migration failed"
  exit 1
fi
