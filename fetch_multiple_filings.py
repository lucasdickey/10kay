#!/usr/bin/env python3
"""
Fetch multiple filings per company (3 10-Qs + 1 10-K per company)

This script fetches 3 most recent 10-Q filings and 1 most recent 10-K
for each specified company, storing them in S3 and database.
"""

import sys
import os
from pathlib import Path

# Add pipeline to path
sys.path.insert(0, str(Path(__file__).parent / 'pipeline'))

from utils import get_config, setup_root_logger
from fetchers import EdgarFetcher, FilingType
import psycopg2

def main():
    config = get_config()

    print("=" * 70)
    print("Fetching Multiple Filings Per Company (3x 10-Q + 1x 10-K)")
    print("=" * 70)

    # List of new tickers to fetch for
    tickers = [
        'NXPI', 'MCHP', 'AMAT', 'SNPS', 'NET', 'DDOG', 'FTNT', 'S', 'ENTG', 'ON',
        'MPWR', 'ARM', 'SWKS', 'QRVO', 'SLAB', 'CFLT', 'PATH', 'DOCN', 'HUBS', 'BILL',
        'AFRM', 'SOFI', 'COIN', 'HOOD', 'RBLX', 'TWLO', 'ESTC', 'DT', 'MNDY', 'ZUO',
        'GTLB', 'RPD', 'TENB', 'CYBR', 'VEEV', 'APPF', 'PAYC', 'PCTY', 'ALKT', 'QLYS',
        'FFIV', 'CHKP', 'GEN', 'CVLT', 'PSTG', 'NTAP', 'WIX', 'BIGC', 'LITE', 'COHR'
    ]

    print(f"Tickers to process: {len(tickers)}")
    print(f"Filings per company: 3 x 10-Q + 1 x 10-K = 4 filings each")
    print(f"Total filings: {len(tickers) * 4}")
    print()

    try:
        conn = psycopg2.connect(config.database.url)
        print("✓ Connected to database")

        # Initialize fetcher (without logger for now)
        fetcher = EdgarFetcher(config, conn, logger=None)

        total_10q = 0
        total_10k = 0
        failed_tickers = []

        for ticker in tickers:
            print(f"Processing {ticker}...")

            try:
                # Fetch 3 most recent 10-Q filings
                count_10q = fetcher.process_company(
                    ticker=ticker,
                    filing_type=FilingType.FORM_10Q,
                    limit=3,
                    skip_existing=True
                )
                total_10q += count_10q
                print(f"  ✓ 10-Q: {count_10q} filings")

                # Fetch 1 most recent 10-K filing
                count_10k = fetcher.process_company(
                    ticker=ticker,
                    filing_type=FilingType.FORM_10K,
                    limit=1,
                    skip_existing=True
                )
                total_10k += count_10k
                print(f"  ✓ 10-K: {count_10k} filings")

                total = count_10q + count_10k
                print(f"  → Total: {total} filings")
                print()

            except Exception as e:
                print(f"  ✗ Error: {str(e)[:80]}")
                failed_tickers.append(ticker)
                print()
                continue

        print("=" * 70)
        print("FETCH COMPLETE")
        print("=" * 70)
        print(f"Total 10-Q filings fetched: {total_10q}")
        print(f"Total 10-K filings fetched: {total_10k}")
        print(f"Total filings: {total_10q + total_10k}")
        print(f"Failed tickers: {len(failed_tickers)}")

        if failed_tickers:
            print(f"Failed: {', '.join(failed_tickers)}")

        print()
        print("Next steps:")
        print("  1. Analyze filings: python3 pipeline/main.py --phase analyze")
        print("  2. Generate content: python3 pipeline/main.py --phase generate")

        conn.close()

    except Exception as e:
        print(f"✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
