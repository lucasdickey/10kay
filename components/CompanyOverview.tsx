/**
 * CompanyOverview Component
 *
 * Displays company description, website, and key characteristics
 * including sector, employee count, revenue, and R&D spend
 */

import { CompanyMetadata, formatCurrency, formatEmployeeCount } from '@/lib/company-types';

interface CompanyOverviewProps {
  ticker: string;
  name: string;
  metadata?: CompanyMetadata | null;
}

export function CompanyOverview({ ticker, name, metadata }: CompanyOverviewProps) {
  const characteristics = metadata?.characteristics;
  const description = metadata?.description;
  const website = metadata?.website;

  // If no data is available, don't render the component
  if (!description && !website && !characteristics) {
    return null;
  }

  return (
    <div className="bg-white border rounded-lg p-6 shadow-sm">
      <h2 className="text-xl font-bold text-gray-900 mb-4">Company Overview</h2>

      {/* Company Description */}
      {description && (
        <div className="mb-6">
          <p className="text-gray-700 leading-relaxed">{description}</p>
        </div>
      )}

      {/* Website */}
      {website && (
        <div className="mb-6">
          <div className="flex items-center gap-2">
            <svg className="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
            </svg>
            <a
              href={website}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 hover:text-blue-700 hover:underline font-medium"
            >
              {website.replace(/^https?:\/\//, '')}
            </a>
          </div>
        </div>
      )}

      {/* Company Characteristics */}
      {characteristics && (
        <div>
          <h3 className="text-sm font-semibold text-gray-900 mb-3 uppercase tracking-wide">
            Key Characteristics
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {/* Sector */}
            {characteristics.sector && (
              <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                <div className="text-xs text-gray-500 mb-1 uppercase tracking-wide">Sector</div>
                <div className="text-sm font-semibold text-gray-900">{characteristics.sector}</div>
              </div>
            )}

            {/* Employee Count */}
            {characteristics.employee_count && (
              <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                <div className="text-xs text-gray-500 mb-1 uppercase tracking-wide">Employees</div>
                <div className="text-sm font-semibold text-gray-900">
                  {formatEmployeeCount(characteristics.employee_count)}
                </div>
              </div>
            )}

            {/* Founded Year */}
            {characteristics.founded_year && (
              <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                <div className="text-xs text-gray-500 mb-1 uppercase tracking-wide">Founded</div>
                <div className="text-sm font-semibold text-gray-900">{characteristics.founded_year}</div>
              </div>
            )}

            {/* Revenue TTM */}
            {characteristics.revenue_ttm && (
              <div className="bg-blue-50 rounded-lg p-4 border border-blue-200">
                <div className="text-xs text-blue-600 mb-1 uppercase tracking-wide">Revenue (TTM)</div>
                <div className="text-sm font-semibold text-blue-900">
                  {formatCurrency(characteristics.revenue_ttm)}
                </div>
              </div>
            )}

            {/* Revenue Prior Year */}
            {characteristics.revenue_prior_year && (
              <div className="bg-blue-50 rounded-lg p-4 border border-blue-200">
                <div className="text-xs text-blue-600 mb-1 uppercase tracking-wide">Revenue (Prior Year)</div>
                <div className="text-sm font-semibold text-blue-900">
                  {formatCurrency(characteristics.revenue_prior_year)}
                </div>
              </div>
            )}

            {/* R&D Spend TTM */}
            {characteristics.r_and_d_spend_ttm && (
              <div className="bg-purple-50 rounded-lg p-4 border border-purple-200">
                <div className="text-xs text-purple-600 mb-1 uppercase tracking-wide">R&D Spend (TTM)</div>
                <div className="text-sm font-semibold text-purple-900">
                  {formatCurrency(characteristics.r_and_d_spend_ttm)}
                </div>
              </div>
            )}

            {/* R&D Spend Prior Year */}
            {characteristics.r_and_d_spend_prior_year && (
              <div className="bg-purple-50 rounded-lg p-4 border border-purple-200">
                <div className="text-xs text-purple-600 mb-1 uppercase tracking-wide">R&D Spend (Prior Year)</div>
                <div className="text-sm font-semibold text-purple-900">
                  {formatCurrency(characteristics.r_and_d_spend_prior_year)}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
