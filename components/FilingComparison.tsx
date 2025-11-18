import React from 'react';

interface ComparisonData {
  comparison_summary: string;
  key_deltas: {
    area: string;
    change: string;
    trend: string;
  }[];
}

interface FilingComparisonProps {
  comparison: ComparisonData;
}

const FilingComparison: React.FC<FilingComparisonProps> = ({ comparison }) => {
  return (
    <div className="bg-gray-50 p-6 rounded-lg shadow-md">
      <h2 className="text-2xl font-bold mb-4">Quarter-over-Quarter Comparison</h2>
      <p className="mb-6">{comparison.comparison_summary}</p>
      <div>
        {comparison.key_deltas.map((delta, index) => (
          <div key={index} className="mb-4">
            <h3 className="text-xl font-semibold">{delta.area}</h3>
            <p><strong>Change:</strong> {delta.change}</p>
            <p><strong>Trend:</strong> {delta.trend}</p>
          </div>
        ))}
      </div>
    </div>
  );
};

export default FilingComparison;
