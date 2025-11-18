#!/usr/bin/env python3
"""
Flexible backfill script for fetching multiple filings per company.

Supports three modes:
1. all-enabled: Fetch from all enabled companies in database
2. predefined-50: Fetch from hardcoded list of 50 tech companies
3. custom-list: Fetch from user-specified ticker list

Can be configured for any number of 10-Q and 10-K filings per company.

Usage:
    python3 backfill_filings.py --source all-enabled --num-10q 3 --num-10k 1
    python3 backfill_filings.py --source predefined-50 --num-10q 4 --num-10k 2
    python3 backfill_filings.py --source custom-list --tickers AAPL,GOOGL,MSFT --num-10q 3 --num-10k 1
"""

import sys
import os
import argparse
from pathlib import Path
from datetime import datetime

# Add pipeline to path
sys.path.insert(0, str(Path(__file__).parent / 'pipeline'))

from utils import get_config, setup_root_logger
from fetchers import EdgarFetcher, FilingType
import psycopg2


# Predefined list of 50 tech companies for default backfill
PREDEFINED_TICKERS = [
    'NXPI', 'MCHP', 'AMAT', 'SNPS', 'NET', 'DDOG', 'FTNT', 'S', 'ENTG', 'ON',
    'MPWR', 'ARM', 'SWKS', 'QRVO', 'SLAB', 'CFLT', 'PATH', 'DOCN', 'HUBS', 'BILL',
    'AFRM', 'SOFI', 'COIN', 'HOOD', 'RBLX', 'TWLO', 'ESTC', 'DT', 'MNDY', 'ZUO',
    'GTLB', 'RPD', 'TENB', 'CYBR', 'VEEV', 'APPF', 'PAYC', 'PCTY', 'ALKT', 'QLYS',
    'FFIV', 'CHKP', 'GEN', 'CVLT', 'PSTG', 'NTAP', 'WIX', 'BIGC', 'LITE', 'COHR'
]


def get_enabled_companies_from_db(conn):
    """Fetch list of enabled companies from database"""
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT ticker
            FROM companies
            WHERE enabled = true
            ORDER BY ticker
        """)
        tickers = [row[0] for row in cursor.fetchall()]
        return tickers
    finally:
        cursor.close()


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Backfill multiple SEC filings per company',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fetch from all enabled companies
  python3 backfill_filings.py --source all-enabled --num-10q 3 --num-10k 1

  # Fetch from predefined tech company list
  python3 backfill_filings.py --source predefined-50 --num-10q 4 --num-10k 2

  # Fetch from custom ticker list
  python3 backfill_filings.py --source custom-list --tickers AAPL,GOOGL,MSFT --num-10q 3 --num-10k 1
        """
    )

    parser.add_argument(
        '--source',
        required=True,
        choices=['all-enabled', 'predefined-50', 'custom-list'],
        help='Source of companies to process'
    )

    parser.add_argument(
        '--tickers',
        type=str,
        help='Comma-separated ticker list (required if source=custom-list)'
    )

    parser.add_argument(
        '--num-10q',
        type=int,
        default=3,
        help='Number of 10-Q filings to fetch per company (default: 3)'
    )

    parser.add_argument(
        '--num-10k',
        type=int,
        default=1,
        help='Number of 10-K filings to fetch per company (default: 1)'
    )

    parser.add_argument(
        '--log-level',
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Logging level (default: INFO)'
    )

    args = parser.parse_args()

    # Validate arguments
    if args.source == 'custom-list' and not args.tickers:
        parser.error('--tickers is required when using --source custom-list')

    return args


def get_tickers_to_process(conn, args):
    """Get list of tickers based on source parameter"""
    if args.source == 'all-enabled':
        tickers = get_enabled_companies_from_db(conn)
    elif args.source == 'predefined-50':
        tickers = PREDEFINED_TICKERS
    elif args.source == 'custom-list':
        tickers = [t.strip().upper() for t in args.tickers.split(',')]
    else:
        raise ValueError(f"Unknown source: {args.source}")

    return tickers


