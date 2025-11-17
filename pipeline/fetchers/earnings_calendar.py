"""
Finnhub Earnings Calendar fetcher

Fetches scheduled earnings dates from Finnhub API and stores them in the database.
This provides actual company-announced earnings dates, rather than estimates based
on historical filing patterns.
"""
import time
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import requests

from ..utils.logger import PipelineLogger


class EarningsCalendarFetcher:
    """
    Fetches upcoming earnings dates from Finnhub API

    Finnhub provides scheduled earnings dates announced by companies,
    including fiscal quarter/year and analyst estimates for EPS and revenue.

    Rate limiting: Free tier allows 60 API calls/minute, 250/day
    """

    def __init__(self, config, db_connection=None, logger: Optional[PipelineLogger] = None):
        """
        Initialize earnings calendar fetcher

        Args:
            config: PipelineConfig instance with finnhub.api_key
            db_connection: Database connection (psycopg2)
            logger: PipelineLogger instance
        """
        self.config = config
        self.db_connection = db_connection
        self.logger = logger

        # Finnhub API configuration
        self.api_key = config.finnhub.api_key
        self.base_url = "https://finnhub.io/api/v1"

        # Rate limiting (60 requests/minute = 1 per second for free tier)
        self.last_request_time = 0
        self.min_request_interval = 1.0  # seconds

        if self.logger:
            self.logger.info("Initialized EarningsCalendarFetcher")

    def _rate_limit(self):
        """Enforce Finnhub rate limit (60 requests/minute for free tier)"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            sleep_time = self.min_request_interval - elapsed
            time.sleep(sleep_time)
        self.last_request_time = time.time()

    def _make_request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make HTTP request to Finnhub API

        Args:
            endpoint: API endpoint path (e.g., '/calendar/earnings')
            params: Query parameters

        Returns:
            JSON response as dictionary

        Raises:
            EarningsCalendarError: If request fails
        """
        self._rate_limit()

        url = f"{self.base_url}{endpoint}"
        params['token'] = self.api_key

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise EarningsCalendarError(f"Failed to fetch from Finnhub: {e}")

    def fetch_earnings_calendar(
        self,
        from_date: datetime,
        to_date: datetime,
        symbol: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch earnings calendar for a date range

        Args:
            from_date: Start date (inclusive)
            to_date: End date (inclusive)
            symbol: Optional ticker symbol to filter by

        Returns:
            List of earnings events with fields:
                - date: Earnings date (YYYY-MM-DD)
                - epsActual: Actual EPS (null if not reported yet)
                - epsEstimate: Estimated EPS
                - hour: 'bmo' (before market open) or 'amc' (after market close)
                - quarter: Fiscal quarter (1-4)
                - revenueActual: Actual revenue (null if not reported yet)
                - revenueEstimate: Estimated revenue
                - symbol: Ticker symbol
                - year: Fiscal year

        Raises:
            EarningsCalendarError: If fetch fails
        """
        params = {
            'from': from_date.strftime('%Y-%m-%d'),
            'to': to_date.strftime('%Y-%m-%d'),
        }

        if symbol:
            params['symbol'] = symbol

        if self.logger:
            self.logger.info(
                f"Fetching earnings calendar from {params['from']} to {params['to']}" +
                (f" for {symbol}" if symbol else "")
            )

        try:
            data = self._make_request('/calendar/earnings', params)
            events = data.get('earningsCalendar', [])

            if self.logger:
                self.logger.info(f"Found {len(events)} earnings events")

            return events
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to fetch earnings calendar", exception=e)
            raise

    def save_to_database(self, events: List[Dict[str, Any]]) -> int:
        """
        Save earnings calendar events to database

        Args:
            events: List of earnings events from Finnhub

        Returns:
            Number of records inserted/updated

        Raises:
            DatabaseError: If save fails
        """
        if not self.db_connection:
            raise DatabaseError("No database connection provided")

        if not events:
            if self.logger:
                self.logger.info("No earnings events to save")
            return 0

        cursor = self.db_connection.cursor()
        saved_count = 0

        for event in events:
            try:
                # Skip events without required fields
                if not event.get('symbol') or not event.get('date'):
                    continue

                # Get company_id from ticker
                cursor.execute(
                    "SELECT id FROM companies WHERE ticker = %s",
                    (event['symbol'],)
                )
                result = cursor.fetchone()

                if not result:
                    if self.logger:
                        self.logger.debug(
                            f"Skipping {event['symbol']} - not in companies table"
                        )
                    continue

                company_id = result[0]

                # Parse earnings date
                earnings_date = datetime.strptime(event['date'], '%Y-%m-%d').date()

                # Upsert earnings event
                # Use ON CONFLICT to update if the same company/fiscal period already exists
                cursor.execute("""
                    INSERT INTO scheduled_earnings (
                        company_id,
                        ticker,
                        earnings_date,
                        earnings_time,
                        fiscal_year,
                        fiscal_quarter,
                        eps_estimate,
                        revenue_estimate,
                        status,
                        source,
                        fetched_at,
                        updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (company_id, fiscal_year, fiscal_quarter)
                    DO UPDATE SET
                        earnings_date = EXCLUDED.earnings_date,
                        earnings_time = EXCLUDED.earnings_time,
                        eps_estimate = EXCLUDED.eps_estimate,
                        revenue_estimate = EXCLUDED.revenue_estimate,
                        fetched_at = EXCLUDED.fetched_at,
                        updated_at = EXCLUDED.updated_at
                    RETURNING id
                """, (
                    company_id,
                    event['symbol'],
                    earnings_date,
                    event.get('hour'),  # 'bmo' or 'amc'
                    event.get('year'),
                    event.get('quarter'),
                    event.get('epsEstimate'),
                    event.get('revenueEstimate'),
                    'scheduled',
                    'finnhub',
                    datetime.now(),
                    datetime.now()
                ))

                saved_count += 1

            except Exception as e:
                if self.logger:
                    self.logger.error(
                        f"Failed to save earnings event for {event.get('symbol')}",
                        exception=e
                    )
                continue

        # Commit all changes
        self.db_connection.commit()
        cursor.close()

        if self.logger:
            self.logger.info(f"Saved {saved_count} earnings events to database")

        return saved_count

    def fetch_upcoming_earnings(
        self,
        days_ahead: int = 90,
        tickers: Optional[List[str]] = None
    ) -> int:
        """
        Fetch upcoming earnings for all tracked companies

        Args:
            days_ahead: How many days into the future to fetch (default 90)
            tickers: Optional list of specific tickers to fetch

        Returns:
            Number of earnings events saved

        This is the main entry point for fetching earnings calendar data.
        """
        from_date = datetime.now()
        to_date = from_date + timedelta(days=days_ahead)

        if self.logger:
            self.logger.info(
                f"Fetching upcoming earnings for next {days_ahead} days" +
                (f" for {len(tickers)} tickers" if tickers else " for all companies")
            )

        # If specific tickers provided, fetch for each one
        # This is more efficient than fetching the entire calendar
        if tickers:
            all_events = []
            for ticker in tickers:
                try:
                    events = self.fetch_earnings_calendar(from_date, to_date, ticker)
                    all_events.extend(events)
                except Exception as e:
                    if self.logger:
                        self.logger.error(
                            f"Failed to fetch earnings for {ticker}",
                            exception=e
                        )
                    continue
        else:
            # Fetch entire calendar (no symbol filter)
            all_events = self.fetch_earnings_calendar(from_date, to_date)

        # Save to database
        return self.save_to_database(all_events)


class EarningsCalendarError(Exception):
    """Raised when earnings calendar operations fail"""
    pass


class DatabaseError(Exception):
    """Raised when database operations fail"""
    pass
