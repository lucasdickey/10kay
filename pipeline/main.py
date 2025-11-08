#!/usr/bin/env python3
"""
Main pipeline orchestrator for 10KAY

This script coordinates the full pipeline:
1. Fetch latest SEC filings
2. Analyze with Claude AI
3. Generate multi-format content
4. Publish to subscribers

Can be run manually or via GitHub Actions on a schedule.
"""
import sys
import argparse
from typing import List, Optional
import psycopg2

from utils import get_config, PipelineLogger, setup_root_logger
from fetchers import EdgarFetcher, FilingType
from analyzers import ClaudeAnalyzer, AnalysisType
from generators import BlogGenerator, ContentFormat
from publishers import EmailPublisher, PublishChannel


def get_enabled_companies(conn) -> List[dict]:
    """Fetch list of enabled companies from database"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT ticker, name, metadata
        FROM companies
        WHERE enabled = true
        ORDER BY ticker
    """)

    companies = []
    for row in cursor.fetchall():
        companies.append({
            'ticker': row[0],
            'name': row[1],
            'metadata': row[2] or {}
        })

    cursor.close()
    return companies


def fetch_phase(conn, logger, config, tickers: Optional[List[str]] = None):
    """
    Phase 1: Fetch latest SEC filings for all enabled companies

    Args:
        conn: Database connection
        logger: PipelineLogger
        config: PipelineConfig
        tickers: Optional list of specific tickers to process
    """
    logger.info("=" * 60)
    logger.info("PHASE 1: Fetching SEC Filings")
    logger.info("=" * 60)

    # Get companies to process
    if tickers:
        companies = [{'ticker': t} for t in tickers]
    else:
        companies = get_enabled_companies(conn)

    logger.info(f"Processing {len(companies)} companies")

    # Initialize fetcher
    fetcher = EdgarFetcher(config, conn, logger)

    total_fetched = 0

    for company in companies:
        ticker = company['ticker']
        logger.info(f"Fetching filings for {ticker}")

        try:
            count = fetcher.process_company(
                ticker=ticker,
                filing_type=None,  # Fetch both 10-K and 10-Q
                limit=1,  # Only fetch most recent filing
                skip_existing=True
            )
            total_fetched += count

            logger.info(f"✓ Fetched {count} new filings for {ticker}")

        except Exception as e:
            logger.error(f"✗ Failed to fetch {ticker}", exception=e)
            continue

    logger.info(f"Fetch phase complete: {total_fetched} new filings")
    return total_fetched


def analyze_phase(conn, logger, config):
    """
    Phase 2: Analyze pending filings with Claude AI

    Args:
        conn: Database connection
        logger: PipelineLogger
        config: PipelineConfig
    """
    logger.info("=" * 60)
    logger.info("PHASE 2: Analyzing Filings")
    logger.info("=" * 60)

    # Get pending filings (those without content)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT f.id, c.ticker, f.filing_type, c.name
        FROM filings f
        JOIN companies c ON f.company_id = c.id
        WHERE f.status = 'pending'
        AND NOT EXISTS (
            SELECT 1 FROM content
            WHERE filing_id = f.id
        )
        ORDER BY f.filing_date DESC
        LIMIT 50
    """)

    pending_filings = cursor.fetchall()
    cursor.close()

    logger.info(f"Found {len(pending_filings)} pending filings to analyze")

    # Initialize analyzer
    analyzer = ClaudeAnalyzer(config, conn, logger)

    total_analyzed = 0

    for filing_id, ticker, filing_type, company_name in pending_filings:
        logger.info(f"Analyzing {ticker} {filing_type}")

        try:
            content_id = analyzer.process_filing(
                filing_id=filing_id,
                analysis_type=AnalysisType.DEEP_ANALYSIS,
                skip_existing=True
            )

            if content_id:
                total_analyzed += 1
                logger.info(f"✓ Analyzed {ticker} {filing_type}")

        except Exception as e:
            logger.error(f"✗ Failed to analyze {ticker}", exception=e)
            continue

    logger.info(f"Analysis phase complete: {total_analyzed} filings analyzed")
    return total_analyzed


def generate_phase(conn, logger, config):
    """
    Phase 3: Generate multi-format content

    Args:
        conn: Database connection
        logger: PipelineLogger
        config: PipelineConfig
    """
    logger.info("=" * 60)
    logger.info("PHASE 3: Generating Content")
    logger.info("=" * 60)

    # Get content that needs formatting
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, filing_id
        FROM content
        WHERE status = 'published'
        AND (blog_html IS NULL OR email_html IS NULL)
        ORDER BY published_at DESC
        LIMIT 50
    """)

    pending_content = cursor.fetchall()
    cursor.close()

    logger.info(f"Found {len(pending_content)} content items to format")

    # Initialize generator
    generator = BlogGenerator(config, conn, logger)

    total_generated = 0

    for content_id, filing_id in pending_content:
        logger.info(f"Generating formats for content {content_id}")

        try:
            # Generate blog post HTML
            # Note: Email HTML would use a separate EmailGenerator class
            formats = [
                ContentFormat.BLOG_POST_HTML
            ]

            results = generator.process_content(
                content_id=content_id,
                formats=formats
            )

            if results:
                total_generated += 1
                logger.info(f"✓ Generated {len(results)} formats")

        except Exception as e:
            logger.error(f"✗ Failed to generate formats", exception=e)
            continue

    logger.info(f"Generation phase complete: {total_generated} items formatted")
    return total_generated


