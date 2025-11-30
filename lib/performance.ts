/**
 * Performance calculation utilities for company market data
 *
 * Provides functions to calculate:
 * - 7-day stock price performance
 * - Aggregate performance across all companies
 * - Sector-based performance benchmarks
 */

import { query } from './db';

export interface CompanyPerformance {
  ticker: string;
  companyName: string;
  sector: string | null;
  currentPrice: number | null;
  marketCap: bigint | null;
  marketCapFormatted: string | null;
  priceChange7d: number | null;  // Percentage change
  aggregateChange7d: number | null;  // All companies average
  sectorChange7d: number | null;  // Sector average
  vsAggregate: number | null;  // Difference from aggregate
  vsSector: number | null;  // Difference from sector
  lastUpdated: Date | null;
}

/**
 * Format market cap in billions or millions
 */
function formatMarketCap(marketCap: bigint | null): string | null {
  if (!marketCap) return null;

  const value = Number(marketCap);

  if (value >= 1_000_000_000_000) {
    return `$${(value / 1_000_000_000_000).toFixed(2)}T`;
  } else if (value >= 1_000_000_000) {
    return `$${(value / 1_000_000_000).toFixed(2)}B`;
  } else if (value >= 1_000_000) {
    return `$${(value / 1_000_000).toFixed(2)}M`;
  }

  return `$${value.toLocaleString()}`;
}

/**
 * Get 7-day performance for a single company
 */
export async function getCompany7DayPerformance(ticker: string): Promise<{
  priceChange7d: number | null;
  currentPrice: number | null;
  priceSevenDaysAgo: number | null;
}> {
  const result = await query<{
    current_price: number;
    price_7d_ago: number;
    price_change_7d: number;
  }>(`
    WITH latest_data AS (
      SELECT
        company_id,
        price as current_price,
        data_date as latest_date
      FROM company_market_data
      WHERE ticker = $1
      ORDER BY data_date DESC
      LIMIT 1
    ),
    week_ago_data AS (
      SELECT
        price as price_7d_ago
      FROM company_market_data
      WHERE ticker = $1
        AND data_date >= (SELECT latest_date - INTERVAL '7 days' FROM latest_data)
        AND data_date < (SELECT latest_date FROM latest_data)
      ORDER BY data_date DESC
      LIMIT 1
    )
    SELECT
      l.current_price,
      w.price_7d_ago,
      CASE
        WHEN w.price_7d_ago IS NOT NULL AND w.price_7d_ago > 0
        THEN ((l.current_price - w.price_7d_ago) / w.price_7d_ago * 100)
        ELSE NULL
      END as price_change_7d
    FROM latest_data l
    LEFT JOIN week_ago_data w ON true
  `, [ticker]);

  if (result.length === 0) {
    return { priceChange7d: null, currentPrice: null, priceSevenDaysAgo: null };
  }

  return {
    priceChange7d: result[0].price_change_7d,
    currentPrice: result[0].current_price,
    priceSevenDaysAgo: result[0].price_7d_ago,
  };
}

/**
 * Get aggregate 7-day performance across all tracked companies
 */
export async function getAggregate7DayPerformance(): Promise<number | null> {
  const result = await query<{ avg_change: number }>(`
    WITH company_changes AS (
      SELECT
        cmd1.ticker,
        ((cmd1.price - cmd2.price) / cmd2.price * 100) as change_7d
      FROM company_market_data cmd1
      INNER JOIN companies c ON cmd1.company_id = c.id
      INNER JOIN LATERAL (
        SELECT price
        FROM company_market_data cmd2
        WHERE cmd2.company_id = cmd1.company_id
          AND cmd2.data_date >= cmd1.data_date - INTERVAL '7 days'
          AND cmd2.data_date < cmd1.data_date
        ORDER BY cmd2.data_date DESC
        LIMIT 1
      ) cmd2 ON true
      WHERE cmd1.data_date = (SELECT MAX(data_date) FROM company_market_data)
        AND c.enabled = true
        AND cmd1.price IS NOT NULL
        AND cmd2.price IS NOT NULL
        AND cmd2.price > 0
    )
    SELECT AVG(change_7d) as avg_change
    FROM company_changes
  `);

  return result.length > 0 ? result[0].avg_change : null;
}

/**
 * Get sector-specific 7-day performance
 */
