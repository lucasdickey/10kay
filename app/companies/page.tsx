/**
 * Companies Page
 *
 * Displays all tracked companies with market cap and performance metrics
 */

import Link from 'next/link';
import { getAllCompaniesPerformance, CompanyPerformance } from '@/lib/performance';
import { CompanyLogo } from '@/lib/company-logo';
import { query } from '@/lib/db';

async function getCompanyDomains(): Promise<Map<string, string>> {
  const results = await query<{ ticker: string; domain: string }>(
    `SELECT ticker, metadata->>'domain' as domain FROM companies WHERE metadata->>'domain' IS NOT NULL`
  );

  const domains = new Map<string, string>();
  results.forEach(r => {
    if (r.domain) {
      domains.set(r.ticker, r.domain);
    }
  });

  return domains;
}

function PerformanceIndicator({ value, label }: { value: number | null; label: string }) {
  if (value === null) {
    return (
      <div className="text-xs text-gray-400">
        {label}: N/A
      </div>
    );
  }

  const isPositive = value > 0;
  const isNeutral = value === 0;

  return (
    <div className="flex items-center gap-1 text-xs">
      <span className="text-gray-600">{label}:</span>
      <span className={`font-semibold ${isPositive ? 'text-green-600' : isNeutral ? 'text-gray-600' : 'text-red-600'}`}>
        {isPositive && '+'}{value.toFixed(2)}%
      </span>
      {!isNeutral && (
        <svg
          className={`w-3 h-3 ${isPositive ? 'text-green-600' : 'text-red-600'}`}
          fill="currentColor"
          viewBox="0 0 20 20"
        >
          {isPositive ? (
            <path
              fillRule="evenodd"
              d="M12 7a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0V8.414l-4.293 4.293a1 1 0 01-1.414 0L8 10.414l-4.293 4.293a1 1 0 01-1.414-1.414l5-5a1 1 0 011.414 0L11 10.586 14.586 7H12z"
              clipRule="evenodd"
            />
          ) : (
            <path
              fillRule="evenodd"
              d="M12 13a1 1 0 100 2h5a1 1 0 001-1v-5a1 1 0 10-2 0v2.586l-4.293-4.293a1 1 0 00-1.414 0L8 9.586l-4.293-4.293a1 1 0 00-1.414 1.414l5 5a1 1 0 001.414 0L11 9.414 14.586 13H12z"
              clipRule="evenodd"
            />
          )}
        </svg>
      )}
    </div>
  );
}

