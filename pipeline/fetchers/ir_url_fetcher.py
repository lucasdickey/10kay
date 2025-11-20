"""
Fetcher for company investor relations URLs.
"""
from .base import BaseFetcher, FetchError
from googlesearch import search

class IrUrlFetcher(BaseFetcher):
    """
    Fetches investor relations URLs from search results.
    """
    def find_ir_url(self, company_name):
        """
        Uses a search engine to find the investor relations page for a company.
        """
        query = f"{company_name} investor relations"
        try:
            # Using the 'googlesearch-python' library
            search_results = search(query, num_results=5)
            for url in search_results:
                if "investor" in url or "relations" in url:
                    return url
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error searching for IR URL for {company_name}: {e}")
        return None

    def process_company(self, company_id, company_name):
        """
        Processes a single company to find and store its investor relations URL.
        """
        ir_url = self.find_ir_url(company_name)

        if ir_url:
            if self.logger:
                self.logger.info(f"  Found IR URL for {company_name}: {ir_url}")
            with self.db_connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE companies SET investor_relations_url = %s WHERE id = %s;",
                    (ir_url, company_id)
                )
            self.db_connection.commit()
