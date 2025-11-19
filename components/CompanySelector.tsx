'use client';

import { useState, useEffect } from 'react';
import { CompanyInfo } from '@/lib/types';

interface CompanySelectorProps {
  selectedCompanyIds: string[];
  onChange: (companyIds: string[]) => void;
}

// Company categories for grouping
const CATEGORIES = {
  'Mega-Cap Tech': ['AAPL', 'MSFT', 'GOOGL', 'GOOG', 'AMZN', 'META', 'NVDA', 'TSLA'],
  'Cloud & SaaS': ['SNOW', 'SHOP', 'NOW', 'CRM', 'WDAY'],
  'Semiconductors': ['NVDA', 'AMD', 'INTC', 'QCOM', 'TSM', 'ASML', 'AVGO'],
  'Security': ['PANW', 'CRWD', 'ZS', 'OKTA'],
  'Fintech': ['PYPL', 'SQ', 'SPOT', 'UBER', 'DASH', 'SOFI'],
  'Dev Tools & Platforms': ['MDB', 'TEAM', 'U', 'PINS'],
};

export function CompanySelector({ selectedCompanyIds, onChange }: CompanySelectorProps) {
  const [companies, setCompanies] = useState<CompanyInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(
    new Set(Object.keys(CATEGORIES))
  );

  useEffect(() => {
    fetchCompanies();
  }, []);

  async function fetchCompanies() {
    try {
      const response = await fetch('/api/companies');
      const result = await response.json();
      if (result.success) {
        setCompanies(result.data);
      }
    } catch (error) {
      console.error('Error fetching companies:', error);
    } finally {
      setLoading(false);
    }
  }

  function toggleCompany(companyId: string) {
    if (selectedCompanyIds.includes(companyId)) {
      onChange(selectedCompanyIds.filter(id => id !== companyId));
    } else {
      onChange([...selectedCompanyIds, companyId]);
    }
  }

  function selectAllInCategory(category: string) {
    const categoryTickers = CATEGORIES[category as keyof typeof CATEGORIES];
    const categoryCompanies = companies.filter(c => categoryTickers.includes(c.ticker));
    const categoryIds = categoryCompanies.map(c => c.id);

    // Add all companies from this category
    const newSelection = new Set([...selectedCompanyIds, ...categoryIds]);
    onChange(Array.from(newSelection));
  }

  function deselectAllInCategory(category: string) {
    const categoryTickers = CATEGORIES[category as keyof typeof CATEGORIES];
    const categoryCompanies = companies.filter(c => categoryTickers.includes(c.ticker));
    const categoryIds = new Set(categoryCompanies.map(c => c.id));

    // Remove all companies from this category
    onChange(selectedCompanyIds.filter(id => !categoryIds.has(id)));
  }

  function toggleCategory(category: string) {
    const newExpanded = new Set(expandedCategories);
    if (newExpanded.has(category)) {
      newExpanded.delete(category);
    } else {
      newExpanded.add(category);
    }
    setExpandedCategories(newExpanded);
  }

  function getCategoryCompanies(category: string): CompanyInfo[] {
    const categoryTickers = CATEGORIES[category as keyof typeof CATEGORIES];
    return companies.filter(c => categoryTickers.includes(c.ticker));
  }

  function getFilteredCompanies(): CompanyInfo[] {
    if (!searchTerm) return [];
    return companies.filter(c =>
      c.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      c.ticker.toLowerCase().includes(searchTerm.toLowerCase())
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="text-gray-600">Loading companies...</div>
      </div>
    );
  }

  const filteredCompanies = getFilteredCompanies();
  const showCategories = !searchTerm;

  return (
    <div className="space-y-4">
      {/* Search */}
      <div className="relative">
        <input
          type="text"
          placeholder="Search companies..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        {searchTerm && (
          <button
            onClick={() => setSearchTerm('')}
            className="absolute right-3 top-2.5 text-gray-400 hover:text-gray-600"
          >
            ✕
          </button>
        )}
      </div>

      {/* Summary */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
        <p className="text-sm text-blue-800">
          <strong>{selectedCompanyIds.length}</strong> of <strong>{companies.length}</strong> companies selected
        </p>
      </div>

      {/* Search Results */}
      {!showCategories && (
        <div className="space-y-2">
          {filteredCompanies.length === 0 ? (
            <p className="text-sm text-gray-500 text-center py-4">No companies found</p>
          ) : (
            filteredCompanies.map((company) => (
              <label
                key={company.id}
                className="flex items-center gap-3 p-3 border rounded-lg hover:bg-gray-50 cursor-pointer transition-colors"
              >
                <input
                  type="checkbox"
                  checked={selectedCompanyIds.includes(company.id)}
                  onChange={() => toggleCompany(company.id)}
                  className="w-5 h-5 text-blue-600 rounded focus:ring-blue-500"
                />
                <div className="flex-1">
                  <div className="font-medium text-gray-900">{company.name}</div>
                  <div className="text-sm text-gray-600">{company.ticker}</div>
                </div>
              </label>
            ))
          )}
        </div>
      )}

      {/* Categories */}
      {showCategories && (
        <div className="space-y-3">
          {Object.entries(CATEGORIES).map(([category, _]) => {
            const categoryCompanies = getCategoryCompanies(category);
            const selectedInCategory = categoryCompanies.filter(c =>
              selectedCompanyIds.includes(c.id)
            ).length;
            const isExpanded = expandedCategories.has(category);

            return (
              <div key={category} className="border rounded-lg">
                {/* Category Header */}
                <div className="bg-gray-50 p-3 flex items-center justify-between">
                  <button
                    onClick={() => toggleCategory(category)}
                    className="flex items-center gap-2 flex-1 text-left"
                  >
                    <span className="text-lg">{isExpanded ? '▼' : '▶'}</span>
                    <span className="font-semibold text-gray-900">{category}</span>
                    <span className="text-sm text-gray-600">
                      ({selectedInCategory}/{categoryCompanies.length})
                    </span>
                  </button>
                  <div className="flex gap-2">
                    <button
                      onClick={() => selectAllInCategory(category)}
                      className="text-xs px-2 py-1 text-blue-600 hover:bg-blue-50 rounded"
                    >
                      Select All
                    </button>
                    <button
                      onClick={() => deselectAllInCategory(category)}
                      className="text-xs px-2 py-1 text-gray-600 hover:bg-gray-100 rounded"
                    >
                      Clear
                    </button>
                  </div>
                </div>

                {/* Category Companies */}
                {isExpanded && (
                  <div className="p-3 space-y-2">
                    {categoryCompanies.map((company) => (
                      <label
                        key={company.id}
                        className="flex items-center gap-3 p-2 hover:bg-gray-50 rounded cursor-pointer transition-colors"
                      >
                        <input
                          type="checkbox"
                          checked={selectedCompanyIds.includes(company.id)}
                          onChange={() => toggleCompany(company.id)}
                          className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
                        />
                        <div className="flex-1">
                          <span className="font-medium text-gray-900">{company.name}</span>
                          <span className="text-sm text-gray-600 ml-2">({company.ticker})</span>
                        </div>
                      </label>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
