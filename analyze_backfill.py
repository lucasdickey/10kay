#!/usr/bin/env python3
"""
Analyze phase runner for cloud-based pipeline execution.

Analyzes pending filings with Claude AI using AWS Bedrock.
Reads from filings table where status='pending' and writes to content table.

Can be run with configurable limits and worker count.

Usage:
    python3 analyze_backfill.py --limit 100 --workers 5
    python3 analyze_backfill.py --limit 500
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime

# Add pipeline to path
sys.path.insert(0, str(Path(__file__).parent / 'pipeline'))

from utils import get_config, setup_root_logger
from analyzers import ClaudeAnalyzer


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Analyze pending SEC filings with Claude AI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze up to 100 filings with 5 workers
  python3 analyze_backfill.py --limit 100 --workers 5

  # Analyze all pending filings with 3 workers
  python3 analyze_backfill.py --workers 3

  # Analyze 50 filings with default settings
  python3 analyze_backfill.py --limit 50
        """
    )

    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Maximum number of filings to analyze (default: all pending)'
    )

    parser.add_argument(
        '--workers',
        type=int,
        default=3,
        help='Number of parallel workers (default: 3)'
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
    print(f"SEC Filings Analysis - Started at {datetime.now().isoformat()}")
    print("=" * 80)
    print(f"Max filings to analyze: {args.limit or 'unlimited'}")
    print(f"Worker threads: {args.workers}")
    print()

    try:
        analyzer = ClaudeAnalyzer(config)

        # Get pending filings
        pending_count = analyzer.count_pending_filings()
        print(f"Pending filings in database: {pending_count}")

        if pending_count == 0:
            print("No pending filings to analyze.")
            sys.exit(0)

        # Determine limit
        limit = args.limit or pending_count
        print(f"Will analyze up to: {limit} filings")
        print()

        # Run analysis
        print(f"Starting analysis with {args.workers} workers...")
        print()

        total_analyzed = 0
        failed_count = 0

        try:
            # This uses the analyzer's built-in parallelization
            results = analyzer.analyze_batch(limit=limit, workers=args.workers)
            
            if results:
                total_analyzed = results.get('analyzed', 0)
                failed_count = results.get('failed', 0)
                
                print()
                print("=" * 80)
                print(f"ANALYSIS COMPLETE - Finished at {datetime.now().isoformat()}")
                print("=" * 80)
                print(f"Filings analyzed: {total_analyzed}")
                print(f"Failed analyses: {failed_count}")
                print(f"Success rate: {(total_analyzed / (total_analyzed + failed_count) * 100):.1f}%" if (total_analyzed + failed_count) > 0 else "N/A")
            else:
                print("No results returned from analyzer")

        except AttributeError:
            # Fallback: If analyze_batch doesn't exist, use process_company approach
            print("Note: Using fallback analysis method")
            print()
            
            filings = analyzer.get_pending_filings(limit=limit)
            print(f"Found {len(filings)} pending filings to analyze")
            print()

            for idx, filing in enumerate(filings, 1):
                filing_id = filing['filing_id']
                ticker = filing['ticker']
                filing_type = filing['filing_type']
                
                print(f"[{idx}/{len(filings)}] Analyzing {ticker} ({filing_type})...")
                
                try:
                    analyzer.analyze_filing(filing_id)
                    total_analyzed += 1
                    print(f"  ✓ Analysis complete")
                except Exception as e:
                    error_msg = str(e)[:100]
                    print(f"  ✗ Error: {error_msg}")
                    failed_count += 1
                
                print()

            print("=" * 80)
            print(f"ANALYSIS COMPLETE - Finished at {datetime.now().isoformat()}")
            print("=" * 80)
            print(f"Filings analyzed: {total_analyzed}")
            print(f"Failed analyses: {failed_count}")
            if total_analyzed + failed_count > 0:
                print(f"Success rate: {(total_analyzed / (total_analyzed + failed_count) * 100):.1f}%")

        # Write summary for GitHub Actions
        print()
        print("Writing summary...")
        
        summary_file = 'analyze_summary.txt'
        with open(summary_file, 'w') as f:
            f.write(f"**Analysis Summary**\n\n")
            f.write(f"- **Filings analyzed**: {total_analyzed}\n")
            f.write(f"- **Failed**: {failed_count}\n")
            if total_analyzed + failed_count > 0:
                f.write(f"- **Success rate**: {(total_analyzed / (total_analyzed + failed_count) * 100):.1f}%\n")
            f.write(f"- **Completed**: {datetime.now().isoformat()}\n")
        
        print(f"✓ Summary written to {summary_file}")
        print()
        print("Next steps:")
        print("  1. Generate content: python3 pipeline/main.py --phase generate")
        print("  2. Publish content: python3 pipeline/main.py --phase publish")

    except Exception as e:
        print(f"✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
