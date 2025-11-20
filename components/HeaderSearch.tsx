'use client';

/**
 * Header Search Component
 *
 * Quick search dropdown for finding tracked companies in the navigation header
 */

import { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import { CompanyLogo } from '@/lib/company-logo';

interface Company {
  id: string;
  ticker: string;
  name: string;
  sector: string | null;
  metadata: Record<string, any> | null;
}

export function HeaderSearch() {
  const [searchQuery, setSearchQuery] = useState('');
  const [companies, setCompanies] = useState<Company[]>([]);
  const [filteredCompanies, setFilteredCompanies] = useState<Company[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const searchRef = useRef<HTMLDivElement>(null);

  // Fetch companies on mount
  useEffect(() => {
    async function fetchCompanies() {
      setIsLoading(true);
      try {
        const response = await fetch('/api/companies');
        const data = await response.json();
        if (data.success) {
          setCompanies(data.data);
        }
      } catch (error) {
        console.error('Error fetching companies:', error);
      } finally {
        setIsLoading(false);
      }
    }

    fetchCompanies();
  }, []);

  // Filter companies based on search query
  useEffect(() => {
    if (!searchQuery.trim()) {
      setFilteredCompanies([]);
      setIsOpen(false);
      return;
    }

    const query = searchQuery.toLowerCase().trim();
    const filtered = companies
      .filter(
        (company) =>
          company.ticker.toLowerCase().includes(query) ||
          company.name.toLowerCase().includes(query)
      )
      .slice(0, 8); // Limit to 8 results

    setFilteredCompanies(filtered);
    setIsOpen(filtered.length > 0);
  }, [searchQuery, companies]);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        searchRef.current &&
        !searchRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    }

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  // Handle keyboard navigation
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      setIsOpen(false);
      setSearchQuery('');
    }
  };

  return (
    <div ref={searchRef} className="relative">
      {/* Search Input */}
      <div className="relative">
        <input
          type="text"
          placeholder="Search companies..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          onFocus={() => searchQuery && setIsOpen(true)}
          onKeyDown={handleKeyDown}
          className="w-64 px-4 py-2 pr-10 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          disabled={isLoading}
        />
        <div className="absolute right-3 top-1/2 -translate-y-1/2">
          <svg
            className="w-4 h-4 text-gray-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
            />
          </svg>
        </div>
      </div>

      {/* Dropdown Results */}
      {isOpen && (
        <div className="absolute top-full mt-2 w-96 bg-white border border-gray-200 rounded-lg shadow-lg z-50 max-h-96 overflow-y-auto">
          {filteredCompanies.length === 0 ? (
            <div className="px-4 py-3 text-sm text-gray-500">
              No companies found
            </div>
          ) : (
            <div className="py-2">
              {filteredCompanies.map((company) => {
                const domain = company.metadata?.domain || null;

                return (
                  <Link
                    key={company.id}
                    href={`/${company.ticker.toLowerCase()}`}
                    onClick={() => {
                      setIsOpen(false);
                      setSearchQuery('');
                    }}
                    className="flex items-center gap-3 px-4 py-3 hover:bg-gray-50 transition-colors"
                  >
                    <CompanyLogo
                      domain={domain}
                      ticker={company.ticker}
                      size={32}
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-gray-900">
                          {company.ticker}
                        </span>
                        {company.sector && (
                          <span className="text-xs text-gray-500 px-2 py-0.5 bg-gray-100 rounded">
                            {company.sector}
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-gray-600 truncate">
                        {company.name}
                      </p>
                    </div>
                  </Link>
                );
              })}
            </div>
          )}

          {/* View All Link */}
          {filteredCompanies.length > 0 && (
            <div className="border-t">
              <Link
                href="/companies"
                onClick={() => {
                  setIsOpen(false);
                  setSearchQuery('');
                }}
                className="block px-4 py-3 text-sm text-center text-blue-600 hover:bg-gray-50 transition-colors"
              >
                View all companies →
              </Link>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
