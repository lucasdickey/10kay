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
from datetime import datetime

from pipeline.db import ConnectionPool, FilingRepository
from pipeline.utils import get_config, PipelineLogger, setup_root_logger
from pipeline.analyzers import ClaudeAnalyzer, AnalysisType


def analyze_filing(
    filing_id: str,
    ticker: str,
    filing_type: str,
    config,
    logger: PipelineLogger,
    pool: ConnectionPool,
) -> Tuple[str, bool, str]:
    """
    Analyze a single filing.

    Borrows a pooled connection instead of opening one per work item. The old
    version called ``conn.close()`` only on the success path, so every failed
    filing leaked a backend; a long backfill eventually exhausted the RDS
    connection limit and the remaining workers all failed to connect.

    Returns:
        (filing_id, success, message)
    """
    try:
        with pool.connection() as conn:
            analyzer = ClaudeAnalyzer(config, conn, logger)
            content_id = analyzer.process_filing(
                filing_id=filing_id,
                analysis_type=AnalysisType.DEEP_ANALYSIS,
                skip_existing=True,
            )

        if content_id:
            return (filing_id, True, f"✓ {ticker} {filing_type}")
        return (filing_id, False, f"⊘ {ticker} {filing_type} (already analyzed)")

    except Exception as e:
        return (filing_id, False, f"✗ {ticker} {filing_type}: {str(e)[:150]}")


def get_pending_filings(conn, limit: int = 500) -> List[dict]:
    """Pending filings, with ``limit`` bound as a parameter, not interpolated."""
    return FilingRepository(conn).pending(limit=limit)


def main():
    """Main parallel analyzer"""
    parser = argparse.ArgumentParser(
        description="Parallel filing analyzer using concurrent processing"
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=5,
        help='Number of concurrent analysis workers (default: 5, max recommended: 8)'
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
    if args.workers < 1 or args.workers > 15:
        print("✗ Workers must be between 1 and 15")
        sys.exit(1)

    # Setup logging. The old call was PipelineLogger(root_logger, 'parallel_analyze'),
    # which does not match the signature: the Logger object landed in `step`
    # (a NOT NULL column) and the name landed in `filing_id`.
    setup_root_logger()
    logger = PipelineLogger('parallel_analyze')

    # Load config
    config = get_config()

    print("\n" + "=" * 70)
    print("PARALLEL FILING ANALYZER")
    print("=" * 70)
    print(f"Workers: {args.workers}")
    print(f"Limit: {args.limit} filings")
    print(f"Dry-run: {args.dry_run}")
    print("=" * 70 + "\n")

    # One pool shared by every worker, sized to the worker count.
    try:
        pool = ConnectionPool(
            config.database.url,
            maxconn=args.workers + 1,
            application_name='10kay-analyze-parallel',
        )
        with pool.connection() as conn:
            pending_filings = get_pending_filings(conn, args.limit)
    except Exception as e:
        print(f"✗ Failed to connect to database: {e}")
        sys.exit(1)

    if not pending_filings:
        print("✓ No pending filings to analyze")
        return

    print(f"Found {len(pending_filings)} pending filings\n")

    if args.dry_run:
        print("DRY-RUN MODE: Showing filings that would be analyzed:")
        for i, filing in enumerate(pending_filings[:10], 1):
            print(f"  {i}. {filing['ticker']} {filing['filing_type']}")
        if len(pending_filings) > 10:
            print(f"  ... and {len(pending_filings) - 10} more")
        pool.close()
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
                filing['filing_id'],
                filing['ticker'],
                filing['filing_type'],
                config,
                logger,
                pool,
            ): filing
            for filing in pending_filings
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

    pool.close()
    logger.close()

    if failed > 0:
        # Non-zero exit so a scheduled workflow surfaces the failures instead of
        # reporting a green run that analyzed nothing.
        print(f"⚠ {failed} filings failed to analyze")
        sys.exit(1)


if __name__ == '__main__':
    main()
