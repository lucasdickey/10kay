import { NextResponse } from 'next/server';
import { query } from '@/lib/db';
import { calculateUpcomingFilings } from '@/lib/upcoming-filings';

/**
 * GET /api/upcoming-filings
 *
 * Returns estimated upcoming SEC filings based on historical filing patterns
 * Query params:
 * - days: Number of days ahead to look (default: 120)
 * - limit: Maximum number of results to return (default: 10)
 */
export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const daysAhead = parseInt(searchParams.get('days') || '120');
    const limit = parseInt(searchParams.get('limit') || '10');

    // Get the most recent filing for each enabled company
    const latestFilings = await query<{
      company_id: string;
      ticker: string;
      name: string;
      filing_type: string;
      filing_date: Date;
      fiscal_year: number | null;
      fiscal_quarter: number | null;
      period_end_date: Date | null;
    }>(
      `
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
      `
    );

    // Calculate upcoming filings using the utility function
    const upcomingFilings = calculateUpcomingFilings(latestFilings, daysAhead);

    // Apply limit
    const limitedFilings = upcomingFilings.slice(0, limit);

    return NextResponse.json({
      success: true,
      count: limitedFilings.length,
      daysAhead,
      filings: limitedFilings,
    });
  } catch (error) {
    console.error('Error fetching upcoming filings:', error);
    return NextResponse.json(
      {
        success: false,
        error: 'Failed to fetch upcoming filings',
      },
      { status: 500 }
    );
  }
}
