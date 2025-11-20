import { NextResponse } from 'next/server';

export async function GET(
  request: Request,
  { params }: { params: { ticker: string } }
) {
  const { ticker } = params;

  // TODO: Implement database logic to fetch the latest institutional ownership summary
  // for the given ticker from the company_summaries table.

  const summary = {
    ticker,
    summary_type: 'INSTITUTIONAL_OWNERSHIP',
    fiscal_year: 2023,
    fiscal_quarter: 4,
    summary_content: {
      "headline": "Institutions Show Increased Confidence in AAPL",
      "top_buyers": ["Vanguard", "BlackRock"],
      "top_sellers": ["State Street"],
      "net_change": 15000000
    }
  };

  return NextResponse.json(summary);
}
