/**
 * Individual Analysis Page
 *
 * Displays a single SEC filing analysis with the generated blog HTML
 */

import { notFound } from 'next/navigation';
import { queryOne, Analysis } from '@/lib/db';

interface AnalysisPageProps {
  params: {
    id: string;
  };
}

async function getAnalysis(id: string): Promise<Analysis | null> {
  return await queryOne<Analysis>(
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
  const analysis = await getAnalysis(params.id);

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
  const analysis = await getAnalysis(params.id);

  if (!analysis || !analysis.blog_html) {
    notFound();
  }

  // Render the pre-generated HTML directly
  // The BlogGenerator already created a complete HTML document with styles
  return (
    <div
      className="analysis-content"
      dangerouslySetInnerHTML={{ __html: analysis.blog_html }}
    />
  );
}
