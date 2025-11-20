/**
 * Homepage
 *
 * Displays latest SEC filing analyses from tracked companies
 */

import Link from 'next/link';
import { query, Analysis } from '@/lib/db';
import { CompanyLogo } from '@/lib/company-logo';
import UpcomingFilings from '@/components/UpcomingFilings';
import { RecentFilingsCarousel } from '@/components/RecentFilingsCarousel';
import { LatestAnalysesFilter } from '@/components/LatestAnalysesFilter';
import { Navigation } from '@/components/Navigation';

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
    AND f.filing_date >= NOW() - INTERVAL '30 days'
    ORDER BY f.filing_date DESC
    LIMIT 10
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
    AND f.filing_date >= NOW() - INTERVAL '60 days'
    ORDER BY f.filing_date DESC
    LIMIT 10
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
    LIMIT 30
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

  // Combine and sort recent filings by date
  const recentFilings = [...recent10Q, ...recent10K].sort(
    (a, b) => new Date(b.filing_date).getTime() - new Date(a.filing_date).getTime()
  );

  return (
    <div className="min-h-screen bg-white">
      {/* Header */}
      <header className="border-b">
        <div className="max-w-[1920px] mx-auto px-4 sm:px-6 lg:px-12 xl:px-16 py-6">
          <Navigation />
          <p className="mt-4 text-lg text-gray-600">
            Strategic Insights from SEC Filings for Tech Companies
          </p>
        </div>
      </header>

      {/* Stats Bar */}
      <div className="bg-gray-50 border-b">
        <div className="max-w-[1920px] mx-auto px-4 sm:px-6 lg:px-12 xl:px-16 py-4">
          <div className="flex gap-8 text-sm">
            <Link href="/companies" className="hover:opacity-75 transition-opacity cursor-pointer">
              <span className="font-semibold text-gray-900">{companyCount}</span>
              <span className="text-gray-600 ml-1">Companies Tracked</span>
            </Link>
            <div>
              <span className="font-semibold text-gray-900">{filingCount}</span>
              <span className="text-gray-600 ml-1">Analyses Published</span>
            </div>
          </div>
        </div>
      </div>

      {/* Upcoming Filings Section */}
      <UpcomingFilings />

      {/* Recent Filings Carousel */}
      <RecentFilingsCarousel filings={recentFilings} />

      {/* Main Content */}
      <main className="max-w-[1920px] mx-auto px-4 sm:px-6 lg:px-12 xl:px-16 py-12">
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
            <LatestAnalysesFilter analyses={latestAnalyses} />
          </>
        )}
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
