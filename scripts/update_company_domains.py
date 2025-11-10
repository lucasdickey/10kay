#!/usr/bin/env python3
"""
Update existing companies in database with domain information from companies.json

This script updates the metadata field of existing companies to include the domain.
"""
import os
import json
from pathlib import Path
import psycopg2

# Load DATABASE_URL from environment
DATABASE_URL = os.getenv('DATABASE_URL')

# If not in environment, try to load from .env.local
if not DATABASE_URL:
    env_file = Path(__file__).parent.parent / '.env.local'
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    if key.strip() == 'DATABASE_URL':
                        DATABASE_URL = value.strip().strip('"').strip("'")
                        break

COMPANIES_FILE = Path(__file__).parent.parent / 'companies.json'

def load_companies():
    """Load companies from companies.json"""
    with open(COMPANIES_FILE, 'r') as f:
        data = json.load(f)
    return data['companies']

def update_company_domains(conn):
    """Update company metadata with domain information"""
    companies = load_companies()

    print(f"📋 Updating {len(companies)} companies with domain information")
    print()

    cursor = conn.cursor()

    # Update each company's metadata to include the domain
    update_count = 0
    for company in companies:
        ticker = company['ticker']
        domain = company.get('domain')

        if not domain:
            print(f"   ⚠️  No domain for {ticker}, skipping")
            continue

        # Update the metadata field with the complete company object
        cursor.execute(
            """
            UPDATE companies
            SET metadata = %s
            WHERE ticker = %s
            """,
            (json.dumps(company), ticker)
        )

        if cursor.rowcount > 0:
            update_count += 1
            print(f"   ✓ Updated {ticker} with domain {domain}")

    conn.commit()

    print()
    print(f"✅ Successfully updated {update_count} companies!")

    cursor.close()
    return update_count

def main():
    """Main update function"""
    print("="* 60)
    print("10KAY Company Domain Updater")
    print("="* 60)
    print()

    if not DATABASE_URL:
        print("✗ DATABASE_URL not found in environment variables")
        import sys
        sys.exit(1)

    if not COMPANIES_FILE.exists():
        print(f"✗ companies.json not found at {COMPANIES_FILE}")
        import sys
        sys.exit(1)

    try:
        # Connect to database
        print("🔌 Connecting to database...")
        conn = psycopg2.connect(DATABASE_URL)
        print("✓ Connected")
        print()

        # Update companies
        count = update_company_domains(conn)

        print()
        print("="* 60)
        print(f"✅ Update complete! Updated {count} companies.")
        print("="* 60)

    except psycopg2.Error as e:
        print(f"✗ Database error: {e}")
        import sys
        sys.exit(1)
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        import sys
        sys.exit(1)
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == '__main__':
    main()
