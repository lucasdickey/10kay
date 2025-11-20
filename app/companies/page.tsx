/**
 * Tracked Companies Page
 *
 * Displays all companies being tracked by 10KAY with search and filter functionality
 */

import Link from 'next/link';
import { query } from '@/lib/db';
import { CompanyLogo } from '@/lib/company-logo';
import { Navigation } from '@/components/Navigation';
import { CompaniesFilter } from '@/components/CompaniesFilter';

interface CompanyWithStats {
  id: string;
  ticker: string;
  name: string;
  sector: string | null;
  enabled: boolean;
  metadata: Record<string, any> | null;
  filings_count: string;
  latest_filing_date: Date | null;
  latest_filing_type: string | null;
}

async function getTrackedCompanies(): Promise<CompanyWithStats[]> {
  return await query<CompanyWithStats>(
    `
    SELECT
      c.id,
      c.ticker,
      c.name,
      c.sector,
      c.enabled,
      c.metadata,
      COUNT(f.id) as filings_count,
      MAX(f.filing_date) as latest_filing_date,
      (
        SELECT f2.filing_type
        FROM filings f2
        WHERE f2.company_id = c.id
        ORDER BY f2.filing_date DESC
        LIMIT 1
      ) as latest_filing_type
    FROM companies c
    LEFT JOIN filings f ON c.id = f.company_id
    WHERE c.enabled = true
    GROUP BY c.id, c.ticker, c.name, c.sector, c.enabled, c.metadata
    ORDER BY c.name ASC
    `
  );
}

export default async function CompaniesPage() {
  const companies = await getTrackedCompanies();

  return (
    <div className="min-h-screen bg-white">
      {/* Header */}
      <header className="border-b">
        <div className="max-w-[1920px] mx-auto px-4 sm:px-6 lg:px-12 xl:px-16 py-6">
          <Navigation />
        </div>
      </header>

      {/* Page Header */}
      <div className="bg-gray-50 border-b">
        <div className="max-w-[1920px] mx-auto px-4 sm:px-6 lg:px-12 xl:px-16 py-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            Tracked Companies
          </h1>
          <p className="text-lg text-gray-600">
            {companies.length} tech companies monitored for SEC filing insights
          </p>
        </div>
      </div>

      {/* Main Content */}
      <main className="max-w-[1920px] mx-auto px-4 sm:px-6 lg:px-12 xl:px-16 py-12">
        <CompaniesFilter companies={companies} />
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
