/**
 * Homepage
 *
 * Displays latest SEC filing analyses from tracked companies
 */

import Link from 'next/link';
import { query, Analysis } from '@/lib/db';
import { CompanyLogo } from '@/lib/company-logo';
import UpcomingFilings from '@/components/UpcomingFilings';
import { EnhancedFilingCard } from '@/components/EnhancedFilingCard';

interface AnalysisWithDomain extends Analysis {
  company_domain?: string | null;
}

async function getRecent10Q(): Promise<AnalysisWithDomain[]> {
  return await query<AnalysisWithDomain>(
    `
    SELECT
      c.id,
      c.slug,
      co.ticker as company_ticker,
      co.name as company_name,
      co.metadata->>'domain' as company_domain,
      f.filing_type,
      f.filing_date,
      f.fiscal_year,
      f.fiscal_quarter,
      c.key_takeaways,
      c.executive_summary
    FROM content c
    JOIN filings f ON c.filing_id = f.id
    JOIN companies co ON c.company_id = co.id
    WHERE c.blog_html IS NOT NULL
    AND f.filing_type = '10-Q'
    AND f.filing_date >= NOW() - INTERVAL '7 days'
    ORDER BY f.filing_date DESC
    LIMIT 5
  `
  );
}

async function getRecent10K(): Promise<AnalysisWithDomain[]> {
  return await query<AnalysisWithDomain>(
    `
    SELECT
      c.id,
      c.slug,
      co.ticker as company_ticker,
      co.name as company_name,
      co.metadata->>'domain' as company_domain,
      f.filing_type,
      f.filing_date,
      f.fiscal_year,
      f.fiscal_quarter,
      c.key_takeaways,
      c.executive_summary
    FROM content c
    JOIN filings f ON c.filing_id = f.id
    JOIN companies co ON c.company_id = co.id
    WHERE c.blog_html IS NOT NULL
    AND f.filing_type = '10-K'
    AND f.filing_date >= NOW() - INTERVAL '14 days'
    ORDER BY f.filing_date DESC
    LIMIT 5
  `
  );
}

