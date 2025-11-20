"""
Finnhub Market Data fetcher

Fetches stock price, market cap, and trading volume data from Finnhub API.
Supports both historical backfill and daily updates.
"""
import time
from datetime import datetime, timedelta, date
from typing import List, Optional, Dict, Any
import requests

from utils import PipelineLogger


class MarketDataFetcher:
    """
    Fetches stock market data from Finnhub API

    Provides current quotes (price, market cap, volume) for tracked companies.
    Rate limiting: Free tier allows 60 API calls/minute
    """

    def __init__(self, config, db_connection=None, logger: Optional[PipelineLogger] = None):
        """
        Initialize market data fetcher

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
            self.logger.info("Initialized MarketDataFetcher")

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
            endpoint: API endpoint path (e.g., '/quote')
            params: Query parameters

        Returns:
            JSON response as dictionary

        Raises:
            MarketDataError: If request fails
        """
        self._rate_limit()

        url = f"{self.base_url}{endpoint}"
        params['token'] = self.api_key

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise MarketDataError(f"Failed to fetch from Finnhub: {e}")

    def fetch_quote(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Fetch current quote for a ticker

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dictionary with quote data:
                - c: Current price
                - d: Change
                - dp: Percent change
                - h: High price of the day
                - l: Low price of the day
                - o: Open price of the day
                - pc: Previous close price
                - t: Timestamp

        Returns None if ticker not found or API error
        """
        if self.logger:
            self.logger.debug(f"Fetching quote for {ticker}")

        try:
            data = self._make_request('/quote', {'symbol': ticker})

            # Check if we got valid data (Finnhub returns 0s for invalid tickers)
            if data.get('c', 0) == 0 and data.get('pc', 0) == 0:
                if self.logger:
                    self.logger.warning(f"No quote data available for {ticker}")
                return None

            return data
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to fetch quote for {ticker}", exception=e)
            return None

    def fetch_company_profile(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Fetch company profile including market cap

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dictionary with company profile data:
                - marketCapitalization: Market cap in millions
                - shareOutstanding: Outstanding shares
                - country: Country of domicile
                - currency: Trading currency
                - exchange: Exchange
                - name: Company name
                - ticker: Stock ticker
                - weburl: Company website
                - logo: Logo URL
                - finnhubIndustry: Industry classification

        Returns None if ticker not found or API error
        """
        if self.logger:
            self.logger.debug(f"Fetching company profile for {ticker}")

        try:
            data = self._make_request('/stock/profile2', {'symbol': ticker})

            # Check if we got valid data
            if not data or 'marketCapitalization' not in data:
                if self.logger:
                    self.logger.warning(f"No profile data available for {ticker}")
                return None

            return data
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to fetch profile for {ticker}", exception=e)
            return None

    def fetch_market_data_for_ticker(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Fetch combined market data (quote + profile) for a ticker

        This combines the quote (price, volume) with the profile (market cap)
        to get all needed data in 2 API calls.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dictionary with:
                - ticker: Stock ticker
                - price: Current price
                - market_cap: Market cap in USD
                - volume: Trading volume
                - change_percent: Daily change percentage
                - data_date: Date of the data

        Returns None if data cannot be fetched
        """
        # Fetch quote data
        quote = self.fetch_quote(ticker)
        if not quote:
            return None

        # Fetch company profile for market cap
        profile = self.fetch_company_profile(ticker)
        if not profile:
            # Still return quote data even if profile fails
            if self.logger:
                self.logger.warning(f"Using quote data without market cap for {ticker}")

        # Get volume from separate endpoint if needed
        # For now, we'll use basic quote data
        # Note: Finnhub free tier doesn't include volume in quote endpoint
        # Volume would require a separate candle/stock candle endpoint

        market_data = {
            'ticker': ticker,
            'price': quote.get('c'),  # Current price
            'change_percent': quote.get('dp'),  # Percent change
            'data_date': datetime.now().date(),  # Today's date
        }

        # Add market cap if available (in millions, convert to dollars)
        if profile and 'marketCapitalization' in profile:
            market_data['market_cap'] = int(profile['marketCapitalization'] * 1_000_000)

        # Volume would go here if we had it from candle data
        market_data['volume'] = None

        return market_data

    def fetch_all_companies_market_data(self, tickers: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Fetch market data for all tracked companies

        Args:
            tickers: Optional list of specific tickers. If None, fetches all enabled companies from DB.

        Returns:
            List of market data dictionaries
        """
        # Get tickers from database if not provided
        if tickers is None and self.db_connection:
            cursor = self.db_connection.cursor()
            cursor.execute("SELECT ticker FROM companies WHERE enabled = true ORDER BY ticker")
            tickers = [row[0] for row in cursor.fetchall()]
            cursor.close()

        if not tickers:
            if self.logger:
                self.logger.warning("No tickers to fetch market data for")
            return []

        if self.logger:
            self.logger.info(f"Fetching market data for {len(tickers)} companies")

        all_data = []
        for ticker in tickers:
            try:
                data = self.fetch_market_data_for_ticker(ticker)
                if data:
                    all_data.append(data)
                else:
                    if self.logger:
                        self.logger.warning(f"No market data returned for {ticker}")
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Failed to fetch market data for {ticker}", exception=e)
                continue

        if self.logger:
            self.logger.info(f"Successfully fetched market data for {len(all_data)} companies")

        return all_data

    def save_to_database(self, market_data_list: List[Dict[str, Any]]) -> int:
        """
        Save market data to database

        Args:
            market_data_list: List of market data dictionaries

        Returns:
            Number of records inserted/updated
        """
        if not self.db_connection:
            raise DatabaseError("No database connection provided")

        if not market_data_list:
            if self.logger:
                self.logger.info("No market data to save")
            return 0

        cursor = self.db_connection.cursor()
        saved_count = 0

        for data in market_data_list:
            try:
                ticker = data['ticker']

                # Get company_id from ticker
                cursor.execute(
                    "SELECT id FROM companies WHERE ticker = %s",
                    (ticker,)
                )
                result = cursor.fetchone()

                if not result:
                    if self.logger:
                        self.logger.debug(f"Skipping {ticker} - not in companies table")
                    continue

                company_id = result[0]

                # Upsert market data
                cursor.execute("""
                    INSERT INTO company_market_data (
                        company_id,
                        ticker,
                        price,
                        market_cap,
                        volume,
                        change_percent,
                        data_date,
                        fetched_at,
                        source
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (company_id, data_date)
                    DO UPDATE SET
                        price = EXCLUDED.price,
                        market_cap = EXCLUDED.market_cap,
                        volume = EXCLUDED.volume,
                        change_percent = EXCLUDED.change_percent,
                        fetched_at = EXCLUDED.fetched_at
                    RETURNING id
                """, (
                    company_id,
                    ticker,
                    data.get('price'),
                    data.get('market_cap'),
                    data.get('volume'),
                    data.get('change_percent'),
                    data['data_date'],
                    datetime.now(),
                    'finnhub'
                ))

                saved_count += 1

            except Exception as e:
                if self.logger:
                    self.logger.error(
                        f"Failed to save market data for {data.get('ticker')}",
                        exception=e
                    )
                continue

        # Commit all changes
        self.db_connection.commit()
        cursor.close()

        if self.logger:
            self.logger.info(f"Saved {saved_count} market data records to database")

        return saved_count

    def fetch_and_save_market_data(self, tickers: Optional[List[str]] = None) -> int:
        """
        Main entry point: Fetch and save market data for companies

        Args:
            tickers: Optional list of specific tickers

        Returns:
            Number of records saved
        """
        market_data_list = self.fetch_all_companies_market_data(tickers)
        return self.save_to_database(market_data_list)


class MarketDataError(Exception):
    """Raised when market data operations fail"""
    pass


class DatabaseError(Exception):
    """Raised when database operations fail"""
    pass
