"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import { CompanyLogo } from "@/lib/company-logo";

interface Analysis {
  id: string;
  slug: string;
  company_ticker: string;
  company_name: string;
  filing_type: string;
  filing_date: Date | string;
  key_takeaways: Record<string, any>;
  company_domain?: string | null;
  executive_summary?: string;
}

interface LatestAnalysesFilterProps {
  analyses: Analysis[];
}

type DateRangeFilter = "trailing_2_weeks" | "trailing_month" | "trailing_90_days" | "year_to_date";

/**
 * Simple fuzzy search implementation
 * Returns a score between 0 and 1 where 1 is a perfect match
 */
function fuzzySearch(query: string, text: string): number {
  const queryLower = query.toLowerCase();
  const textLower = text.toLowerCase();

  // Exact match gets highest score
  if (textLower === queryLower) return 1;

  // Substring match gets high score
  if (textLower.includes(queryLower)) return 0.8;

  // Check if all characters match in order
  let queryIdx = 0;
  let textIdx = 0;
  const matches: number[] = [];

  while (queryIdx < queryLower.length && textIdx < textLower.length) {
    if (queryLower[queryIdx] === textLower[textIdx]) {
      matches.push(textIdx);
      queryIdx++;
    }
    textIdx++;
  }

  if (queryIdx !== queryLower.length) return 0; // Not all characters matched

  // Calculate score based on how close the matches are and their position
  if (matches.length === 0) return 0;

  let score = 0.6; // Base score for partial match
  let consecutiveCount = 0;

  for (let i = 1; i < matches.length; i++) {
    if (matches[i] === matches[i - 1] + 1) {
      consecutiveCount++;
    }
  }

  // Bonus for consecutive matches
  score += (consecutiveCount / matches.length) * 0.2;

  // Bonus for early matches
  score += (1 - matches[0] / textLower.length) * 0.2;

  return Math.min(score, 0.9); // Cap at 0.9 for non-exact partial matches
}

/**
 * Get the date range boundaries based on the selected filter
 */
function getDateRangeBoundaries(filter: DateRangeFilter): { start: Date; end: Date } {
  const today = new Date();
  const end = today;

  let start: Date;

  switch (filter) {
    case "trailing_2_weeks":
      start = new Date(today);
      start.setDate(today.getDate() - 14);
      break;
    case "trailing_month":
      start = new Date(today);
      start.setMonth(today.getMonth() - 1);
      break;
    case "trailing_90_days":
      start = new Date(today);
      start.setDate(today.getDate() - 90);
      break;
    case "year_to_date":
      start = new Date(today.getFullYear(), 0, 1);
      break;
  }

  return { start, end };
}

