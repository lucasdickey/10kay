import { NextResponse } from 'next/server';
import { query } from '@/lib/db';
import { calculateUpcomingFilings } from '@/lib/upcoming-filings';

/**
 * GET /api/upcoming-filings
 *
 * Returns upcoming SEC filings from scheduled earnings calendar (Finnhub)
 * with fallback to estimated dates based on historical filing patterns
 *
 * Query params:
 * - days: Number of days ahead to look (default: 60)
 * - limit: Maximum number of results to return (default: 10)
 */
export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const daysAhead = parseInt(searchParams.get('days') || '60');
    const limit = parseInt(searchParams.get('limit') || '10');

    // Get scheduled earnings from Finnhub (actual company-announced dates)
    const scheduledEarnings = await query<{
      ticker: string;
      name: string;
      filing_type: string;
      earnings_date: Date;
      earnings_time: string | null;
      fiscal_year: number;
      fiscal_quarter: number | null;
      eps_estimate: number | null;
      revenue_estimate: number | null;
      source: string;
    }>(
      `
      SELECT
        se.ticker,
        co.name,
        CASE
          WHEN se.fiscal_quarter IS NULL THEN '10-K'
          ELSE '10-Q'
        END as filing_type,
        se.earnings_date,
        se.earnings_time,
        se.fiscal_year,
        se.fiscal_quarter,
        se.eps_estimate,
        se.revenue_estimate,
        se.source
      FROM scheduled_earnings se
      JOIN companies co ON se.company_id = co.id
      WHERE co.enabled = true
        AND se.status = 'scheduled'
        AND se.earnings_date >= CURRENT_DATE
        AND se.earnings_date <= CURRENT_DATE + $1
      ORDER BY se.earnings_date ASC
      `,
      [daysAhead]
    );

    // Get the most recent filing for each enabled company (for estimation fallback)
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

    // Calculate estimated upcoming filings for companies without scheduled data
    const estimatedFilings = calculateUpcomingFilings(latestFilings, daysAhead);

    // Create a set of tickers that have scheduled earnings
    const scheduledTickers = new Set(scheduledEarnings.map((se) => se.ticker));

    // Filter out estimated filings for companies that have scheduled data
    const estimatedOnly = estimatedFilings.filter(
      (filing) => !scheduledTickers.has(filing.ticker)
    );

    // Merge scheduled and estimated filings
    const allFilings = [
      ...scheduledEarnings.map((se) => {
        const now = new Date();
        const earningsDate = new Date(se.earnings_date);
        const diffTime = earningsDate.getTime() - now.getTime();
        const daysUntil = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

        return {
          ticker: se.ticker,
          name: se.name,
          filingType: se.filing_type,
          estimatedDate: earningsDate,
          daysUntil,
          fiscalPeriod: se.fiscal_quarter
            ? `Q${se.fiscal_quarter} ${se.fiscal_year}`
            : `FY ${se.fiscal_year}`,
          source: 'scheduled', // Mark as scheduled (vs. estimated)
          earningsTime: se.earnings_time, // 'bmo' or 'amc'
          epsEstimate: se.eps_estimate,
          revenueEstimate: se.revenue_estimate,
        };
      }),
      ...estimatedOnly.map((filing) => ({
        ...filing,
        source: 'estimated', // Mark as estimated
      })),
    ];

    // Sort by date (soonest first) and apply limit
    const sortedFilings = allFilings
      .sort((a, b) => a.estimatedDate.getTime() - b.estimatedDate.getTime())
      .slice(0, limit);

    return NextResponse.json({
      success: true,
      count: sortedFilings.length,
      daysAhead,
      filings: sortedFilings,
      metadata: {
        scheduled: scheduledEarnings.length,
        estimated: estimatedOnly.length,
      },
    });
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    console.error('Error fetching upcoming filings:', errorMessage);
    return NextResponse.json(
      {
        success: false,
        error: 'Failed to fetch upcoming filings',
        debug: errorMessage,
      },
      { status: 500 }
    );
  }
}
