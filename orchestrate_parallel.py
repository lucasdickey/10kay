#!/usr/bin/env python3
"""
Pipeline orchestrator with parallel phase execution

This script runs the analysis phase with 5 workers and automatically triggers
the generate phase once analyze reaches 10% completion. This overlaps the phases
to reduce total pipeline execution time.

Usage:
    python3 orchestrate_parallel.py                              # Run with default limits (200 each)
    python3 orchestrate_parallel.py --analyze-only               # Only run analyze phase
    python3 orchestrate_parallel.py --generate-only              # Only run generate phase
    python3 orchestrate_parallel.py --publish                    # Also run publish phase after
    python3 orchestrate_parallel.py --analyze-limit 500          # Process up to 500 filings
    python3 orchestrate_parallel.py --generate-limit 500         # Process up to 500 content items

Default limits are set to 200 to ensure scheduled runs complete within 2 hours.
For manual runs or when more time is available, use higher limits.
"""
import sys
import subprocess
import time
import argparse
import psycopg2
from datetime import datetime

from pipeline.utils import get_config


def get_analyze_progress(conn) -> tuple:
    """
    Get current analyze progress

    Returns:
        (total_filings, analyzed, pending, percent_complete)
    """
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE EXISTS (SELECT 1 FROM content WHERE filing_id = filings.id)) as analyzed,
                COUNT(*) FILTER (WHERE filings.status = 'pending' AND NOT EXISTS (SELECT 1 FROM content WHERE filing_id = filings.id)) as pending
            FROM filings
            JOIN companies c ON filings.company_id = c.id
            WHERE c.enabled = true
        """)

        result = cursor.fetchone()
        total, analyzed, pending = result[0], result[1], result[2]
        percent = round(100.0 * analyzed / total, 1) if total > 0 else 0

        cursor.close()
        return total, analyzed, pending, percent
    except Exception as e:
        print(f"Error querying progress: {e}")
        return 0, 0, 0, 0


def get_generate_progress(conn) -> tuple:
    """
    Get current generate progress

    Returns:
        (total_content, with_blog_html, percent_complete)
    """
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                COUNT(*) as total_content,
                COUNT(*) FILTER (WHERE blog_html IS NOT NULL) as with_blog_html
            FROM content
        """)

        result = cursor.fetchone()
        total, blog_html = result[0], result[1]
        percent = round(100.0 * blog_html / total, 1) if total > 0 else 0

        cursor.close()
        return total, blog_html, percent
    except Exception as e:
        print(f"Error querying progress: {e}")
        return 0, 0, 0


