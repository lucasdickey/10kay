'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';

interface UpcomingFiling {
  ticker: string;
  name: string;
  filingType: string;
  estimatedDate: string;
  daysUntil: number;
  fiscalPeriod: string;
}

interface UpcomingFilingsResponse {
  success: boolean;
  count: number;
  daysAhead: number;
  filings: UpcomingFiling[];
}

export default function UpcomingFilings() {
  const [filings, setFilings] = useState<UpcomingFiling[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchUpcomingFilings() {
      try {
        // Fetch filings within 90 days to capture Q4 filings (typically ~75-90 days out)
        const response = await fetch('/api/upcoming-filings?days=90&limit=8');
        if (!response.ok) {
          throw new Error('Failed to fetch upcoming filings');
        }
        const data: UpcomingFilingsResponse = await response.json();
        setFilings(data.filings);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'An error occurred');
      } finally {
        setLoading(false);
      }
    }

    fetchUpcomingFilings();
  }, []);

  if (loading) {
    return (
      <div className="w-full bg-gray-50 border-y">
        <div className="max-w-[1920px] mx-auto px-4 sm:px-6 lg:px-12 xl:px-16 py-4">
          <div className="flex items-center gap-2">
            <div className="h-4 w-4 rounded-full border-2 border-gray-600 border-t-transparent animate-spin" />
            <span className="text-sm text-gray-600">Loading upcoming filings...</span>
          </div>
        </div>
      </div>
    );
  }

  if (error || filings.length === 0) {
    return null; // Don't show anything if there's an error or no filings
  }

  return (
    <div className="w-full bg-gray-50 border-y">
      <div className="max-w-[1920px] mx-auto px-4 sm:px-6 lg:px-12 xl:px-16 py-4">
        <div className="flex items-center gap-4">
          {/* Label */}
          <div className="flex items-center gap-2 flex-shrink-0">
            <svg
              className="w-4 h-4 text-gray-700"
              fill="none"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            <span className="text-sm font-semibold text-gray-900">Estimated Upcoming Filings</span>
          </div>

          {/* Scrollable filings list */}
          <div className="flex-1 overflow-x-auto">
            <div className="flex gap-3 pb-1">
              {filings.map((filing) => (
                <Link
                  key={`${filing.ticker}-${filing.filingType}-${filing.fiscalPeriod}`}
                  href={`/${filing.ticker.toLowerCase()}`}
                  className="group flex items-center gap-2 px-3 py-1.5 bg-white rounded-md border border-gray-200 hover:border-gray-400 hover:shadow-md transition-all flex-shrink-0"
                >
                  {/* Ticker */}
                  <span className="text-sm font-semibold text-gray-900">
                    {filing.ticker}
                  </span>

                  {/* Filing type badge */}
                  <span className="text-xs px-1.5 py-0.5 bg-gray-100 text-gray-700 rounded font-semibold">
                    {filing.filingType}
                  </span>

                  {/* Days until */}
                  <span className="text-xs text-gray-500">
                    ~{filing.daysUntil}d
                  </span>
                </Link>
              ))}
            </div>
          </div>
        </div>

        {/* Small disclaimer */}
        <div className="mt-2 text-xs text-gray-500 italic">
          Estimated based on historical filing patterns and SEC deadlines
        </div>
      </div>
    </div>
  );
}
