#!/usr/bin/env python3
"""
Script to check NVDA report status through the pipeline
"""
import os
import psycopg2
from datetime import datetime

# Get database URL from environment
DATABASE_URL = os.environ.get('DATABASE_URL')

if not DATABASE_URL:
    print("ERROR: DATABASE_URL environment variable not set")
    exit(1)

# Connect to database
conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

print("=" * 100)
print("NVDA REPORT STATUS CHECK")
print("=" * 100)

# 1. Check if NVDA company exists
cursor.execute("""
SELECT id, ticker, name, enabled
FROM companies
WHERE ticker = 'NVDA';
""")
company = cursor.fetchone()

if company:
    company_id, ticker, name, enabled = company
    print(f"\n✓ Company found: {name} ({ticker})")
    print(f"  Enabled: {enabled}")
    print(f"  Company ID: {company_id}")
else:
    print("\n✗ NVDA company not found in database!")
    cursor.close()
    conn.close()
    exit(1)

# 2. Check recent filings
print(f"\n{'='*100}")
print("RECENT FILINGS FOR NVDA")
print(f"{'='*100}")
cursor.execute("""
SELECT
    id,
    filing_type,
    filing_date,
    period_end_date,
    fiscal_year,
    fiscal_quarter,
    accession_number,
    status
FROM filings
WHERE company_id = %s
ORDER BY filing_date DESC
LIMIT 5;
""", (company_id,))

filings = cursor.fetchall()
if filings:
    print(f"{'Filing ID':<38} {'Type':<6} {'Filing Date':<12} {'Period End':<12} {'FY':<6} {'Q':<3} {'Status':<12} {'Accession':<20}")
    print("-" * 100)
    for filing in filings:
        filing_id, filing_type, filing_date, period_end, fy, fq, accession, status = filing
        filing_date_str = filing_date.strftime('%Y-%m-%d') if filing_date else 'N/A'
        period_end_str = period_end.strftime('%Y-%m-%d') if period_end else 'N/A'
        fy_str = str(fy) if fy else 'N/A'
        fq_str = str(fq) if fq else 'N/A'
        accession_str = (accession[:18] + '..') if accession and len(accession) > 20 else (accession or 'N/A')
        status_str = status or 'N/A'
        print(f"{filing_id!s:<38} {filing_type:<6} {filing_date_str:<12} {period_end_str:<12} {fy_str:<6} {fq_str:<3} {status_str:<12} {accession_str:<20}")
else:
    print("No filings found for NVDA!")

# 3. Check content/analyses
print(f"\n{'='*100}")
print("CONTENT/ANALYSES FOR NVDA")
print(f"{'='*100}")

cursor.execute("""
SELECT
    c.id as content_id,
    f.filing_type,
    f.filing_date,
    c.format,
    c.headline,
    c.status,
    c.created_at
FROM content c
JOIN filings f ON c.filing_id = f.id
WHERE f.company_id = %s
ORDER BY f.filing_date DESC, c.created_at DESC
LIMIT 10;
""", (company_id,))

content = cursor.fetchall()
if content:
    print(f"{'Content ID':<38} {'Type':<6} {'Filing Date':<12} {'Format':<10} {'Status':<12} {'Created':<20} {'Headline':<30}")
    print("-" * 140)
    for row in content:
        content_id, filing_type, filing_date, format_val, headline, status, created_at = row
        filing_date_str = filing_date.strftime('%Y-%m-%d') if filing_date else 'N/A'
        created_str = created_at.strftime('%Y-%m-%d %H:%M') if created_at else 'N/A'
        headline_str = (headline[:28] + '..') if headline and len(headline) > 30 else (headline or 'N/A')
        format_str = format_val or 'N/A'
        status_str = status or 'N/A'
        print(f"{content_id!s:<38} {filing_type:<6} {filing_date_str:<12} {format_str:<10} {status_str:<12} {created_str:<20} {headline_str:<30}")
else:
    print("No content/analyses found for NVDA!")

# 4. Check latest filing details
print(f"\n{'='*100}")
print("LATEST FILING FULL DETAILS")
print(f"{'='*100}")

if filings:
    latest_filing_id = filings[0][0]

    # Get all content for the latest filing
    cursor.execute("""
    SELECT
        id,
        format,
        headline,
        status,
        created_at,
        updated_at
    FROM content
    WHERE filing_id = %s
    ORDER BY created_at DESC;
    """, (latest_filing_id,))

    latest_content = cursor.fetchall()

    print(f"\nFiling ID: {latest_filing_id}")
    print(f"Filing Type: {filings[0][1]}")
    print(f"Filing Date: {filings[0][2]}")
    print(f"Status: {filings[0][7]}")

    if latest_content:
        print(f"\nContent generated:")
        for content_row in latest_content:
            content_id, format_val, headline, status, created_at, updated_at = content_row
            print(f"  - Format: {format_val}, Status: {status}")
            print(f"    Created: {created_at}")
            print(f"    Headline: {headline}")
    else:
        print("\n⚠ No content generated for this filing yet!")

# 5. Check if content is ready to be published
print(f"\n{'='*100}")
print("PUBLICATION STATUS")
print(f"{'='*100}")

cursor.execute("""
SELECT
    c.id,
    c.format,
    c.status,
    f.filing_type,
    f.filing_date
FROM content c
JOIN filings f ON c.filing_id = f.id
WHERE f.company_id = %s
    AND c.format IN ('blog', 'email')
    AND c.status = 'ready'
ORDER BY f.filing_date DESC
LIMIT 5;
""", (company_id,))

ready_content = cursor.fetchall()
if ready_content:
    print("Content ready for publication:")
    for row in ready_content:
        content_id, format_val, status, filing_type, filing_date = row
        print(f"  - {format_val} content (Filing: {filing_type}, Date: {filing_date})")
else:
    print("⚠ No content marked as 'ready' for publication")

cursor.close()
conn.close()

print(f"\n{'='*100}")