def start_analyze_phase(limit: int = 500):
    """Start the parallel analyze phase"""
    print(f"\n{'='*70}")
    print(f"STARTING PHASE 2: PARALLEL ANALYZE (5 workers, limit: {limit})")
    print(f"{'='*70}\n")

    try:
        # Start analyze in background with 5 workers
        process = subprocess.Popen(
            ['python3', 'analyze_parallel.py', '--workers', '5', '--limit', str(limit)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        return process
    except Exception as e:
        print(f"✗ Failed to start analyze phase: {e}")
        sys.exit(1)


def start_generate_phase(limit: int = 500):
    """Start the parallel generate phase"""
    print(f"\n{'='*70}")
    print(f"STARTING PHASE 3: PARALLEL GENERATE (3 workers, limit: {limit})")
    print(f"{'='*70}\n")

    try:
        # Start generate in background with 3 workers
        process = subprocess.Popen(
            ['python3', 'generate_parallel.py', '--workers', '3', '--limit', str(limit)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        return process
    except Exception as e:
        print(f"✗ Failed to start generate phase: {e}")
        return None


def start_publish_phase():
    """Start the publish phase"""
    print(f"\n{'='*70}")
    print("STARTING PHASE 4: PUBLISH")
    print(f"{'='*70}\n")

    try:
        # Start publish phase
        process = subprocess.Popen(
            ['python3', 'pipeline/main.py', '--phase', 'publish'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        return process
    except Exception as e:
        print(f"✗ Failed to start publish phase: {e}")
        return None


def wait_for_process(process, phase_name: str):
    """Wait for a process to complete and stream output"""
    try:
        while True:
            line = process.stdout.readline()
            if not line:
                break
            print(line.rstrip())

        process.wait()
        if process.returncode == 0:
            print(f"✓ {phase_name} completed successfully")
        else:
            print(f"✗ {phase_name} failed with return code {process.returncode}")
    except Exception as e:
        print(f"Error monitoring {phase_name}: {e}")


def main():
    """Main orchestrator"""
    parser = argparse.ArgumentParser(
        description="Pipeline orchestrator with parallel phase execution"
    )
    parser.add_argument(
        '--analyze-only',
        action='store_true',
        help='Only run analyze phase'
    )
    parser.add_argument(
        '--generate-only',
        action='store_true',
        help='Only run generate phase'
    )
    parser.add_argument(
        '--publish',
        action='store_true',
        help='Also run publish phase after generate completes'
    )
    parser.add_argument(
        '--analyze-limit',
        type=int,
        default=200,
        help='Maximum filings to analyze (default: 200 for scheduled runs)'
    )
    parser.add_argument(
        '--generate-limit',
        type=int,
        default=200,
        help='Maximum content items to generate (default: 200 for scheduled runs)'
    )

    args = parser.parse_args()

    config = get_config()

    print("\n" + "=" * 70)
    print("10KAY PARALLEL PIPELINE ORCHESTRATOR")
    print("=" * 70)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # If generate-only, skip analyze
    if args.generate_only:
        print("\nMode: GENERATE PHASE ONLY")
        process = start_generate_phase(args.generate_limit)
        wait_for_process(process, "Generate Phase")
        return

    # Start analyze phase
    print("\nMode: PARALLEL EXECUTION (Analyze → auto-trigger Generate → optional Publish)")
    print(f"Analyze limit: {args.analyze_limit} filings")
    print(f"Generate limit: {args.generate_limit} content items")

    analyze_process = start_analyze_phase(args.analyze_limit)
    generate_process = None
    publish_process = None
    generate_triggered = False

    # Connect to database for monitoring
    try:
        db_conn = psycopg2.connect(config.database.url)
    except Exception as e:
        print(f"✗ Failed to connect to database: {e}")
        analyze_process.terminate()
        sys.exit(1)

    # Monitor analyze phase and trigger generate at 10%
    print("\nWaiting for analyze to reach 10% before triggering generate...\n")

    last_status_time = time.time()
    monitor_interval = 0.1  # Check more frequently
    status_interval = 30  # Print status every 30 seconds

    while analyze_process.poll() is None:
        current_time = time.time()

        # CRITICAL: Consume stdout to prevent buffer deadlock
        # Non-blocking read of stdout
        try:
            import select
            if analyze_process.stdout:
                ready, _, _ = select.select([analyze_process.stdout], [], [], 0)
                if ready:
                    line = analyze_process.stdout.readline()
                    if line:
                        print(line.rstrip())
        except Exception:
            pass  # Continue monitoring even if stdout read fails

        # Check if we should trigger generate
        if not generate_triggered and not args.analyze_only:
            total, analyzed, pending, percent = get_analyze_progress(db_conn)

            if percent >= 10:
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Analyze reached {percent}% - Triggering generate phase...")
                generate_process = start_generate_phase(args.generate_limit)
                generate_triggered = True

        # Print status periodically
        if current_time - last_status_time >= status_interval:
            total, analyzed, pending, analyze_percent = get_analyze_progress(db_conn)
            gen_total, gen_html, gen_percent = get_generate_progress(db_conn)

            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Pipeline Status:")
            print(f"  Analyze: {analyzed}/{total} ({analyze_percent}%)")
            if generate_triggered:
                print(f"  Generate: {gen_html}/{gen_total} ({gen_percent}%)")
            print()

            last_status_time = current_time

        time.sleep(monitor_interval)

    # Wait for analyze to finish and drain any remaining output
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Analyze phase completed, draining output...")
    try:
        if analyze_process.stdout:
            for line in analyze_process.stdout:
                print(line.rstrip())
    except Exception:
        pass

    # If generate was triggered, wait for it
    if generate_triggered and generate_process:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Waiting for generate phase to complete...")
        wait_for_process(generate_process, "Generate Phase")

        # Trigger publish if requested
        if args.publish:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Starting publish phase...")
            publish_process = start_publish_phase()
            wait_for_process(publish_process, "Publish Phase")
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] ✓ PIPELINE COMPLETE")

    # Get final status BEFORE closing connection
    total, analyzed, pending, analyze_percent = get_analyze_progress(db_conn)
    gen_total, gen_html, gen_percent = get_generate_progress(db_conn)

    # Now close the connection
    db_conn.close()

    print(f"\n{'='*70}")
    print("FINAL STATUS")
    print(f"{'='*70}")
    print(f"Analyze: {analyzed}/{total} ({analyze_percent}%)")
    print(f"Generate: {gen_html}/{gen_total} ({gen_percent}%)")
    print(f"{'='*70}\n")


if __name__ == '__main__':
    main()
