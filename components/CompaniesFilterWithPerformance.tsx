'use client';

/**
 * Companies Filter Component with Performance Metrics
 *
 * Provides search and filtering functionality for tracked companies
 * Enhanced with market cap and performance data
 */

import { useState, useMemo, useRef, useEffect } from 'react';
import Link from 'next/link';
import { CompanyLogo } from '@/lib/company-logo';
import { CompanyPerformance } from '@/lib/performance';
import { InfoTooltip } from '@/components/InfoTooltip';

/**
 * Generates a sector code from the first word of the sector name
 * Examples: "Semiconductors" → "SEMI", "Consumer Discretionary" → "CONS"
 */
function getSectorCode(sector: string): string {
  if (!sector) return '';
  return sector.split(' ')[0].substring(0, 4).toUpperCase();
}

interface CompaniesFilterProps {
  companies: CompanyPerformance[];
  totalFilingsCount: number;
}

function PerformanceIndicator({
  value,
  label,
  tooltip,
}: {
  value: number | string | null;
  label: string;
  tooltip?: string;
}) {
  if (value === null) {
    return (
      <div className="text-xs text-gray-400">
        {label}: N/A
      </div>
    );
  }

  const numValue = typeof value === 'string' ? parseFloat(value) : value;
  const isPositive = numValue > 0;
  const isNeutral = numValue === 0;

  return (
    <div className="flex items-center gap-1 text-xs">
      <span className="text-gray-600">
        {label}:
        {tooltip && <InfoTooltip label={label} info={tooltip} iconClassName="w-3 h-3" />}
      </span>
      <span className={`font-semibold ${isPositive ? 'text-green-600' : isNeutral ? 'text-gray-600' : 'text-red-600'}`}>
        {isPositive && '+'}{numValue.toFixed(2)}%
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

function ComparisonBadge({
  value,
  label,
  tooltip,
}: {
  value: number | string | null;
  label: string;
  tooltip?: string;
}) {
  if (value === null) {
    return null;
  }

  const numValue = typeof value === 'string' ? parseFloat(value) : value;
  const isPositive = numValue > 0;
  const absValue = Math.abs(numValue);

  if (absValue < 0.1) {
    return null; // Don't show if difference is negligible
  }

  return (
    <div className={`text-xs px-2 py-1 rounded inline-flex items-center gap-1 ${isPositive ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
      <span>
        {isPositive ? '+' : ''}{numValue.toFixed(1)}% vs {label}
      </span>
      {tooltip && <InfoTooltip label={`${label} Comparison`} info={tooltip} iconClassName="w-3 h-3" />}
    </div>
  );
}

export function CompaniesFilter({ companies, totalFilingsCount }: CompaniesFilterProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedSectors, setSelectedSectors] = useState<Set<string>>(new Set());
  const [showSectorDropdown, setShowSectorDropdown] = useState(false);
  const [sortBy, setSortBy] = useState<'marketCap' | 'performance' | 'name'>('marketCap');
  const sectorDropdownRef = useRef<HTMLDivElement>(null);

  // Get unique sectors
  const sectors = useMemo(() => {
    const uniqueSectors = new Set(
      companies
        .map((c) => c.sector)
        .filter((s): s is string => s !== null && s !== '')
    );
    return Array.from(uniqueSectors).sort();
  }, [companies]);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (sectorDropdownRef.current && !sectorDropdownRef.current.contains(event.target as Node)) {
        setShowSectorDropdown(false);
      }
    };

    if (showSectorDropdown) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [showSectorDropdown]);

  // Handle sector checkbox toggle
  const toggleSector = (sector: string) => {
    setSelectedSectors((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(sector)) {
        newSet.delete(sector);
      } else {
        newSet.add(sector);
      }
      return newSet;
    });
  };

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

      // Sector filter (if no sectors selected, show all)
      const matchesSector = selectedSectors.size === 0 || (company.sector && selectedSectors.has(company.sector));

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
          const aPerf = typeof a.priceChange7d === 'string' ? parseFloat(a.priceChange7d) : a.priceChange7d;
          const bPerf = typeof b.priceChange7d === 'string' ? parseFloat(b.priceChange7d) : b.priceChange7d;
          return bPerf - aPerf;
        case 'name':
          return a.companyName.localeCompare(b.companyName);
        default:
          return 0;
      }
    });

    return filtered;
  }, [companies, searchQuery, selectedSectors, sortBy]);

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

        {/* Sector Filter - Multi-Select Dropdown */}
        <div ref={sectorDropdownRef} className="relative">
          <button
            onClick={() => setShowSectorDropdown(!showSectorDropdown)}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg bg-white text-left focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent hover:border-gray-400 transition-colors flex items-center justify-between"
          >
            <span className="text-gray-700">
              {selectedSectors.size === 0 ? 'All Sectors' : `${selectedSectors.size} Sector${selectedSectors.size !== 1 ? 's' : ''} Selected`}
            </span>
            <svg
              className={`w-4 h-4 text-gray-600 transition-transform ${showSectorDropdown ? 'rotate-180' : ''}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
            </svg>
          </button>

          {/* Dropdown Menu */}
          {showSectorDropdown && (
            <div className="absolute top-full left-0 right-0 mt-2 bg-white border border-gray-300 rounded-lg shadow-lg z-50 max-h-80 overflow-y-auto">
              {/* Select All / Clear All Options */}
              <div className="sticky top-0 bg-white border-b border-gray-200 p-3 space-y-2">
                <button
                  onClick={() => setSelectedSectors(new Set(sectors))}
                  className="w-full text-left px-3 py-2 text-sm text-blue-600 hover:bg-blue-50 rounded transition-colors"
                >
                  ✓ Select All
                </button>
                <button
                  onClick={() => setSelectedSectors(new Set())}
                  className="w-full text-left px-3 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded transition-colors"
                >
                  ✕ Clear All
                </button>
              </div>

              {/* Sector Checkboxes */}
              <div className="p-2">
                {sectors.map((sector) => (
                  <label
                    key={sector}
                    className="flex items-center gap-3 px-3 py-2 rounded hover:bg-gray-50 cursor-pointer transition-colors group"
                  >
                    <input
                      type="checkbox"
                      checked={selectedSectors.has(sector)}
                      onChange={() => toggleSector(sector)}
                      className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-2 focus:ring-blue-500 cursor-pointer accent-blue-600"
                    />
                    <span className="text-sm text-gray-700 group-hover:text-gray-900 flex-1">{sector}</span>
                    <span className="text-xs text-gray-400">
                      {companies.filter((c) => c.sector === sector).length}
                    </span>
                  </label>
                ))}
              </div>
            </div>
          )}
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
                className="block bg-white border rounded-lg hover:shadow-lg transition-shadow"
              >
                {/* Company Header */}
                <div className="flex items-start gap-3 p-4 bg-gray-50 border-b">
                  <CompanyLogo
                    ticker={company.ticker}
                    domain={company.sector || undefined}
                    size={32}
                    className="flex-shrink-0 mt-1"
                  />
                  <div className="flex-1 min-w-0">
                    <h3 className="text-lg font-bold text-gray-900 truncate">
                      {company.ticker}
                    </h3>
                    <div className="flex items-center gap-1.5 mt-1">
                      <p className="text-xs text-gray-600 truncate flex-1">
                        {company.companyName}
                      </p>
                      {company.sector && (
                        <InfoTooltip label="Sector" info={company.sector} position="top">
                          <span className="inline-block px-2 py-0.5 text-xs font-semibold bg-blue-100 text-blue-700 rounded hover:bg-blue-200 transition-colors">
                            {getSectorCode(company.sector)}
                          </span>
                        </InfoTooltip>
                      )}
                    </div>
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
                      <PerformanceIndicator
                        value={company.priceChange7d}
                        label="7d Δ"
                        tooltip="Price change over the past 7 calendar days (Nov 17 vs Nov 24)"
                      />
                    </div>
                  )}

                  {/* Comparisons */}
                  {(company.vsAggregate !== null || company.vsSector !== null) && (
                    <div className="flex flex-nowrap gap-2 pt-2">
                      <ComparisonBadge
                        value={company.vsAggregate}
                        label="Index"
                        tooltip="Performance vs. the average of all 96 tracked companies"
                      />
                      <ComparisonBadge
                        value={company.vsSector}
                        label="Sector"
                        tooltip={`Performance vs. other companies in the ${company.sector || 'same sector'}`}
                      />
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
