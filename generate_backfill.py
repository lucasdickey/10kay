#!/usr/bin/env python3
"""
Generate phase runner for cloud-based pipeline execution.

Generates multi-format content (HTML, email, etc.) from analyzed filings.
Reads from content table where analysis exists and generates HTML.

Can be run with configurable limits and worker count.

Usage:
    python3 generate_backfill.py --limit 100 --workers 3
    python3 generate_backfill.py --limit 500
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime

# Add pipeline to path
sys.path.insert(0, str(Path(__file__).parent / 'pipeline'))

from utils import get_config, setup_root_logger
from generators import BlogGenerator, ContentFormat


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Generate content from analyzed SEC filings',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate content for up to 100 filings with 3 workers
  python3 generate_backfill.py --limit 100 --workers 3

  # Generate content for all analyzed filings
  python3 generate_backfill.py

  # Generate content for 50 filings with default settings
  python3 generate_backfill.py --limit 50
        """
    )

    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Maximum number of filings to generate (default: all analyzed)'
    )

    parser.add_argument(
        '--workers',
        type=int,
        default=3,
        help='Number of parallel workers (default: 3)'
    )

    parser.add_argument(
        '--formats',
        nargs='+',
        default=['blog', 'email'],
        choices=['blog', 'email', 'social'],
        help='Output formats to generate (default: blog email)'
    )

    parser.add_argument(
        '--log-level',
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Logging level (default: INFO)'
    )

    return parser.parse_args()


def main():
    args = parse_args()
    config = get_config()

    # Setup logging
    setup_root_logger(level=args.log_level)

    print("=" * 80)
    print(f"Content Generation - Started at {datetime.now().isoformat()}")
    print("=" * 80)
    print(f"Max filings to generate: {args.limit or 'unlimited'}")
    print(f"Worker threads: {args.workers}")
    print(f"Formats: {', '.join(args.formats)}")
    print()

    try:
        generator = BlogGenerator(config)

        # Get pending generations
        pending_count = generator.count_pending_generations()
        print(f"Filings needing content generation: {pending_count}")

        if pending_count == 0:
            print("No filings need content generation.")
            sys.exit(0)

        # Determine limit
        limit = args.limit or pending_count
        print(f"Will generate content for up to: {limit} filings")
        print()

        # Run generation
        print(f"Starting generation with {args.workers} workers...")
        print()

        total_generated = 0
        failed_count = 0

        try:
            # This uses the generator's built-in parallelization
            results = generator.generate_batch(
                limit=limit,
                workers=args.workers,
                formats=[ContentFormat[fmt.upper()] for fmt in args.formats]
            )
            
            if results:
                total_generated = results.get('generated', 0)
                failed_count = results.get('failed', 0)
                
                print()
                print("=" * 80)
                print(f"GENERATION COMPLETE - Finished at {datetime.now().isoformat()}")
                print("=" * 80)
                print(f"Content generated: {total_generated}")
                print(f"Failed generations: {failed_count}")
                if total_generated + failed_count > 0:
                    print(f"Success rate: {(total_generated / (total_generated + failed_count) * 100):.1f}%")
            else:
                print("No results returned from generator")

        except (AttributeError, KeyError):
            # Fallback: If batch methods don't exist, use individual approach
            print("Note: Using fallback generation method")
            print()
            
            filings = generator.get_pending_generations(limit=limit)
            print(f"Found {len(filings)} filings needing generation")
            print()

            for idx, filing in enumerate(filings, 1):
                filing_id = filing['filing_id']
                ticker = filing['ticker']
                
                print(f"[{idx}/{len(filings)}] Generating content for {ticker}...")
                
                try:
                    for fmt in args.formats:
                        content_format = ContentFormat[fmt.upper()]
                        generator.generate_filing(filing_id, content_format)
                    total_generated += 1
                    print(f"  ✓ Generation complete ({', '.join(args.formats)})")
                except Exception as e:
                    error_msg = str(e)[:100]
                    print(f"  ✗ Error: {error_msg}")
                    failed_count += 1
                
                print()

            print("=" * 80)
            print(f"GENERATION COMPLETE - Finished at {datetime.now().isoformat()}")
            print("=" * 80)
            print(f"Content generated: {total_generated}")
            print(f"Failed generations: {failed_count}")
            if total_generated + failed_count > 0:
                print(f"Success rate: {(total_generated / (total_generated + failed_count) * 100):.1f}%")

        # Write summary for GitHub Actions
        print()
        print("Writing summary...")
        
        summary_file = 'generate_summary.txt'
        with open(summary_file, 'w') as f:
            f.write(f"**Generation Summary**\n\n")
            f.write(f"- **Content generated**: {total_generated}\n")
            f.write(f"- **Failed**: {failed_count}\n")
            if total_generated + failed_count > 0:
                f.write(f"- **Success rate**: {(total_generated / (total_generated + failed_count) * 100):.1f}%\n")
            f.write(f"- **Formats**: {', '.join(args.formats)}\n")
            f.write(f"- **Completed**: {datetime.now().isoformat()}\n")
        
        print(f"✓ Summary written to {summary_file}")
        print()
        print("Next steps:")
        print("  1. Publish content: python3 pipeline/main.py --phase publish")
        print("  2. Or test with dry-run: python3 pipeline/main.py --phase publish --dry-run")

    except Exception as e:
        print(f"✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