function formatDate(date: Date | string): string {
  const d = new Date(date);
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function getSentimentBadge(keyTakeaways: Record<string, any>): { label: string; className: string } {
  const sentiment = keyTakeaways?.sentiment || 0;
  if (sentiment > 0.3) {
    return { label: "Positive", className: "bg-green-100 text-green-800" };
  } else if (sentiment < -0.3) {
    return { label: "Negative", className: "bg-red-100 text-red-800" };
  }
  return { label: "Neutral", className: "bg-gray-100 text-gray-800" };
}

function getSentimentHeaderColor(keyTakeaways: Record<string, any>): string {
  const sentiment = keyTakeaways?.sentiment || 0;
  if (sentiment > 0.3) {
    return "#ecfdf5"; // green-100
  } else if (sentiment < -0.3) {
    return "#fce7e6"; // red-100
  }
  return "#f9fafb"; // gray-50
}

function getSentimentBorderColor(keyTakeaways: Record<string, any>): string {
  const sentiment = keyTakeaways?.sentiment || 0;
  if (sentiment > 0.3) {
    return "#16a34a"; // green-600
  } else if (sentiment < -0.3) {
    return "#dc2626"; // red-600
  }
  return "#6b7280"; // gray-500
}

function getFilingTypeBadge(filingType: string): string {
  if (filingType === "10-K") {
    return "bg-gray-900 text-white px-2 py-0.5 rounded text-xs font-bold";
  } else if (filingType === "10-Q") {
    return "border-2 border-gray-900 text-gray-900 px-2 py-0.5 rounded text-xs font-semibold";
  }
  return "bg-gray-100 text-gray-800 px-2 py-0.5 rounded text-xs font-semibold";
}

function getFiscalPeriod(fiscalYear: number | null, fiscalQuarter: number | null): string {
  if (!fiscalYear) return "";
  if (fiscalQuarter) return `Q${fiscalQuarter} ${fiscalYear}`;
  return `FY ${fiscalYear}`;
}

export function LatestAnalysesFilter({ analyses }: LatestAnalysesFilterProps) {
  const [dateRangeFilter, setDateRangeFilter] = useState<DateRangeFilter>("trailing_month");
  const [searchQuery, setSearchQuery] = useState("");

  const filteredAnalyses = useMemo(() => {
    const { start, end } = getDateRangeBoundaries(dateRangeFilter);

    let filtered = analyses.filter((analysis) => {
      const filingDate = new Date(analysis.filing_date);
      return filingDate >= start && filingDate <= end;
    });

    // Apply fuzzy search if query exists
    if (searchQuery.trim()) {
      const scores = filtered.map((analysis) => {
        const tickerScore = fuzzySearch(searchQuery, analysis.company_ticker);
        const nameScore = fuzzySearch(searchQuery, analysis.company_name);
        const maxScore = Math.max(tickerScore, nameScore);
        return { analysis, score: maxScore };
      });

      filtered = scores
        .filter(({ score }) => score > 0) // Only include matches
        .sort(({ score: scoreA }, { score: scoreB }) => scoreB - scoreA) // Sort by relevance
        .map(({ analysis }) => analysis);
    }

    return filtered;
  }, [analyses, dateRangeFilter, searchQuery]);

  const dateRangeOptions: Array<{ value: DateRangeFilter; label: string }> = [
    { value: "trailing_2_weeks", label: "Trailing 2 Weeks" },
    { value: "trailing_month", label: "Trailing Month" },
    { value: "trailing_90_days", label: "Trailing 90 Days" },
    { value: "year_to_date", label: "Year to Date" },
  ];

  return (
    <>
      {/* Heading and Filter Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center gap-4 mb-8">
        <h2 className="text-2xl font-bold text-gray-900 whitespace-nowrap">Latest Analyses</h2>

        {/* Filter Controls */}
        <div className="flex flex-col sm:flex-row gap-4 flex-1">
          {/* Date Range Filter */}
          <select
            value={dateRangeFilter}
            onChange={(e) => setDateRangeFilter(e.target.value as DateRangeFilter)}
            className="px-4 py-2 border border-gray-300 rounded-lg bg-white text-gray-900 font-medium text-sm hover:border-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-colors"
          >
            {dateRangeOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>

          {/* Fuzzy Search Input */}
          <div className="flex-1 relative">
            <input
              type="text"
              placeholder="Search by ticker or company name..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg text-gray-900 placeholder-gray-500 font-medium text-sm hover:border-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-colors"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery("")}
                className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors"
                aria-label="Clear search"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Results Count */}
      {searchQuery && (
        <div className="mb-4 text-sm text-gray-600">
          Showing {filteredAnalyses.length} result{filteredAnalyses.length !== 1 ? "s" : ""}
        </div>
      )}

      {/* Grid of Cards */}
      {filteredAnalyses.length === 0 ? (
        <div className="text-center py-12">
          <svg
            className="w-12 h-12 mx-auto text-gray-400 mb-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
            />
          </svg>
          <h3 className="text-lg font-semibold text-gray-900 mb-1">No analyses found</h3>
          <p className="text-gray-600">
            {searchQuery
              ? "Try adjusting your search query or date range"
              : "No analyses available in this time period"}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
          {filteredAnalyses.map((analysis) => {
            const sentiment = getSentimentBadge(analysis.key_takeaways);
            const headline = analysis.key_takeaways?.headline || "";
            const summary = (analysis.executive_summary?.substring(0, 200) || "") + "...";

            const headerBgColor = getSentimentHeaderColor(analysis.key_takeaways);
            const borderColor = getSentimentBorderColor(analysis.key_takeaways);

            return (
              <Link
                key={analysis.id}
                href={`/${analysis.slug}`}
                className="block bg-white border rounded-lg overflow-hidden hover:shadow-lg transition-shadow"
                style={{ borderLeft: `6px solid ${borderColor}` }}
              >
                {/* Company Header */}
                <div
                  className="flex items-center gap-4 p-4 border-b"
                  style={{ backgroundColor: headerBgColor }}
                >
                  <CompanyLogo
                    ticker={analysis.company_ticker}
                    domain={analysis.company_domain}
                    size={24}
                    className="flex-shrink-0"
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                      <h3 className="text-lg font-bold text-gray-900 truncate max-w-[150px]">
                        {analysis.company_name}
                      </h3>
                      <span
                        className={`px-2 py-1 rounded text-xs font-semibold whitespace-nowrap ${sentiment.className}`}
                      >
                        {sentiment.label}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Content Section */}
                <div className="p-6">
                  {/* Filing Info */}
                  <div className="flex items-center gap-2 text-sm text-gray-500 mb-3">
                    <span className={getFilingTypeBadge(analysis.filing_type)}>
                      {analysis.filing_type}
                    </span>
                    <span>•</span>
                    <span>
                      {getFiscalPeriod(analysis.key_takeaways?.fiscal_year, analysis.key_takeaways?.fiscal_quarter)}
                    </span>
                    <span>•</span>
                    <span>{formatDate(analysis.filing_date)}</span>
                  </div>

                  {/* Headline */}
                  {headline && (
                    <h4 className="font-semibold text-gray-900 mb-2 line-clamp-2">
                      {headline}
                    </h4>
                  )}

                  {/* Bull/Bear Takeaways */}
                  {(analysis.key_takeaways?.bull_case || analysis.key_takeaways?.bear_case) && (
                    <div className="space-y-2 mb-3">
                      {analysis.key_takeaways.bull_case && (
                        <div className="flex items-start gap-2">
                          <svg
                            className="w-4 h-4 text-green-600 flex-shrink-0 mt-0.5"
                            fill="currentColor"
                            viewBox="0 0 20 20"
                          >
                            <path
                              fillRule="evenodd"
                              d="M12 7a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0V8.414l-4.293 4.293a1 1 0 01-1.414 0L8 10.414l-4.293 4.293a1 1 0 01-1.414-1.414l5-5a1 1 0 011.414 0L11 10.586 14.586 7H12z"
                              clipRule="evenodd"
                            />
                          </svg>
                          <p className="text-xs text-gray-700 leading-snug">
                            {analysis.key_takeaways.bull_case}
                          </p>
                        </div>
                      )}
                      {analysis.key_takeaways.bear_case && (
                        <div className="flex items-start gap-2">
                          <svg
                            className="w-4 h-4 text-red-600 flex-shrink-0 mt-0.5"
                            fill="currentColor"
                            viewBox="0 0 20 20"
                          >
                            <path
                              fillRule="evenodd"
                              d="M12 13a1 1 0 100 2h5a1 1 0 001-1v-5a1 1 0 10-2 0v2.586l-4.293-4.293a1 1 0 00-1.414 0L8 9.586l-4.293-4.293a1 1 0 00-1.414 1.414l5 5a1 1 0 001.414 0L11 9.414 14.586 13H12z"
                              clipRule="evenodd"
                            />
                          </svg>
                          <p className="text-xs text-gray-700 leading-snug">
                            {analysis.key_takeaways.bear_case}
                          </p>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Summary */}
                  <p className="text-sm text-gray-600 line-clamp-3">{summary}</p>
                </div>
              </Link>
            );
          })}
        </div>
      )}

    </>
  );
}
