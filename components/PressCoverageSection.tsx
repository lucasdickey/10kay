/**
 * Press Coverage Section Component
 *
 * Displays press coverage articles for a filing with filtering and statistics
 */

'use client';

import { useEffect, useState } from 'react';
import { PressCoverageCard } from './PressCoverageCard';

interface PressArticle {
  id: string;
  source: string;
  headline: string;
  url: string;
  author: string | null;
  published_at: string;
  article_snippet: string | null;
  sentiment_score: number | null;
  relevance_score: number | null;
}

interface PressStats {
  avg_sentiment: number | null;
  min_sentiment: number | null;
  max_sentiment: number | null;
  avg_relevance: number | null;
  source_count: number;
}

interface PressCoverageSectionProps {
  filingId?: string;
  ticker?: string;
  limit?: number;
}

export function PressCoverageSection({ filingId, ticker, limit = 10 }: PressCoverageSectionProps) {
  const [articles, setArticles] = useState<PressArticle[]>([]);
  const [stats, setStats] = useState<PressStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedSource, setSelectedSource] = useState<string>('all');

  useEffect(() => {
    fetchPressCoverage();
  }, [filingId, ticker, limit]);

  async function fetchPressCoverage() {
    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams();
      if (filingId) params.append('filing_id', filingId);
      if (ticker) params.append('ticker', ticker);
      params.append('limit', limit.toString());

      const response = await fetch(`/api/press-coverage?${params.toString()}`);

      if (!response.ok) {
        throw new Error('Failed to fetch press coverage');
      }

      const data = await response.json();
      setArticles(data.articles || []);
      setStats(data.stats || null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }

  // Get unique sources for filter
  const sources = Array.from(new Set(articles.map(a => a.source)));
  const filteredArticles = selectedSource === 'all'
    ? articles
    : articles.filter(a => a.source === selectedSource);

  if (loading) {
    return (
      <div className="py-8 text-center">
        <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-blue-600 border-r-transparent"></div>
        <p className="mt-2 text-gray-600">Loading press coverage...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg bg-red-50 border border-red-200 p-4">
        <p className="text-red-800">Error: {error}</p>
      </div>
    );
  }

  if (articles.length === 0) {
    return (
      <div className="rounded-lg bg-gray-50 border border-gray-200 p-6 text-center">
        <p className="text-gray-600">No press coverage found for this filing.</p>
        <p className="text-sm text-gray-500 mt-1">
          Articles are captured within 48 hours of filing date.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Stats Bar */}
      {stats && (
        <div className="rounded-lg bg-gradient-to-r from-blue-50 to-purple-50 border border-blue-200 p-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <div className="text-sm text-gray-600 font-medium">Articles</div>
              <div className="text-2xl font-bold text-gray-900">{articles.length}</div>
            </div>
            {stats.avg_sentiment !== null && (
              <div>
                <div className="text-sm text-gray-600 font-medium">Avg Sentiment</div>
                <div className={`text-2xl font-bold ${stats.avg_sentiment > 0 ? 'text-green-600' : stats.avg_sentiment < 0 ? 'text-red-600' : 'text-gray-600'}`}>
                  {stats.avg_sentiment > 0 ? '+' : ''}{stats.avg_sentiment.toFixed(2)}
                </div>
              </div>
            )}
            {stats.avg_relevance !== null && (
              <div>
                <div className="text-sm text-gray-600 font-medium">Avg Relevance</div>
                <div className="text-2xl font-bold text-blue-600">
                  {(stats.avg_relevance * 100).toFixed(0)}%
                </div>
              </div>
            )}
            <div>
              <div className="text-sm text-gray-600 font-medium">Sources</div>
              <div className="text-2xl font-bold text-purple-600">{stats.source_count}</div>
            </div>
          </div>
        </div>
      )}

      {/* Filter Buttons */}
      {sources.length > 1 && (
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setSelectedSource('all')}
            className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${
              selectedSource === 'all'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            All ({articles.length})
          </button>
          {sources.map(source => {
            const count = articles.filter(a => a.source === source).length;
            return (
              <button
                key={source}
                onClick={() => setSelectedSource(source)}
                className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${
                  selectedSource === source
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                {source} ({count})
              </button>
            );
          })}
        </div>
      )}

      {/* Articles Grid */}
      <div className="grid gap-4 md:grid-cols-2">
        {filteredArticles.map(article => (
          <PressCoverageCard
            key={article.id}
            source={article.source}
            headline={article.headline}
            url={article.url}
            author={article.author}
            publishedAt={article.published_at}
            snippet={article.article_snippet}
            sentimentScore={article.sentiment_score}
            relevanceScore={article.relevance_score}
          />
        ))}
      </div>

      {filteredArticles.length === 0 && selectedSource !== 'all' && (
        <div className="text-center py-8 text-gray-500">
          No articles from {selectedSource}
        </div>
      )}
    </div>
  );
}
