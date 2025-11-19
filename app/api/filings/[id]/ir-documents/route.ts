/**
 * GET /api/filings/[id]/ir-documents
 *
 * Fetch IR documents linked to a specific filing
 * Returns documents published within ±72 hours of the filing date
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
  time_delta_hours: number;
  window_type: 'pre_filing' | 'post_filing' | 'concurrent';
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;

    // Fetch IR documents linked to this filing
    const documents = await query<IRDocument>(
      `
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
        ifl.time_delta_hours,
        ifl.window_type
      FROM ir_documents ir
      JOIN ir_filing_links ifl ON ir.id = ifl.ir_document_id
      WHERE ifl.filing_id = $1
        AND ifl.show_on_filing_page = true
      ORDER BY ifl.display_order ASC, ABS(ifl.time_delta_hours) ASC
    `,
      [id]
    );

    // Parse salient_takeaways if it's a JSON string
    const processedDocuments = documents.map(doc => ({
      ...doc,
      salient_takeaways: typeof doc.salient_takeaways === 'string'
        ? JSON.parse(doc.salient_takeaways)
        : doc.salient_takeaways
    }));

    return NextResponse.json({
      documents: processedDocuments,
      count: processedDocuments.length
    });
  } catch (error) {
    console.error('Error fetching IR documents:', error);
    return NextResponse.json(
      { error: 'Failed to fetch IR documents' },
      { status: 500 }
    );
  }
}
