'use client';

import React, { useEffect, useState } from 'react';
import { ExternalLink, FileText, TrendingUp, AlertCircle, CheckCircle } from 'lucide-react';

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
  time_delta_hours: number;
  window_type: 'pre_filing' | 'post_filing' | 'concurrent';
}

interface IRDocumentsProps {
  filingId: string;
}

export default function IRDocuments({ filingId }: IRDocumentsProps) {
  const [documents, setDocuments] = useState<IRDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchIRDocuments = async () => {
      try {
        setLoading(true);
        const response = await fetch(`/api/filings/${filingId}/ir-documents`);

        if (!response.ok) {
          throw new Error('Failed to fetch IR documents');
        }

        const data = await response.json();
        setDocuments(data.documents || []);
      } catch (err) {
        console.error('Error fetching IR documents:', err);
        setError('Failed to load investor relations updates');
      } finally {
        setLoading(false);
      }
    };

    if (filingId) {
      fetchIRDocuments();
    }
  }, [filingId]);

  if (loading) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6">
        <div className="animate-pulse">
          <div className="h-6 bg-gray-200 dark:bg-gray-700 rounded w-1/3 mb-4"></div>
          <div className="space-y-3">
            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded"></div>
            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-5/6"></div>
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
    return null; // Don't show anything if no IR documents
  }

  // Helper functions
  const getRelevanceBadge = (score: number | null) => {
    if (!score) return null;

    if (score >= 0.9) {
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300">
          <CheckCircle className="h-3 w-3 mr-1" />
          Highly Relevant
        </span>
      );
    } else if (score >= 0.7) {
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300">
          <TrendingUp className="h-3 w-3 mr-1" />
          Moderately Relevant
        </span>
      );
    } else if (score >= 0.5) {
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300">
          Somewhat Relevant
        </span>
      );
    }
    return null;
  };

  const getTimingBadge = (windowType: string, deltaHours: number) => {
    const daysBeforeAfter = Math.abs(deltaHours / 24).toFixed(1);
    const timing = windowType === 'pre_filing'
      ? `${daysBeforeAfter} days before`
      : windowType === 'post_filing'
      ? `${daysBeforeAfter} days after`
      : 'Same day';

    return (
      <span className="text-xs text-gray-500 dark:text-gray-400">
        {timing}
      </span>
    );
  };

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

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6 mb-8">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
          Related Investor Relations Updates
        </h2>
        <p className="text-gray-600 dark:text-gray-400">
          Company announcements and updates published around this filing
        </p>
      </div>

      <div className="space-y-6">
        {documents.map((doc) => (
          <div
            key={doc.id}
            className="border border-gray-200 dark:border-gray-700 rounded-lg p-5 hover:shadow-md transition-shadow"
          >
            {/* Header */}
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-start gap-3 flex-1">
                <div className="text-blue-600 dark:text-blue-400 mt-1">
                  {getDocumentTypeIcon(doc.document_type)}
                </div>
                <div className="flex-1">
                  <a
                    href={doc.document_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-lg font-semibold text-gray-900 dark:text-white hover:text-blue-600 dark:hover:text-blue-400 inline-flex items-center gap-2 group"
                  >
                    {doc.title}
                    <ExternalLink className="h-4 w-4 opacity-0 group-hover:opacity-100 transition-opacity" />
                  </a>
                  <div className="flex items-center gap-3 mt-1">
                    <span className="text-sm text-gray-500 dark:text-gray-400">
                      {formatDate(doc.published_at)}
                    </span>
                    {getTimingBadge(doc.window_type, doc.time_delta_hours)}
                  </div>
                </div>
              </div>
              <div className="ml-4">
                {getRelevanceBadge(doc.relevance_score)}
              </div>
            </div>

            {/* Summary */}
            {doc.analysis_summary && (
              <div className="mb-4">
                <p className="text-gray-700 dark:text-gray-300">
                  {doc.analysis_summary}
                </p>
              </div>
            )}

            {/* Key Topics */}
            {doc.key_topics && doc.key_topics.length > 0 && (
              <div className="mb-4">
                <div className="flex flex-wrap gap-2">
                  {doc.key_topics.map((topic, idx) => (
                    <span
                      key={idx}
                      className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300"
                    >
                      {topic}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Salient Takeaways */}
            {doc.salient_takeaways && doc.salient_takeaways.length > 0 && (
              <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
                <h4 className="text-sm font-semibold text-blue-900 dark:text-blue-200 mb-2">
                  Key Investor Takeaways
                </h4>
                <ul className="space-y-2">
                  {doc.salient_takeaways.map((takeaway, idx) => (
                    <li
                      key={idx}
                      className="text-sm text-blue-800 dark:text-blue-300 flex items-start gap-2"
                    >
                      <span className="text-blue-600 dark:text-blue-400 mt-0.5">•</span>
                      <span>{takeaway}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Footer note */}
      <div className="mt-6 pt-4 border-t border-gray-200 dark:border-gray-700">
        <p className="text-xs text-gray-500 dark:text-gray-400">
          These documents were published within 72 hours before or after this filing and may provide
          additional context about the company's performance and outlook.
        </p>
      </div>
    </div>
  );
}
