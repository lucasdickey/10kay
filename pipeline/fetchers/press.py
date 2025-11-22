"""
Press Coverage Fetcher

Fetches financial press articles related to SEC filings from multiple news sources.
Captures articles published within 48 hours of filing date.

Supported sources:
- Finnhub News API (free tier available)
- NewsAPI.org (requires paid subscription for commercial use)
- Yahoo Finance (direct scraping)
- Direct scraping: WSJ, Bloomberg, FT, NYT (future enhancement)
"""
import time
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import requests
from dataclasses import dataclass
import uuid

from utils import PipelineLogger


@dataclass
class PressArticle:
    """
    Metadata about a press article

    This matches the structure of the press_coverage table in the database.
    """
    filing_id: str
    source: str
    headline: str
    url: str
    published_at: datetime
    author: Optional[str] = None
    article_snippet: Optional[str] = None
    full_text: Optional[str] = None
    sentiment_score: Optional[float] = None
    relevance_score: Optional[float] = None
    source_api: str = 'unknown'
    metadata: Optional[Dict[str, Any]] = None


class PressFetcher:
    """
    Fetches financial press coverage from multiple news sources

    Supports both API-based sources (Finnhub, NewsAPI) and direct scraping.
    Implements rate limiting per source and 48-hour window filtering.
    """

    def __init__(self, config, db_connection=None, logger: Optional[PipelineLogger] = None):
        """
        Initialize press fetcher

        Args:
            config: PipelineConfig instance with API keys
            db_connection: Database connection (psycopg2)
            logger: PipelineLogger instance
        """
        self.config = config
        self.db_connection = db_connection
        self.logger = logger

        # API keys from config
        self.finnhub_api_key = getattr(config.finnhub, 'api_key', None)
        self.newsapi_key = getattr(config.newsapi, 'api_key', None)

        # Rate limiting tracking (per source)
        self.last_request_times = {}
        self.rate_limits = {
            'finnhub': 1.0,  # 60 requests/minute for free tier
            'newsapi': 0.5,  # 120 requests/minute for developer tier
            'scraping': 2.0,  # Be conservative with web scraping
        }

        if self.logger:
            self.logger.info("Initialized PressFetcher")

    def _rate_limit(self, source: str):
        """
        Enforce rate limit for a specific news source

        Args:
            source: Source identifier ('finnhub', 'newsapi', 'scraping')
        """
        limit = self.rate_limits.get(source, 2.0)
        last_time = self.last_request_times.get(source, 0)

        elapsed = time.time() - last_time
        if elapsed < limit:
            sleep_time = limit - elapsed
            time.sleep(sleep_time)

        self.last_request_times[source] = time.time()

    def fetch_articles_for_filing(
        self,
        filing_id: str,
        ticker: str,
        filing_date: datetime,
        company_name: Optional[str] = None,
        sources: Optional[List[str]] = None
    ) -> List[PressArticle]:
        """
        Fetch press articles related to a filing within 48-hour window

        Args:
            filing_id: UUID of filing in database
            ticker: Company ticker symbol
            filing_date: When the filing was submitted to SEC
            company_name: Optional company name for better search results
            sources: Optional list of sources to query (defaults to all enabled)

        Returns:
            List of PressArticle objects
        """
        if self.logger:
            self.logger.info(
                f"Fetching press coverage for {ticker} filing on {filing_date}"
            )

        # Default to all available sources
        if sources is None:
            sources = ['finnhub']  # Start with Finnhub as it's most reliable
            if self.newsapi_key:
                sources.append('newsapi')

        # Calculate 48-hour window
        start_time = filing_date
        end_time = filing_date + timedelta(hours=48)

        all_articles = []

        # Fetch from each source
        for source in sources:
            try:
                if source == 'finnhub':
                    articles = self._fetch_from_finnhub(
                        filing_id, ticker, start_time, end_time, company_name
                    )
                    all_articles.extend(articles)
                elif source == 'newsapi':
                    articles = self._fetch_from_newsapi(
                        filing_id, ticker, start_time, end_time, company_name
                    )
                    all_articles.extend(articles)
                else:
                    if self.logger:
                        self.logger.warning(f"Unknown source: {source}")
            except Exception as e:
                if self.logger:
                    self.logger.error(
                        f"Failed to fetch from {source} for {ticker}",
                        exception=e
                    )
                # Continue with other sources
                continue

        # Deduplicate by URL
        seen_urls = set()
        unique_articles = []
        for article in all_articles:
            if article.url not in seen_urls:
                seen_urls.add(article.url)
                unique_articles.append(article)

        if self.logger:
            self.logger.info(
                f"Found {len(unique_articles)} unique articles for {ticker}"
            )

        return unique_articles

    def _fetch_from_finnhub(
        self,
        filing_id: str,
        ticker: str,
        start_time: datetime,
        end_time: datetime,
        company_name: Optional[str] = None
    ) -> List[PressArticle]:
        """
        Fetch articles from Finnhub News API

        Args:
            filing_id: UUID of filing
            ticker: Company ticker
            start_time: Start of 48-hour window
            end_time: End of 48-hour window
            company_name: Optional company name

        Returns:
            List of PressArticle objects
        """
        if not self.finnhub_api_key:
            if self.logger:
                self.logger.warning("Finnhub API key not configured")
            return []

        self._rate_limit('finnhub')

        # Finnhub expects YYYY-MM-DD format
        from_date = start_time.strftime('%Y-%m-%d')
        to_date = end_time.strftime('%Y-%m-%d')

        url = "https://finnhub.io/api/v1/company-news"
        params = {
            'symbol': ticker,
            'from': from_date,
            'to': to_date,
            'token': self.finnhub_api_key
        }

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            articles = []
            for item in data:
                # Parse datetime
                pub_time = datetime.fromtimestamp(item.get('datetime', 0))

                # Filter to exact 48-hour window (Finnhub returns full days)
                if not (start_time <= pub_time <= end_time):
                    continue

                # Map Finnhub source to our standardized names
                source = self._normalize_source_name(item.get('source', 'Unknown'))

                article = PressArticle(
                    filing_id=filing_id,
                    source=source,
                    headline=item.get('headline', ''),
                    url=item.get('url', ''),
                    published_at=pub_time,
                    article_snippet=item.get('summary', ''),
                    source_api='finnhub',
                    metadata={
                        'category': item.get('category', ''),
                        'image': item.get('image', ''),
                        'related_symbols': item.get('related', []),
                        'finnhub_id': item.get('id')
                    }
                )
                articles.append(article)

            if self.logger:
                self.logger.debug(
                    f"Finnhub returned {len(articles)} articles for {ticker}"
                )

            return articles

        except requests.exceptions.RequestException as e:
            raise PressArticleError(f"Failed to fetch from Finnhub: {e}")

    def _fetch_from_newsapi(
        self,
        filing_id: str,
        ticker: str,
        start_time: datetime,
        end_time: datetime,
        company_name: Optional[str] = None
    ) -> List[PressArticle]:
        """
        Fetch articles from NewsAPI.org

        Args:
            filing_id: UUID of filing
            ticker: Company ticker
            start_time: Start of 48-hour window
            end_time: End of 48-hour window
            company_name: Optional company name for search query

        Returns:
            List of PressArticle objects

        Note: NewsAPI requires paid plan for commercial use
        """
        if not self.newsapi_key:
            if self.logger:
                self.logger.warning("NewsAPI key not configured")
            return []

        self._rate_limit('newsapi')

        # Build search query
        if company_name:
            query = f'"{ticker}" OR "{company_name}"'
        else:
            query = f'"{ticker}"'

        # NewsAPI expects ISO 8601 format
        from_date = start_time.strftime('%Y-%m-%dT%H:%M:%S')
        to_date = end_time.strftime('%Y-%m-%dT%H:%M:%S')

        url = "https://newsapi.org/v2/everything"
        params = {
            'q': query,
            'from': from_date,
            'to': to_date,
            'language': 'en',
            'sortBy': 'publishedAt',
            'apiKey': self.newsapi_key,
            # Filter to financial sources
            'domains': 'wsj.com,bloomberg.com,ft.com,nytimes.com,reuters.com,cnbc.com'
        }

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            articles = []
            for item in data.get('articles', []):
                # Parse datetime (NewsAPI returns ISO 8601)
                pub_time_str = item.get('publishedAt', '')
                try:
                    pub_time = datetime.fromisoformat(pub_time_str.replace('Z', '+00:00'))
                except ValueError:
                    continue

                # Extract source name from URL
                source = self._extract_source_from_url(item.get('url', ''))

                article = PressArticle(
                    filing_id=filing_id,
                    source=source,
                    headline=item.get('title', ''),
                    url=item.get('url', ''),
                    author=item.get('author'),
                    published_at=pub_time,
                    article_snippet=item.get('description', ''),
                    source_api='newsapi',
                    metadata={
                        'source_name': item.get('source', {}).get('name'),
                        'image': item.get('urlToImage'),
                        'content_preview': item.get('content')
                    }
                )
                articles.append(article)

            if self.logger:
                self.logger.debug(
                    f"NewsAPI returned {len(articles)} articles for {ticker}"
                )

            return articles

        except requests.exceptions.RequestException as e:
            raise PressArticleError(f"Failed to fetch from NewsAPI: {e}")

    def _normalize_source_name(self, source: str) -> str:
        """
        Normalize source names to standard identifiers

        Args:
            source: Raw source name from API

        Returns:
            Standardized source name
        """
        source_lower = source.lower()

        if 'wall street journal' in source_lower or 'wsj' in source_lower:
            return 'WSJ'
        elif 'bloomberg' in source_lower:
            return 'Bloomberg'
        elif 'financial times' in source_lower or 'ft.com' in source_lower:
            return 'FT'
        elif 'new york times' in source_lower or 'nytimes' in source_lower:
            return 'NYT'
        elif 'yahoo finance' in source_lower or 'yahoo' in source_lower:
            return 'Yahoo Finance'
        elif 'reuters' in source_lower:
            return 'Reuters'
        elif 'cnbc' in source_lower:
            return 'CNBC'
        elif 'marketwatch' in source_lower:
            return 'MarketWatch'
        else:
            return source

    def _extract_source_from_url(self, url: str) -> str:
        """
        Extract source name from article URL

        Args:
            url: Article URL

        Returns:
            Source name
        """
        url_lower = url.lower()

        if 'wsj.com' in url_lower:
            return 'WSJ'
        elif 'bloomberg.com' in url_lower:
            return 'Bloomberg'
        elif 'ft.com' in url_lower:
            return 'FT'
        elif 'nytimes.com' in url_lower:
            return 'NYT'
        elif 'finance.yahoo.com' in url_lower:
            return 'Yahoo Finance'
        elif 'reuters.com' in url_lower:
            return 'Reuters'
        elif 'cnbc.com' in url_lower:
            return 'CNBC'
        elif 'marketwatch.com' in url_lower:
            return 'MarketWatch'
        else:
            return 'Unknown'

    def save_articles_to_database(self, articles: List[PressArticle]) -> int:
        """
        Save press articles to database

        Args:
            articles: List of PressArticle objects

        Returns:
            Number of articles saved

        Raises:
            DatabaseError: If save fails
        """
        if not self.db_connection:
            raise DatabaseError("No database connection available")

        if not articles:
            if self.logger:
                self.logger.info("No articles to save")
            return 0

        cursor = self.db_connection.cursor()
        saved = 0

        for article in articles:
            try:
                # Check if article already exists (by URL)
                cursor.execute(
                    "SELECT id FROM press_coverage WHERE url = %s",
                    (article.url,)
                )

                if cursor.fetchone():
                    if self.logger:
                        self.logger.debug(f"Article already exists: {article.url}")
                    continue

                # Insert new article
                cursor.execute(
                    """
                    INSERT INTO press_coverage (
                        id, filing_id, source, headline, url, author,
                        published_at, article_snippet, full_text,
                        sentiment_score, relevance_score, source_api, metadata
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    """,
                    (
                        str(uuid.uuid4()),
                        article.filing_id,
                        article.source,
                        article.headline,
                        article.url,
                        article.author,
                        article.published_at,
                        article.article_snippet,
                        article.full_text,
                        article.sentiment_score,
                        article.relevance_score,
                        article.source_api,
                        article.metadata
                    )
                )

                saved += 1

            except Exception as e:
                if self.logger:
                    self.logger.error(
                        f"Failed to save article {article.url}",
                        exception=e
                    )
                # Continue with other articles
                continue

        self.db_connection.commit()
        cursor.close()

        if self.logger:
            self.logger.info(f"Saved {saved}/{len(articles)} articles to database")

        return saved

    def process_filing(
        self,
        filing_id: str,
        ticker: str,
        filing_date: datetime,
        company_name: Optional[str] = None,
        sources: Optional[List[str]] = None
    ) -> int:
        """
        Complete workflow: fetch and save press articles for a filing

        Args:
            filing_id: UUID of filing in database
            ticker: Company ticker symbol
            filing_date: When filing was submitted
            company_name: Optional company name
            sources: Optional list of sources to query

        Returns:
            Number of articles saved
        """
        # Fetch articles
        articles = self.fetch_articles_for_filing(
            filing_id, ticker, filing_date, company_name, sources
        )

        # Save to database
        saved = self.save_articles_to_database(articles)

        return saved


class PressArticleError(Exception):
    """Raised when fetching press articles fails"""
    pass


class DatabaseError(Exception):
    """Raised when database operations fail"""
    pass
