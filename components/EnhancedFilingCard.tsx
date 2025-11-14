import Link from 'next/link';
import { CompanyLogo } from '@/lib/company-logo';

interface FilingCardProps {
  ticker: string;
  companyName: string;
  filingType: string;
  sentiment: number;
  metrics: any;
  slug: string;
  filingDate: Date;
  domain?: string | null;
}

function getSentimentBadge(sentiment: number): { label: string; className: string } {
  if (sentiment > 0.3) {
    return { label: 'Positive', className: 'bg-green-100 text-green-800' };
  } else if (sentiment < -0.3) {
    return { label: 'Negative', className: 'bg-red-100 text-red-800' };
  }
  return { label: 'Neutral', className: 'bg-gray-100 text-gray-800' };
}

function getSentimentBorderColor(sentiment: number): string {
  if (sentiment > 0.3) {
    return '#16a34a'; // green-600 for positive
  } else if (sentiment < -0.3) {
    return '#dc2626'; // red-600 for negative
  }
  return '#6b7280'; // gray-500 for neutral
}

function extractMetrics(metrics: any) {
  if (!metrics) return { primary: [], secondary: [] };

  // Extract key metrics from the metrics object
  const primary: { label: string; value: string; change?: string }[] = [];
  const secondary: { label: string; value: string }[] = [];

  // Helper function to extract value and change from metric strings
  const parseMetricValue = (metricString: string): { value: string; change?: string } => {
    if (!metricString) return { value: '' };

    // Try to match patterns like "$XXB (±X.X% YoY)" or "XX.X% (±XXbps YoY)"
    const valueMatch = metricString.match(/^([^(]+)/);
    const value = valueMatch?.[1]?.trim() || '';

    const changeMatch = metricString.match(/([+-][\d.]+(?:%|bps))/);
    const change = changeMatch?.[1] || undefined;

    return { value, change };
  };

  // Extract Revenue (top-line growth)
  if (metrics.revenue) {
    const { value, change } = parseMetricValue(metrics.revenue);
    if (value) {
      primary.push({
        label: 'Revenue',
        value,
        change
      });
    }
  }

  // Extract Net Income (bottom-line profitability)
  if (metrics.net_income) {
    const { value, change } = parseMetricValue(metrics.net_income);
    if (value) {
      primary.push({
        label: 'Net Income',
        value,
        change
      });
    }
  }

  // Extract R&D Spend (investment in future)
  if (metrics.rd_spend) {
    const { value, change } = parseMetricValue(metrics.rd_spend);
    if (value) {
      primary.push({
        label: 'R&D Spend',
        value,
        change
      });
    }
  }

  // Look for growth indicators in nested objects (company-specific metrics)
  if (metrics.growth_indicators) {
    const indicators = metrics.growth_indicators;
    const firstKey = Object.keys(indicators)[0];
    if (firstKey && indicators[firstKey]) {
      const value = indicators[firstKey].toString();
      secondary.push({ label: formatLabel(firstKey), value });
    }
  }

  return { primary, secondary };
}

function formatLabel(key: string): string {
  return key
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

function formatDate(date: Date): string {
  return new Date(date).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  });
}

export function EnhancedFilingCard({
  ticker,
  companyName,
  filingType,
  sentiment,
  metrics,
  slug,
  filingDate,
  domain,
}: FilingCardProps) {
  const sentimentBadge = getSentimentBadge(sentiment);
  const { primary, secondary } = extractMetrics(metrics);
  // Convert sentiment (-1 to 1) to 2-digit scale (0 to 100)
  const sentimentValue = Math.round((sentiment + 1) * 50);

  // Determine background color based on sentiment
  let backgroundColor = '#ffffff';
  if (sentiment > 0.3) {
    backgroundColor = '#ecfdf5'; // Subtle green background for positive (green-100 equivalent)
  } else if (sentiment < -0.3) {
    backgroundColor = '#fef2f2'; // Subtle red background for negative (red-100 equivalent)
  }

  const borderColor = getSentimentBorderColor(sentiment);

  return (
    <div
      className="rounded-lg shadow-sm hover:shadow-md transition-shadow h-full flex flex-col"
      style={{ backgroundColor, borderLeft: `6px solid ${borderColor}` }}
    >
      {/* Header */}
      <div className="p-3 border-b border-gray-100">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <CompanyLogo ticker={ticker} domain={domain} size={24} className="flex-shrink-0" />
              <h4 className="text-base font-bold text-gray-900">{ticker}</h4>
              <span className="px-1.5 py-0.5 bg-gray-100 text-gray-700 rounded text-xs font-semibold">
                {filingType}
              </span>
              <span className="text-sm text-gray-600">{companyName}</span>
            </div>
          </div>
          <div className="text-right ml-3">
            <div className="text-xl font-bold text-green-600">{sentimentValue}</div>
            <span className={`px-2 py-0.5 rounded text-xs font-semibold ${sentimentBadge.className}`}>
              {sentimentBadge.label}
            </span>
          </div>
        </div>
      </div>

      {/* Metrics */}
      {(primary.length > 0 || secondary.length > 0) && (
        <div className="p-3 border-b border-gray-100">
          {/* Primary metrics (Revenue, Net Income, R&D Spend - 3 column KPI row) */}
          {primary.length > 0 && (
            <div className="grid grid-cols-3 gap-3 mb-3 pb-3 border-b border-gray-100">
              {primary.map((metric, idx) => (
                <div key={idx}>
                  <div className="text-sm text-gray-500 font-medium">{metric.label}</div>
                  <div className="font-bold text-gray-900">{metric.value}</div>
                  {metric.change && (
                    <div className="flex items-center gap-0.5 text-xs text-green-600 font-semibold">
                      <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M5.293 9.707a1 1 0 010-1.414l4-4a1 1 0 011.414 0l4 4a1 1 0 01-1.414 1.414L11 7.414V15a1 1 0 11-2 0V7.414L6.707 9.707a1 1 0 01-1.414 0z" clipRule="evenodd" />
                      </svg>
                      {metric.change}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Secondary metrics (Contextually important stat - full width) */}
          {secondary.length > 0 && (
            <div className="space-y-2">
              {secondary.map((metric, idx) => (
                <div key={`sec-${idx}`}>
                  <div className="text-sm text-gray-500 font-medium">{metric.label}</div>
                  <div className="font-bold text-gray-900">{metric.value}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Footer */}
      <div className="px-3 py-2 flex items-center justify-between mt-auto">
        <span className="text-xs text-gray-500">{formatDate(filingDate)}</span>
        <Link
          href={`/${slug}`}
          className="text-xs font-semibold text-blue-600 hover:text-blue-700 flex items-center gap-1"
        >
          Dig In
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </Link>
      </div>
    </div>
  );
}
