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
from pathlib import Path
from typing import List, Optional

# This module is executed as a script (`python3 pipeline/main.py`), which puts
# `pipeline/` — not the repo root — on sys.path. Submodules use package-relative
# imports (`from ..db import ...`), so the repo root has to be importable for
# `pipeline` to exist as a package. Adding it here keeps both entry points
# working: `python3 pipeline/main.py` and `from pipeline.main import ...`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.db import (  # noqa: E402
    CompanyRepository,
    ContentRepository,
    DatabaseError,
    DeliveryRecord,
    DeliveryRepository,
    FilingRepository,
    connect,
    transaction,
)
from pipeline.utils import get_config, PipelineLogger, setup_root_logger  # noqa: E402
from pipeline.fetchers import EdgarFetcher, FilingType  # noqa: E402
from pipeline.fetchers.earnings_calendar import EarningsCalendarFetcher  # noqa: E402
from pipeline.fetchers.market_data import MarketDataFetcher  # noqa: E402
from pipeline.analyzers import ClaudeAnalyzer, AnalysisType  # noqa: E402
from pipeline.generators import BlogGenerator, ContentFormat  # noqa: E402
from pipeline.publishers import EmailPublisher, PublishChannel  # noqa: E402


def get_enabled_companies(conn) -> List[dict]:
    """Fetch list of enabled companies from database"""
    return CompanyRepository(conn).list_enabled()


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


def earnings_calendar_phase(conn, logger, config, tickers: Optional[List[str]] = None):
    """
    Fetch upcoming earnings dates from Finnhub API

    This provides actual company-announced earnings dates rather than estimates.
    Should be run less frequently than SEC filing fetches (e.g., every other day).

    Args:
        conn: Database connection
        logger: PipelineLogger
        config: PipelineConfig
        tickers: Optional list of specific tickers to fetch
    """
    logger.info("=" * 60)
    logger.info("EARNINGS CALENDAR: Fetching Scheduled Dates")
    logger.info("=" * 60)

    # Initialize earnings calendar fetcher
    fetcher = EarningsCalendarFetcher(config, conn, logger)

    # Get tickers if not provided
    if not tickers:
        companies = get_enabled_companies(conn)
        tickers = [c['ticker'] for c in companies]

    logger.info(f"Fetching earnings calendar for {len(tickers)} companies")
    logger.info("Looking ahead 90 days")

    try:
        # Fetch upcoming earnings (90 days ahead)
        count = fetcher.fetch_upcoming_earnings(
            days_ahead=90,
            tickers=tickers
        )

        logger.info(f"✓ Saved {count} scheduled earnings dates")
        logger.info("Earnings calendar fetch complete")
        return count

    except Exception as e:
        logger.error("✗ Failed to fetch earnings calendar", exception=e)
        return 0


def market_data_phase(conn, logger, config, tickers: Optional[List[str]] = None):
    """
    Fetch market data (stock prices, market cap) from Finnhub API

    This should be run weekly to update market capitalization and daily stock prices
    for 7-day performance tracking.

    Args:
        conn: Database connection
        logger: PipelineLogger
        config: PipelineConfig
        tickers: Optional list of specific tickers to fetch
    """
    logger.info("=" * 60)
    logger.info("MARKET DATA: Fetching Stock Prices & Market Cap")
    logger.info("=" * 60)

    # Initialize market data fetcher
    fetcher = MarketDataFetcher(config, conn, logger)

    # Get tickers if not provided
    if not tickers:
        companies = get_enabled_companies(conn)
        tickers = [c['ticker'] for c in companies]

    logger.info(f"Fetching market data for {len(tickers)} companies")

    try:
        # Fetch and save market data
        count = fetcher.fetch_and_save_market_data(tickers)

        logger.info(f"✓ Saved market data for {count} companies")
        logger.info("Market data fetch complete")
        return count

    except Exception as e:
        logger.error("✗ Failed to fetch market data", exception=e)
        return 0


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

    pending_content = ContentRepository(conn).pending_generation(limit=50)
    logger.info(f"Found {len(pending_content)} content items to format")

    # Initialize generator
    generator = BlogGenerator(config, conn, logger)

    total_generated = 0

    for item in pending_content:
        content_id = item['content_id']
        logger.info(f"Generating formats for content {content_id}")

        try:
            # Generate both blog post HTML and email HTML formats for publishing
            formats = [
                ContentFormat.BLOG_POST_HTML,
                ContentFormat.EMAIL_HTML
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

    ready_content = ContentRepository(conn).ready_to_publish(limit=10)
    logger.info(f"Found {len(ready_content)} content items ready to publish")

    # Initialize publisher
    publisher = EmailPublisher(config, conn, logger)

    total_published = 0

    for item in ready_content:
        content_id = item['content_id']
        logger.info(f"Publishing: {item['ticker']} - {item['headline']}")

        try:
            # Publish to email newsletter (respecting free vs paid tiers)
            result = publisher.publish(
                content_id=content_id,
                channel=PublishChannel.EMAIL_NEWSLETTER,
                dry_run=dry_run
            )

            if not dry_run:
                # Delivery record and published_at in one transaction: recording
                # the send but failing to mark it published would mail the same
                # analysis again on the next run.
                with transaction(conn):
                    DeliveryRepository(conn).record(DeliveryRecord(
                        content_id=content_id,
                        status=result.status.value,
                        sent_at=result.delivered_at,
                        resend_email_id=result.external_id,
                        metadata={
                            'channel': result.channel.value,
                            'recipient_count': result.recipient_count,
                        },
                    ))
                    ContentRepository(conn).mark_published(content_id)

            total_published += 1
            logger.info(f"✓ Published to {result.recipient_count} subscribers")

        except Exception as e:
            logger.error("✗ Failed to publish", exception=e,
                         extra={'content_id': content_id})
            continue

    logger.info(f"Publish phase complete: {total_published} items published")
    return total_published


def main():
    """Main pipeline execution"""
    parser = argparse.ArgumentParser(description='10KAY Pipeline Orchestrator')
    parser.add_argument(
        '--phase',
        choices=['fetch', 'earnings-calendar', 'market-data', 'analyze', 'generate', 'publish', 'all'],
        default='all',
        help='Pipeline phase to run'
    )
    parser.add_argument(
        '--tickers',
        nargs='+',
        help='Specific ticker symbols to process (fetch and earnings-calendar phases)'
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
    conn = None
    logger = None
    try:
        conn = connect(config.database.url, application_name='10kay-pipeline-main')
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

        if args.phase in ['earnings-calendar']:
            earnings_calendar_phase(conn, logger, config, args.tickers)

        if args.phase in ['market-data']:
            market_data_phase(conn, logger, config, args.tickers)

        if args.phase in ['analyze', 'all']:
            analyze_phase(conn, logger, config)

        if args.phase in ['generate', 'all']:
            generate_phase(conn, logger, config)

        if args.phase in ['publish', 'all']:
            publish_phase(conn, logger, config, args.dry_run)

        logger.info("=" * 60)
        logger.info("Pipeline complete!")
        logger.info("=" * 60)

    except DatabaseError as e:
        print(f"✗ Pipeline failed (database): {e}")
        sys.exit(1)

    except Exception as e:
        print(f"✗ Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        # Roll back before closing: exiting with an open transaction leaves the
        # server tearing down an aborted backend rather than a clean one.
        if logger is not None:
            logger.close()
        if conn is not None and not conn.closed:
            try:
                conn.rollback()
            finally:
                conn.close()


if __name__ == '__main__':
    main()
