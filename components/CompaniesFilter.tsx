'use client';

/**
 * Companies Filter Component
 *
 * Provides search and filtering functionality for tracked companies
 */

import { useState, useMemo } from 'react';
import Link from 'next/link';
import { CompanyLogo } from '@/lib/company-logo';

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

interface CompaniesFilterProps {
  companies: CompanyWithStats[];
}

export function CompaniesFilter({ companies }: CompaniesFilterProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [sectorFilter, setSectorFilter] = useState<string>('all');

  // Get unique sectors
  const sectors = useMemo(() => {
    const uniqueSectors = new Set(
      companies
        .map((c) => c.sector)
        .filter((s): s is string => s !== null && s !== '')
    );
    return Array.from(uniqueSectors).sort();
  }, [companies]);

  // Filter companies based on search and sector
  const filteredCompanies = useMemo(() => {
    return companies.filter((company) => {
      // Search filter (ticker or company name)
      const searchLower = searchQuery.toLowerCase().trim();
      const matchesSearch =
        !searchQuery ||
        company.ticker.toLowerCase().includes(searchLower) ||
        company.name.toLowerCase().includes(searchLower);

      // Sector filter
      const matchesSector =
        sectorFilter === 'all' || company.sector === sectorFilter;

      return matchesSearch && matchesSector;
    });
  }, [companies, searchQuery, sectorFilter]);

  // Format date
  const formatDate = (date: Date | null) => {
    if (!date) return 'No filings';
    return new Date(date).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  return (
    <div>
      {/* Search and Filter Controls */}
      <div className="mb-8 flex flex-col sm:flex-row gap-4">
        {/* Search Input */}
        <div className="flex-1">
          <input
            type="text"
            placeholder="Search by ticker or company name..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        {/* Sector Filter */}
        <div>
          <select
            value={sectorFilter}
            onChange={(e) => setSectorFilter(e.target.value)}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white"
          >
            <option value="all">All Sectors</option>
            {sectors.map((sector) => (
              <option key={sector} value={sector}>
                {sector}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Results Count */}
      <div className="mb-4 text-sm text-gray-600">
        Showing {filteredCompanies.length} of {companies.length} companies
      </div>

      {/* Companies Grid */}
      {filteredCompanies.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-gray-600">
            No companies found matching your search criteria.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredCompanies.map((company) => {
            const domain = company.metadata?.domain || null;

            return (
              <Link
                key={company.id}
                href={`/${company.ticker.toLowerCase()}`}
                className="block border rounded-lg p-6 hover:shadow-lg transition-shadow bg-white"
              >
                {/* Company Header */}
                <div className="flex items-start gap-4 mb-4">
                  <CompanyLogo
                    domain={domain}
                    ticker={company.ticker}
                    size={48}
                  />
                  <div className="flex-1 min-w-0">
                    <h2 className="text-xl font-semibold text-gray-900 mb-1">
                      {company.ticker}
                    </h2>
                    <p className="text-sm text-gray-600 line-clamp-2">
                      {company.name}
                    </p>
                  </div>
                </div>

                {/* Company Stats */}
                <div className="space-y-2 text-sm">
                  {company.sector && (
                    <div className="flex items-center justify-between">
                      <span className="text-gray-500">Sector:</span>
                      <span className="font-medium text-gray-900">
                        {company.sector}
                      </span>
                    </div>
                  )}

                  <div className="flex items-center justify-between">
                    <span className="text-gray-500">Filings Analyzed:</span>
                    <span className="font-medium text-gray-900">
                      {company.filings_count}
                    </span>
                  </div>

                  {company.latest_filing_date && (
                    <div className="flex items-center justify-between">
                      <span className="text-gray-500">Latest Filing:</span>
                      <span className="font-medium text-gray-900">
                        {company.latest_filing_type}{' '}
                        <span className="text-gray-500 font-normal">
                          ({formatDate(company.latest_filing_date)})
                        </span>
                      </span>
                    </div>
                  )}
                </div>

                {/* View Details Link */}
                <div className="mt-4 pt-4 border-t">
                  <span className="text-blue-600 hover:text-blue-700 text-sm font-medium">
                    View Analyses →
                  </span>
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
