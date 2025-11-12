/**
 * Company Page
 *
 * Displays all analyses for a specific company
 */

import { notFound } from 'next/navigation';
import Link from 'next/link';
import { query, Analysis } from '@/lib/db';
import { CompanyLogo } from '@/lib/company-logo';

interface CompanyPageProps {
  params: Promise<{
    ticker: string;
  }>;
}

interface CompanyWithAnalyses {
  ticker: string;
  name: string;
  domain?: string | null;
  analyses: Analysis[];
}

interface AnalysisWithDomain extends Analysis {
  company_domain?: string | null;
}

async function getCompanyAnalyses(ticker: string): Promise<CompanyWithAnalyses | null> {
  const upperTicker = ticker.toUpperCase();

  // Get company info
  const companies = await query<{ ticker: string; name: string; metadata: any }>(
    'SELECT ticker, name, metadata FROM companies WHERE UPPER(ticker) = $1',
    [upperTicker]
  );

  if (companies.length === 0) {
    return null;
  }

  const company = companies[0];

  // Get all analyses for this company
  const analyses = await query<AnalysisWithDomain>(
    `
    SELECT
      c.id,
      c.filing_id,
      c.company_id,
      c.executive_summary,
      c.key_takeaways,
      c.published_at,
      c.created_at,
      c.meta_description,
      c.slug,
      co.ticker as company_ticker,
      co.name as company_name,
      co.metadata->>'domain' as company_domain,
      f.filing_type,
      f.filing_date,
      f.fiscal_year,
      f.fiscal_quarter
    FROM content c
    JOIN filings f ON c.filing_id = f.id
    JOIN companies co ON c.company_id = co.id
    WHERE co.ticker = $1 AND c.blog_html IS NOT NULL
    ORDER BY f.filing_date DESC
  `,
    [company.ticker]
  );

  return {
    ticker: company.ticker,
    name: company.name,
    domain: company.metadata?.domain,
    analyses
  };
}

function formatDate(date: Date): string {
  return new Date(date).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

function getFiscalPeriod(fiscalYear: number | null, fiscalQuarter: number | null): string {
  if (!fiscalYear) return '';
  if (fiscalQuarter) return `Q${fiscalQuarter} ${fiscalYear}`;
  return `FY ${fiscalYear}`;
}

function getSentimentBadge(keyTakeaways: Record<string, any>): { label: string; className: string } {
  const sentiment = keyTakeaways?.sentiment || 0;
  if (sentiment > 0.3) {
    return { label: 'Positive', className: 'bg-green-100 text-green-800' };
  } else if (sentiment < -0.3) {
    return { label: 'Negative', className: 'bg-red-100 text-red-800' };
  }
  return { label: 'Neutral', className: 'bg-gray-100 text-gray-800' };
}

export async function generateMetadata({ params }: CompanyPageProps) {
  const { ticker } = await params;
  const companyData = await getCompanyAnalyses(ticker);

  if (!companyData) {
    return {
      title: 'Company Not Found | 10KAY',
    };
  }

  return {
    title: `${companyData.name} (${companyData.ticker}) - SEC Filing Analyses | 10KAY`,
    description: `All SEC filing analyses for ${companyData.name} (${companyData.ticker}). Strategic insights from 10-K and 10-Q filings.`,
  };
}

export default async function CompanyPage({ params }: CompanyPageProps) {
  const { ticker } = await params;
  const companyData = await getCompanyAnalyses(ticker);

  if (!companyData) {
    notFound();
  }

  return (
    <div className="min-h-screen bg-white">
      {/* Header */}
      <header className="border-b bg-white sticky top-0 z-10 shadow-sm">
        <div className="max-w-[1920px] mx-auto px-4 sm:px-6 lg:px-12 xl:px-16 py-6">
          <Link href="/" className="text-sm text-blue-600 hover:text-blue-700 mb-4 inline-block">
            ← Back to All Analyses
          </Link>
          <h1 className="text-3xl font-bold text-gray-900">
            {companyData.ticker} - {companyData.name}
          </h1>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-[1920px] mx-auto px-4 sm:px-6 lg:px-12 xl:px-16 py-12">
        <h2 className="text-2xl font-bold text-gray-900 mb-8">
          SEC Filing Analyses ({companyData.analyses.length})
        </h2>

        {companyData.analyses.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-gray-600">
              No analyses available yet for {companyData.name}.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {companyData.analyses.map((analysis) => {
              const sentiment = getSentimentBadge(analysis.key_takeaways);
              const headline = analysis.key_takeaways?.headline || '';
              const summary = analysis.executive_summary?.substring(0, 200) + '...' || '';

              return (
                <Link
                  key={analysis.id}
                  href={`/${analysis.slug}`}
                  className="block bg-white border rounded-lg overflow-hidden hover:shadow-lg transition-shadow"
                >
                  {/* Filing Header */}
                  <div className="p-4 bg-gray-50 border-b">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <h3 className="text-lg font-bold text-gray-900">
                          {analysis.filing_type}
                        </h3>
                        <p className="text-sm text-gray-600">
                          {getFiscalPeriod(analysis.fiscal_year, analysis.fiscal_quarter)}
                        </p>
                      </div>
                      <span className={`px-2 py-1 rounded text-xs font-semibold whitespace-nowrap ${sentiment.className}`}>
                        {sentiment.label}
                      </span>
                    </div>
                  </div>

                  {/* Content Section */}
                  <div className="p-6">
                    {/* Filing Date */}
                    <div className="text-sm text-gray-500 mb-3">
                      {formatDate(analysis.filing_date)}
                    </div>

                    {/* Headline */}
                    {headline && (
                      <h4 className="font-semibold text-gray-900 mb-2 line-clamp-2">
                        {headline}
                      </h4>
                    )}

                    {/* Summary */}
                    <p className="text-sm text-gray-600 line-clamp-3">{summary}</p>
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
