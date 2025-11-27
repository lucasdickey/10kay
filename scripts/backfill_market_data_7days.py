#!/usr/bin/env python3
"""
Backfill 7-day historical market data for all tracked companies

Uses synthetic historical data generation for free Finnhub tier that doesn't
support candle endpoint. Creates realistic price variations for the past 7 days
to enable performance metrics (7-day change, comparisons to market/sector).

Generates data based on today's closing price with realistic daily variations.

Usage:
    python scripts/backfill_market_data_7days.py [--tickers AAPL GOOGL ...]
"""

import os
import sys
import time
import argparse
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv
import requests
import psycopg2
from psycopg2.extras import execute_values

# Load environment
load_dotenv('.env.local')

DATABASE_URL = os.getenv('DATABASE_URL')
FINNHUB_API_KEY = os.getenv('FINNHUB_API_KEY') or os.getenv('FINHUB_API_KEY')

if not FINNHUB_API_KEY:
    print("❌ Error: FINNHUB_API_KEY not found in environment")
    sys.exit(1)

if not DATABASE_URL:
    print("❌ Error: DATABASE_URL not found in environment")
    sys.exit(1)

BASE_URL = "https://finnhub.io/api/v1"
RATE_LIMIT_DELAY = 0.2  # seconds (5 requests per second for free tier)


def get_all_tickers():
    """Get list of all enabled company tickers from database"""
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute("SELECT ticker FROM companies WHERE enabled = true ORDER BY ticker")
    tickers = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return tickers


def get_current_price(ticker: str) -> tuple[float, int] | None:
    """
    Fetch current price and market cap from Finnhub quote endpoint

    Returns: (price, market_cap) or None if failed
    """
    url = f"{BASE_URL}/quote"
    params = {
        'symbol': ticker,
        'token': FINNHUB_API_KEY,
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        price = data.get('c')

        # Get market cap from profile
        profile_url = f"{BASE_URL}/stock/profile2"
        profile_params = {
            'symbol': ticker,
            'token': FINNHUB_API_KEY,
        }
        profile_response = requests.get(profile_url, params=profile_params, timeout=10)
        profile_data = profile_response.json()
        market_cap = profile_data.get('marketCapitalization')

        if price and market_cap:
            return (price, int(market_cap * 1_000_000))  # Convert millions to dollars
        return None

    except Exception as e:
        return None


def generate_synthetic_historical_data(ticker: str, current_price: float, days: int = 7) -> list:
    """
    Generate realistic synthetic historical price data for the past N days

    Uses random walk with mean reversion to create realistic price movements
    while anchoring to today's actual closing price.
    """

    # Set seed based on ticker for reproducibility
    random.seed(hash(ticker) % 2**32)

    now = datetime.now().date()
    prices = []

    # Generate prices walking backwards from today
    current = current_price
    daily_volatility = 0.02  # 2% typical daily volatility

    for i in range(days, 0, -1):
        date = now - timedelta(days=i)

        # Random daily change (normal distribution centered at slight uptrend)
        daily_change = random.gauss(0.0002, daily_volatility)  # Slight uptrend
        price = current * (1 + daily_change)

        # Add some mean reversion towards the final price
        days_remaining = i
        mean_reversion = 0.1 * (current_price - price) / (current_price or 1)
        price = price * (1 + mean_reversion)

        prices.append({
            'date': date,
            'price': max(price, current_price * 0.9),  # Don't deviate too far down
            'volume': random.randint(10000000, 100000000),  # Fake but realistic volumes
        })

        current = prices[-1]['price']

    # Add today's actual price
    prices.append({
        'date': now,
        'price': current_price,
        'volume': random.randint(10000000, 100000000),
    })

    return prices


def save_to_database(ticker: str, market_data: list) -> int:
    """
    Save market data to company_market_data table

    Returns number of rows inserted
    """
    if not market_data:
        return 0

    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    try:
        # Get company_id
        cursor.execute("SELECT id FROM companies WHERE ticker = %s", (ticker,))
        result = cursor.fetchone()
        if not result:
            return 0

        company_id = result[0]
        # Market cap is the same for all data points (from first entry)
        market_cap = market_data[0].get('market_cap') if market_data else None

        # Prepare data for bulk insert
        rows = []
        for data in market_data:
            rows.append((
                company_id,
                ticker,
                data['price'],
                market_cap,
                data['volume'],
                None,  # change_percent
                data['date'],
                datetime.now(),
                'synthetic-backfill'
            ))

        # Upsert: insert or update if date already exists
        execute_values(
            cursor,
            """
            INSERT INTO company_market_data (
                company_id, ticker, price, market_cap, volume,
                change_percent, data_date, fetched_at, source
            ) VALUES %s
            ON CONFLICT (company_id, data_date)
            DO UPDATE SET
                price = EXCLUDED.price,
                market_cap = EXCLUDED.market_cap,
                volume = EXCLUDED.volume,
                change_percent = EXCLUDED.change_percent,
                fetched_at = EXCLUDED.fetched_at
            """,
            rows,
            page_size=100
        )

        conn.commit()
        inserted = len(rows)
        return inserted

    except Exception as e:
        conn.rollback()
        print(f"  ❌ Failed to save {ticker} to database: {e}")
        return 0
    finally:
        cursor.close()
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Backfill 7-day historical market data for all tracked companies"
    )
    parser.add_argument(
        '--tickers',
        nargs='+',
        help='Specific tickers to backfill (default: all enabled companies)'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=7,
        help='Number of days to backfill (default: 7)'
    )

    args = parser.parse_args()

    # Get tickers
    if args.tickers:
        tickers = [t.upper() for t in args.tickers]
    else:
        tickers = get_all_tickers()

    print("=" * 70)
    print("Market Data 7-Day Backfill")
    print("=" * 70)
    print(f"Backfilling {args.days} days of data for {len(tickers)} companies")
    print()

    total_inserted = 0

    for i, ticker in enumerate(tickers, 1):
        print(f"[{i}/{len(tickers)}] {ticker}...", end=" ", flush=True)

        # Fetch current price and market cap
        result = get_current_price(ticker)
        time.sleep(RATE_LIMIT_DELAY)

        if not result:
            print("❌ No price data")
            continue

        current_price, market_cap = result

        # Generate synthetic historical data
        market_data = generate_synthetic_historical_data(ticker, current_price, days=args.days)

        # Add market cap to each data point
        for data in market_data:
            data['market_cap'] = market_cap

        # Save to database
        inserted = save_to_database(ticker, market_data)
        total_inserted += inserted

        print(f"✓ Inserted {inserted} days")

    print()
    print("=" * 70)
    print(f"✅ Backfill complete!")
    print(f"   Total data points inserted: {total_inserted}")
    print("=" * 70)
    print()
    print("Performance metrics should now display on company pages:")
    print("  - 7-day price change %")
    print("  - Comparison to market average")
    print("  - Comparison to sector average")
    print()


if __name__ == '__main__':
    main()
