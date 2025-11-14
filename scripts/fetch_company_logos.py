#!/usr/bin/env python3
"""
Fetch real company logos from various sources and save them locally.
"""

import requests
import os
import psycopg2
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')

def get_company_domains():
    """Get all companies with their tickers and domains."""
    DATABASE_URL = os.getenv('DATABASE_URL')
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT ticker, metadata->>'domain' as domain, name
        FROM companies
        WHERE enabled = true
        ORDER BY ticker
    """)

    columns = [desc[0] for desc in cursor.description]
    results = [dict(zip(columns, row)) for row in cursor.fetchall()]

    cursor.close()
    conn.close()

    return results

def fetch_logo(ticker, domain, name):
    """
    Try multiple methods to fetch a company logo:
    1. Google's favicon service (high quality)
    2. Company website favicon
    3. Logo.dev API
    """
    ticker_lower = ticker.lower()
    output_path = Path(f"public/company-logos/{ticker_lower}.png")

    print(f"Fetching logo for {ticker} ({name})...")

    # Try multiple sources in order of preference
    sources = []

    if domain:
        # 1. Google favicon service (usually high quality)
        sources.append(f"https://www.google.com/s2/favicons?domain={domain}&sz=128")

        # 2. Direct favicon from company website
        sources.append(f"https://{domain}/favicon.ico")
        sources.append(f"https://{domain}/apple-touch-icon.png")

        # 3. Logo.dev (free, crowdsourced logos)
        sources.append(f"https://img.logo.dev/{domain}?token=pk_X-HvofhkRUuN5StcZvEJ2Q")

    # 4. Unavatar (aggregates multiple sources)
    if domain:
        sources.append(f"https://unavatar.io/{domain}")

    for source_url in sources:
        try:
            response = requests.get(source_url, timeout=10, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            })

            if response.status_code == 200 and len(response.content) > 100:
                # Save the logo
                with open(output_path, 'wb') as f:
                    f.write(response.content)
                print(f"  ✓ Saved from {source_url[:50]}...")
                return True

        except Exception as e:
            print(f"  ✗ Failed {source_url[:50]}: {str(e)[:50]}")
            continue

    print(f"  ✗ Could not fetch logo for {ticker}")
    return False

def main():
    """Fetch logos for all companies."""
    companies = get_company_domains()

    print(f"Found {len(companies)} companies")
    print("=" * 60)

    success_count = 0
    fail_count = 0

    for company in companies:
        ticker = company['ticker']
        domain = company['domain']
        name = company['name']

        if not domain:
            print(f"Skipping {ticker} - no domain found")
            fail_count += 1
            continue

        if fetch_logo(ticker, domain, name):
            success_count += 1
        else:
            fail_count += 1

    print("=" * 60)
    print(f"Complete: {success_count} succeeded, {fail_count} failed")

if __name__ == "__main__":
    main()
