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

from pipeline.db import connect

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

    print(f"\U0001F4CB Loading {len(companies)} companies from companies.json")
    print()

    from pipeline.db import CompanyRepository, DatabaseError, read_cursor, savepoint, transaction

    repo = CompanyRepository(conn)
    created = updated = failed = 0

    # Upsert rather than INSERT ... DO NOTHING. The old version skipped every
    # existing ticker, so edits to companies.json (a renamed company, a new
    # sector, re-enabling a disabled one) never reached the database even though
    # the docs describe this script as "sync the database".
    with transaction(conn):
        for company in companies:
            ticker = company['ticker']
            try:
                with savepoint(conn):
                    result = repo.upsert(
                        ticker=ticker,
                        name=company['name'],
                        exchange=company.get('exchange'),
                        sector=company.get('sector'),
                        enabled=company.get('enabled', True),
                        metadata=company,
                    )
                if result.created:
                    created += 1
                    print(f"   + {ticker} - {company['name']}")
                else:
                    updated += 1
            except DatabaseError as e:
                failed += 1
                print(f"   \u2717 {ticker}: {e}")

    print()
    print(f"\u2705 {created} added, {updated} refreshed, {failed} failed")

    with read_cursor(conn) as cursor:
        cursor.execute(
            "SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE enabled) AS enabled FROM companies"
        )
        stats = cursor.fetchone()

    print()
    print("\U0001F4CA Database Stats:")
    print(f"   Total companies: {stats['total']}")
    print(f"   Enabled: {stats['enabled']}")
    print(f"   Disabled: {stats['total'] - stats['enabled']}")

    return created


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
        conn = connect(DATABASE_URL, application_name='10kay-seed-companies')
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
        if 'conn' in locals() and not conn.closed:
            conn.close()

if __name__ == '__main__':
    main()
