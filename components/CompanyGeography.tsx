/**
 * CompanyGeography Component
 *
 * Displays geographic information about where the company operates
 * and offers its services, including headquarters and regional presence
 */

import { CompanyGeography as GeographyData } from '@/lib/company-types';

interface CompanyGeographyProps {
  geography?: GeographyData | null;
}

export function CompanyGeography({ geography }: CompanyGeographyProps) {
  // Don't render if no geography data
  if (!geography || (!geography.headquarters && !geography.operates_in && !geography.revenue_by_region)) {
    return null;
  }

  const hasRevenueBreakdown = geography.revenue_by_region && Object.keys(geography.revenue_by_region).length > 0;

  return (
    <div className="bg-white border rounded-lg p-6 shadow-sm">
      <h2 className="text-xl font-bold text-gray-900 mb-6">Geographic Presence</h2>

      {/* Headquarters */}
      {geography.headquarters && (
        <div className="mb-6">
          <div className="flex items-center gap-2 mb-2">
            <svg className="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
            </svg>
            <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Headquarters</div>
          </div>
          <div className="text-base font-semibold text-gray-900 ml-7">{geography.headquarters}</div>
        </div>
      )}

      {/* Operating Regions */}
      {geography.operates_in && geography.operates_in.length > 0 && (
        <div className="mb-6">
          <div className="flex items-center gap-2 mb-3">
            <svg className="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
              Operating Regions ({geography.operates_in.length})
            </div>
          </div>

          <div className="ml-7 flex flex-wrap gap-2">
            {geography.operates_in.map((region, index) => (
              <span
                key={index}
                className="inline-flex items-center px-3 py-1.5 rounded-full text-sm font-medium bg-blue-100 text-blue-800 border border-blue-200"
              >
                {region}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Revenue by Region */}
      {hasRevenueBreakdown && (
        <div>
          <div className="flex items-center gap-2 mb-3">
            <svg className="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
            <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
              Revenue by Region
            </div>
          </div>

          <div className="ml-7 space-y-3">
            {Object.entries(geography.revenue_by_region || {}).map(([region, percentage]) => (
              <div key={region}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-medium text-gray-900">{region}</span>
                  <span className="text-sm font-semibold text-gray-900">{percentage}%</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-blue-600 h-2 rounded-full transition-all"
                    style={{ width: `${percentage}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
