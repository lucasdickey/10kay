"""
Investor Relations Page Scraper

Scrapes company IR pages for documents and updates published within ±72 hours
of 10-K/10-Q filings. Supports various IR page structures through flexible
heuristic detection.
"""
import time
import hashlib
import requests
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re

from utils import PipelineLogger


class IRDocument:
    """Represents a document scraped from an IR page"""

    def __init__(
        self,
        title: str,
        document_url: str,
        published_at: datetime,
        document_type: str = 'other',
        summary: Optional[str] = None,
        raw_content: Optional[str] = None
    ):
        self.title = title
        self.document_url = document_url
        self.published_at = published_at
        self.document_type = document_type
        self.summary = summary
        self.raw_content = raw_content

    def get_content_hash(self) -> str:
        """Generate SHA256 hash of document content for deduplication"""
        content = f"{self.title}|{self.document_url}|{self.published_at.isoformat()}"
        return hashlib.sha256(content.encode()).hexdigest()


class IRPageScraper:
    """
    Scrapes investor relations pages for documents and updates

    Supports multiple strategies for finding documents:
    1. RSS/Atom feeds (most reliable)
    2. Structured press release sections
    3. Common HTML patterns (links with dates)
    4. JSON-LD structured data
    """

    def __init__(self, config, db_connection=None, logger: Optional[PipelineLogger] = None):
        """
        Initialize IR page scraper

        Args:
            config: PipelineConfig instance
            db_connection: Database connection (psycopg2)
            logger: PipelineLogger instance
        """
        self.config = config
        self.db_connection = db_connection
        self.logger = logger

        # HTTP request configuration
        self.user_agent = config.sec.user_agent if hasattr(config, 'sec') else '10KAY IR Scraper'
        self.timeout = 30
        self.max_retries = 3

        # Rate limiting (be respectful to IR pages)
        self.last_request_time = 0
        self.min_request_interval = 2.0  # 2 seconds between requests

        if self.logger:
            self.logger.info("Initialized IRPageScraper")

    def _rate_limit(self):
        """Enforce polite rate limiting"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            sleep_time = self.min_request_interval - elapsed
            time.sleep(sleep_time)
        self.last_request_time = time.time()

    def _make_request(self, url: str, headers: Optional[Dict] = None) -> requests.Response:
        """
        Make HTTP request with retries

        Args:
            url: URL to fetch
            headers: Optional HTTP headers

        Returns:
            Response object

        Raises:
            IRScraperError: If request fails after retries
        """
        self._rate_limit()

        default_headers = {
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }

        if headers:
            default_headers.update(headers)

        for attempt in range(self.max_retries):
            try:
                response = requests.get(url, headers=default_headers, timeout=self.timeout)
                response.raise_for_status()
                return response
            except requests.exceptions.RequestException as e:
                if attempt == self.max_retries - 1:
                    raise IRScraperError(f"Failed to fetch {url} after {self.max_retries} attempts: {e}")
                time.sleep(2 ** attempt)  # Exponential backoff

    def scrape_ir_page(
        self,
        ir_url: str,
        from_date: datetime,
        to_date: datetime
    ) -> List[IRDocument]:
        """
        Scrape IR page for documents within a date range

        Args:
            ir_url: URL of the investor relations page
            from_date: Start date (inclusive)
            to_date: End date (inclusive)

        Returns:
            List of IRDocument objects

        This method tries multiple strategies to find documents:
        1. Look for RSS/Atom feeds
        2. Find press release sections
        3. Parse structured data
        4. Use heuristics to find dated content
        """
        if self.logger:
            self.logger.info(
                f"Scraping IR page: {ir_url} from {from_date.date()} to {to_date.date()}"
            )

        documents = []

        # Strategy 1: Try to find RSS feed
        try:
            rss_docs = self._scrape_rss_feed(ir_url, from_date, to_date)
            if rss_docs:
                documents.extend(rss_docs)
                if self.logger:
                    self.logger.info(f"Found {len(rss_docs)} documents from RSS feed")
        except Exception as e:
            if self.logger:
                self.logger.debug(f"RSS feed scraping failed: {e}")

        # Strategy 2: Scrape HTML for press releases/news
        try:
            html_docs = self._scrape_html_content(ir_url, from_date, to_date)
            if html_docs:
                documents.extend(html_docs)
                if self.logger:
                    self.logger.info(f"Found {len(html_docs)} documents from HTML scraping")
        except Exception as e:
            if self.logger:
                self.logger.error(f"HTML scraping failed: {e}", exception=e)

        # Deduplicate by content hash
        unique_docs = {}
        for doc in documents:
            hash_key = doc.get_content_hash()
            if hash_key not in unique_docs:
                unique_docs[hash_key] = doc

        if self.logger:
            self.logger.info(
                f"Scraped {len(unique_docs)} unique documents from {ir_url}"
            )

        return list(unique_docs.values())

    def _scrape_rss_feed(
        self,
        base_url: str,
        from_date: datetime,
        to_date: datetime
    ) -> List[IRDocument]:
        """
        Try to find and scrape RSS/Atom feed

        Common RSS feed locations:
        - /rss
        - /feed
        - /newsroom/rss
        - Link in HTML <head>
        """
        documents = []

        # First, check HTML for RSS feed links
        try:
            response = self._make_request(base_url)
            soup = BeautifulSoup(response.content, 'html.parser')

            # Look for RSS feed link in HTML
            rss_link = soup.find('link', {'type': 'application/rss+xml'})
            if not rss_link:
                rss_link = soup.find('link', {'type': 'application/atom+xml'})

            if rss_link and rss_link.get('href'):
                feed_url = urljoin(base_url, rss_link['href'])
                return self._parse_rss_feed(feed_url, from_date, to_date)

        except Exception as e:
            if self.logger:
                self.logger.debug(f"Could not find RSS link in HTML: {e}")

        # Try common RSS URLs
        common_paths = ['/rss', '/feed', '/newsroom/rss', '/investor-relations/rss']
        for path in common_paths:
            try:
                feed_url = urljoin(base_url, path)
                docs = self._parse_rss_feed(feed_url, from_date, to_date)
                if docs:
                    return docs
            except:
                continue

        return documents

    def _parse_rss_feed(
        self,
        feed_url: str,
        from_date: datetime,
        to_date: datetime
    ) -> List[IRDocument]:
        """Parse RSS/Atom feed for documents"""
        documents = []

        try:
            response = self._make_request(feed_url)
            soup = BeautifulSoup(response.content, 'xml')

            # Try RSS format first
            items = soup.find_all('item')
            if not items:
                # Try Atom format
                items = soup.find_all('entry')

            for item in items:
                try:
                    # Extract title
                    title_tag = item.find('title')
                    title = title_tag.text.strip() if title_tag else ''

                    # Extract link
                    link_tag = item.find('link')
                    if link_tag:
                        link = link_tag.get('href', link_tag.text).strip()
                    else:
                        continue

                    # Extract date (try multiple formats)
                    date_tag = item.find('pubDate') or item.find('published') or item.find('updated')
                    if not date_tag:
                        continue

                    pub_date = self._parse_date(date_tag.text)
                    if not pub_date:
                        continue

                    # Filter by date range
                    if not (from_date <= pub_date <= to_date):
                        continue

                    # Extract description/summary
                    desc_tag = item.find('description') or item.find('summary')
                    summary = desc_tag.text.strip() if desc_tag else None

                    # Determine document type from title/category
                    doc_type = self._classify_document_type(title, summary or '')

                    documents.append(IRDocument(
                        title=title,
                        document_url=urljoin(feed_url, link),
                        published_at=pub_date,
                        document_type=doc_type,
                        summary=summary
                    ))

                except Exception as e:
                    if self.logger:
                        self.logger.debug(f"Failed to parse RSS item: {e}")
                    continue

        except Exception as e:
            if self.logger:
                self.logger.debug(f"Failed to parse RSS feed {feed_url}: {e}")

        return documents

    def _scrape_html_content(
        self,
        url: str,
        from_date: datetime,
        to_date: datetime
    ) -> List[IRDocument]:
        """
        Scrape HTML page for documents using heuristics

        Looks for:
        - Press release sections
        - News items with dates
        - Links with common IR document patterns
        """
        documents = []

        try:
            response = self._make_request(url)
            soup = BeautifulSoup(response.content, 'html.parser')

            # Look for press release/news sections
            # Common class names and patterns
            section_patterns = [
                {'class_': re.compile(r'press|news|release|ir-news|investor-news', re.I)},
                {'id': re.compile(r'press|news|release', re.I)}
            ]

            sections = []
            for pattern in section_patterns:
                sections.extend(soup.find_all(['div', 'section', 'article'], pattern))

            # If no specific sections found, use the whole page
            if not sections:
                sections = [soup]

            # Extract documents from sections
            for section in sections:
                # Find all links
                links = section.find_all('a', href=True)

                for link in links:
                    try:
                        title = link.get_text(strip=True)
                        href = link.get('href')

                        # Skip empty titles or non-document links
                        if not title or len(title) < 10:
                            continue

                        # Skip navigation links
                        if any(nav in href.lower() for nav in ['#', 'javascript:', 'mailto:']):
                            continue

                        # Try to find associated date
                        # Look in nearby elements (parent, siblings)
                        date_element = self._find_nearby_date(link)
                        if not date_element:
                            continue

                        pub_date = self._parse_date(date_element)
                        if not pub_date:
                            continue

                        # Filter by date range
                        if not (from_date <= pub_date <= to_date):
                            continue

                        # Build absolute URL
                        doc_url = urljoin(url, href)

                        # Find summary (nearby text)
                        summary = self._find_nearby_summary(link)

                        # Classify document type
                        doc_type = self._classify_document_type(title, summary or '')

                        documents.append(IRDocument(
                            title=title,
                            document_url=doc_url,
                            published_at=pub_date,
                            document_type=doc_type,
                            summary=summary
                        ))

                    except Exception as e:
                        if self.logger:
                            self.logger.debug(f"Failed to parse link: {e}")
                        continue

        except Exception as e:
            if self.logger:
                self.logger.error(f"HTML scraping failed for {url}: {e}")

        return documents

    def _find_nearby_date(self, element) -> Optional[str]:
        """Find date text near an element"""
        # Check element itself
        text = element.get_text()
        if self._contains_date_pattern(text):
            return text

        # Check parent
        parent = element.find_parent()
        if parent:
            text = parent.get_text()
            if self._contains_date_pattern(text):
                return text

            # Check siblings
            for sibling in parent.find_all(['span', 'time', 'div', 'p']):
                text = sibling.get_text()
                if self._contains_date_pattern(text):
                    return text

        return None

    def _find_nearby_summary(self, element) -> Optional[str]:
        """Find summary/description text near an element"""
        parent = element.find_parent()
        if parent:
            # Look for description/summary elements
            desc = parent.find(['p', 'div'], class_=re.compile(r'description|summary|excerpt', re.I))
            if desc:
                return desc.get_text(strip=True)

        return None

    def _contains_date_pattern(self, text: str) -> bool:
        """Check if text contains a date pattern"""
        # Common date patterns
        patterns = [
            r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}\b',
            r'\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b',
            r'\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b',
        ]

        for pattern in patterns:
            if re.search(pattern, text, re.I):
                return True

        return False

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string to datetime object"""
        # Try common date formats
        formats = [
            '%Y-%m-%d',
            '%m/%d/%Y',
            '%d/%m/%Y',
            '%B %d, %Y',
            '%b %d, %Y',
            '%d %B %Y',
            '%d %b %Y',
            '%Y-%m-%dT%H:%M:%S%z',
            '%Y-%m-%dT%H:%M:%SZ',
            '%a, %d %b %Y %H:%M:%S %Z',
            '%a, %d %b %Y %H:%M:%S %z',
        ]

        date_str = date_str.strip()

        # Extract date from text if needed
        date_match = re.search(
            r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}\b',
            date_str,
            re.I
        )
        if date_match:
            date_str = date_match.group(0)

        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                # If no timezone, assume UTC
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=None)
                return dt
            except ValueError:
                continue

        return None

    def _classify_document_type(self, title: str, content: str) -> str:
        """
        Classify document type based on title and content

        Returns:
            One of: press_release, earnings_presentation, webcast, 8k, other
        """
        combined = f"{title} {content}".lower()

        if any(word in combined for word in ['earnings', 'quarterly results', 'q1', 'q2', 'q3', 'q4', 'full year']):
            if 'presentation' in combined or 'slides' in combined:
                return 'earnings_presentation'
            elif 'webcast' in combined or 'call' in combined:
                return 'webcast'
            else:
                return 'press_release'

        if '8-k' in combined or 'form 8-k' in combined:
            return '8k'

        if 'press release' in combined or 'news release' in combined:
            return 'press_release'

        return 'other'

    def save_documents(
        self,
        ir_page_id: str,
        company_id: str,
        ticker: str,
        documents: List[IRDocument]
    ) -> int:
        """
        Save scraped documents to database

        Args:
            ir_page_id: UUID of ir_pages record
            company_id: UUID of company
            ticker: Company ticker symbol
            documents: List of IRDocument objects

        Returns:
            Number of documents saved

        Raises:
            DatabaseError: If save fails
        """
        if not self.db_connection:
            raise DatabaseError("No database connection provided")

        if not documents:
            if self.logger:
                self.logger.info("No documents to save")
            return 0

        cursor = self.db_connection.cursor()
        saved_count = 0

        for doc in documents:
            try:
                content_hash = doc.get_content_hash()

                # Insert document (skip if duplicate hash exists)
                cursor.execute("""
                    INSERT INTO ir_documents (
                        ir_page_id,
                        company_id,
                        ticker,
                        title,
                        document_url,
                        document_type,
                        published_at,
                        scraped_at,
                        summary,
                        raw_content,
                        content_hash,
                        status,
                        created_at,
                        updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (ir_page_id, content_hash) DO NOTHING
                    RETURNING id
                """, (
                    ir_page_id,
                    company_id,
                    ticker,
                    doc.title,
                    doc.document_url,
                    doc.document_type,
                    doc.published_at,
                    datetime.now(),
                    doc.summary,
                    doc.raw_content,
                    content_hash,
                    'pending',
                    datetime.now(),
                    datetime.now()
                ))

                result = cursor.fetchone()
                if result:
                    saved_count += 1

            except Exception as e:
                if self.logger:
                    self.logger.error(
                        f"Failed to save document: {doc.title}",
                        exception=e
                    )
                continue

        # Commit all changes
        self.db_connection.commit()
        cursor.close()

        if self.logger:
            self.logger.info(f"Saved {saved_count} new documents to database")

        return saved_count

    def link_documents_to_filings(
        self,
        company_id: str,
        filing_id: str,
        filing_date: datetime,
        window_hours: int = 72
    ) -> int:
        """
        Link IR documents to a filing within a time window

        Args:
            company_id: UUID of company
            filing_id: UUID of filing
            filing_date: Date of the filing
            window_hours: Time window in hours (default 72 = ±3 days)

        Returns:
            Number of links created

        Creates links for documents published within ±window_hours of filing
        """
        if not self.db_connection:
            raise DatabaseError("No database connection provided")

        cursor = self.db_connection.cursor()

        # Calculate date range
        from_date = filing_date - timedelta(hours=window_hours)
        to_date = filing_date + timedelta(hours=window_hours)

        # Find documents within window
        cursor.execute("""
            SELECT id, published_at, title
            FROM ir_documents
            WHERE company_id = %s
            AND published_at BETWEEN %s AND %s
            AND status IN ('pending', 'analyzed')
        """, (company_id, from_date, to_date))

        documents = cursor.fetchall()
        links_created = 0

        for doc_id, pub_date, title in documents:
            try:
                # Calculate time delta in hours
                delta = (pub_date - filing_date).total_seconds() / 3600
                time_delta_hours = int(delta)

                # Determine window type
                if delta < -1:
                    window_type = 'pre_filing'
                elif delta > 1:
                    window_type = 'post_filing'
                else:
                    window_type = 'concurrent'

                # Create link
                cursor.execute("""
                    INSERT INTO ir_filing_links (
                        ir_document_id,
                        filing_id,
                        time_delta_hours,
                        window_type,
                        link_type,
                        show_on_filing_page,
                        show_on_ticker_page,
                        created_at,
                        created_by
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (ir_document_id, filing_id) DO NOTHING
                    RETURNING id
                """, (
                    doc_id,
                    filing_id,
                    time_delta_hours,
                    window_type,
                    'auto',
                    True,
                    True,
                    datetime.now(),
                    'system'
                ))

                result = cursor.fetchone()
                if result:
                    links_created += 1
                    if self.logger:
                        self.logger.debug(
                            f"Linked document '{title}' to filing ({window_type}, {time_delta_hours}h)"
                        )

            except Exception as e:
                if self.logger:
                    self.logger.error(f"Failed to create link for document {doc_id}: {e}")
                continue

        self.db_connection.commit()
        cursor.close()

        if self.logger:
            self.logger.info(f"Created {links_created} IR document links for filing")

        return links_created

    def scrape_for_filing(
        self,
        filing_id: str,
        company_id: str,
        ticker: str,
        filing_date: datetime,
        window_hours: int = 72
    ) -> Tuple[int, int]:
        """
        Complete workflow: scrape IR page for a filing and link documents

        Args:
            filing_id: UUID of filing
            company_id: UUID of company
            ticker: Company ticker symbol
            filing_date: Date of the filing
            window_hours: Time window in hours (default 72)

        Returns:
            Tuple of (documents_scraped, links_created)
        """
        if not self.db_connection:
            raise DatabaseError("No database connection provided")

        # Get IR page for company
        cursor = self.db_connection.cursor()
        cursor.execute("""
            SELECT id, ir_url, scraping_enabled, status
            FROM ir_pages
            WHERE company_id = %s
        """, (company_id,))

        result = cursor.fetchone()
        if not result:
            if self.logger:
                self.logger.info(f"No IR page configured for {ticker}")
            return (0, 0)

        ir_page_id, ir_url, scraping_enabled, status = result

        if not scraping_enabled or status != 'active':
            if self.logger:
                self.logger.info(f"IR scraping disabled for {ticker}")
            return (0, 0)

        # Calculate date range
        from_date = filing_date - timedelta(hours=window_hours)
        to_date = filing_date + timedelta(hours=window_hours)

        try:
            # Scrape IR page
            documents = self.scrape_ir_page(ir_url, from_date, to_date)

            # Save documents
            docs_saved = self.save_documents(ir_page_id, company_id, ticker, documents)

            # Link to filing
            links_created = self.link_documents_to_filings(
                company_id,
                filing_id,
                filing_date,
                window_hours
            )

            # Update last_scraped_at
            cursor.execute("""
                UPDATE ir_pages
                SET last_scraped_at = %s,
                    consecutive_failures = 0,
                    error_message = NULL,
                    updated_at = %s
                WHERE id = %s
            """, (datetime.now(), datetime.now(), ir_page_id))

            self.db_connection.commit()
            cursor.close()

            return (docs_saved, links_created)

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to scrape IR page for {ticker}: {e}", exception=e)

            # Update error status
            cursor.execute("""
                UPDATE ir_pages
                SET consecutive_failures = consecutive_failures + 1,
                    error_message = %s,
                    status = CASE
                        WHEN consecutive_failures >= 5 THEN 'failed'
                        ELSE status
                    END,
                    updated_at = %s
                WHERE id = %s
            """, (str(e)[:500], datetime.now(), ir_page_id))

            self.db_connection.commit()
            cursor.close()

            raise


class IRScraperError(Exception):
    """Raised when IR scraping fails"""
    pass


class DatabaseError(Exception):
    """Raised when database operations fail"""
    pass