def main():
    args = parse_args()
    config = get_config()

    # Setup logging
    logger = setup_root_logger(level=args.log_level)

    print("=" * 80)
    print(f"SEC Filings Backfill - Started at {datetime.now().isoformat()}")
    print("=" * 80)
    print(f"Source: {args.source}")
    print(f"10-Q per company: {args.num_10q}")
    print(f"10-K per company: {args.num_10k}")
    print()

    try:
        conn = psycopg2.connect(config.database.url)
        logger.info("✓ Connected to database")

        # Get tickers to process
        tickers = get_tickers_to_process(conn, args)
        print(f"Companies to process: {len(tickers)}")
        print(f"Total filings to fetch: {len(tickers) * (args.num_10q + args.num_10k)}")
        print()

        # Initialize fetcher
        fetcher = EdgarFetcher(config, conn, logger=logger)

        # Statistics
        total_10q = 0
        total_10k = 0
        total_skipped = 0
        failed_tickers = []

        # Process each ticker
        for idx, ticker in enumerate(tickers, 1):
            print(f"[{idx}/{len(tickers)}] Processing {ticker}...")

            try:
                # Fetch 10-Q filings
                if args.num_10q > 0:
                    count_10q = fetcher.process_company(
                        ticker=ticker,
                        filing_type=FilingType.FORM_10Q,
                        limit=args.num_10q,
                        skip_existing=True
                    )
                    total_10q += count_10q
                    print(f"  ✓ 10-Q: {count_10q}/{args.num_10q} filings")
                else:
                    count_10q = 0
                    print(f"  ⊘ 10-Q: skipped")

                # Fetch 10-K filings
                if args.num_10k > 0:
                    count_10k = fetcher.process_company(
                        ticker=ticker,
                        filing_type=FilingType.FORM_10K,
                        limit=args.num_10k,
                        skip_existing=True
                    )
                    total_10k += count_10k
                    print(f"  ✓ 10-K: {count_10k}/{args.num_10k} filings")
                else:
                    count_10k = 0
                    print(f"  ⊘ 10-K: skipped")

                total = count_10q + count_10k
                requested = args.num_10q + args.num_10k
                skipped = requested - total
                if skipped > 0:
                    total_skipped += skipped
                    print(f"  → Total: {total}/{requested} filings ({skipped} already existed)")
                else:
                    print(f"  → Total: {total}/{requested} filings")
                print()

            except Exception as e:
                error_msg = str(e)[:120]
                print(f"  ✗ Error: {error_msg}")
                logger.error(f"Failed to process {ticker}", exception=e)
                failed_tickers.append(ticker)
                print()

        # Summary
        print("=" * 80)
        print(f"BACKFILL COMPLETE - Finished at {datetime.now().isoformat()}")
        print("=" * 80)
        print(f"Total 10-Q filings fetched: {total_10q}")
        print(f"Total 10-K filings fetched: {total_10k}")
        print(f"Total filings: {total_10q + total_10k}")
        print(f"Already existing (skipped): {total_skipped}")
        print(f"Failed tickers: {len(failed_tickers)}")

        if failed_tickers:
            print(f"\nFailed companies: {', '.join(failed_tickers)}")

        print()
        print("Next steps:")
        print("  1. Analyze filings: python3 pipeline/main.py --phase analyze")
        print("  2. Generate content: python3 pipeline/main.py --phase generate")
        print("  3. Publish content: python3 pipeline/main.py --phase publish")

        # Write summary file for GitHub Actions
        summary_file = 'backfill_summary.txt'
        with open(summary_file, 'w') as f:
            f.write(f"**Backfill Summary**\n\n")
            f.write(f"- **Source**: {args.source}\n")
            f.write(f"- **Companies processed**: {len(tickers) - len(failed_tickers)}/{len(tickers)}\n")
            f.write(f"- **10-Q filings fetched**: {total_10q}\n")
            f.write(f"- **10-K filings fetched**: {total_10k}\n")
            f.write(f"- **Total filings**: {total_10q + total_10k}\n")
            f.write(f"- **Skipped (existing)**: {total_skipped}\n")
            if failed_tickers:
                f.write(f"- **Failed**: {len(failed_tickers)} ({', '.join(failed_tickers)})\n")
        print(f"\n✓ Summary written to {summary_file}")

        conn.close()

    except Exception as e:
        print(f"✗ Fatal error: {e}")
        logger.error("Fatal error during backfill", exception=e)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
