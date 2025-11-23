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
import AnalysisPageShare from '@/components/AnalysisPageShare';

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

  // Inject download icon next to sentiment badge in the pre-generated HTML
  const downloadIcon = analysis.edgar_url
    ? `<a href="${analysis.edgar_url}" target="_blank" rel="noopener noreferrer" class="filing-download-icon" title="View Original SEC Filing" style="display: inline-flex; align-items: center; margin-left: 8px; color: #6b7280; vertical-align: middle;"><svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg></a>`
    : '';

  // Add placeholder for share button after download icon
  const modifiedHtml = analysis.blog_html.replace(
    /(<span class="sentiment[^"]*">[^<]*<\/span>)/,
    `$1${downloadIcon}<span id="share-button-mount"></span>`
  );

  const shareTitle = `${analysis.company_name} ${analysis.filing_type} Analysis`;

  return (
    <div className="min-h-screen bg-white">
      {/* Blog Content with injected download icon */}
      <div
        className="analysis-content"
        dangerouslySetInnerHTML={{ __html: modifiedHtml }}
      />
      {/* Share button (renders into mount point via portal) */}
      <AnalysisPageShare slug={analysis.slug || ''} title={shareTitle} />
    </div>
  );
}
