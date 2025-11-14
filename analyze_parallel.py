#!/usr/bin/env python3
"""
Parallel filing analyzer - processes multiple filings concurrently

This script uses concurrent.futures to process multiple filings simultaneously
with Bedrock API, dramatically reducing total execution time.

Usage:
    python3 analyze_parallel.py                    # Analyze with default workers
    python3 analyze_parallel.py --workers 5        # Use 5 concurrent workers
    python3 analyze_parallel.py --limit 100        # Process up to 100 filings
    python3 analyze_parallel.py --dry-run           # Preview without saving
"""
import sys
import argparse
from typing import List, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import psycopg2
from datetime import datetime

from pipeline.utils import get_config, PipelineLogger, setup_root_logger
from pipeline.analyzers import ClaudeAnalyzer, AnalysisType


def analyze_filing(
    filing_id: str,
    ticker: str,
    filing_type: str,
    config,
    logger: PipelineLogger
) -> Tuple[str, bool, str]:
    """
    Analyze a single filing

    Returns:
        (filing_id, success, message)
    """
    try:
        # Create a new connection for this thread
        conn = psycopg2.connect(config.database.url)
        analyzer = ClaudeAnalyzer(config, conn, logger)

        content_id = analyzer.process_filing(
            filing_id=filing_id,
            analysis_type=AnalysisType.DEEP_ANALYSIS,
            skip_existing=True
        )

        conn.close()

        if content_id:
            return (filing_id, True, f"✓ {ticker} {filing_type}")
        else:
            return (filing_id, False, f"⊘ {ticker} {filing_type} (no content_id)")

    except Exception as e:
        return (filing_id, False, f"✗ {ticker} {filing_type}: {str(e)[:100]}")


def get_pending_filings(conn, limit: int = 500) -> List[Tuple[str, str, str, str]]:
    """Get list of pending filings to analyze"""
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT f.id, c.ticker, f.filing_type, c.name
        FROM filings f
        JOIN companies c ON f.company_id = c.id
        WHERE f.status = 'pending'
        AND NOT EXISTS (
            SELECT 1 FROM content
            WHERE filing_id = f.id
        )
        ORDER BY f.filing_date DESC
        LIMIT {limit}
    """)

    filings = cursor.fetchall()
    cursor.close()
    return filings


def main():
    """Main parallel analyzer"""
    parser = argparse.ArgumentParser(
        description="Parallel filing analyzer using concurrent processing"
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=3,
        help='Number of concurrent analysis workers (default: 3, max recommended: 5)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=500,
        help='Maximum filings to process (default: 500)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview without actually analyzing'
    )

    args = parser.parse_args()

    # Validate worker count
    if args.workers < 1 or args.workers > 10:
        print("✗ Workers must be between 1 and 10")
        sys.exit(1)

    # Setup logging
    root_logger = setup_root_logger()
    logger = PipelineLogger(root_logger, 'parallel_analyze')

    # Load config
    config = get_config()

    print("\n" + "=" * 70)
    print("PARALLEL FILING ANALYZER")
    print("=" * 70)
    print(f"Workers: {args.workers}")
    print(f"Limit: {args.limit} filings")
    print(f"Dry-run: {args.dry_run}")
    print("=" * 70 + "\n")

    # Connect and get pending filings
    try:
        conn = psycopg2.connect(config.database.url)
        pending_filings = get_pending_filings(conn, args.limit)
        conn.close()
    except Exception as e:
        print(f"✗ Failed to connect to database: {e}")
        sys.exit(1)

    if not pending_filings:
        print("✓ No pending filings to analyze")
        return

    print(f"Found {len(pending_filings)} pending filings\n")

    if args.dry_run:
        print("DRY-RUN MODE: Showing filings that would be analyzed:")
        for i, (filing_id, ticker, filing_type, company_name) in enumerate(pending_filings[:10], 1):
            print(f"  {i}. {ticker} {filing_type}")
        if len(pending_filings) > 10:
            print(f"  ... and {len(pending_filings) - 10} more")
        return

    # Analyze in parallel
    successful = 0
    failed = 0
    start_time = datetime.now()

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        # Submit all tasks
        futures = {
            executor.submit(
                analyze_filing,
                filing_id,
                ticker,
                filing_type,
                config,
                logger
            ): (filing_id, ticker, filing_type)
            for filing_id, ticker, filing_type, _ in pending_filings
        }

        # Process completed tasks as they finish
        completed = 0
        for future in as_completed(futures):
            completed += 1
            filing_id, success, message = future.result()

            status = "✓" if success else "✗"
            print(f"[{completed:3d}/{len(pending_filings)}] {message}")

            if success:
                successful += 1
            else:
                failed += 1

    # Summary
    duration = (datetime.now() - start_time).total_seconds()
    avg_time = duration / len(pending_filings) if pending_filings else 0

    print("\n" + "=" * 70)
    print("ANALYSIS COMPLETE")
    print("=" * 70)
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Total: {len(pending_filings)}")
    print(f"Duration: {duration:.1f} seconds")
    print(f"Avg time per filing: {avg_time:.1f} seconds")
    print("=" * 70 + "\n")

    if failed > 0:
        print(f"⚠ {failed} filings failed to analyze")


if __name__ == '__main__':
    main()