function ComparisonBadge({ value, label }: { value: number | null; label: string }) {
  if (value === null) {
    return null;
  }

  const isPositive = value > 0;
  const absValue = Math.abs(value);

  if (absValue < 0.1) {
    return null; // Don't show if difference is negligible
  }

  return (
    <div className={`text-xs px-2 py-1 rounded ${isPositive ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
      {isPositive ? '+' : ''}{value.toFixed(1)}% vs {label}
    </div>
  );
}

export default async function CompaniesPage() {
  const [performance, domains] = await Promise.all([
    getAllCompaniesPerformance(),
    getCompanyDomains(),
  ]);

  // Sort by market cap descending (nulls last)
  const sortedCompanies = [...performance].sort((a, b) => {
    if (a.marketCap === null) return 1;
    if (b.marketCap === null) return -1;
    return Number(b.marketCap) - Number(a.marketCap);
  });

  // Calculate some stats
  const companiesWithData = performance.filter(c => c.priceChange7d !== null).length;
  const averageChange = performance
    .filter(c => c.priceChange7d !== null)
    .reduce((sum, c) => sum + (c.priceChange7d || 0), 0) / (companiesWithData || 1);

  return (
    <div className="min-h-screen bg-white">
      {/* Header */}
      <header className="border-b bg-white sticky top-0 z-10 shadow-sm">
        <div className="max-w-[1920px] mx-auto px-4 sm:px-6 lg:px-12 xl:px-16 py-6">
          <Link href="/" className="text-sm text-blue-600 hover:text-blue-700 mb-4 inline-flex items-center gap-2">
            <img src="/logo.png" alt="10KAY" className="w-5 h-5" />
            ← Back to All Analyses
          </Link>
          <h1 className="text-3xl font-bold text-gray-900">
            Tracked Companies
          </h1>
          <p className="text-gray-600 mt-2">
            Market capitalization and 7-day performance metrics
          </p>
        </div>
      </header>

      {/* Stats Bar */}
      <div className="bg-gray-50 border-b">
        <div className="max-w-[1920px] mx-auto px-4 sm:px-6 lg:px-12 xl:px-16 py-4">
          <div className="flex gap-8 text-sm">
            <div>
              <span className="font-semibold text-gray-900">{performance.length}</span>
              <span className="text-gray-600 ml-1">Companies Tracked</span>
            </div>
            <div>
              <span className="font-semibold text-gray-900">{companiesWithData}</span>
              <span className="text-gray-600 ml-1">With Market Data</span>
            </div>
            <div>
              <span className="text-gray-600">Avg 7d Change: </span>
              <span className={`font-semibold ${averageChange > 0 ? 'text-green-600' : averageChange < 0 ? 'text-red-600' : 'text-gray-900'}`}>
                {averageChange > 0 && '+'}{averageChange.toFixed(2)}%
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <main className="max-w-[1920px] mx-auto px-4 sm:px-6 lg:px-12 xl:px-16 py-12">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {sortedCompanies.map((company) => {
            const domain = domains.get(company.ticker);

            return (
              <Link
                key={company.ticker}
                href={`/${company.ticker}`}
                className="block bg-white border rounded-lg overflow-hidden hover:shadow-lg transition-shadow"
              >
                {/* Company Header */}
                <div className="flex items-center gap-3 p-4 bg-gray-50 border-b">
                  <CompanyLogo
                    ticker={company.ticker}
                    domain={domain}
                    size={32}
                    className="flex-shrink-0"
                  />
                  <div className="flex-1 min-w-0">
                    <h3 className="text-lg font-bold text-gray-900 truncate">
                      {company.ticker}
                    </h3>
                    <p className="text-xs text-gray-600 truncate">
                      {company.companyName}
                    </p>
                  </div>
                </div>

                {/* Performance Section */}
                <div className="p-4 space-y-3">
                  {/* Market Cap */}
                  {company.marketCapFormatted && (
                    <div>
                      <div className="text-xs text-gray-500 uppercase tracking-wide mb-1">
                        Market Cap
                      </div>
                      <div className="text-2xl font-bold text-gray-900">
                        {company.marketCapFormatted}
                      </div>
                      {company.lastUpdated && (
                        <div className="text-xs text-gray-400 mt-1">
                          Updated {new Date(company.lastUpdated).toLocaleDateString()}
                        </div>
                      )}
                    </div>
                  )}

                  {/* 7-Day Performance */}
                  {company.priceChange7d !== null && (
                    <div className="pt-3 border-t">
                      <PerformanceIndicator value={company.priceChange7d} label="7d Change" />
                    </div>
                  )}

                  {/* Comparisons */}
                  {(company.vsAggregate !== null || company.vsSector !== null) && (
                    <div className="flex flex-wrap gap-2 pt-2">
                      <ComparisonBadge value={company.vsAggregate} label="Market" />
                      <ComparisonBadge value={company.vsSector} label="Sector" />
                    </div>
                  )}

                  {/* Sector Badge */}
                  {company.sector && (
                    <div className="pt-2">
                      <span className="inline-block px-2 py-1 text-xs bg-blue-50 text-blue-700 rounded">
                        {company.sector}
                      </span>
                    </div>
                  )}

                  {/* No Data State */}
                  {!company.marketCapFormatted && company.priceChange7d === null && (
                    <div className="text-center py-4 text-sm text-gray-400">
                      No market data available
                    </div>
                  )}
                </div>
              </Link>
            );
          })}
        </div>
      </main>
    </div>
  );
}
