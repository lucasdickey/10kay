'use client';

import React, { useEffect, useState } from 'react';
import { ExternalLink, FileText, TrendingUp, Calendar, AlertCircle } from 'lucide-react';
import Link from 'next/link';

interface LinkedFiling {
  filing_id: string;
  filing_type: string;
  filing_date: string;
  fiscal_year: number;
  fiscal_quarter: number | null;
}

interface IRDocument {
  id: string;
  title: string;
  document_url: string;
  document_type: string;
  published_at: string;
  summary: string | null;
  analysis_summary: string | null;
  relevance_score: number | null;
  key_topics: string[] | null;
  salient_takeaways: string[] | null;
  linked_filings: LinkedFiling[] | null;
}

interface RecentIRUpdatesProps {
  ticker: string;
  limit?: number;
}

export default function RecentIRUpdates({ ticker, limit = 5 }: RecentIRUpdatesProps) {
  const [documents, setDocuments] = useState<IRDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchIRUpdates = async () => {
      try {
        setLoading(true);
        const response = await fetch(
          `/api/companies/${ticker}/ir-documents?limit=${limit}`
        );

        if (!response.ok) {
          throw new Error('Failed to fetch IR updates');
        }

        const data = await response.json();
        setDocuments(data.documents || []);
      } catch (err) {
        console.error('Error fetching IR updates:', err);
        setError('Failed to load recent updates');
      } finally {
        setLoading(false);
      }
    };

    if (ticker) {
      fetchIRUpdates();
    }
  }, [ticker, limit]);

  if (loading) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6">
        <div className="animate-pulse">
          <div className="h-6 bg-gray-200 dark:bg-gray-700 rounded w-1/2 mb-4"></div>
          <div className="space-y-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="space-y-2">
                <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded"></div>
                <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-3/4"></div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
        <div className="flex items-center gap-2 text-red-800 dark:text-red-200">
          <AlertCircle className="h-5 w-5" />
          <span>{error}</span>
        </div>
      </div>
    );
  }

  if (documents.length === 0) {
    return null; // Don't show section if no updates
  }

  // Helper functions
  const getDocumentTypeIcon = (type: string) => {
    switch (type) {
      case 'press_release':
        return <FileText className="h-4 w-4" />;
      case 'earnings_presentation':
        return <TrendingUp className="h-4 w-4" />;
      default:
        return <FileText className="h-4 w-4" />;
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    });
  };

  const getFiscalPeriod = (filing: LinkedFiling) => {
    return filing.fiscal_quarter
      ? `Q${filing.fiscal_quarter} ${filing.fiscal_year}`
      : `FY ${filing.fiscal_year}`;
  };

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-1">
            Recent Investor Relations Updates
          </h2>
          <p className="text-gray-600 dark:text-gray-400 text-sm">
            Latest announcements and press releases
          </p>
        </div>
      </div>

      <div className="space-y-4">
        {documents.map((doc) => (
          <div
            key={doc.id}
            className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 hover:bg-gray-50 dark:hover:bg-gray-750 transition-colors"
          >
            {/* Header */}
            <div className="flex items-start gap-3 mb-2">
              <div className="text-blue-600 dark:text-blue-400 mt-1">
                {getDocumentTypeIcon(doc.document_type)}
              </div>
              <div className="flex-1 min-w-0">
                <a
                  href={doc.document_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-semibold text-gray-900 dark:text-white hover:text-blue-600 dark:hover:text-blue-400 inline-flex items-center gap-2 group"
                >
                  <span className="line-clamp-2">{doc.title}</span>
                  <ExternalLink className="h-3.5 w-3.5 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0" />
                </a>
                <div className="flex items-center gap-2 mt-1">
                  <Calendar className="h-3.5 w-3.5 text-gray-400" />
                  <span className="text-xs text-gray-500 dark:text-gray-400">
                    {formatDate(doc.published_at)}
                  </span>
                </div>
              </div>
            </div>

            {/* Summary */}
            {doc.analysis_summary && (
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-3 line-clamp-2">
                {doc.analysis_summary}
              </p>
            )}

            {/* Key Topics */}
            {doc.key_topics && doc.key_topics.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mb-3">
                {doc.key_topics.slice(0, 3).map((topic, idx) => (
                  <span
                    key={idx}
                    className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300"
                  >
                    {topic}
                  </span>
                ))}
                {doc.key_topics.length > 3 && (
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs text-gray-500">
                    +{doc.key_topics.length - 3} more
                  </span>
                )}
              </div>
            )}

            {/* Linked Filings */}
            {doc.linked_filings && doc.linked_filings.length > 0 && (
              <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
                <span>Related to:</span>
                <div className="flex flex-wrap gap-2">
                  {doc.linked_filings.slice(0, 2).map((filing, idx) => (
                    <Link
                      key={idx}
                      href={`/analysis/${filing.filing_id}`}
                      className="text-blue-600 dark:text-blue-400 hover:underline"
                    >
                      {filing.filing_type} {getFiscalPeriod(filing)}
                    </Link>
                  ))}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* View All Link */}
      {documents.length >= limit && (
        <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
          <a
            href={`/companies/${ticker}/ir-updates`}
            className="text-sm text-blue-600 dark:text-blue-400 hover:underline inline-flex items-center gap-1"
          >
            View all investor relations updates
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
        </div>
      )}
    </div>
  );
}
