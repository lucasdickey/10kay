#!/usr/bin/env python3
"""
Backfill bull/bear takeaways for the 20 most recent analyzed filings.

This script:
1. Queries the 20 most recent analyzed filings
2. Deletes existing content for those filings
3. Re-runs analysis with updated prompt that includes bull_case and bear_case
4. Saves the updated results back to the database

Usage:
    python3 scripts/backfill_bull_bear.py
"""

import sys
import os
from pathlib import Path

# Add parent directory to path to import pipeline modules
script_dir = Path(__file__).parent.parent
sys.path.insert(0, str(script_dir / 'pipeline'))
os.chdir(script_dir)

from utils import get_config, PipelineLogger
from analyzers import ClaudeAnalyzer, AnalysisType
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')

# Initialize config
config = get_config()


def get_recent_filings(db_connection, limit=20):
    """
    Get the N most recent analyzed filings.

    Returns list of dicts with filing_id, ticker, filing_type, filing_date
    """
    cursor = db_connection.cursor()

    cursor.execute("""
        SELECT
            f.id as filing_id,
            c.ticker,
            f.filing_type,
            f.filing_date,
            f.fiscal_year,
            f.fiscal_quarter
        FROM filings f
        JOIN companies c ON f.company_id = c.id
        WHERE f.status = 'analyzed'
        AND c.enabled = true
        ORDER BY f.filing_date DESC
        LIMIT %s
    """, (limit,))

    columns = [desc[0] for desc in cursor.description]
    results = [dict(zip(columns, row)) for row in cursor.fetchall()]

    cursor.close()
    return results


def delete_existing_content(db_connection, filing_id):
    """Delete existing content for a filing to allow re-analysis."""
    cursor = db_connection.cursor()

    cursor.execute("DELETE FROM content WHERE filing_id = %s", (filing_id,))
    cursor.execute("UPDATE filings SET status = 'fetched' WHERE id = %s", (filing_id,))

    db_connection.commit()
    cursor.close()


def main():
    """Main backfill workflow."""
    print("=" * 80)
    print("Bull/Bear Takeaways Backfill Script")
    print("=" * 80)
    print("\nThis will re-analyze the 20 most recent filings with updated prompts")
    print("to include bull_case and bear_case takeaways.\n")

    # Initialize logger
    logger = PipelineLogger(step='backfill')

    # Connect to database
    DATABASE_URL = os.getenv('DATABASE_URL')
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL not found in environment")
        sys.exit(1)

    db_connection = psycopg2.connect(DATABASE_URL)

    # Get 20 most recent filings
    filings = get_recent_filings(db_connection, limit=20)

    if not filings:
        print("No filings found to backfill.")
        db_connection.close()
        return

    print(f"Found {len(filings)} filings to backfill:")
    for i, filing in enumerate(filings, 1):
        print(f"  {i}. {filing['ticker']} - {filing['filing_type']} ({filing['filing_date']})")

    print("\n" + "=" * 80)

    # Initialize analyzer
    analyzer = ClaudeAnalyzer(config, db_connection=db_connection, logger=logger)

    success_count = 0
    fail_count = 0

    for i, filing in enumerate(filings, 1):
        filing_id = filing['filing_id']
        ticker = filing['ticker']
        filing_type = filing['filing_type']
        filing_date = filing['filing_date']

        print(f"\n[{i}/{len(filings)}] Processing {ticker} - {filing_type} ({filing_date})...")

        try:
            # Delete existing content
            print(f"  → Deleting existing content for filing {filing_id}")
            delete_existing_content(db_connection, filing_id)

            # Re-analyze with new prompt (includes bull/bear cases)
            print(f"  → Re-analyzing with updated prompt...")
            result = analyzer.analyze_filing(filing_id, AnalysisType.DEEP_ANALYSIS)

            # Save to database
            print(f"  → Saving updated analysis...")
            content_id = analyzer.save_to_database(result)

            # Verify bull/bear cases were captured
            if result.bull_case:
                print(f"  ✓ Bull case: {result.bull_case[:60]}...")
            else:
                print(f"  ⚠ Warning: No bull case generated")

            if result.bear_case:
                print(f"  ✓ Bear case: {result.bear_case[:60]}...")
            else:
                print(f"  ⚠ Warning: No bear case generated")

            print(f"  ✓ Successfully backfilled {ticker} (content_id: {content_id})")
            success_count += 1

        except Exception as e:
            print(f"  ✗ Failed to backfill {ticker}: {str(e)[:100]}")
            logger.error(f"Failed to backfill {filing_id}", exception=e)
            fail_count += 1
            continue

    # Summary
    print("\n" + "=" * 80)
    print(f"Backfill Complete!")
    print(f"  ✓ Successful: {success_count}")
    print(f"  ✗ Failed: {fail_count}")
    print("=" * 80)

    db_connection.close()


if __name__ == "__main__":
    main()
