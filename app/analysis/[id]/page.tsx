/**
 * Individual Analysis Page
 *
 * Displays a single SEC filing analysis with the generated blog HTML
 */

import { notFound } from 'next/navigation';
import Link from 'next/link';
import { queryOne, Analysis } from '@/lib/db';
import { CompanyLogo } from '@/lib/company-logo';
import IRDocuments from '@/components/IRDocuments';

interface AnalysisPageProps {
  params: Promise<{
    id: string;
  }>;
}

interface AnalysisWithDomain extends Analysis {
  company_domain?: string | null;
}

async function getAnalysis(id: string): Promise<AnalysisWithDomain | null> {
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
    WHERE c.id = $1 AND c.blog_html IS NOT NULL
  `,
    [id]
  );
}

export async function generateMetadata({ params }: AnalysisPageProps) {
  const { id } = await params;
  const analysis = await getAnalysis(id);

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
  const { id } = await params;
  const analysis = await getAnalysis(id);

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

      {/* IR Documents Section */}
      <div className="max-w-4xl mx-auto px-4 py-8">
        <IRDocuments filingId={analysis.filing_id} />
      </div>
    </div>
  );
}
