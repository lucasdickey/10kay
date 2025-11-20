"""
SEC EDGAR 13F fetcher implementation

Fetches 13F filings from SEC EDGAR API and stores them in S3.
"""
import re
import time
from datetime import datetime
from typing import List, Optional
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

class Edgar13FFetcher(BaseFetcher):
    """
    Concrete implementation of SEC EDGAR fetcher for 13F filings.
    """

    def __init__(self, config, db_connection=None, logger=None):
        """Initialize EDGAR 13F fetcher with AWS S3 client"""
        super().__init__(config, db_connection, logger)
        self.s3_client = boto3.client(
            's3',
            region_name=config.aws.region,
            aws_access_key_id=config.aws.access_key_id,
            aws_secret_access_key=config.aws.secret_access_key
        )
        self.base_url = config.sec.base_url
        self.user_agent = config.sec.user_agent
        self.last_request_time = 0
        self.min_request_interval = 1.0 / config.sec.rate_limit_requests
        if self.logger:
            self.logger.info(
                f"Initialized Edgar13FFetcher",
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
        """Make HTTP request to SEC with proper headers and rate limiting"""
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

    def fetch_latest_filings(self, manager_cik: str, limit: int = 10) -> List[FilingMetadata]:
        """Fetch latest 13F filings for an institutional manager."""
        if self.logger:
            self.logger.info(f"Fetching 13F filings for manager CIK {manager_cik}")

        try:
            url = f"{self.base_url}/cgi-bin/browse-edgar?action=getcompany&CIK={manager_cik}&type=13F-HR&dateb=&owner=exclude&count={limit}"
            response = self._make_request(url)
            soup = BeautifulSoup(response.content, 'html.parser')

            filings = []
            table = soup.find('table', {'class': 'tableFile2'})
            if not table:
                if self.logger:
                    self.logger.warning(f"No filings table found for manager CIK {manager_cik}")
                return []

            rows = table.find_all('tr')[1:]
            for row in rows:
                cols = row.find_all('td')
                if len(cols) < 5:
                    continue

                form_type = cols[0].text.strip()
                if form_type != '13F-HR':
                    continue

                filing_date_str = cols[3].text.strip()
                filing_date = datetime.strptime(filing_date_str, '%Y-%m-%d')
                description = cols[2].text.strip()
                acc_match = re.search(r'Acc-no:\s*([\d-]+)', description)
                if not acc_match:
                    continue
                accession_number = acc_match.group(1)

                doc_link = cols[1].find('a')
                if not doc_link:
                    continue
                doc_href = doc_link['href']
                document_url = f"{self.base_url}{doc_href}"

                metadata = FilingMetadata(
                    ticker=None,
                    filing_type=FilingType.FORM_13F,
                    filing_date=filing_date,
                    fiscal_year=filing_date.year,
                    fiscal_period=f"Q{((filing_date.month - 1) // 3) + 1}",
                    accession_number=accession_number,
                    document_url=document_url,
                    manager_cik=manager_cik,
                    form_type=form_type
                )
                filings.append(metadata)
                if len(filings) >= limit:
                    break

            if self.logger:
                self.logger.info(f"Found {len(filings)} 13F filings for manager CIK {manager_cik}")
            return filings

        except Exception as e:
            raise FetchError(f"Failed to fetch 13F filings for manager CIK {manager_cik}: {e}")

    def download_filing(self, filing: FilingMetadata) -> bytes:
        """Download the actual 13F filing document (XML)."""
        if self.logger:
            self.logger.debug(f"Downloading 13F filing {filing.accession_number}")

        try:
            response = self._make_request(filing.document_url)
            soup = BeautifulSoup(response.content, 'html.parser')
            doc_table = soup.find('table', {'class': 'tableFile'})
            if not doc_table:
                raise DownloadError("Could not find document table")

            xml_url = None
            for row in doc_table.find_all('tr')[1:]:
                cols = row.find_all('td')
                if len(cols) < 4:
                    continue
                doc_link = cols[2].find('a')
                if doc_link and 'xml' in doc_link['href']:
                    xml_url = f"{self.base_url}{doc_link['href']}"
                    break

            if not xml_url:
                raise DownloadError("Could not find XML document link")

            response = self._make_request(xml_url)
            filing.html_url = xml_url
            if self.logger:
                self.logger.info(f"Downloaded 13F XML filing: {len(response.content)} bytes", extra={'url': xml_url})
            return response.content

        except Exception as e:
            raise DownloadError(f"Failed to download 13F filing: {e}")

    def upload_to_s3(self, filing: FilingMetadata, content: bytes) -> str:
        """Upload 13F filing to S3 bucket."""
        s3_key = (
            f"13F/{filing.manager_cik}/"
            f"{filing.fiscal_year}/"
            f"{filing.accession_number}.xml"
        )
        bucket = self.config.aws.s3_filings_bucket

        try:
            self.s3_client.put_object(
                Bucket=bucket,
                Key=s3_key,
                Body=content,
                ContentType='application/xml',
                Metadata={
                    'manager_cik': filing.manager_cik,
                    'filing_type': filing.filing_type.value,
                    'filing_date': filing.filing_date.isoformat(),
                    'accession_number': filing.accession_number
                }
            )
            s3_url = f"s3://{bucket}/{s3_key}"
            if self.logger:
                self.logger.info(f"Uploaded 13F filing to S3", extra={'s3_url': s3_url, 'size_bytes': len(content)})
            return s3_url
        except ClientError as e:
            raise UploadError(f"Failed to upload 13F to S3: {e}")

    def save_to_database(self, filing: FilingMetadata, s3_url: str) -> str:
        """Save 13F filing metadata to database."""
        if not self.db_connection:
            raise DatabaseError("No database connection available")

        try:
            cursor = self.db_connection.cursor()
            cursor.execute(
                "SELECT id FROM institutional_managers WHERE cik = %s",
                (filing.manager_cik,)
            )
            manager_row = cursor.fetchone()
            if not manager_row:
                raise DatabaseError(f"Manager with CIK {filing.manager_cik} not found in database")
            manager_id = manager_row[0]

            cursor.execute("""
                INSERT INTO filings (
                    manager_id,
                    filing_type,
                    filing_date,
                    accession_number,
                    edgar_url,
                    raw_document_url,
                    status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                manager_id,
                filing.filing_type.value,
                filing.filing_date,
                filing.accession_number,
                filing.document_url,
                s3_url,
                'pending'
            ))
            filing_id = cursor.fetchone()[0]
            self.db_connection.commit()
            cursor.close()

            if self.logger:
                self.logger.info(f"Saved 13F filing to database", extra={'filing_id': filing_id})
            return filing_id
        except Exception as e:
            self.db_connection.rollback()
            raise DatabaseError(f"Failed to save 13F filing to database: {e}")
