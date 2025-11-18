/**
 * Analysis Page (Slug-based Route)
 *
 * Displays a single SEC filing analysis via friendly URL:
 * /ticker/year/quarter/type (e.g., /dash/2025/q3/10q)
 */

import { notFound } from 'next/navigation';
import Link from 'next/link';
import { queryOne, Analysis } from '@/lib/db';
import { CompanyLogo } from '@/lib/company-logo';
import FilingComparison from '@/components/FilingComparison';

interface AnalysisPageProps {
  params: Promise<{
    ticker: string;
    year: string;
    quarter: string;
    type: string;
  }>;
}

interface AnalysisWithDomain extends Analysis {
  company_domain?: string | null;
}

async function getAnalysisBySlug(
  ticker: string,
  year: string,
  quarter: string,
  type: string
): Promise<AnalysisWithDomain | null> {
  const slug = `${ticker}/${year}/${quarter}/${type}`;

  const analysisPromise = queryOne<AnalysisWithDomain>(
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
      c.published_at,
      c.slug,
      c.created_at,
      c.meta_description,
      c.meta_keywords,
      co.ticker as company_ticker,
      co.name as company_name,
      co.metadata->>'domain' as company_domain,
      f.filing_type,
      f.filing_date,
      f.fiscal_year,
      f.fiscal_quarter,
      f.edgar_url
    FROM content c
    JOIN filings f ON c.filing_id = f.id
    JOIN companies co ON c.company_id = co.id
    WHERE c.slug = $1 AND c.blog_html IS NOT NULL
  `,
    [slug]
  );

  const comparisonPromise = queryOne<{ comparison_content: any }>(
    `
    SELECT fc.content as comparison_content
    FROM filing_comparisons fc
    JOIN filings f ON f.id = fc.current_filing_id
    JOIN content c ON c.filing_id = f.id
    WHERE c.slug = $1
    `,
    [slug]
  );

  const [analysis, comparison] = await Promise.all([
    analysisPromise,
    comparisonPromise,
  ]);

  if (!analysis) {
    return null;
  }

  return {
    ...analysis,
    comparison: comparison?.comparison_content,
  };
}

export async function generateMetadata({ params }: AnalysisPageProps) {
  const { ticker, year, quarter, type } = await params;
  const analysis = await getAnalysisBySlug(ticker, year, quarter, type);

  if (!analysis) {
    return {
      title: 'Analysis Not Found | 10KAY',
    };
  }

  const title = `${analysis.company_name} (${analysis.company_ticker}) ${analysis.filing_type} Analysis | 10KAY`;
  const description =
    analysis.meta_description ||
    `Strategic insights from ${analysis.company_name}'s latest ${analysis.filing_type} filing.`;

  return {
    title,
    description,
    keywords: analysis.meta_keywords || [
      analysis.company_ticker,
      analysis.company_name,
      analysis.filing_type,
      'SEC filing',
      '10-K analysis',
      '10-Q analysis',
    ],
    openGraph: {
      title,
      description,
      type: 'article',
      publishedTime: analysis.published_at?.toISOString(),
    },
    twitter: {
      card: 'summary_large_image',
      title,
      description,
    },
  };
}

export default async function AnalysisPage({ params }: AnalysisPageProps) {
  const { ticker, year, quarter, type } = await params;
  const analysis = await getAnalysisBySlug(ticker, year, quarter, type);

  if (!analysis || !analysis.blog_html) {
    notFound();
  }

  // Render with pre-generated HTML only (no redundant header)
  return (
    <div className="min-h-screen bg-white">
      {/* Blog Content */}
      <div
        className="analysis-content"
        dangerouslySetInnerHTML={{ __html: analysis.blog_html }}
      />
      {analysis.comparison && (
        <div className="p-8">
          <FilingComparison comparison={analysis.comparison} />
        </div>
      )}
    </div>
  );
}
