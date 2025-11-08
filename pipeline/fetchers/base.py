"""
Base fetcher class for SEC EDGAR filings

Provides abstract interface for fetching and storing SEC filings.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List
from enum import Enum


class FilingType(str, Enum):
    """SEC filing types we track"""
    FORM_10K = '10-K'
    FORM_10Q = '10-Q'


@dataclass
class FilingMetadata:
    """
    Metadata about a SEC filing

    This matches the structure of the filings table in the database.
    """
    ticker: str
    filing_type: FilingType
    filing_date: datetime
    fiscal_year: int
    fiscal_period: str  # 'FY', 'Q1', 'Q2', 'Q3', 'Q4'
    accession_number: str
    document_url: str
    html_url: Optional[str] = None

    # Additional metadata
    company_name: Optional[str] = None
    cik: Optional[str] = None
    form_type: Optional[str] = None
    file_size: Optional[int] = None


class BaseFetcher(ABC):
    """
    Abstract base class for SEC filing fetchers

    Implementations should:
    1. Fetch latest filings from SEC EDGAR
    2. Parse filing metadata
    3. Download filing documents
    4. Upload to S3
    5. Record in database

    Example:
        fetcher = EdgarFetcher(config)
        filings = fetcher.fetch_latest_filings(ticker='AAPL', limit=5)

        for filing in filings:
            content = fetcher.download_filing(filing)
            s3_url = fetcher.upload_to_s3(filing, content)
            fetcher.save_to_database(filing, s3_url)
    """

    def __init__(self, config, db_connection=None, logger=None):
        """
        Initialize fetcher

        Args:
            config: PipelineConfig instance
            db_connection: Database connection (psycopg2)
            logger: PipelineLogger instance
        """
        self.config = config
        self.db_connection = db_connection
        self.logger = logger

    @abstractmethod
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
            filing_type: Optional filter by filing type (10-K, 10-Q)
            limit: Maximum number of filings to fetch

        Returns:
            List of FilingMetadata objects

        Raises:
            FetchError: If fetching fails
        """
        pass

    @abstractmethod
    def download_filing(self, filing: FilingMetadata) -> bytes:
        """
        Download the actual filing document

        Args:
            filing: FilingMetadata with document_url

        Returns:
            Raw filing content as bytes

        Raises:
            DownloadError: If download fails
        """
        pass

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass

    def check_if_exists(self, accession_number: str) -> bool:
        """
        Check if filing already exists in database

        Args:
            accession_number: SEC accession number

        Returns:
            True if filing exists, False otherwise
        """
        if not self.db_connection:
            return False

        cursor = self.db_connection.cursor()
        cursor.execute(
            "SELECT 1 FROM filings WHERE accession_number = %s",
            (accession_number,)
        )
        exists = cursor.fetchone() is not None
        cursor.close()

        return exists

    def process_company(
        self,
        ticker: str,
        filing_type: Optional[FilingType] = None,
        limit: int = 1,
        skip_existing: bool = True
    ) -> int:
        """
        Complete workflow: fetch, download, upload, and save filings for a company

        Args:
            ticker: Company ticker symbol
            filing_type: Optional filter by filing type
            limit: Maximum number of filings to process
            skip_existing: Skip filings that already exist in database

        Returns:
            Number of filings processed

        This is a convenience method that orchestrates the full pipeline.
        """
        if self.logger:
            self.logger.info(f"Processing filings for {ticker}")

        # Fetch latest filings
        filings = self.fetch_latest_filings(ticker, filing_type, limit)

        if self.logger:
            self.logger.info(f"Found {len(filings)} filings for {ticker}")

        processed = 0

        for filing in filings:
            # Skip if already exists
            if skip_existing and self.check_if_exists(filing.accession_number):
                if self.logger:
                    self.logger.debug(
                        f"Skipping existing filing {filing.accession_number}"
                    )
                continue

            try:
                # Download filing
                content = self.download_filing(filing)

                # Upload to S3
                s3_url = self.upload_to_s3(filing, content)

                # Save to database
                filing_id = self.save_to_database(filing, s3_url)

                if self.logger:
                    self.logger.info(
                        f"Successfully processed filing {filing.accession_number}",
                        extra={'filing_id': filing_id}
                    )

                processed += 1

            except Exception as e:
                if self.logger:
                    self.logger.error(
                        f"Failed to process filing {filing.accession_number}",
                        exception=e
                    )
                # Continue with next filing
                continue

        return processed


class FetchError(Exception):
    """Raised when fetching filings fails"""
    pass


class DownloadError(Exception):
    """Raised when downloading filing content fails"""
    pass


class UploadError(Exception):
    """Raised when uploading to S3 fails"""
    pass


class DatabaseError(Exception):
    """Raised when database operations fail"""
    pass
