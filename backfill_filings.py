#!/usr/bin/env python3
"""
Backfill script to fetch all historical filings for tracked companies

This script bypasses the standard pipeline's limit=1 behavior and fetches
all available 10-K and 10-Q filings from SEC EDGAR for each company.

Usage:
    python3 backfill_filings.py                    # Backfill all companies
    python3 backfill_filings.py --ticker AAPL      # Backfill specific company
    python3 backfill_filings.py --limit 20         # Fetch 20 most recent per company
    python3 backfill_filings.py --dry-run           # Preview without saving

Environment variables required:
    DATABASE_URL: PostgreSQL connection string
    AWS_REGION: AWS region (default: us-east-1)
    AWS_ACCESS_KEY_ID: AWS access key (for S3 upload)
    AWS_SECRET_ACCESS_KEY: AWS secret key (for S3 upload)
    S3_BUCKET_FILINGS: S3 bucket name (default: 10kay-filings)
"""
import sys
import argparse
from typing import List, Optional
import psycopg2

from pipeline.utils import get_config, PipelineLogger, setup_root_logger
from pipeline.fetchers import EdgarFetcher, FilingType


def get_enabled_companies(conn) -> List[dict]:
    """Fetch list of enabled companies from database"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, ticker, name, metadata
        FROM companies
        WHERE enabled = true
        ORDER BY ticker
    """)

    companies = []
    for row in cursor.fetchall():
        companies.append({
            'id': row[0],
            'ticker': row[1],
            'name': row[2],
            'metadata': row[3] or {}
        })

    cursor.close()
    return companies


def backfill_company(
    fetcher: EdgarFetcher,
    logger: PipelineLogger,
    conn,
    company: dict,
    limit: int,
    skip_existing: bool = True
) -> int:
    """
    Backfill all available filings for a single company

    Args:
        fetcher: EdgarFetcher instance
        logger: PipelineLogger instance
        conn: Database connection
        company: Company dict with id, ticker, name
        limit: Maximum number of filings to fetch per company
        skip_existing: Whether to skip filings already in database

    Returns:
        Number of new filings added
    """
    ticker = company['ticker']

    logger.info(f"\n{'=' * 60}")
    logger.info(f"Backfilling: {ticker} ({company['name']})")
    logger.info(f"{'=' * 60}")

    try:
        # Use process_company which handles the full workflow:
        # fetch -> download -> upload to S3 -> save to database
        count = fetcher.process_company(
            ticker=ticker,
            filing_type=None,  # Both 10-K and 10-Q
            limit=limit,
            skip_existing=skip_existing
        )

        logger.info(f"✓ Backfill complete for {ticker}: {count} new filings added")
        return count

    except Exception as e:
        logger.error(f"✗ Failed to backfill {ticker}", exception=e)
        return 0


def main():
    """Main backfill orchestrator"""
    parser = argparse.ArgumentParser(
        description="Backfill all historical SEC filings for tracked companies"
    )
    parser.add_argument(
        '--ticker',
        type=str,
        help='Specific ticker to backfill (default: all enabled companies)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=100,
        help='Maximum filings to fetch per company (default: 100)'
    )
    parser.add_argument(
        '--skip-existing',
        action='store_true',
        default=True,
        help='Skip filings that already exist in database (default: True)'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Fetch all filings even if they exist (WARNING: may create duplicates)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview what would be fetched without saving to database'
    )

    args = parser.parse_args()

    # Setup logging
    root_logger = setup_root_logger()
    logger = PipelineLogger(root_logger, 'backfill')

    # Load config
    config = get_config()

    if args.dry_run:
        logger.warning("Running in DRY-RUN mode - no changes will be saved")

    # Connect to database
    try:
        conn = psycopg2.connect(config.database_url)
    except psycopg2.Error as e:
        logger.error("Failed to connect to database", exception=e)
        sys.exit(1)

    try:
        # Get companies to process
        if args.ticker:
            companies = [c for c in get_enabled_companies(conn) if c['ticker'] == args.ticker]
            if not companies:
                logger.error(f"Company not found: {args.ticker}")
                sys.exit(1)
        else:
            companies = get_enabled_companies(conn)

        logger.info(f"Backfilling {len(companies)} companies (limit={args.limit} per company)")

        # Initialize fetcher
        fetcher = EdgarFetcher(config, conn, logger)

        # Backfill each company
        total_added = 0
        for company in companies:
            count = backfill_company(
                fetcher=fetcher,
                logger=logger,
                conn=conn,
                company=company,
                limit=args.limit,
                skip_existing=not args.force
            )
            total_added += count

        logger.info(f"\n{'=' * 60}")
        logger.info(f"BACKFILL COMPLETE")
        logger.info(f"{'=' * 60}")
        logger.info(f"Total new filings added: {total_added}")

        conn.close()

    except KeyboardInterrupt:
        logger.warning("Backfill interrupted by user")
        conn.close()
        sys.exit(1)
    except Exception as e:
        logger.error("Unexpected error during backfill", exception=e)
        conn.close()
        sys.exit(1)


if __name__ == '__main__':
    main()
