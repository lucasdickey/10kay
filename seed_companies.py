#!/usr/bin/env python3
"""
Seed companies from companies.json into the database

This script reads the companies.json file and inserts all companies
into the database, skipping any that already exist.
"""
import os
import json
from pathlib import Path
import psycopg2
from psycopg2.extras import execute_batch

# Load DATABASE_URL from environment
DATABASE_URL = os.getenv('DATABASE_URL')

# If not in environment, try to load from .env.local
if not DATABASE_URL:
    env_file = Path(__file__).parent / '.env.local'
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    if key.strip() == 'DATABASE_URL':
                        DATABASE_URL = value.strip().strip('"').strip("'")
                        break

COMPANIES_FILE = Path(__file__).parent / 'companies.json'

def load_companies():
    """Load companies from companies.json"""
    with open(COMPANIES_FILE, 'r') as f:
        data = json.load(f)
    return data['companies']

def seed_companies(conn):
    """Insert companies into database"""
    companies = load_companies()

    print(f"📋 Loading {len(companies)} companies from companies.json")
    print()

    cursor = conn.cursor()

    # Check existing companies
    cursor.execute("SELECT ticker FROM companies")
    existing_tickers = set(row[0] for row in cursor.fetchall())

    new_companies = [c for c in companies if c['ticker'] not in existing_tickers]
    existing_companies = [c for c in companies if c['ticker'] in existing_tickers]

    if existing_companies:
        print(f"⏭️  Skipping {len(existing_companies)} existing companies:")
        for company in existing_companies[:5]:
            print(f"   • {company['ticker']} - {company['name']}")
        if len(existing_companies) > 5:
            print(f"   ... and {len(existing_companies) - 5} more")
        print()

    if not new_companies:
        print("✅ All companies already in database!")
        return 0

    print(f"➕ Inserting {len(new_companies)} new companies:")

    # Prepare insert data
    insert_data = []
    for company in new_companies:
        insert_data.append((
            company['ticker'],
            company['name'],
            company.get('exchange'),  # May not be in all entries
            company.get('sector'),
            company.get('enabled', True),
            json.dumps(company)  # Store full data in metadata
        ))
        print(f"   • {company['ticker']} - {company['name']}")

    # Batch insert
    insert_sql = """
        INSERT INTO companies (ticker, name, exchange, sector, enabled, metadata)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (ticker) DO NOTHING
    """

    execute_batch(cursor, insert_sql, insert_data)
    conn.commit()

    print()
    print(f"✅ Successfully inserted {len(new_companies)} companies!")

    # Show stats
    cursor.execute("SELECT COUNT(*) FROM companies")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM companies WHERE enabled = true")
    enabled = cursor.fetchone()[0]

    print()
    print("📊 Database Stats:")
    print(f"   Total companies: {total}")
    print(f"   Enabled: {enabled}")
    print(f"   Disabled: {total - enabled}")

    cursor.close()
    return len(new_companies)

def main():
    """Main seeding function"""
    print("="* 60)
    print("10KAY Company Seeder")
    print("="* 60)
    print()

    if not DATABASE_URL:
        print("✗ DATABASE_URL not found in environment variables")
        sys.exit(1)

    if not COMPANIES_FILE.exists():
        print(f"✗ companies.json not found at {COMPANIES_FILE}")
        sys.exit(1)

    try:
        # Connect to database
        print("🔌 Connecting to database...")
        conn = psycopg2.connect(DATABASE_URL)
        print("✓ Connected")
        print()

        # Seed companies
        count = seed_companies(conn)

        print()
        print("="* 60)
        if count > 0:
            print(f"✅ Seeding complete! Added {count} companies.")
        else:
            print("✅ Database already up to date!")
        print("="* 60)

    except psycopg2.Error as e:
        print(f"✗ Database error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == '__main__':
    main()
