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

  return await queryOne<AnalysisWithDomain>(
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
      {/* Filing Header with Download Link */}
      {analysis.edgar_url && (
        <div className="border-b border-gray-200 bg-gray-50">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className="text-sm text-gray-600">
                  {analysis.company_ticker} • {analysis.filing_type} • Filed {new Date(analysis.filing_date).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })}
                </span>
              </div>
              <a
                href={analysis.edgar_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 hover:text-gray-900 transition-colors"
                title="View Original SEC Filing"
              >
                <svg
                  className="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                  />
                </svg>
                View Original Filing
              </a>
            </div>
          </div>
        </div>
      )}

      {/* Blog Content */}
      <div
        className="analysis-content"
        dangerouslySetInnerHTML={{ __html: analysis.blog_html }}
      />
    </div>
  );
}
