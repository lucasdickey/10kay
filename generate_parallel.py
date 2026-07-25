#!/usr/bin/env python3
"""
Parallel content generator - processes multiple content items concurrently

This script uses concurrent.futures to generate blog HTML and email HTML
for multiple content items simultaneously, dramatically reducing total execution time.

Usage:
    python3 generate_parallel.py                    # Generate with default workers
    python3 generate_parallel.py --workers 3        # Use 3 concurrent workers
    python3 generate_parallel.py --limit 200        # Process up to 200 content items
    python3 generate_parallel.py --dry-run           # Preview without saving
"""
import sys
import argparse
from typing import List, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from pipeline.db import ConnectionPool, ContentRepository
from pipeline.utils import get_config, PipelineLogger, setup_root_logger
from pipeline.generators import BlogGenerator, ContentFormat


def generate_content(
    content_id: str,
    filing_id: str,
    ticker: str,
    headline: str,
    config,
    logger: PipelineLogger,
    pool: ConnectionPool,
) -> Tuple[str, bool, str]:
    """
    Generate blog and email HTML for a single content item.

    Uses a pooled connection; the previous per-item ``psycopg2.connect()`` was
    only closed on the success path, leaking a backend for every failure.

    Returns:
        (content_id, success, message)
    """
    try:
        with pool.connection() as conn:
            generator = BlogGenerator(config, conn, logger)
            results = generator.process_content(
                content_id=content_id,
                formats=[ContentFormat.BLOG_POST_HTML, ContentFormat.EMAIL_HTML],
            )

        if results:
            return (content_id, True, f"✓ {ticker} - {(headline or '')[:40]}")
        return (content_id, False, f"⊘ {ticker} - {(headline or '')[:40]} (no results)")

    except Exception as e:
        return (content_id, False, f"✗ {ticker}: {str(e)[:150]}")


def get_pending_content(conn, limit: int = 500) -> List[dict]:
    """Content needing HTML, with ``limit`` bound as a parameter."""
    return ContentRepository(conn).pending_generation(limit=limit)


def main():
    """Main parallel generator"""
    parser = argparse.ArgumentParser(
        description="Parallel content generator using concurrent processing"
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=3,
        help='Number of concurrent generation workers (default: 3, max recommended: 5)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=500,
        help='Maximum content items to process (default: 500)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview without actually generating'
    )

    args = parser.parse_args()

    # Validate worker count
    if args.workers < 1 or args.workers > 15:
        print("✗ Workers must be between 1 and 15")
        sys.exit(1)

    # Setup logging. The old call did not match PipelineLogger's signature:
    # the Logger object went into `step` (NOT NULL) and the name into `filing_id`.
    setup_root_logger()
    logger = PipelineLogger('parallel_generate')

    # Load config
    config = get_config()

    print("\n" + "=" * 70)
    print("PARALLEL CONTENT GENERATOR")
    print("=" * 70)
    print(f"Workers: {args.workers}")
    print(f"Limit: {args.limit} content items")
    print(f"Dry-run: {args.dry_run}")
    print("=" * 70 + "\n")

    # One pool shared by every worker, sized to the worker count.
    try:
        pool = ConnectionPool(
            config.database.url,
            maxconn=args.workers + 1,
            application_name='10kay-generate-parallel',
        )
        with pool.connection() as conn:
            pending_content = get_pending_content(conn, args.limit)
    except Exception as e:
        print(f"✗ Failed to connect to database: {e}")
        sys.exit(1)

    if not pending_content:
        print("✓ No pending content to generate")
        return

    print(f"Found {len(pending_content)} content items needing generation\n")

    if args.dry_run:
        print("DRY-RUN MODE: Showing content that would be generated:")
        for i, item in enumerate(pending_content[:10], 1):
            print(f"  {i}. {item['ticker']} {item['filing_type']}")
        if len(pending_content) > 10:
            print(f"  ... and {len(pending_content) - 10} more")
        pool.close()
        return

    # Generate in parallel
    successful = 0
    failed = 0
    start_time = datetime.now()

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        # Submit all tasks
        futures = {
            executor.submit(
                generate_content,
                item['content_id'],
                item['filing_id'],
                item['ticker'],
                item.get('filing_type', ''),
                config,
                logger,
                pool,
            ): item
            for item in pending_content
        }

        # Process completed tasks as they finish
        completed = 0
        for future in as_completed(futures):
            completed += 1
            content_id, success, message = future.result()

            status = "✓" if success else "✗"
            print(f"[{completed:3d}/{len(pending_content)}] {message}")

            if success:
                successful += 1
            else:
                failed += 1

    # Summary
    duration = (datetime.now() - start_time).total_seconds()
    avg_time = duration / len(pending_content) if pending_content else 0

    print("\n" + "=" * 70)
    print("GENERATION COMPLETE")
    print("=" * 70)
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Total: {len(pending_content)}")
    print(f"Duration: {duration:.1f} seconds")
    print(f"Avg time per item: {avg_time:.1f} seconds")
    print("=" * 70 + "\n")

    pool.close()
    logger.close()

    if failed > 0:
        # Non-zero exit so a scheduled workflow surfaces the failures.
        print(f"⚠ {failed} content items failed to generate")
        sys.exit(1)


if __name__ == '__main__':
    main()
