#!/usr/bin/env python3
"""
Backfill period_end_date for all filings based on fiscal_year and fiscal_quarter.

This script calculates the period end date based on:
- For 10-Q (quarterly filings): Quarter end date
  - Q1: March 31
  - Q2: June 30
  - Q3: September 30
  - Q4: December 31
- For 10-K (annual filings): Fiscal year end date (December 31 for calendar year companies)

Usage:
    python3 scripts/backfill_period_end_dates.py
"""

import psycopg2
from datetime import date
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv('.env.local')

def get_quarter_end_date(fiscal_year: int, fiscal_quarter: int) -> date:
    """Calculate quarter end date based on fiscal year and quarter."""
    if fiscal_quarter == 1:
        return date(fiscal_year, 3, 31)
    elif fiscal_quarter == 2:
        return date(fiscal_year, 6, 30)
    elif fiscal_quarter == 3:
        return date(fiscal_year, 9, 30)
    elif fiscal_quarter == 4:
        return date(fiscal_year, 12, 31)
    else:
        raise ValueError(f"Invalid fiscal quarter: {fiscal_quarter}")

def get_year_end_date(fiscal_year: int) -> date:
    """Get fiscal year end date (assuming calendar year end)."""
    return date(fiscal_year, 12, 31)

def main():
    """Main backfill workflow."""
    print("=" * 80)
    print("Backfill period_end_date Script")
    print("=" * 80)

    DATABASE_URL = os.getenv('DATABASE_URL')
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL not found in environment")
        return

    db_connection = psycopg2.connect(DATABASE_URL)
    cursor = db_connection.cursor()

    # First, check how many filings need backfill
    cursor.execute("SELECT COUNT(*) as count FROM filings WHERE period_end_date IS NULL")
    result = cursor.fetchone()
    total_to_backfill = result[0]

    print(f"\nFound {total_to_backfill} filings with NULL period_end_date")

    if total_to_backfill == 0:
        print("Nothing to backfill!")
        cursor.close()
        db_connection.close()
        return

    # Get all filings that need period_end_date
    cursor.execute("""
        SELECT id, filing_type, fiscal_year, fiscal_quarter
        FROM filings
        WHERE period_end_date IS NULL
        AND fiscal_year IS NOT NULL
        ORDER BY filing_date DESC
    """)

    filings = cursor.fetchall()

    print(f"\nProcessing {len(filings)} filings...")

    success_count = 0
    fail_count = 0

    for i, (filing_id, filing_type, fiscal_year, fiscal_quarter) in enumerate(filings, 1):
        try:
            if filing_type == '10-Q' and fiscal_quarter:
                period_end = get_quarter_end_date(fiscal_year, fiscal_quarter)
            elif filing_type == '10-K':
                period_end = get_year_end_date(fiscal_year)
            else:
                # Skip filings without enough data
                print(f"  [{i}/{len(filings)}] Skipping {filing_id} (insufficient data)")
                continue

            cursor.execute(
                "UPDATE filings SET period_end_date = %s WHERE id = %s",
                (period_end, filing_id)
            )
            success_count += 1

            if i % 50 == 0:
                db_connection.commit()
                print(f"  ✓ Processed {i}/{len(filings)} filings...")

        except Exception as e:
            print(f"  ✗ Failed to backfill {filing_id}: {str(e)}")
            fail_count += 1
            continue

    # Final commit
    db_connection.commit()

    # Verify results
    cursor.execute("SELECT COUNT(*) as count FROM filings WHERE period_end_date IS NOT NULL")
    final_count = cursor.fetchone()[0]

    print("\n" + "=" * 80)
    print(f"Backfill Complete!")
    print(f"  ✓ Successful updates: {success_count}")
    print(f"  ✗ Failed: {fail_count}")
    print(f"  Total filings with period_end_date: {final_count}")
    print("=" * 80)

    cursor.close()
    db_connection.close()

if __name__ == "__main__":
    main()
