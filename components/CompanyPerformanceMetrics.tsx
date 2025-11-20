/**
 * CompanyPerformanceMetrics Component
 *
 * Displays company stock performance metrics including:
 * - 7-day price change
 * - Comparison to market aggregate
 * - Comparison to sector performance
 */

interface CompanyPerformanceMetricsProps {
  ticker: string;
  priceChange7d: number | null;
  aggregateChange7d: number | null;
  sectorChange7d: number | null;
  sector: string | null;
}

function PerformanceBar({ value, label, comparison }: {
  value: number;
  label: string;
  comparison?: { value: number; label: string };
}) {
  const isPositive = value > 0;
  const absValue = Math.abs(value);

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-gray-700">{label}</span>
        <div className="flex items-center gap-2">
          <span className={`text-lg font-bold ${isPositive ? 'text-green-600' : value < 0 ? 'text-red-600' : 'text-gray-600'}`}>
            {isPositive && '+'}{value.toFixed(2)}%
          </span>
          {value !== 0 && (
            <svg
              className={`w-5 h-5 ${isPositive ? 'text-green-600' : 'text-red-600'}`}
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              {isPositive ? (
                <path
                  fillRule="evenodd"
                  d="M12 7a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0V8.414l-4.293 4.293a1 1 0 01-1.414 0L8 10.414l-4.293 4.293a1 1 0 01-1.414-1.414l5-5a1 1 0 011.414 0L11 10.586 14.586 7H12z"
                  clipRule="evenodd"
                />
              ) : (
                <path
                  fillRule="evenodd"
                  d="M12 13a1 1 0 100 2h5a1 1 0 001-1v-5a1 1 0 10-2 0v2.586l-4.293-4.293a1 1 0 00-1.414 0L8 9.586l-4.293-4.293a1 1 0 00-1.414 1.414l5 5a1 1 0 001.414 0L11 9.414 14.586 13H12z"
                  clipRule="evenodd"
                />
              )}
            </svg>
          )}
        </div>
      </div>

      {comparison && (
        <div className="text-xs text-gray-600">
          <span className={Math.abs(value - comparison.value) > 0.5 ? 'font-semibold' : ''}>
            {value > comparison.value ? 'Outperforming' : value < comparison.value ? 'Underperforming' : 'Matching'} {comparison.label}
          </span>
          {' '}
          <span className={value > comparison.value ? 'text-green-600' : value < comparison.value ? 'text-red-600' : 'text-gray-600'}>
            ({value > comparison.value ? '+' : ''}{(value - comparison.value).toFixed(2)}%)
          </span>
        </div>
      )}

      {/* Visual bar */}
      <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden">
        <div
          className={`h-full transition-all ${isPositive ? 'bg-green-500' : 'bg-red-500'}`}
          style={{ width: `${Math.min(absValue * 2, 100)}%` }}
        />
      </div>
    </div>
  );
}

export function CompanyPerformanceMetrics({
  ticker,
  priceChange7d,
  aggregateChange7d,
  sectorChange7d,
  sector,
}: CompanyPerformanceMetricsProps) {
  // If no performance data is available, don't render the component
  if (priceChange7d === null) {
    return null;
  }

  return (
    <div className="bg-white border rounded-lg p-6 shadow-sm">
      <h2 className="text-xl font-bold text-gray-900 mb-4">Performance Metrics</h2>

      <div className="space-y-6">
        {/* Company 7-day performance */}
        <PerformanceBar value={priceChange7d} label="7-Day Stock Performance" />

        {/* Comparison to aggregate */}
        {aggregateChange7d !== null && (
          <div className="pt-4 border-t">
            <PerformanceBar
              value={priceChange7d}
              label="vs. Market Average"
              comparison={{ value: aggregateChange7d, label: 'market average' }}
            />
          </div>
        )}

        {/* Comparison to sector */}
        {sector && sectorChange7d !== null && (
          <div className="pt-4 border-t">
            <PerformanceBar
              value={priceChange7d}
              label={`vs. ${sector} Sector`}
              comparison={{ value: sectorChange7d, label: `${sector} sector` }}
            />
          </div>
        )}
      </div>

      {/* Reference values */}
      <div className="mt-6 pt-4 border-t">
        <div className="grid grid-cols-2 gap-4 text-sm">
          {aggregateChange7d !== null && (
            <div className="bg-gray-50 rounded p-3">
              <div className="text-xs text-gray-500 uppercase tracking-wide mb-1">Market Avg</div>
              <div className={`font-semibold ${aggregateChange7d > 0 ? 'text-green-600' : aggregateChange7d < 0 ? 'text-red-600' : 'text-gray-600'}`}>
                {aggregateChange7d > 0 && '+'}{aggregateChange7d.toFixed(2)}%
              </div>
            </div>
          )}
          {sector && sectorChange7d !== null && (
            <div className="bg-gray-50 rounded p-3">
              <div className="text-xs text-gray-500 uppercase tracking-wide mb-1">{sector} Avg</div>
              <div className={`font-semibold ${sectorChange7d > 0 ? 'text-green-600' : sectorChange7d < 0 ? 'text-red-600' : 'text-gray-600'}`}>
                {sectorChange7d > 0 && '+'}{sectorChange7d.toFixed(2)}%
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="mt-4 text-xs text-gray-500 italic">
        * Performance data based on trailing 7-day stock price changes
      </div>
    </div>
  );
}
