"""
Claude AI analyzer implementation for 13F filings

Parses 13F XML filings, stores holdings, and generates AI summaries.
"""
import xml.etree.ElementTree as ET
import boto3
from botocore.exceptions import ClientError
from .base import (
    BaseAnalyzer,
    AnalysisError,
    FetchError,
    DatabaseError
)

class Claude13FAnalyzer(BaseAnalyzer):
    """
    Concrete implementation of Claude AI analyzer for 13F filings.
    """

    def __init__(self, config, db_connection=None, logger=None):
        """Initialize Claude 13F analyzer."""
        super().__init__(config, db_connection, logger)
        self.s3_client = boto3.client(
            's3',
            region_name=config.aws.region,
            aws_access_key_id=config.aws.access_key_id,
            aws_secret_access_key=config.aws.secret_access_key
        )
        if self.logger:
            self.logger.info("Initialized Claude13FAnalyzer")

    def fetch_filing_content(self, filing_id: str) -> str:
        """Fetch 13F filing content from S3."""
        if not self.db_connection:
            raise FetchError("No database connection available")
        try:
            cursor = self.db_connection.cursor()
            cursor.execute(
                "SELECT raw_document_url FROM filings WHERE id = %s",
                (filing_id,)
            )
            row = cursor.fetchone()
            cursor.close()
            if not row:
                raise FetchError(f"Filing {filing_id} not found")
            s3_url = row[0]
            if not s3_url.startswith('s3://'):
                raise FetchError(f"Invalid S3 URL: {s3_url}")
            parts = s3_url[5:].split('/', 1)
            bucket, key = parts[0], parts[1]
            response = self.s3_client.get_object(Bucket=bucket, Key=key)
            content = response['Body'].read().decode('utf-8')
            if self.logger:
                self.logger.debug(f"Fetched {len(content)} chars from S3 for filing {filing_id}")
            return content
        except ClientError as e:
            raise FetchError(f"Failed to fetch from S3: {e}")
        except Exception as e:
            raise FetchError(f"Failed to fetch filing content: {e}")

    def parse_13f_xml(self, xml_content: str) -> list:
        """Parse the XML of a 13F filing to extract holdings."""
        holdings = []
        try:
            root = ET.fromstring(xml_content)
            ns = {'n1': 'http://www.sec.gov/edgar/thirteenffiler'}
            for info_table in root.findall('n1:infoTable', ns):
                holding = {}
                for child in info_table:
                    tag = child.tag.split('}')[-1]
                    if tag == 'shrsOrPrnAmt':
                        holding['shares'] = int(child.find('n1:sshPrnamt', ns).text)
                    else:
                        holding[tag] = child.text
                holdings.append(holding)
            if self.logger:
                self.logger.info(f"Parsed {len(holdings)} holdings from 13F XML")
            return holdings
        except ET.ParseError as e:
            raise AnalysisError(f"Failed to parse 13F XML: {e}")

    def analyze_filing(self, filing_id: str):
        """Analyze a 13F filing."""
        if self.logger:
            self.logger.info(f"Analyzing 13F filing {filing_id}")
        try:
            xml_content = self.fetch_filing_content(filing_id)
            holdings = self.parse_13f_xml(xml_content)
            self.save_holdings_to_database(filing_id, holdings)
            # Placeholder for future AI analysis
            # self.generate_ai_summary(filing_id)
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to analyze 13F filing {filing_id}", exception=e)
            raise AnalysisError(f"Failed to analyze 13F filing: {e}")

    def save_holdings_to_database(self, filing_id: str, holdings: list):
        """Save parsed holdings to the database."""
        if not self.db_connection:
            raise DatabaseError("No database connection available")

        try:
            cursor = self.db_connection.cursor()
            cursor.execute("SELECT manager_id FROM filings WHERE id = %s", (filing_id,))
            manager_id = cursor.fetchone()[0]

            for holding in holdings:
                cursor.execute("SELECT id FROM companies WHERE cusip = %s", (holding.get('cusip'),))
                company_row = cursor.fetchone()
                company_id = company_row[0] if company_row else None
                if not company_id:
                    if self.logger:
                        self.logger.warning(f"Company with CUSIP {holding.get('cusip')} not found, skipping holding.")
                    continue

                cursor.execute("""
                    INSERT INTO institutional_holdings (filing_id, company_id, manager_id, cusip, shares, value_usd)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    filing_id,
                    company_id,
                    manager_id,
                    holding.get('cusip'),
                    holding.get('shares'),
                    holding.get('value')
                ))

            self.db_connection.commit()
            cursor.close()
            if self.logger:
                self.logger.info(f"Saved {len(holdings)} holdings to database for filing {filing_id}")
        except Exception as e:
            self.db_connection.rollback()
            raise DatabaseError(f"Failed to save holdings to database: {e}")
