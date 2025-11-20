'use client';

import { useEffect, useState } from 'react';

interface OwnershipSummary {
  ticker: string;
  summary_type: string;
  fiscal_year: number;
  fiscal_quarter: number;
  summary_content: {
    headline: string;
    top_buyers: string[];
    top_sellers: string[];
    net_change: number;
  };
}

export default function InstitutionalOwnership({ ticker }: { ticker: string }) {
  const [summary, setSummary] = useState<OwnershipSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchData() {
      try {
        const response = await fetch(`/api/summaries/${ticker}`);
        if (!response.ok) {
          throw new Error('Failed to fetch data');
        }
        const data = await response.json();
        setSummary(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setIsLoading(false);
      }
    }
    fetchData();
  }, [ticker]);

  if (isLoading) return <div>Loading institutional ownership...</div>;
  if (error) return <div>Error: {error}</div>;
  if (!summary) return <div>No data available.</div>;

  return (
    <div className="bg-white p-6 rounded-lg shadow-md">
      <h2 className="text-xl font-bold mb-4">Institutional Ownership (Q{summary.fiscal_quarter} {summary.fiscal_year})</h2>
      <p className="text-lg mb-4">{summary.summary_content.headline}</p>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <h3 className="font-semibold">Top Buyers</h3>
          <ul>
            {summary.summary_content.top_buyers.map(buyer => <li key={buyer}>{buyer}</li>)}
          </ul>
        </div>
        <div>
          <h3 className="font-semibold">Top Sellers</h3>
          <ul>
            {summary.summary_content.top_sellers.map(seller => <li key={seller}>{seller}</li>)}
          </ul>
        </div>
      </div>
      <p className="mt-4">Net Change: {summary.summary_content.net_change.toLocaleString()} shares</p>
    </div>
  );
}
