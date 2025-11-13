#!/usr/bin/env python3
"""
Quick script to check the latest filing dates in the database
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

# Query to get latest filing for each major company
query = """
SELECT
    c.ticker,
    c.name,
    f.filing_type,
    f.filing_date,
    f.period_end_date,
    f.fiscal_year,
    f.fiscal_quarter,
    f.accession_number
FROM companies c
LEFT JOIN LATERAL (
    SELECT * FROM filings
    WHERE company_id = c.id
    ORDER BY filing_date DESC
    LIMIT 1
) f ON true
WHERE c.ticker IN ('AAPL', 'MSFT', 'GOOGL', 'NVDA', 'TSLA', 'META', 'AMZN', 'AMD', 'INTC')
ORDER BY c.ticker;
"""

print("=" * 100)
print("LATEST FILINGS IN DATABASE (Major Companies)")
print("=" * 100)
print(f"{'Ticker':<8} {'Company':<20} {'Type':<6} {'Filing Date':<12} {'Period End':<12} {'FY':<6} {'Q':<3} {'Accession':<20}")
print("-" * 100)

cursor.execute(query)
rows = cursor.fetchall()

for row in rows:
    ticker, name, filing_type, filing_date, period_end, fy, fq, accession = row

    # Format values
    name_short = name[:18] + '..' if name and len(name) > 20 else (name or 'N/A')
    filing_type_str = filing_type or 'NONE'
    filing_date_str = filing_date.strftime('%Y-%m-%d') if filing_date else 'N/A'
    period_end_str = period_end.strftime('%Y-%m-%d') if period_end else 'N/A'
    fy_str = str(fy) if fy else 'N/A'
    fq_str = str(fq) if fq else 'N/A'
    accession_str = accession[:18] + '..' if accession and len(accession) > 20 else (accession or 'N/A')

    print(f"{ticker:<8} {name_short:<20} {filing_type_str:<6} {filing_date_str:<12} {period_end_str:<12} {fy_str:<6} {fq_str:<3} {accession_str:<20}")

print("\n" + "=" * 100)
print("FILING DATE ANALYSIS")
print("=" * 100)

# Check if any filings are after November 6, 2024
cursor.execute("""
SELECT COUNT(*)
FROM filings
WHERE filing_date > '2024-11-06';
""")
count_after_nov6 = cursor.fetchone()[0]
print(f"Filings after November 6, 2024: {count_after_nov6}")

# Get the most recent filing date overall
cursor.execute("""
SELECT MAX(filing_date)
FROM filings;
""")
most_recent = cursor.fetchone()[0]
print(f"Most recent filing date in database: {most_recent.strftime('%Y-%m-%d') if most_recent else 'N/A'}")

# Get count by filing date
cursor.execute("""
SELECT filing_date, COUNT(*) as count
FROM filings
WHERE filing_date >= '2024-01-01'
GROUP BY filing_date
ORDER BY filing_date DESC
LIMIT 20;
""")
print("\nRecent filing dates and counts:")
print(f"{'Date':<12} {'Count':<6}")
print("-" * 20)
for date, count in cursor.fetchall():
    print(f"{date.strftime('%Y-%m-%d'):<12} {count:<6}")

cursor.close()
conn.close()

print("\n" + "=" * 100)
