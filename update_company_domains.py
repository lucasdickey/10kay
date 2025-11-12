"""
Update company metadata with domain information
"""
import psycopg2
import os
import json
from dotenv import load_dotenv

load_dotenv('.env.local')

# Load companies.json
with open('companies.json', 'r') as f:
    data = json.load(f)
    companies = data['companies']

# Connect to database
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cursor = conn.cursor()

print("Updating company domains...")
updated_count = 0

for company in companies:
    ticker = company['ticker']
    domain = company.get('domain')

    if domain:
        # Update the metadata JSONB field with domain
        cursor.execute("""
            UPDATE companies
            SET metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object('domain', %s)
            WHERE ticker = %s
        """, (domain, ticker))

        if cursor.rowcount > 0:
            updated_count += 1
            print(f"  ✓ {ticker:6} -> {domain}")

conn.commit()

print(f"\n✓ Updated {updated_count} companies with domain data")

# Verify
cursor.execute("""
    SELECT ticker, name, metadata->>'domain' as domain
    FROM companies
    WHERE metadata->>'domain' IS NOT NULL
    LIMIT 10
""")

print("\nSample companies with domains:")
print("-" * 80)
for row in cursor.fetchall():
    ticker, name, domain = row
    print(f"  {ticker:6} | {name:30} | {domain}")

cursor.close()
conn.close()
print("\n✓ Migration complete!")