export async function getSector7DayPerformance(sector: string): Promise<number | null> {
  const result = await query<{ avg_change: number }>(`
    WITH company_changes AS (
      SELECT
        cmd1.ticker,
        ((cmd1.price - cmd2.price) / cmd2.price * 100) as change_7d
      FROM company_market_data cmd1
      INNER JOIN companies c ON cmd1.company_id = c.id
      INNER JOIN LATERAL (
        SELECT price
        FROM company_market_data cmd2
        WHERE cmd2.company_id = cmd1.company_id
          AND cmd2.data_date >= cmd1.data_date - INTERVAL '7 days'
          AND cmd2.data_date < cmd1.data_date
        ORDER BY cmd2.data_date DESC
        LIMIT 1
      ) cmd2 ON true
      WHERE cmd1.data_date = (SELECT MAX(data_date) FROM company_market_data)
        AND c.enabled = true
        AND c.sector = $1
        AND cmd1.price IS NOT NULL
        AND cmd2.price IS NOT NULL
        AND cmd2.price > 0
    )
    SELECT AVG(change_7d) as avg_change
    FROM company_changes
  `, [sector]);

  return result.length > 0 ? result[0].avg_change : null;
}

/**
 * Get all companies with their 7-day performance and comparisons
 */
export async function getAllCompaniesPerformance(): Promise<CompanyPerformance[]> {
  // First, get aggregate performance
  const aggregateChange = await getAggregate7DayPerformance();

  // Get all companies with their performance data
  const results = await query<{
    ticker: string;
    company_name: string;
    sector: string | null;
    current_price: number | null;
    market_cap: bigint | null;
    price_change_7d: number | null;
    last_updated: Date | null;
  }>(`
    WITH latest_prices AS (
      SELECT
        c.id as company_id,
        c.ticker,
        c.name as company_name,
        c.sector,
        cmd1.price as current_price,
        cmd1.market_cap,
        cmd1.data_date as last_updated,
        cmd2.price as price_7d_ago
      FROM companies c
      LEFT JOIN company_market_data cmd1 ON c.id = cmd1.company_id
        AND cmd1.data_date = (
          SELECT MAX(data_date)
          FROM company_market_data
          WHERE company_id = c.id
        )
      LEFT JOIN LATERAL (
        SELECT price
        FROM company_market_data cmd2
        WHERE cmd2.company_id = c.id
          AND cmd2.data_date >= cmd1.data_date - INTERVAL '7 days'
          AND cmd2.data_date < cmd1.data_date
        ORDER BY cmd2.data_date DESC
        LIMIT 1
      ) cmd2 ON true
      WHERE c.enabled = true AND c.status = 'active'
      ORDER BY c.ticker
    )
    SELECT
      ticker,
      company_name,
      sector,
      current_price,
      market_cap,
      CASE
        WHEN price_7d_ago IS NOT NULL AND price_7d_ago > 0
        THEN ((current_price - price_7d_ago) / price_7d_ago * 100)
        ELSE NULL
      END as price_change_7d,
      last_updated
    FROM latest_prices
  `);

  // Get sector averages
  const sectorAverages = new Map<string, number>();
  const companiesBySector = new Map<string, typeof results>();

  results.forEach(company => {
    if (company.sector) {
      if (!companiesBySector.has(company.sector)) {
        companiesBySector.set(company.sector, []);
      }
      companiesBySector.get(company.sector)!.push(company);
    }
  });

  // Calculate sector averages
  for (const [sector, companies] of companiesBySector.entries()) {
    const validChanges = companies
      .map(c => c.price_change_7d)
      .filter((c): c is number => c !== null);

    if (validChanges.length > 0) {
      const avg = validChanges.reduce((sum, val) => sum + val, 0) / validChanges.length;
      sectorAverages.set(sector, avg);
    }
  }

  // Map to CompanyPerformance objects
  return results.map(company => {
    const sectorChange = company.sector ? sectorAverages.get(company.sector) || null : null;

    return {
      ticker: company.ticker,
      companyName: company.company_name,
      sector: company.sector,
      currentPrice: company.current_price,
      marketCap: company.market_cap,
      marketCapFormatted: formatMarketCap(company.market_cap),
      priceChange7d: company.price_change_7d,
      aggregateChange7d: aggregateChange,
      sectorChange7d: sectorChange,
      vsAggregate: company.price_change_7d !== null && aggregateChange !== null
        ? company.price_change_7d - aggregateChange
        : null,
      vsSector: company.price_change_7d !== null && sectorChange !== null
        ? company.price_change_7d - sectorChange
        : null,
      lastUpdated: company.last_updated,
    };
  });
}
