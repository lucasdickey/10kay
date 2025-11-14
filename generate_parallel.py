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
import psycopg2
from datetime import datetime

from pipeline.utils import get_config, PipelineLogger, setup_root_logger
from pipeline.generators import BlogGenerator, ContentFormat


def generate_content(
    content_id: str,
    filing_id: str,
    ticker: str,
    headline: str,
    config,
    logger: PipelineLogger
) -> Tuple[str, bool, str]:
    """
    Generate blog and email HTML for a single content item

    Returns:
        (content_id, success, message)
    """
    try:
        # Create a new connection for this thread
        conn = psycopg2.connect(config.database.url)
        generator = BlogGenerator(config, conn, logger)

        # Generate blog post HTML
        formats = [ContentFormat.BLOG_POST_HTML]

        results = generator.process_content(
            content_id=content_id,
            formats=formats
        )

        conn.close()

        if results:
            return (content_id, True, f"✓ {ticker} - {headline[:40]}")
        else:
            return (content_id, False, f"⊘ {ticker} - {headline[:40]} (no results)")

    except Exception as e:
        return (content_id, False, f"✗ {ticker}: {str(e)[:100]}")


def get_pending_content(conn, limit: int = 500) -> List[Tuple[str, str, str, str]]:
    """Get list of content items needing generation"""
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT c.id, c.filing_id, comp.ticker,
               COALESCE(c.key_takeaways->>'headline', c.executive_summary)
        FROM content c
        JOIN filings f ON c.filing_id = f.id
        JOIN companies comp ON f.company_id = comp.id
        WHERE c.executive_summary IS NOT NULL
        AND (c.blog_html IS NULL OR c.email_html IS NULL)
        ORDER BY c.created_at DESC
        LIMIT {limit}
    """)

    content_items = cursor.fetchall()
    cursor.close()
    return content_items


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

    # Setup logging
    root_logger = setup_root_logger()
    logger = PipelineLogger(root_logger, 'parallel_generate')

    # Load config
    config = get_config()

    print("\n" + "=" * 70)
    print("PARALLEL CONTENT GENERATOR")
    print("=" * 70)
    print(f"Workers: {args.workers}")
    print(f"Limit: {args.limit} content items")
    print(f"Dry-run: {args.dry_run}")
    print("=" * 70 + "\n")

    # Connect and get pending content
    try:
        conn = psycopg2.connect(config.database.url)
        pending_content = get_pending_content(conn, args.limit)
        conn.close()
    except Exception as e:
        print(f"✗ Failed to connect to database: {e}")
        sys.exit(1)

    if not pending_content:
        print("✓ No pending content to generate")
        return

    print(f"Found {len(pending_content)} content items needing generation\n")

    if args.dry_run:
        print("DRY-RUN MODE: Showing content that would be generated:")
        for i, (content_id, filing_id, ticker, headline) in enumerate(pending_content[:10], 1):
            print(f"  {i}. {ticker} - {headline[:50]}")
        if len(pending_content) > 10:
            print(f"  ... and {len(pending_content) - 10} more")
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
                content_id,
                filing_id,
                ticker,
                headline,
                config,
                logger
            ): (content_id, ticker, headline)
            for content_id, filing_id, ticker, headline in pending_content
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

    if failed > 0:
        print(f"⚠ {failed} content items failed to generate")


if __name__ == '__main__':
    main()
