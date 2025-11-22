/**
 * GET /api/press-coverage
 *
 * Fetch press coverage articles for filings with optional filtering
 */

import { NextRequest, NextResponse } from 'next/server';
import { query } from '@/lib/db';

export interface PressArticle {
  id: string;
  filing_id: string;
  source: string;
  headline: string;
  url: string;
  author: string | null;
  published_at: string;
  article_snippet: string | null;
  sentiment_score: number | null;
  relevance_score: number | null;
  source_api: string;
  metadata: any;
  // Joined data
  ticker?: string;
  company_name?: string;
  filing_type?: string;
  filing_date?: string;
}

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const limit = parseInt(searchParams.get('limit') || '20');
    const offset = parseInt(searchParams.get('offset') || '0');
    const filingId = searchParams.get('filing_id');
    const ticker = searchParams.get('ticker');
    const source = searchParams.get('source');
    const minSentiment = searchParams.get('min_sentiment');
    const maxSentiment = searchParams.get('max_sentiment');
    const minRelevance = searchParams.get('min_relevance');

    let sql = `
      SELECT
        pc.id,
        pc.filing_id,
        pc.source,
        pc.headline,
        pc.url,
        pc.author,
        pc.published_at,
        pc.article_snippet,
        pc.sentiment_score,
        pc.relevance_score,
        pc.source_api,
        pc.metadata,
        co.ticker,
        co.name as company_name,
        f.filing_type,
        f.filing_date
      FROM press_coverage pc
      JOIN filings f ON pc.filing_id = f.id
      JOIN companies co ON f.company_id = co.id
      WHERE 1=1
    `;

    const params: any[] = [];
    let paramIndex = 1;

    // Filter by filing_id
    if (filingId) {
      sql += ` AND pc.filing_id = $${paramIndex}`;
      params.push(filingId);
      paramIndex++;
    }

    // Filter by ticker
    if (ticker) {
      sql += ` AND co.ticker = $${paramIndex}`;
      params.push(ticker);
      paramIndex++;
    }

    // Filter by source
    if (source) {
      sql += ` AND pc.source = $${paramIndex}`;
      params.push(source);
      paramIndex++;
    }

    // Filter by sentiment range
    if (minSentiment) {
      sql += ` AND pc.sentiment_score >= $${paramIndex}`;
      params.push(parseFloat(minSentiment));
      paramIndex++;
    }

    if (maxSentiment) {
      sql += ` AND pc.sentiment_score <= $${paramIndex}`;
      params.push(parseFloat(maxSentiment));
      paramIndex++;
    }

    // Filter by minimum relevance
    if (minRelevance) {
      sql += ` AND pc.relevance_score >= $${paramIndex}`;
      params.push(parseFloat(minRelevance));
      paramIndex++;
    }

    sql += ` ORDER BY pc.published_at DESC LIMIT $${paramIndex} OFFSET $${paramIndex + 1}`;
    params.push(limit, offset);

    const articles = await query<PressArticle>(sql, params);

    // Get total count
    let countSql = `
      SELECT COUNT(*) as total
      FROM press_coverage pc
      JOIN filings f ON pc.filing_id = f.id
      JOIN companies co ON f.company_id = co.id
      WHERE 1=1
    `;

    const countParams: any[] = [];
    let countParamIndex = 1;

    if (filingId) {
      countSql += ` AND pc.filing_id = $${countParamIndex}`;
      countParams.push(filingId);
      countParamIndex++;
    }

    if (ticker) {
      countSql += ` AND co.ticker = $${countParamIndex}`;
      countParams.push(ticker);
      countParamIndex++;
    }

    if (source) {
      countSql += ` AND pc.source = $${countParamIndex}`;
      countParams.push(source);
      countParamIndex++;
    }

    if (minSentiment) {
      countSql += ` AND pc.sentiment_score >= $${countParamIndex}`;
      countParams.push(parseFloat(minSentiment));
      countParamIndex++;
    }

    if (maxSentiment) {
      countSql += ` AND pc.sentiment_score <= $${countParamIndex}`;
      countParams.push(parseFloat(maxSentiment));
      countParamIndex++;
    }

    if (minRelevance) {
      countSql += ` AND pc.relevance_score >= $${countParamIndex}`;
      countParams.push(parseFloat(minRelevance));
      countParamIndex++;
    }

    const countResult = await query<{ total: string }>(countSql, countParams);
    const total = parseInt(countResult[0]?.total || '0');

    // Calculate aggregate statistics
    const statsQuery = `
      SELECT
        AVG(pc.sentiment_score) as avg_sentiment,
        MIN(pc.sentiment_score) as min_sentiment,
        MAX(pc.sentiment_score) as max_sentiment,
        AVG(pc.relevance_score) as avg_relevance,
        COUNT(DISTINCT pc.source) as source_count
      FROM press_coverage pc
      JOIN filings f ON pc.filing_id = f.id
      JOIN companies co ON f.company_id = co.id
      WHERE 1=1
      ${filingId ? `AND pc.filing_id = $1` : ''}
      ${ticker && !filingId ? `AND co.ticker = $1` : ''}
    `;

    const statsParams = filingId ? [filingId] : (ticker ? [ticker] : []);
    const statsResult = await query(statsQuery, statsParams);
    const stats = statsResult[0] || {};

    return NextResponse.json({
      articles,
      pagination: {
        limit,
        offset,
        total,
        hasMore: offset + limit < total,
      },
      stats: {
        avg_sentiment: parseFloat(stats.avg_sentiment) || null,
        min_sentiment: parseFloat(stats.min_sentiment) || null,
        max_sentiment: parseFloat(stats.max_sentiment) || null,
        avg_relevance: parseFloat(stats.avg_relevance) || null,
        source_count: parseInt(stats.source_count) || 0,
      },
    });
  } catch (error) {
    console.error('Error fetching press coverage:', error);
    return NextResponse.json(
      { error: 'Failed to fetch press coverage' },
      { status: 500 }
    );
  }
}