def publish_phase(conn, logger, config, dry_run: bool = False):
    """
    Phase 4: Publish content to subscribers

    Args:
        conn: Database connection
        logger: PipelineLogger
        config: PipelineConfig
        dry_run: If True, don't actually send emails
    """
    logger.info("=" * 60)
    logger.info(f"PHASE 4: Publishing Content (dry_run={dry_run})")
    logger.info("=" * 60)

    # Get content ready to publish (has all formats, not yet sent)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.id, c.filing_id, f.ticker, c.tldr_headline
        FROM content c
        JOIN filings f ON c.filing_id = f.id
        WHERE c.status = 'published'
        AND c.email_html IS NOT NULL
        AND NOT EXISTS (
            SELECT 1 FROM email_deliveries
            WHERE content_id = c.id
            AND status = 'sent'
        )
        ORDER BY c.published_at DESC
        LIMIT 10
    """)

    ready_content = cursor.fetchall()
    cursor.close()

    logger.info(f"Found {len(ready_content)} content items ready to publish")

    # Initialize publisher
    publisher = EmailPublisher(config, conn, logger)

    total_published = 0

    for content_id, filing_id, ticker, headline in ready_content:
        logger.info(f"Publishing: {ticker} - {headline}")

        try:
            # Publish to email newsletter (respecting free vs paid tiers)
            result = publisher.publish(
                content_id=content_id,
                channel=PublishChannel.EMAIL_NEWSLETTER,
                dry_run=dry_run
            )

            if not dry_run:
                publisher.save_delivery_record(result)

            total_published += 1
            logger.info(f"✓ Published to {result.recipient_count} subscribers")

        except Exception as e:
            logger.error(f"✗ Failed to publish", exception=e)
            continue

    logger.info(f"Publish phase complete: {total_published} items published")
    return total_published


def main():
    """Main pipeline execution"""
    parser = argparse.ArgumentParser(description='10KAY Pipeline Orchestrator')
    parser.add_argument(
        '--phase',
        choices=['fetch', 'analyze', 'generate', 'publish', 'all'],
        default='all',
        help='Pipeline phase to run'
    )
    parser.add_argument(
        '--tickers',
        nargs='+',
        help='Specific ticker symbols to process (fetch phase only)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Validate without actually publishing (publish phase only)'
    )
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Logging level'
    )

    args = parser.parse_args()

    # Setup logging
    setup_root_logger(args.log_level)

    # Load configuration
    config = get_config()

    # Connect to database
    try:
        conn = psycopg2.connect(config.database.url)
        logger = PipelineLogger('main', db_connection=conn)

        logger.info("=" * 60)
        logger.info("10KAY Pipeline Starting")
        logger.info("=" * 60)
        logger.info(f"Phase: {args.phase}")
        logger.info(f"Dry run: {config.dry_run or args.dry_run}")
        logger.info("=" * 60)

        # Execute requested phase(s)
        if args.phase in ['fetch', 'all']:
            fetch_phase(conn, logger, config, args.tickers)

        if args.phase in ['analyze', 'all']:
            analyze_phase(conn, logger, config)

        if args.phase in ['generate', 'all']:
            generate_phase(conn, logger, config)

        if args.phase in ['publish', 'all']:
            publish_phase(conn, logger, config, args.dry_run)

        logger.info("=" * 60)
        logger.info("Pipeline complete!")
        logger.info("=" * 60)

    except Exception as e:
        print(f"✗ Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        if 'conn' in locals():
            conn.close()


if __name__ == '__main__':
    main()
