"""
Fetcher for company press releases related to earnings announcements.
"""
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from urllib.parse import urljoin
from .base import BaseFetcher, FetchError

class PressReleaseFetcher(BaseFetcher):
    """
    Fetches press releases from company investor relations sites.
    """

    def get_investor_relations_url(self, ticker: str) -> str:
        """
        Retrieves the investor relations URL for a given company.
        """
        with self.db_connection.cursor() as cursor:
            cursor.execute("SELECT investor_relations_url FROM companies WHERE ticker = %s", (ticker,))
            result = cursor.fetchone()
            if result and result[0]:
                return result[0]
            else:
                raise FetchError(f"No investor relations URL for {ticker}")

    def find_press_releases(self, filing):
        """
        Finds press releases related to a specific filing.
        """
        try:
            ir_url = self.get_investor_relations_url(filing.ticker)
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            response = requests.get(ir_url, headers=headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            press_releases = []
            filing_date = filing.filing_date.date()
            date_range = [filing_date + timedelta(days=d) for d in range(-2, 3)]

            for link in soup.find_all('a', href=True):
                link_text = link.get_text(strip=True).lower()
                link_href = link['href']

                # Keywords to identify earnings press releases
                if any(keyword in link_text for keyword in ['earnings', 'quarter', 'results', 'financial']):
                    # Check if the link text or URL contains a date within our range
                    if any(d.strftime("%Y-%m-%d") in link_text or d.strftime("%Y-%m-%d") in link_href for d in date_range) or \
                       any(d.strftime("%b %d") in link_text or d.strftime("%b %d") in link_href for d in date_range):

                        full_url = urljoin(ir_url, link_href)
                        press_releases.append({
                            "url": full_url,
                            "title": link.get_text(strip=True),
                            "published_at": filing.filing_date,
                        })

            return press_releases

        except (requests.RequestException, FetchError) as e:
            if self.logger:
                self.logger.error(f"Could not fetch press releases for {filing.ticker}: {e}")
            return []

    def process_filing(self, filing):
        """
        Processes a single filing to find and store related press releases.
        """
        press_releases = self.find_press_releases(filing)

        if not press_releases:
            return

        with self.db_connection.cursor() as cursor:
            for pr in press_releases:
                if self.logger:
                    self.logger.info(f"  Storing press release: {pr['title']}")
                cursor.execute(
                    """
                    INSERT INTO press_releases (filing_id, url, title, published_at)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (url) DO NOTHING;
                    """,
                    (filing.id, pr['url'], pr['title'], pr['published_at'])
                )
        self.db_connection.commit()
