#!/usr/bin/env python3
"""Debug script to check upcoming filings calculation"""

import os
from datetime import datetime
from pipeline.utils.db import get_db_connection

def main():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get the query that the API uses
    query = """
        SELECT DISTINCT ON (f.company_id)
            f.company_id,
            co.ticker,
            co.name,
            f.filing_type,
            f.filing_date,
            f.fiscal_year,
            f.fiscal_quarter,
            f.period_end_date
        FROM filings f
        JOIN companies co ON f.company_id = co.id
        WHERE co.enabled = true
            AND f.fiscal_year IS NOT NULL
            AND f.period_end_date IS NOT NULL
        ORDER BY f.company_id, f.filing_date DESC
    """

    cursor.execute(query)
    results = cursor.fetchall()

    print(f"Found {len(results)} companies with fiscal data")
    print("\nMost recent filing per company:")
    print("-" * 100)

    for row in results[:10]:
        company_id, ticker, name, filing_type, filing_date, fiscal_year, fiscal_quarter, period_end_date = row
        print(f"{ticker:6s} | {filing_type:5s} | Filed: {filing_date} | Period End: {period_end_date} | FY: {fiscal_year} Q: {fiscal_quarter}")

    # Now let's manually calculate what the next filing should be
    print("\n" + "=" * 100)
    print("Calculating next expected filings...")
    print("=" * 100)

    now = datetime.now()
    for row in results[:5]:
        company_id, ticker, name, filing_type, filing_date, fiscal_year, fiscal_quarter, period_end_date = row

        print(f"\n{ticker} - Last filing: {filing_type} for FY{fiscal_year} Q{fiscal_quarter or 'N/A'}")
        print(f"  Period ended: {period_end_date}")
        print(f"  Filed on: {filing_date}")

        # Calculate next filing
        if filing_type == '10-Q':
            if fiscal_quarter == 4:
                next_type = '10-K'
                next_quarter = None
                next_year = fiscal_year
                # Period end is the same (Q4 = year end)
                import datetime as dt
                next_period_end = period_end_date
                estimated_filing = next_period_end + dt.timedelta(days=67)
            else:
                next_type = '10-Q'
                next_quarter = (fiscal_quarter % 4) + 1 if fiscal_quarter else 1
                next_year = fiscal_year + 1 if fiscal_quarter == 4 else fiscal_year
                # Calculate next quarter end
                import datetime as dt
                quarter_end_months = [2, 5, 8, 11]  # Mar, Jun, Sep, Dec (0-indexed)
                quarter_end_days = [31, 30, 30, 31]
                end_month = quarter_end_months[next_quarter - 1]
                end_day = quarter_end_days[next_quarter - 1]
                year_for_quarter = next_year
                next_period_end = dt.datetime(year_for_quarter, end_month + 1, end_day)
                estimated_filing = next_period_end + dt.timedelta(days=42)
        else:  # 10-K
            next_type = '10-Q'
            next_quarter = 1
            next_year = fiscal_year + 1
            # Q1 end is typically 3 months after year end
            import datetime as dt
            next_period_end = period_end_date + dt.timedelta(days=90)
            estimated_filing = next_period_end + dt.timedelta(days=42)

        days_until = (estimated_filing - now).days

        print(f"  → Next: {next_type} FY{next_year} Q{next_quarter or 'N/A'}")
        print(f"     Expected period end: {next_period_end}")
        print(f"     Estimated filing date: {estimated_filing.date()}")
        print(f"     Days from now: {days_until}")

    cursor.close()
    conn.close()

if __name__ == "__main__":
    main()
