/**
 * Press Coverage Card Component
 *
 * Displays a single press article with source, headline, sentiment, and relevance
 */

import Link from 'next/link';
import { formatDistanceToNow } from 'date-fns';

interface PressCoverageCardProps {
  source: string;
  headline: string;
  url: string;
  author: string | null;
  publishedAt: Date | string;
  snippet: string | null;
  sentimentScore: number | null;
  relevanceScore: number | null;
}

function getSentimentBadge(sentiment: number | null): { label: string; className: string } {
  if (sentiment === null) {
    return { label: 'Unknown', className: 'bg-gray-100 text-gray-600' };
  }

  if (sentiment > 0.3) {
    return { label: 'Bullish', className: 'bg-green-100 text-green-800' };
  } else if (sentiment < -0.3) {
    return { label: 'Bearish', className: 'bg-red-100 text-red-800' };
  }
  return { label: 'Neutral', className: 'bg-gray-100 text-gray-700' };
}

function getSourceColor(source: string): string {
  const sourceColors: Record<string, string> = {
    'WSJ': '#0080C9',
    'Bloomberg': '#B7830F',
    'FT': '#FF8C66',
    'NYT': '#000000',
    'Yahoo Finance': '#720E9E',
    'Reuters': '#FF8000',
    'CNBC': '#3B5998',
    'MarketWatch': '#15853F',
  };

  return sourceColors[source] || '#6b7280';
}

function formatTimeAgo(date: Date | string): string {
  const dateObj = typeof date === 'string' ? new Date(date) : date;
  return formatDistanceToNow(dateObj, { addSuffix: true });
}

export function PressCoverageCard({
  source,
  headline,
  url,
  author,
  publishedAt,
  snippet,
  sentimentScore,
  relevanceScore,
}: PressCoverageCardProps) {
  const sentimentBadge = getSentimentBadge(sentimentScore);
  const sourceColor = getSourceColor(source);

  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="block rounded-lg border border-gray-200 bg-white shadow-sm hover:shadow-md transition-shadow p-4"
      style={{ borderLeft: `4px solid ${sourceColor}` }}
    >
      {/* Header: Source and Time */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span
            className="px-2 py-1 rounded text-xs font-bold uppercase tracking-wide"
            style={{ color: sourceColor, backgroundColor: `${sourceColor}15` }}
          >
            {source}
          </span>
          {sentimentScore !== null && (
            <span className={`px-2 py-0.5 rounded text-xs font-semibold ${sentimentBadge.className}`}>
              {sentimentBadge.label}
            </span>
          )}
        </div>
        <span className="text-xs text-gray-500">
          {formatTimeAgo(publishedAt)}
        </span>
      </div>

      {/* Headline */}
      <h3 className="text-base font-semibold text-gray-900 mb-2 line-clamp-2 hover:text-blue-600 transition-colors">
        {headline}
      </h3>

      {/* Snippet */}
      {snippet && (
        <p className="text-sm text-gray-600 mb-3 line-clamp-2">
          {snippet}
        </p>
      )}

      {/* Footer: Author and Scores */}
      <div className="flex items-center justify-between text-xs text-gray-500">
        <div>
          {author && (
            <span className="font-medium">
              by {author}
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          {sentimentScore !== null && (
            <div className="flex items-center gap-1">
              <span className="text-gray-400">Sentiment:</span>
              <span className={`font-semibold ${sentimentScore > 0 ? 'text-green-600' : sentimentScore < 0 ? 'text-red-600' : 'text-gray-600'}`}>
                {sentimentScore > 0 ? '+' : ''}{sentimentScore.toFixed(2)}
              </span>
            </div>
          )}
          {relevanceScore !== null && (
            <div className="flex items-center gap-1">
              <span className="text-gray-400">Relevance:</span>
              <span className="font-semibold text-blue-600">
                {(relevanceScore * 100).toFixed(0)}%
              </span>
            </div>
          )}
        </div>
      </div>
    </a>
  );
}
