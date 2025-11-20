#!/bin/bash
# Run migration 009: Add company market data table

# Load environment variables from .env.local
if [ -f .env.local ]; then
  export $(grep -v '^#' .env.local | xargs)
fi

if [ -z "$DATABASE_URL" ]; then
  echo "❌ ERROR: DATABASE_URL not set"
  echo "Make sure .env.local exists and contains DATABASE_URL"
  exit 1
fi

echo "Running migration 009: Add company market data table..."
psql "$DATABASE_URL" -f migrations/009_add_company_market_data.sql

if [ $? -eq 0 ]; then
  echo "✅ Migration 009 completed successfully"
  echo ""
  echo "New table 'company_market_data' created for tracking:"
  echo "  - Market capitalization"
  echo "  - Stock prices"
  echo "  - Trading volume"
  echo "  - 7-day performance metrics"
else
  echo "❌ Migration failed"
  exit 1
fi
