/**
 * Homepage
 *
 * Displays latest SEC filing analyses from tracked companies
 */

import Link from 'next/link';
import { query, Analysis } from '@/lib/db';

async function getLatestAnalyses(): Promise<Analysis[]> {
  return await query<Analysis>(
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
      co.ticker as company_ticker,
      co.name as company_name,
      f.filing_type,
      f.filing_date,
      f.fiscal_year,
      f.fiscal_quarter
    FROM content c
    JOIN filings f ON c.filing_id = f.id
    JOIN companies co ON c.company_id = co.id
    WHERE c.blog_html IS NOT NULL
    ORDER BY f.filing_date DESC
    LIMIT 12
  `
  );
}

async function getCompanyCount(): Promise<number> {
  const result = await query<{ count: string }>(
    'SELECT COUNT(*) as count FROM companies WHERE enabled = true'
  );
  return parseInt(result[0]?.count || '0');
}

async function getFilingCount(): Promise<number> {
  const result = await query<{ count: string }>(
    'SELECT COUNT(DISTINCT c.id) as count FROM content c WHERE c.blog_html IS NOT NULL'
  );
  return parseInt(result[0]?.count || '0');
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

export default async function Home() {
  const [latestAnalyses, companyCount, filingCount] = await Promise.all([
    getLatestAnalyses(),
    getCompanyCount(),
    getFilingCount(),
  ]);

  return (
    <div className="min-h-screen bg-white">
      {/* Header */}
      <header className="border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <h1 className="text-4xl font-bold text-gray-900">10KAY</h1>
          <p className="mt-2 text-lg text-gray-600">
            Strategic Insights from SEC Filings for Tech Companies
          </p>
        </div>
      </header>

      {/* Stats Bar */}
      <div className="bg-gray-50 border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex gap-8 text-sm">
            <div>
              <span className="font-semibold text-gray-900">{companyCount}</span>
              <span className="text-gray-600 ml-1">Companies Tracked</span>
            </div>
            <div>
              <span className="font-semibold text-gray-900">{filingCount}</span>
              <span className="text-gray-600 ml-1">Analyses Published</span>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        {latestAnalyses.length === 0 ? (
          <div className="text-center py-12">
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">
              Processing Latest Filings
            </h2>
            <p className="text-gray-600">
              Our AI is analyzing recent SEC filings. Check back soon for insights!
            </p>
          </div>
        ) : (
          <>
            <h2 className="text-2xl font-bold text-gray-900 mb-8">Latest Analyses</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {latestAnalyses.map((analysis) => {
                const sentiment = getSentimentBadge(analysis.key_takeaways);
                const headline = analysis.key_takeaways?.headline || '';
                const summary = analysis.executive_summary?.substring(0, 200) + '...' || '';

                return (
                  <Link
                    key={analysis.id}
                    href={`/analysis/${analysis.id}`}
                    className="block bg-white border rounded-lg p-6 hover:shadow-lg transition-shadow"
                  >
                    {/* Company Header */}
                    <div className="flex items-start justify-between mb-3">
                      <div>
                        <h3 className="text-lg font-bold text-gray-900">
                          {analysis.company_ticker}
                        </h3>
                        <p className="text-sm text-gray-600">{analysis.company_name}</p>
                      </div>
                      <span className={`px-2 py-1 rounded text-xs font-semibold ${sentiment.className}`}>
                        {sentiment.label}
                      </span>
                    </div>

                    {/* Filing Info */}
                    <div className="flex items-center gap-2 text-sm text-gray-500 mb-3">
                      <span className="font-medium">{analysis.filing_type}</span>
                      <span>•</span>
                      <span>{getFiscalPeriod(analysis.fiscal_year, analysis.fiscal_quarter)}</span>
                      <span>•</span>
                      <span>{formatDate(analysis.filing_date)}</span>
                    </div>

                    {/* Headline */}
                    {headline && (
                      <h4 className="font-semibold text-gray-900 mb-2 line-clamp-2">
                        {headline}
                      </h4>
                    )}

                    {/* Summary */}
                    <p className="text-sm text-gray-600 line-clamp-3">{summary}</p>

                    {/* Read More */}
                    <div className="mt-4">
                      <span className="text-blue-600 text-sm font-medium hover:text-blue-700">
                        Read Full Analysis →
                      </span>
                    </div>
                  </Link>
                );
              })}
            </div>
          </>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t mt-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <p className="text-center text-sm text-gray-500">
            Built with ❤️ for tech operators who want to understand the business landscape
          </p>
        </div>
      </footer>
    </div>
  );
}
