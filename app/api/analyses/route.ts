/**
 * GET /api/analyses
 *
 * Fetch list of published analyses with pagination
 */

import { NextRequest, NextResponse } from 'next/server';
import { query, Analysis } from '@/lib/db';

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const limit = parseInt(searchParams.get('limit') || '20');
    const offset = parseInt(searchParams.get('offset') || '0');
    const ticker = searchParams.get('ticker');

    let sql = `
      SELECT
        c.id,
        c.filing_id,
        c.company_id,
        c.executive_summary,
        c.key_takeaways,
        c.blog_html,
        c.published_at,
        c.slug,
        c.created_at,
        c.meta_description,
        co.ticker as company_ticker,
        co.name as company_name,
        f.filing_type,
        f.filing_date,
        f.fiscal_year,
        f.fiscal_quarter
      FROM content c
      JOIN filings f ON c.filing_id = f.id
      JOIN companies co ON c.company_id = co.id
      WHERE c.blog_html IS NOT NULL
    `;

    const params: any[] = [];
    let paramIndex = 1;

    if (ticker) {
      sql += ` AND co.ticker = $${paramIndex}`;
      params.push(ticker);
      paramIndex++;
    }

    sql += ` ORDER BY f.filing_date DESC LIMIT $${paramIndex} OFFSET $${paramIndex + 1}`;
    params.push(limit, offset);

    const analyses = await query<Analysis>(sql, params);

    // Get total count
    let countSql = `
      SELECT COUNT(*) as total
      FROM content c
      JOIN filings f ON c.filing_id = f.id
      JOIN companies co ON c.company_id = co.id
      WHERE c.blog_html IS NOT NULL
    `;

    const countParams: any[] = [];
    if (ticker) {
      countSql += ` AND co.ticker = $1`;
      countParams.push(ticker);
    }

    const countResult = await query<{ total: string }>(countSql, countParams);
    const total = parseInt(countResult[0]?.total || '0');

    return NextResponse.json({
      analyses,
      pagination: {
        limit,
        offset,
        total,
        hasMore: offset + limit < total,
      },
    });
  } catch (error) {
    console.error('Error fetching analyses:', error);
    return NextResponse.json(
      { error: 'Failed to fetch analyses' },
      { status: 500 }
    );
  }
}
