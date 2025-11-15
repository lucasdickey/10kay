#!/usr/bin/env python3
"""
Backfill bull/bear cases for ALL content records missing them.

This script:
1. Queries all content records without bull_case or bear_case
2. Deletes existing content for those filings
3. Re-runs analysis with updated prompt that includes bull_case and bear_case
4. Saves the updated results back to the database

Usage:
    python3 scripts/backfill_bull_bear_all.py [--batch-size 10]

Options:
    --batch-size N    Process N items at a time (default: 10)
"""

import sys
import os
from pathlib import Path
import argparse

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


def get_records_missing_bull_bear(db_connection, limit=None):
    """
    Get all content records missing bull_case or bear_case.

    Returns list of dicts with content_id, filing_id, company_id, ticker, filing_type, filing_date
    """
    cursor = db_connection.cursor()

    query = """
        SELECT
            c.id as content_id,
            f.id as filing_id,
            c.company_id,
            co.ticker,
            f.filing_type,
            f.filing_date,
            f.fiscal_year,
            f.fiscal_quarter
        FROM content c
        JOIN filings f ON c.filing_id = f.id
        JOIN companies co ON c.company_id = co.id
        WHERE (c.key_takeaways->>'bull_case' IS NULL OR c.key_takeaways->>'bear_case' IS NULL)
        ORDER BY f.filing_date DESC
    """

    if limit:
        query += f" LIMIT {limit}"

    cursor.execute(query)

    columns = [desc[0] for desc in cursor.description]
    results = [dict(zip(columns, row)) for row in cursor.fetchall()]

    cursor.close()
    return results


def delete_existing_content(db_connection, content_id):
    """Delete existing content record to allow re-analysis."""
    cursor = db_connection.cursor()

    cursor.execute("DELETE FROM content WHERE id = %s", (content_id,))

    db_connection.commit()
    cursor.close()


def main():
    """Main backfill workflow."""
    parser = argparse.ArgumentParser(description='Backfill bull/bear cases for all missing records')
    parser.add_argument('--batch-size', type=int, default=10, help='Process N items at a time')
    args = parser.parse_args()

    print("=" * 80)
    print("Comprehensive Bull/Bear Cases Backfill Script")
    print("=" * 80)
    print("\nThis will re-analyze ALL content records missing bull_case or bear_case")
    print("to generate bullish/bearish sentiment takeaways.\n")

    # Initialize logger
    logger = PipelineLogger(step='backfill_bull_bear_all')

    # Connect to database
    DATABASE_URL = os.getenv('DATABASE_URL')
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL not found in environment")
        sys.exit(1)

    db_connection = psycopg2.connect(DATABASE_URL)

    # Get all records missing bull/bear
    records = get_records_missing_bull_bear(db_connection)

    if not records:
        print("No records found missing bull/bear cases. All done!")
        db_connection.close()
        return

    print(f"Found {len(records)} records to backfill:")
    for i, record in enumerate(records[:10], 1):
        print(f"  {i}. {record['ticker']} - {record['filing_type']} ({record['filing_date']})")
    if len(records) > 10:
        print(f"  ... and {len(records) - 10} more")

    print("\n" + "=" * 80)

    # Initialize analyzer
    analyzer = ClaudeAnalyzer(config, db_connection=db_connection, logger=logger)

    success_count = 0
    fail_count = 0

    for i, record in enumerate(records, 1):
        content_id = record['content_id']
        filing_id = record['filing_id']
        ticker = record['ticker']
        filing_type = record['filing_type']
        filing_date = record['filing_date']

        print(f"\n[{i}/{len(records)}] Processing {ticker} - {filing_type} ({filing_date})...")

        try:
            # Delete existing content
            print(f"  → Deleting existing content for content_id {content_id}")
            delete_existing_content(db_connection, content_id)

            # Re-analyze with updated prompt (includes bull/bear cases)
            print(f"  → Re-analyzing filing {filing_id}...")
            result = analyzer.analyze_filing(filing_id, AnalysisType.DEEP_ANALYSIS)

            # Save to database
            print(f"  → Saving updated analysis...")
            new_content_id = analyzer.save_to_database(result)

            # Verify bull/bear cases were captured
            if result.bull_case:
                print(f"  ✓ Bull case: {result.bull_case[:60]}...")
            else:
                print(f"  ⚠ Warning: No bull case generated")

            if result.bear_case:
                print(f"  ✓ Bear case: {result.bear_case[:60]}...")
            else:
                print(f"  ⚠ Warning: No bear case generated")

            print(f"  ✓ Successfully backfilled {ticker} (content_id: {new_content_id})")
            success_count += 1

        except Exception as e:
            print(f"  ✗ Failed to backfill {ticker}: {str(e)[:100]}")
            logger.error(f"Failed to backfill {content_id}", exception=e)
            fail_count += 1
            continue

        # Print progress
        if i % 10 == 0:
            print(f"\n  === Progress: {i}/{len(records)} complete ===")

    # Summary
    print("\n" + "=" * 80)
    print(f"Backfill Complete!")
    print(f"  ✓ Successful: {success_count}")
    print(f"  ✗ Failed: {fail_count}")
    print(f"  Total processed: {success_count + fail_count}/{len(records)}")
    print("=" * 80)

    db_connection.close()


if __name__ == "__main__":
    main()
