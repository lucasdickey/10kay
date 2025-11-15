#!/usr/bin/env python3
"""
Backfill slugs for all content records that are missing them.

This fixes the issue where recent filings with bull/bear cases cannot display
in the homepage filter because they lack the required slug field.

Slug format: {ticker}/{year}/{period}/{filing_type}
- For 10-K: period = "fy"
- For 10-Q: period = "q{quarter}"

Example slugs:
- mu/2025/fy/10k
- adbe/2025/q4/10q
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
script_dir = Path(__file__).parent.parent
sys.path.insert(0, str(script_dir))
os.chdir(script_dir)

import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')


def generate_slug(ticker, filing_type, fiscal_year, fiscal_quarter):
    """Generate a slug from filing metadata."""
    ticker_lower = ticker.lower()
    filing_type_lower = filing_type.lower()

    if filing_type == '10-K':
        period = 'fy'
    elif filing_type == '10-Q' and fiscal_quarter:
        period = f'q{fiscal_quarter}'
    else:
        # Fallback for other filing types
        period = 'other'

    return f"{ticker_lower}/{fiscal_year}/{period}/{filing_type_lower}"


def main():
    print("=" * 80)
    print("Slug Backfill Script (for existing records)")
    print("=" * 80)
    print()

    DATABASE_URL = os.getenv('DATABASE_URL')
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL not found in environment")
        sys.exit(1)

    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    # Get all content records without slugs
    cursor.execute("""
        SELECT
            c.id,
            co.ticker,
            f.filing_type,
            f.fiscal_year,
            f.fiscal_quarter
        FROM content c
        JOIN filings f ON c.filing_id = f.id
        JOIN companies co ON c.company_id = co.id
        WHERE c.slug IS NULL
        ORDER BY f.filing_date DESC
    """)

    records = cursor.fetchall()
    total = len(records)

    if total == 0:
        print("✓ All content records already have slugs!")
        conn.close()
        return

    print(f"Found {total} content records without slugs")
    print()

    # Update each record
    success_count = 0
    error_count = 0
    slug_counter = {}  # Track slug usage to handle duplicates

    for content_id, ticker, filing_type, fiscal_year, fiscal_quarter in records:
        try:
            base_slug = generate_slug(ticker, filing_type, fiscal_year, fiscal_quarter)

            # Handle duplicate slugs by adding a sequence number
            if base_slug in slug_counter:
                slug_counter[base_slug] += 1
                slug = f"{base_slug}-{slug_counter[base_slug]}"
            else:
                slug_counter[base_slug] = 0
                slug = base_slug

            cursor.execute("""
                UPDATE content
                SET slug = %s
                WHERE id = %s
            """, (slug, content_id))

            conn.commit()  # Commit each record individually to avoid transaction abort
            success_count += 1

            if success_count % 50 == 0:
                print(f"  Progress: {success_count}/{total} slugs generated...")

        except Exception as e:
            conn.rollback()  # Rollback failed update
            print(f"  ✗ Error updating content {content_id}: {e}")
            error_count += 1
            continue

    print()
    print("=" * 80)
    print("Backfill Complete!")
    print(f"  ✓ Success: {success_count}")
    print(f"  ✗ Errors: {error_count}")
    print("=" * 80)

    cursor.close()
    conn.close()


if __name__ == "__main__":
    main()
