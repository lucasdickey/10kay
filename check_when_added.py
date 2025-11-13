#!/usr/bin/env python3
"""
Check when filings were added to the database
"""
import os
import psycopg2
from datetime import datetime

DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    print("ERROR: DATABASE_URL environment variable not set")
    exit(1)

conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

print("=" * 100)
print("WHEN WERE FILINGS ADDED TO DATABASE?")
print("=" * 100)

# Get recent filings with their created_at timestamps
cursor.execute("""
SELECT
    c.ticker,
    f.filing_type,
    f.filing_date,
    f.created_at,
    f.accession_number
FROM filings f
JOIN companies c ON f.company_id = c.id
WHERE f.filing_date >= '2024-10-01'
ORDER BY f.created_at DESC
LIMIT 30;
""")

print(f"{'Ticker':<8} {'Type':<6} {'Filing Date':<12} {'Added to DB':<20} {'Accession':<22}")
print("-" * 100)

for ticker, ftype, fdate, created, accession in cursor.fetchall():
    fdate_str = fdate.strftime('%Y-%m-%d') if fdate else 'N/A'
    created_str = created.strftime('%Y-%m-%d %H:%M:%S') if created else 'N/A'
    acc_short = accession[:20] + '..' if accession and len(accession) > 22 else (accession or 'N/A')
    print(f"{ticker:<8} {ftype:<6} {fdate_str:<12} {created_str:<20} {acc_short:<22}")

print("\n" + "=" * 100)
print("FILING CREATION TIMELINE")
print("=" * 100)

cursor.execute("""
SELECT
    DATE(created_at) as creation_date,
    COUNT(*) as count
FROM filings
WHERE created_at IS NOT NULL
GROUP BY DATE(created_at)
ORDER BY creation_date DESC
LIMIT 15;
""")

print(f"{'Date':<12} {'Filings Added':<15}")
print("-" * 30)
for date, count in cursor.fetchall():
    date_str = date.strftime('%Y-%m-%d') if date else 'N/A'
    print(f"{date_str:<12} {count:<15}")

cursor.close()
conn.close()
