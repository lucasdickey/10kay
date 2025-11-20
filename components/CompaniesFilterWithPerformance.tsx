'use client';

/**
 * Companies Filter Component with Performance Metrics
 *
 * Provides search and filtering functionality for tracked companies
 * Enhanced with market cap and performance data
 */

import { useState, useMemo } from 'react';
import Link from 'next/link';
import { CompanyLogo } from '@/lib/company-logo';
import { CompanyPerformance } from '@/lib/performance';

interface CompaniesFilterProps {
  companies: CompanyPerformance[];
  totalFilingsCount: number;
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

export function CompaniesFilter({ companies, totalFilingsCount }: CompaniesFilterProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [sectorFilter, setSectorFilter] = useState<string>('all');
  const [sortBy, setSortBy] = useState<'marketCap' | 'performance' | 'name'>('marketCap');

  // Get unique sectors
  const sectors = useMemo(() => {
    const uniqueSectors = new Set(
      companies
        .map((c) => c.sector)
        .filter((s): s is string => s !== null && s !== '')
    );
    return Array.from(uniqueSectors).sort();
  }, [companies]);

  // Filter and sort companies
  const filteredAndSortedCompanies = useMemo(() => {
    // Filter
    let filtered = companies.filter((company) => {
      // Search filter (ticker or company name)
      const searchLower = searchQuery.toLowerCase().trim();
      const matchesSearch =
        !searchQuery ||
        company.ticker.toLowerCase().includes(searchLower) ||
        company.companyName.toLowerCase().includes(searchLower);

      // Sector filter
      const matchesSector =
        sectorFilter === 'all' || company.sector === sectorFilter;

      return matchesSearch && matchesSector;
    });

    // Sort
    filtered.sort((a, b) => {
      switch (sortBy) {
        case 'marketCap':
          if (a.marketCap === null) return 1;
          if (b.marketCap === null) return -1;
          return Number(b.marketCap) - Number(a.marketCap);
        case 'performance':
          if (a.priceChange7d === null) return 1;
          if (b.priceChange7d === null) return -1;
          return b.priceChange7d - a.priceChange7d;
        case 'name':
          return a.companyName.localeCompare(b.companyName);
        default:
          return 0;
      }
    });

    return filtered;
  }, [companies, searchQuery, sectorFilter, sortBy]);

  return (
    <div>
      {/* Search and Filter Controls */}
      <div className="mb-8 flex flex-col lg:flex-row gap-4">
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
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white"
          >
            <option value="all">All Sectors</option>
            {sectors.map((sector) => (
              <option key={sector} value={sector}>
                {sector}
              </option>
            ))}
          </select>
        </div>

        {/* Sort By */}
        <div>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as 'marketCap' | 'performance' | 'name')}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white"
          >
            <option value="marketCap">Sort by Market Cap</option>
            <option value="performance">Sort by Performance</option>
            <option value="name">Sort by Name</option>
          </select>
        </div>
      </div>

      {/* Results Count */}
      <div className="mb-4 text-sm text-gray-600">
        Showing {filteredAndSortedCompanies.length} of {companies.length} companies
      </div>

      {/* Companies Grid */}
      {filteredAndSortedCompanies.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-gray-600">
            No companies found matching your search criteria.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {filteredAndSortedCompanies.map((company) => {
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
                    domain={company.sector || undefined}
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
      )}
    </div>
  );
}
