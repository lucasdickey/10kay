/**
 * GET /api/companies/[ticker]/ir-documents
 *
 * Fetch recent IR documents for a company
 * Optionally filtered by date range
 */

import { NextRequest, NextResponse } from 'next/server';
import { query } from '@/lib/db';

export interface IRDocument {
  id: string;
  title: string;
  document_url: string;
  document_type: string;
  published_at: string;
  summary: string | null;
  analysis_summary: string | null;
  relevance_score: number | null;
  key_topics: string[] | null;
  salient_takeaways: string[] | null;
  linked_filings: Array<{
    filing_id: string;
    filing_type: string;
    filing_date: string;
    fiscal_year: number;
    fiscal_quarter: number | null;
  }> | null;
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ ticker: string }> }
) {
  try {
    const { ticker } = await params;
    const { searchParams } = new URL(request.url);

    // Optional query parameters
    const limit = parseInt(searchParams.get('limit') || '10', 10);
    const offset = parseInt(searchParams.get('offset') || '0', 10);
    const fromDate = searchParams.get('from_date');
    const toDate = searchParams.get('to_date');

    // Build query
    let queryText = `
      SELECT
        ir.id,
        ir.title,
        ir.document_url,
        ir.document_type,
        ir.published_at,
        ir.summary,
        ir.analysis_summary,
        ir.relevance_score,
        ir.key_topics,
        COALESCE(
          ir.metadata->>'salient_takeaways',
          NULL
        )::jsonb as salient_takeaways,
        -- Aggregate linked filings
        COALESCE(
          json_agg(
            json_build_object(
              'filing_id', f.id,
              'filing_type', f.filing_type,
              'filing_date', f.filing_date,
              'fiscal_year', f.fiscal_year,
              'fiscal_quarter', f.fiscal_quarter
            ) ORDER BY f.filing_date DESC
          ) FILTER (WHERE f.id IS NOT NULL),
          '[]'::json
        ) as linked_filings
      FROM ir_documents ir
      JOIN companies c ON ir.company_id = c.id
      LEFT JOIN ir_filing_links ifl ON ir.id = ifl.ir_document_id
      LEFT JOIN filings f ON ifl.filing_id = f.id
      WHERE c.ticker = $1
        AND ir.status IN ('analyzed', 'linked')
    `;

    const queryParams: any[] = [ticker.toUpperCase()];
    let paramIndex = 2;

    // Add date filters if provided
    if (fromDate) {
      queryText += ` AND ir.published_at >= $${paramIndex}`;
      queryParams.push(fromDate);
      paramIndex++;
    }

    if (toDate) {
      queryText += ` AND ir.published_at <= $${paramIndex}`;
      queryParams.push(toDate);
      paramIndex++;
    }

    queryText += `
      GROUP BY ir.id
      ORDER BY ir.published_at DESC
      LIMIT $${paramIndex}
      OFFSET $${paramIndex + 1}
    `;

    queryParams.push(limit, offset);

    // Execute query
    const documents = await query<IRDocument>(queryText, queryParams);

    // Parse JSON fields if needed
    const processedDocuments = documents.map(doc => ({
      ...doc,
      salient_takeaways: typeof doc.salient_takeaways === 'string'
        ? JSON.parse(doc.salient_takeaways)
        : doc.salient_takeaways,
      linked_filings: typeof doc.linked_filings === 'string'
        ? JSON.parse(doc.linked_filings)
        : doc.linked_filings
    }));

    return NextResponse.json({
      ticker: ticker.toUpperCase(),
      documents: processedDocuments,
      count: processedDocuments.length,
      limit,
      offset
    });
  } catch (error) {
    console.error('Error fetching IR documents:', error);
    return NextResponse.json(
      { error: 'Failed to fetch IR documents' },
      { status: 500 }
    );
  }
}
