"""
SEC EDGAR fetcher implementation

Fetches 10-K and 10-Q filings from SEC EDGAR API and stores them in S3.
"""
import re
import time
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path
import requests
from bs4 import BeautifulSoup
import boto3
from botocore.exceptions import ClientError

from .base import (
    BaseFetcher,
    FilingMetadata,
    FilingType,
    FetchError,
    DownloadError,
    UploadError,
    DatabaseError
)


class EdgarFetcher(BaseFetcher):
    """
    Concrete implementation of SEC EDGAR fetcher

    Uses SEC EDGAR's company search and filing endpoints to fetch
    10-K and 10-Q filings, then stores them in S3.

    Rate limiting: SEC requires max 10 requests/second
    User agent: Must include contact information
    """

    def __init__(self, config, db_connection=None, logger=None):
        """Initialize EDGAR fetcher with AWS S3 client"""
        super().__init__(config, db_connection, logger)

        # Initialize S3 client
        self.s3_client = boto3.client(
            's3',
            region_name=config.aws.region,
            aws_access_key_id=config.aws.access_key_id,
            aws_secret_access_key=config.aws.secret_access_key
        )

        # SEC EDGAR endpoints
        self.base_url = config.sec.base_url
        self.user_agent = config.sec.user_agent

        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 1.0 / config.sec.rate_limit_requests

        if self.logger:
            self.logger.info(
                f"Initialized EdgarFetcher",
                extra={'user_agent': self.user_agent}
            )

    def _rate_limit(self):
        """Enforce SEC rate limit (10 requests/second)"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            sleep_time = self.min_request_interval - elapsed
            time.sleep(sleep_time)
        self.last_request_time = time.time()

    def _make_request(self, url: str) -> requests.Response:
        """
        Make HTTP request to SEC with proper headers and rate limiting

        Args:
            url: URL to request

        Returns:
            Response object

        Raises:
            FetchError: If request fails
        """
        self._rate_limit()

        headers = {
            'User-Agent': self.user_agent,
            'Accept-Encoding': 'gzip, deflate',
            'Host': 'www.sec.gov'
        }

        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            raise FetchError(f"Failed to fetch {url}: {e}")

    def _get_cik_from_ticker(self, ticker: str) -> str:
        """
        Convert ticker symbol to CIK (Central Index Key)

        Args:
            ticker: Company ticker symbol

        Returns:
            10-digit CIK with leading zeros

        Raises:
            FetchError: If ticker not found
        """
        # SEC maintains a company tickers JSON file
        url = f"{self.base_url}/files/company_tickers.json"

        try:
            response = self._make_request(url)
            data = response.json()

            # Find ticker in the data
            for entry in data.values():
                if entry['ticker'].upper() == ticker.upper():
                    # CIK needs to be 10 digits with leading zeros
                    cik = str(entry['cik_str']).zfill(10)
                    if self.logger:
                        self.logger.debug(f"Found CIK {cik} for ticker {ticker}")
                    return cik

            raise FetchError(f"Ticker {ticker} not found in SEC database")

        except Exception as e:
            raise FetchError(f"Failed to lookup CIK for {ticker}: {e}")

    def fetch_latest_filings(
        self,
        ticker: str,
        filing_type: Optional[FilingType] = None,
        limit: int = 10
    ) -> List[FilingMetadata]:
        """
        Fetch latest filings for a company from SEC EDGAR

        Args:
            ticker: Company ticker symbol
            filing_type: Optional filter by filing type
            limit: Maximum number of filings to fetch

        Returns:
            List of FilingMetadata objects

        Raises:
            FetchError: If fetching fails
        """
        if self.logger:
            self.logger.info(f"Fetching filings for {ticker}")

        try:
            # Get CIK for ticker
            cik = self._get_cik_from_ticker(ticker)

            # Fetch company filings page
            # The submissions endpoint provides comprehensive filing data
            url = f"{self.base_url}/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=&dateb=&owner=exclude&count={limit * 2}"

            response = self._make_request(url)
            soup = BeautifulSoup(response.content, 'html.parser')

            # Parse filing table
            filings = []
            table = soup.find('table', {'class': 'tableFile2'})

            if not table:
                if self.logger:
                    self.logger.warning(f"No filings table found for {ticker}")
                return []

            rows = table.find_all('tr')[1:]  # Skip header

            for row in rows:
                cols = row.find_all('td')
                if len(cols) < 5:
                    continue

                # Extract filing type
                form_type = cols[0].text.strip()

                # Filter by filing type if specified
                if filing_type:
                    if form_type != filing_type.value:
                        continue
                elif form_type not in ['10-K', '10-Q']:
                    # Only fetch 10-K and 10-Q if no filter specified
                    continue

                # Extract metadata
                filing_date_str = cols[3].text.strip()
                filing_date = datetime.strptime(filing_date_str, '%Y-%m-%d')

                # Get accession number from description column
                # Format: "Annual report [...]Acc-no: 0000320193-25-000079 (34 Act)"
                description = cols[2].text.strip()
                acc_match = re.search(r'Acc-no:\s*([\d-]+)', description)
                if not acc_match:
                    continue
                accession_number = acc_match.group(1)

                # Get document link
                doc_link = cols[1].find('a')
                if not doc_link:
                    continue
                doc_href = doc_link['href']

                # Build document URL
                document_url = f"{self.base_url}{doc_href}"

                # Determine fiscal period from filing
                fiscal_period = self._determine_fiscal_period(form_type, filing_date)

                # Create metadata object
                metadata = FilingMetadata(
                    ticker=ticker.upper(),
                    filing_type=FilingType.FORM_10K if form_type == '10-K' else FilingType.FORM_10Q,
                    filing_date=filing_date,
                    fiscal_year=filing_date.year,
                    fiscal_period=fiscal_period,
                    accession_number=accession_number,
                    document_url=document_url,
                    cik=cik,
                    form_type=form_type
                )

                filings.append(metadata)

                if len(filings) >= limit:
                    break

            if self.logger:
                self.logger.info(f"Found {len(filings)} filings for {ticker}")

            return filings

        except Exception as e:
            raise FetchError(f"Failed to fetch filings for {ticker}: {e}")

    def _determine_fiscal_period(self, form_type: str, filing_date: datetime) -> str:
        """
        Determine fiscal period from form type and date

        Args:
            form_type: Form type (10-K or 10-Q)
            filing_date: Filing date

        Returns:
            Fiscal period string (FY, Q1, Q2, Q3, Q4)
        """
        if form_type == '10-K':
            return 'FY'

        # For 10-Q, determine quarter from month
        month = filing_date.month

        # Rough approximation - most companies file quarterly
        # Q1: Jan-Mar (filed Apr-May)
        # Q2: Apr-Jun (filed Jul-Aug)
        # Q3: Jul-Sep (filed Oct-Nov)
        # Q4: Oct-Dec (filed Jan-Feb following year)

        if month in [4, 5]:
            return 'Q1'
        elif month in [7, 8]:
            return 'Q2'
        elif month in [10, 11]:
            return 'Q3'
        else:
            return 'Q4'

    def download_filing(self, filing: FilingMetadata) -> bytes:
        """
        Download the actual filing document

        Prioritizes plain text (.txt) complete submission file over HTML to avoid
        iXBRL viewer files that require JavaScript and contain no actual content.

        Args:
            filing: FilingMetadata with document_url

        Returns:
            Raw filing content as bytes

        Raises:
            DownloadError: If download fails
        """
        if self.logger:
            self.logger.debug(f"Downloading filing {filing.accession_number}")

        try:
            # SEC filing URL pattern:
            # https://www.sec.gov/Archives/edgar/data/{CIK}/{accession_no_dashes}/{accession_no}.txt
            # Example: https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/0000320193-25-000079.txt

            # Use CIK from FilingMetadata (already available)
            cik = filing.cik
            if not cik:
                raise DownloadError("No CIK available in filing metadata")

            accession_no_dashes = filing.accession_number.replace('-', '')

            # Try to download complete submission text file first
            txt_url = f"{self.base_url}/Archives/edgar/data/{cik}/{accession_no_dashes}/{filing.accession_number}.txt"

            if self.logger:
                self.logger.debug(f"Attempting to download plain text version: {txt_url}")

            try:
                response = self._make_request(txt_url)

                # Verify we got actual content (not an error page)
                if response.status_code == 200 and len(response.content) > 10000:
                    if self.logger:
                        self.logger.info(
                            f"Downloaded plain text filing: {len(response.content)} bytes",
                            extra={'url': txt_url}
                        )

                    # Store URL for reference
                    filing.html_url = txt_url
                    return response.content
                else:
                    if self.logger:
                        self.logger.debug(f"Plain text file too small or not found, trying HTML")

            except Exception as txt_error:
                if self.logger:
                    self.logger.debug(f"Plain text download failed: {txt_error}, trying HTML")

            # Fallback: Navigate to filing page and find HTML document
            response = self._make_request(filing.document_url)
            soup = BeautifulSoup(response.content, 'html.parser')

            # Find the link to the actual filing document (avoid iXBRL viewer)
            doc_table = soup.find('table', {'class': 'tableFile'})
            if not doc_table:
                raise DownloadError("Could not find document table")

            # Look for the main filing document (Type column = filing type)
            # Prefer non-iXBRL files
            doc_url = None
            for row in doc_table.find_all('tr')[1:]:
                cols = row.find_all('td')
                if len(cols) < 4:
                    continue

                doc_type = cols[3].text.strip()
                if doc_type in ['10-K', '10-Q']:
                    doc_link = cols[2].find('a')
                    if doc_link:
                        doc_href = doc_link['href']
                        # Skip iXBRL files (they're just viewers with JavaScript)
                        if 'ixv' not in doc_href.lower() and 'viewer' not in doc_href.lower():
                            doc_url = f"{self.base_url}{doc_href}"
                            break

            if not doc_url:
                raise DownloadError("Could not find suitable filing document")

            # Download the actual document
            response = self._make_request(doc_url)

            # Store HTML URL for later reference
            filing.html_url = doc_url

            if self.logger:
                self.logger.info(
                    f"Downloaded HTML filing: {len(response.content)} bytes",
                    extra={'url': doc_url}
                )

            return response.content

        except Exception as e:
            raise DownloadError(f"Failed to download filing: {e}")

    def upload_to_s3(self, filing: FilingMetadata, content: bytes) -> str:
        """
        Upload filing to S3 bucket

        Args:
            filing: FilingMetadata
            content: Raw filing content

        Returns:
            S3 URL where filing was stored

        Raises:
            UploadError: If upload fails
        """
        # Determine file extension based on what was downloaded
        # filing.html_url is set in download_filing() to the actual URL used
        file_ext = '.txt' if filing.html_url and filing.html_url.endswith('.txt') else '.html'
        content_type = 'text/plain' if file_ext == '.txt' else 'text/html'

        # Build S3 key: {ticker}/{fiscal_year}/{filing_type}/{accession_number}.{ext}
        s3_key = (
            f"{filing.ticker}/"
            f"{filing.fiscal_year}/"
            f"{filing.filing_type.value}/"
            f"{filing.accession_number}{file_ext}"
        )

        bucket = self.config.aws.s3_filings_bucket

        try:
            # Upload to S3
            self.s3_client.put_object(
                Bucket=bucket,
                Key=s3_key,
                Body=content,
                ContentType=content_type,
                Metadata={
                    'ticker': filing.ticker,
                    'filing_type': filing.filing_type.value,
                    'filing_date': filing.filing_date.isoformat(),
                    'accession_number': filing.accession_number
                }
            )

            s3_url = f"s3://{bucket}/{s3_key}"

            if self.logger:
                self.logger.info(
                    f"Uploaded filing to S3",
                    extra={'s3_url': s3_url, 'size_bytes': len(content)}
                )

            return s3_url

        except ClientError as e:
            raise UploadError(f"Failed to upload to S3: {e}")

    def save_to_database(
        self,
        filing: FilingMetadata,
        s3_url: str,
        html_s3_url: Optional[str] = None
    ) -> str:
        """
        Save filing metadata to database

        Args:
            filing: FilingMetadata
            s3_url: S3 URL where filing is stored
            html_s3_url: Optional S3 URL for HTML version

        Returns:
            Database ID (UUID) of created filing record

        Raises:
            DatabaseError: If save fails
        """
        if not self.db_connection:
            raise DatabaseError("No database connection available")

        try:
            cursor = self.db_connection.cursor()

            # Get company_id from ticker
            cursor.execute(
                "SELECT id FROM companies WHERE ticker = %s",
                (filing.ticker,)
            )
            company_row = cursor.fetchone()
            if not company_row:
                raise DatabaseError(f"Company {filing.ticker} not found in database")
            company_id = company_row[0]

            # Convert fiscal_period to fiscal_quarter
            fiscal_quarter = None
            if filing.fiscal_period and filing.fiscal_period.startswith('Q'):
                fiscal_quarter = int(filing.fiscal_period[1])  # Extract number from 'Q1', 'Q2', etc.

            # Insert filing record (matching actual schema)
            cursor.execute("""
                INSERT INTO filings (
                    company_id,
                    filing_type,
                    filing_date,
                    fiscal_year,
                    fiscal_quarter,
                    accession_number,
                    edgar_url,
                    raw_document_url,
                    status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                company_id,
                filing.filing_type.value,
                filing.filing_date,
                filing.fiscal_year,
                fiscal_quarter,
                filing.accession_number,
                filing.document_url,  # EDGAR URL
                s3_url,  # S3 URL for raw document
                'pending'  # Initial status - ready for processing
            ))

            filing_id = cursor.fetchone()[0]
            self.db_connection.commit()
            cursor.close()

            if self.logger:
                self.logger.info(
                    f"Saved filing to database",
                    extra={'filing_id': filing_id}
                )

            return filing_id

        except Exception as e:
            self.db_connection.rollback()
            raise DatabaseError(f"Failed to save filing to database: {e}")
