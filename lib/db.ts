/**
 * Database utility for PostgreSQL connections
 *
 * Provides connection pooling and query helpers for accessing
 * the 10KAY content database from Next.js API routes and server components.
 */

import { Pool } from 'pg';

// Create a singleton pool instance
let pool: Pool | null = null;

/**
 * Get or create PostgreSQL connection pool
 */
export function getPool(): Pool {
  if (!pool) {
    pool = new Pool({
      connectionString: process.env.DATABASE_URL,
      max: 20, // Maximum number of clients in the pool
      idleTimeoutMillis: 30000,
      connectionTimeoutMillis: 2000,
      // AWS RDS requires SSL encryption
      ssl: {
        rejectUnauthorized: false, // For development; use proper certs in production
      },
    });

    pool.on('error', (err) => {
      console.error('Unexpected error on idle client', err);
      process.exit(-1);
    });
  }

  return pool;
}

/**
 * Execute a query with automatic connection handling
 */
export async function query<T = any>(text: string, params?: any[]): Promise<T[]> {
  const pool = getPool();
  const result = await pool.query(text, params);
  return result.rows;
}

/**
 * Get a single row from a query
 */
export async function queryOne<T = any>(text: string, params?: any[]): Promise<T | null> {
  const rows = await query<T>(text, params);
  return rows.length > 0 ? rows[0] : null;
}

/**
 * Types for database models
 */
export interface Company {
  id: string;
  ticker: string;
  name: string;
  exchange: string | null;
  sector: string | null;
  enabled: boolean;
  added_at: Date;
  metadata: Record<string, any> | null;
}

export interface Filing {
  id: string;
  company_id: string;
  filing_type: string;
  accession_number: string;
  filing_date: Date;
  period_end_date: Date | null;
  fiscal_year: number | null;
  fiscal_quarter: number | null;
  edgar_url: string;
  raw_document_url: string | null;
  status: string;
  processed_at: Date | null;
  created_at: Date;
  updated_at: Date;
}

export interface Content {
  id: string;
  filing_id: string;
  company_id: string;
  version: number;
  is_current: boolean;
  executive_summary: string;
  key_takeaways: Record<string, any>;
  deep_dive_opportunities: string | null;
  deep_dive_risks: string | null;
  deep_dive_strategy: string | null;
  implications: string | null;
  blog_html: string | null;
  email_html: string | null;
  published_at: Date | null;
  slug: string | null;
  created_at: Date;
  updated_at: Date;
  created_by: string;
  meta_description: string | null;
  meta_keywords: string[] | null;
}

export interface Analysis extends Content {
  company_ticker: string;
  company_name: string;
  filing_type: string;
  filing_date: Date;
  fiscal_year: number | null;
  fiscal_quarter: number | null;
}
