/**
 * Companies Page
 *
 * Displays all tracked companies with market cap, performance metrics,
 * and search/filter functionality (merged from Issues #32 and #33)
 */

import { getAllCompaniesPerformance } from '@/lib/performance';
import { query } from '@/lib/db';
import { Navigation } from '@/components/Navigation';
import { CompaniesFilter } from '@/components/CompaniesFilterWithPerformance';

async function getTotalFilingsCount(): Promise<number> {
  const result = await query<{ count: string }>(
    'SELECT COUNT(DISTINCT c.id) as count FROM content c WHERE c.blog_html IS NOT NULL'
  );
  return parseInt(result[0]?.count || '0');
}

export default async function CompaniesPage() {
  const [performance, totalFilingsCount] = await Promise.all([
    getAllCompaniesPerformance(),
    getTotalFilingsCount(),
  ]);

  // Calculate some stats
  const companiesWithData = performance.filter(c => c.currentPrice !== null || c.marketCap !== null).length;
  const companiesWithChange = performance.filter(c => c.priceChange7d !== null);
  const averageChange = companiesWithChange.length > 0
    ? companiesWithChange.reduce((sum, c) => sum + (c.priceChange7d || 0), 0) / companiesWithChange.length
    : 0;

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
          <p className="text-lg text-gray-600 mb-4">
            {performance.length} tech companies monitored for SEC filing insights
          </p>

          {/* Stats */}
          <div className="flex gap-8 text-sm flex-wrap">
            <div>
              <span className="font-semibold text-gray-900">{performance.length}</span>
              <span className="text-gray-600 ml-1">Companies Tracked</span>
            </div>
            <div>
              <span className="font-semibold text-gray-900">{companiesWithData}</span>
              <span className="text-gray-600 ml-1">With Market Data</span>
            </div>
            <div>
              <span className="font-semibold text-gray-900">{totalFilingsCount}</span>
              <span className="text-gray-600 ml-1">Analyses Published</span>
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
        <CompaniesFilter companies={performance} totalFilingsCount={totalFilingsCount} />
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
