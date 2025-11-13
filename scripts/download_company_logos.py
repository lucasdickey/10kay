#!/usr/bin/env python3
"""
Download company logos from Clearbit and save them locally
"""

import os
import json
import requests
import time
from pathlib import Path

def download_company_logos():
    # Load companies
    with open('companies.json', 'r') as f:
        data = json.load(f)
        companies = data['companies']

    # Create logo directory
    logo_dir = Path('public/company-logos')
    logo_dir.mkdir(parents=True, exist_ok=True)

    print(f"Downloading logos for {len(companies)} companies...")

    success_count = 0
    failed = []

    for company in companies:
        ticker = company['ticker']
        domain = company.get('domain')

        if not domain:
            print(f"⚠️  {ticker}: No domain found, skipping")
            failed.append((ticker, "No domain"))
            continue

        # Download from Clearbit with proper headers
        logo_url = f"https://logo.clearbit.com/{domain}?size=128"
        output_path = logo_dir / f"{ticker.lower()}.png"

        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }

        try:
            response = requests.get(logo_url, headers=headers, timeout=10)
            if response.status_code == 200:
                with open(output_path, 'wb') as f:
                    f.write(response.content)
                print(f"✓ {ticker}: Downloaded from {domain}")
                success_count += 1
            else:
                print(f"✗ {ticker}: HTTP {response.status_code} for {domain}")
                failed.append((ticker, f"HTTP {response.status_code}"))
        except Exception as e:
            print(f"✗ {ticker}: Error - {e}")
            failed.append((ticker, str(e)))

        # Be nice to Clearbit API
        time.sleep(0.5)

    print(f"\n{'='*60}")
    print(f"Downloaded {success_count}/{len(companies)} logos")

    if failed:
        print(f"\nFailed downloads ({len(failed)}):")
        for ticker, reason in failed:
            print(f"  - {ticker}: {reason}")

    print(f"\nLogos saved to: {logo_dir.absolute()}")

if __name__ == "__main__":
    download_company_logos()
