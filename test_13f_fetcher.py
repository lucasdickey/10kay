"""
Test for the Edgar13FFetcher
"""
import unittest
from unittest.mock import MagicMock
from pipeline.fetchers.edgar_13f import Edgar13FFetcher
from pipeline.fetchers.base import FilingMetadata

class TestEdgar13FFetcher(unittest.TestCase):
    def test_fetch_13f_filings(self):
        # Dummy config
        config = MagicMock()
        config.aws.region = "us-east-1"
        config.aws.access_key_id = "test"
        config.aws.secret_access_key = "test"
        config.sec.base_url = "https://www.sec.gov"
        config.sec.user_agent = "test@example.com"
        config.sec.rate_limit_requests = 10

        # CIK for Berkshire Hathaway
        manager_cik = "0001067983"

        # Initialize fetcher
        fetcher = Edgar13FFetcher(config)

        # Fetch filings
        filings = fetcher.fetch_latest_filings(manager_cik, limit=1)

        # Assertions
        self.assertIsInstance(filings, list)
        self.assertGreater(len(filings), 0)
        self.assertIsInstance(filings[0], FilingMetadata)

        # Download filing
        content = fetcher.download_filing(filings[0])
        self.assertIsInstance(content, bytes)
        self.assertGreater(len(content), 0)

if __name__ == '__main__':
    unittest.main()
