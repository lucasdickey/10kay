import Link from 'next/link';

interface FilingCardProps {
  ticker: string;
  companyName: string;
  filingType: string;
  sentiment: number;
  metrics: any;
  slug: string;
  filingDate: Date;
}

function getSentimentBadge(sentiment: number): { label: string; className: string } {
  if (sentiment > 0.3) {
    return { label: 'Positive', className: 'bg-blue-600 text-white' };
  } else if (sentiment < -0.3) {
    return { label: 'Negative', className: 'bg-red-600 text-white' };
  }
  return { label: 'Neutral', className: 'bg-gray-600 text-white' };
}

function extractMetrics(metrics: any) {
  if (!metrics) return { primary: [], secondary: [] };

  // Extract key metrics from the metrics object
  const primary: { label: string; value: string; change?: string }[] = [];
  const secondary: { label: string; value: string }[] = [];

  if (metrics.revenue) {
    const match = metrics.revenue.match(/\$([\d.]+[BMK]?).*?([+-]\d+%)/);
    if (match) {
      primary.push({
        label: 'Revenue',
        value: `$${match[1]}`,
        change: match[2]
      });
    }
  }

  // Look for growth indicators in nested objects
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
    year: 'numeric',
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
}: FilingCardProps) {
  const sentimentBadge = getSentimentBadge(sentiment);
  const { primary, secondary } = extractMetrics(metrics);
  const sentimentValue = sentiment.toFixed(2);

  return (
    <div className="bg-white border-l-4 border-blue-600 rounded-lg shadow-sm hover:shadow-md transition-shadow mb-4">
      {/* Header */}
      <div className="p-4 border-b border-gray-100">
        <div className="flex items-start justify-between mb-2">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <h4 className="text-lg font-bold text-gray-900">{ticker}</h4>
              <span className="px-2 py-0.5 bg-gray-100 text-gray-700 rounded text-xs font-semibold">
                {filingType}
              </span>
            </div>
            <p className="text-sm text-gray-600">{companyName}</p>
          </div>
          <div className="text-right">
            <div className="text-2xl font-bold text-green-600 mb-1">{sentimentValue}</div>
            <span className={`px-2 py-1 rounded text-xs font-semibold ${sentimentBadge.className}`}>
              {sentimentBadge.label}
            </span>
          </div>
        </div>
      </div>

      {/* Metrics */}
      {primary.length > 0 && (
        <div className="p-4 border-b border-gray-100">
          <div className="grid grid-cols-2 gap-4">
            {primary.map((metric, idx) => (
              <div key={idx}>
                <div className="text-xs text-gray-500 mb-1">{metric.label}</div>
                <div className="text-lg font-bold text-gray-900">{metric.value}</div>
                {metric.change && (
                  <div className="flex items-center gap-1 text-sm text-green-600 font-semibold">
                    <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M5.293 9.707a1 1 0 010-1.414l4-4a1 1 0 011.414 0l4 4a1 1 0 01-1.414 1.414L11 7.414V15a1 1 0 11-2 0V7.414L6.707 9.707a1 1 0 01-1.414 0z" clipRule="evenodd" />
                    </svg>
                    {metric.change}
                  </div>
                )}
              </div>
            ))}
            {secondary.map((metric, idx) => (
              <div key={`sec-${idx}`}>
                <div className="text-xs text-gray-500 mb-1">{metric.label}</div>
                <div className="text-lg font-bold text-gray-900">{metric.value}</div>
                <div className="text-sm text-gray-500">YoY</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Sector comparison */}
      <div className="p-4 border-b border-gray-100">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs text-gray-500">vs Sector Avg</span>
          <span className="text-sm font-bold text-green-600">+20%</span>
        </div>
        <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
          <div className="h-full bg-green-500 rounded-full" style={{ width: '75%' }} />
        </div>
      </div>

      {/* Footer */}
      <div className="p-4 flex items-center justify-between">
        <span className="text-sm text-gray-500">{formatDate(filingDate)}</span>
        <Link
          href={`/${slug}`}
          className="text-sm font-semibold text-blue-600 hover:text-blue-700 flex items-center gap-1"
        >
          View Analysis
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </Link>
      </div>
    </div>
  );
}