async function getLatestAnalyses(): Promise<AnalysisWithDomain[]> {
  return await query<AnalysisWithDomain>(
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

function EnhancedFilingsSection({
  title,
  filingType,
  analyses,
  showCount = false
}: {
  title: string;
  filingType: string;
  analyses: AnalysisWithDomain[];
  showCount?: boolean;
}) {
  // Calculate average sentiment for 10-K sections
  const avgSentiment = analyses.length > 0
    ? analyses.reduce((sum, a) => sum + (a.key_takeaways?.sentiment || 0), 0) / analyses.length
    : 0;

  return (
    <div className="mb-6">
      {/* Section header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-base font-semibold text-gray-700">{title}</h3>
        {showCount && analyses.length > 0 && (
          <span className="text-sm text-gray-500">{analyses.length} filings</span>
        )}
      </div>

      {/* Empty state */}
      {analyses.length === 0 ? (
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-6 text-center">
          <p className="text-sm text-gray-500">No recent filings</p>
        </div>
      ) : (
        <>
          {/* Average sentiment card for 10-K */}
          {filingType === '10-K' && analyses.length > 0 && (
            <div className="bg-blue-50 border border-blue-100 rounded-lg p-4 mb-4">
              <div className="text-xs text-gray-600 mb-1">Avg Sentiment</div>
              <div className="flex items-baseline gap-2">
                <div className="text-3xl font-bold text-gray-900">
                  {avgSentiment.toFixed(2)}
                </div>
                <div className="flex items-center text-sm text-green-600 font-semibold">
                  <svg className="w-4 h-4 mr-1" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M5.293 9.707a1 1 0 010-1.414l4-4a1 1 0 011.414 0l4 4a1 1 0 01-1.414 1.414L11 7.414V15a1 1 0 11-2 0V7.414L6.707 9.707a1 1 0 01-1.414 0z" clipRule="evenodd" />
                  </svg>
                  +12% vs prev period
                </div>
              </div>
            </div>
          )}

          {/* Filing cards */}
          {analyses.map((analysis) => (
            <EnhancedFilingCard
              key={analysis.id}
              ticker={analysis.company_ticker}
              companyName={analysis.company_name}
              filingType={analysis.filing_type}
              sentiment={analysis.key_takeaways?.sentiment || 0}
              metrics={analysis.key_takeaways?.metrics || {}}
              slug={analysis.slug || ''}
              filingDate={analysis.filing_date}
            />
          ))}
        </>
      )}
    </div>
  );
}

export default async function Home() {
  const [
    latestAnalyses,
    companyCount,
    filingCount,
    recent10Q,
    recent10K,
  ] = await Promise.all([
    getLatestAnalyses(),
    getCompanyCount(),
    getFilingCount(),
    getRecent10Q(),
    getRecent10K(),
  ]);

  return (
    <div className="min-h-screen bg-white">
      {/* Header */}
      <header className="border-b">
        <div className="max-w-[1920px] mx-auto px-4 sm:px-6 lg:px-12 xl:px-16 py-6">
          <div className="flex items-center gap-3">
            <img src="/logo.png" alt="10KAY Logo" className="w-12 h-12" />
            <div>
              <h1 className="text-4xl font-bold text-gray-900">10KAY</h1>
            </div>
          </div>
          <p className="mt-2 text-lg text-gray-600">
            Strategic Insights from SEC Filings for Tech Companies
          </p>
        </div>
      </header>

      {/* Stats Bar */}
      <div className="bg-gray-50 border-b">
        <div className="max-w-[1920px] mx-auto px-4 sm:px-6 lg:px-12 xl:px-16 py-4">
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

      {/* Upcoming Filings Section */}
      <UpcomingFilings />

      {/* Main Content */}
      <main className="max-w-[1920px] mx-auto px-4 sm:px-6 lg:px-12 xl:px-16 py-12">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
          <div className="lg:col-span-3">
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
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
                  {latestAnalyses.map((analysis) => {
                    const sentiment = getSentimentBadge(analysis.key_takeaways);
                    const headline = analysis.key_takeaways?.headline || '';
                const summary = analysis.executive_summary?.substring(0, 200) + '...' || '';

                return (
                  <Link
                    key={analysis.id}
                    href={`/${analysis.slug}`}
                    className="block bg-white border rounded-lg overflow-hidden hover:shadow-lg transition-shadow"
                  >
                    {/* Company Header */}
                    <div className="flex items-start gap-4 p-4 bg-gray-50 border-b">
                      <CompanyLogo
                        ticker={analysis.company_ticker}
                        domain={analysis.company_domain}
                        size={56}
                        className="flex-shrink-0"
                      />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex-1 min-w-0">
                            <h3 className="text-lg font-bold text-gray-900 truncate">
                              {analysis.company_name}
                            </h3>
                            <p className="text-sm text-gray-600 truncate">{analysis.company_ticker}</p>
                          </div>
                          <span className={`px-2 py-1 rounded text-xs font-semibold whitespace-nowrap ${sentiment.className}`}>
                            {sentiment.label}
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Content Section */}
                    <div className="p-6">
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
                    </div>
                  </Link>
                );
                  })}
                </div>
              </>
            )}
          </div>
          <aside className="lg:col-span-1">
            {/* Fixed right rail - sticky positioning */}
            <div className="lg:sticky lg:top-6 lg:max-h-[calc(100vh-3rem)] lg:overflow-y-auto">
              <EnhancedFilingsSection
                title="Recent 10-Qs (Trailing Week)"
                filingType="10-Q"
                analyses={recent10Q}
              />
              <EnhancedFilingsSection
                title="Recent 10-Ks (Trailing 2 Weeks)"
                filingType="10-K"
                analyses={recent10K}
                showCount
              />
            </div>
          </aside>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t mt-16">
        <div className="max-w-[1920px] mx-auto px-4 sm:px-6 lg:px-12 xl:px-16 py-8">
          <p className="text-center text-sm text-gray-500">
            Built with ❤️ for tech operators who want to understand the business landscape
          </p>
        </div>
      </footer>
    </div>
  );
}
