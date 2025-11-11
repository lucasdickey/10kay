/**
 * GET /api/analyses/[id]
 *
 * Fetch single analysis by ID
 */

import { NextRequest, NextResponse } from 'next/server';
import { queryOne, Analysis } from '@/lib/db';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;

    const analysis = await queryOne<Analysis>(
      `
      SELECT
        c.id,
        c.filing_id,
        c.company_id,
        c.executive_summary,
        c.key_takeaways,
        c.deep_dive_opportunities,
        c.deep_dive_risks,
        c.deep_dive_strategy,
        c.implications,
        c.blog_html,
        c.email_html,
        c.published_at,
        c.slug,
        c.created_at,
        c.updated_at,
        c.meta_description,
        c.meta_keywords,
        co.ticker as company_ticker,
        co.name as company_name,
        f.filing_type,
        f.filing_date,
        f.fiscal_year,
        f.fiscal_quarter,
        f.edgar_url
      FROM content c
      JOIN filings f ON c.filing_id = f.id
      JOIN companies co ON c.company_id = co.id
      WHERE c.id = $1
    `,
      [id]
    );

    if (!analysis) {
      return NextResponse.json({ error: 'Analysis not found' }, { status: 404 });
    }

    return NextResponse.json({ analysis });
  } catch (error) {
    console.error('Error fetching analysis:', error);
    return NextResponse.json(
      { error: 'Failed to fetch analysis' },
      { status: 500 }
    );
  }
}
