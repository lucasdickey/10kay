#!/usr/bin/env python3
"""
Backfills the investor_relations_url for all companies in the database.
"""

import os
import sys
import psycopg2
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pipeline.fetchers.ir_url_fetcher import IrUrlFetcher
from pipeline.utils import get_config

def main():
    """
    Main function to backfill investor relations URLs.
    """
    config = get_config()
    database_url = config.database.url
    if not database_url:
        print("DATABASE_URL not set.")
        return

    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, name FROM companies WHERE investor_relations_url IS NULL;")
            companies = cursor.fetchall()

            fetcher = IrUrlFetcher(config, conn)

            for company_id, company_name in companies:
                print(f"Finding URL for {company_name}...")
                fetcher.process_company(company_id, company_name)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
