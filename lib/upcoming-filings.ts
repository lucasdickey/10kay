/**
 * Utility functions for estimating upcoming SEC filing dates
 *
 * Based on SEC filing deadline rules:
 * - 10-Q (Quarterly): Due 40-45 days after quarter end
 * - 10-K (Annual): Due 60-90 days after fiscal year end
 */

interface LatestFiling {
  company_id: string;
  ticker: string;
  name: string;
  filing_type: string;
  filing_date: Date;
  fiscal_year: number | null;
  fiscal_quarter: number | null;
  period_end_date: Date | null;
}

export interface UpcomingFiling {
  ticker: string;
  name: string;
  filingType: string;
  estimatedDate: Date;
  daysUntil: number;
  fiscalPeriod: string;
}

/**
 * Calculate the next quarter end date based on the last filing
 */
function getNextQuarterEnd(lastPeriodEnd: Date, lastQuarter: number): Date {
  const year = lastPeriodEnd.getFullYear();
  const nextQuarter = lastQuarter === 4 ? 1 : lastQuarter + 1;
  const nextYear = lastQuarter === 4 ? year + 1 : year;

  // Standard calendar quarters
  const quarterEndMonths = [2, 5, 8, 11]; // Mar, Jun, Sep, Dec (0-indexed)
  const quarterEndDays = [31, 30, 30, 31]; // Last day of each quarter month

  const endMonth = quarterEndMonths[nextQuarter - 1];
  const endDay = quarterEndDays[nextQuarter - 1];

  return new Date(nextYear, endMonth, endDay);
}

/**
 * Calculate the next fiscal year end date based on the last filing
 */
function getNextYearEnd(lastPeriodEnd: Date): Date {
  const year = lastPeriodEnd.getFullYear();
  const month = lastPeriodEnd.getMonth();
  const day = lastPeriodEnd.getDate();

  // Next year end is same month/day, one year later
  return new Date(year + 1, month, day);
}

/**
 * Estimate the filing date based on period end and filing type
 * Using conservative estimates (mid-range of deadline windows)
 */
function estimateFilingDate(periodEnd: Date, filingType: string): Date {
  const estimatedDate = new Date(periodEnd);

  if (filingType === '10-Q') {
    // Quarterly reports typically filed 40-45 days after quarter end
    // Use 42 days as middle estimate
    estimatedDate.setDate(estimatedDate.getDate() + 42);
  } else if (filingType === '10-K') {
    // Annual reports typically filed 60-75 days after year end
    // Use 67 days as middle estimate
    estimatedDate.setDate(estimatedDate.getDate() + 67);
  }

  return estimatedDate;
}

/**
 * Calculate days until a future date
 */
function getDaysUntil(futureDate: Date): number {
  const now = new Date();
  const diffTime = futureDate.getTime() - now.getTime();
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
  return diffDays;
}

/**
 * Format fiscal period string
 */
function formatFiscalPeriod(filingType: string, year: number, quarter?: number): string {
  if (filingType === '10-K') {
    return `FY ${year}`;
  } else if (filingType === '10-Q' && quarter) {
    return `Q${quarter} ${year}`;
  }
  return `${year}`;
}

/**
 * Calculate upcoming filings based on the most recent filings per company
 */
export function calculateUpcomingFilings(
  latestFilings: LatestFiling[],
  daysAhead: number = 60
): UpcomingFiling[] {
  const now = new Date();
  const upcoming: UpcomingFiling[] = [];

  for (const filing of latestFilings) {
    // Skip if we don't have enough data to estimate
    if (!filing.period_end_date || !filing.fiscal_year) {
      continue;
    }

    const periodEnd = new Date(filing.period_end_date);
    let nextPeriodEnd: Date;
    let nextFilingType: string;
    let nextFiscalYear: number;
    let nextFiscalQuarter: number | undefined;

    // Determine the next filing based on the last filing
    if (filing.filing_type === '10-Q') {
      // If last filing was Q4, next is 10-K for the same fiscal year
      if (filing.fiscal_quarter === 4) {
        nextFilingType = '10-K';
        nextPeriodEnd = new Date(periodEnd); // Q4 end = year end
        nextFiscalYear = filing.fiscal_year;
        nextFiscalQuarter = undefined;
      } else {
        // Next is the following quarter
        nextFilingType = '10-Q';
        nextPeriodEnd = getNextQuarterEnd(periodEnd, filing.fiscal_quarter || 1);
        nextFiscalYear = filing.fiscal_quarter === 4 ? filing.fiscal_year + 1 : filing.fiscal_year;
        nextFiscalQuarter = filing.fiscal_quarter ? (filing.fiscal_quarter % 4) + 1 : 1;
      }
    } else {
      // If last filing was 10-K, next is Q1 of next fiscal year
      nextFilingType = '10-Q';
      nextPeriodEnd = getNextQuarterEnd(periodEnd, 0); // Start from Q1
      nextFiscalYear = filing.fiscal_year + 1;
      nextFiscalQuarter = 1;
    }

    // Calculate estimated filing date
    const estimatedDate = estimateFilingDate(nextPeriodEnd, nextFilingType);
    const daysUntil = getDaysUntil(estimatedDate);

    // Only include filings within the specified time window
    // and exclude past filings (daysUntil > 0)
    if (daysUntil > 0 && daysUntil <= daysAhead) {
      upcoming.push({
        ticker: filing.ticker,
        name: filing.name,
        filingType: nextFilingType,
        estimatedDate,
        daysUntil,
        fiscalPeriod: formatFiscalPeriod(nextFilingType, nextFiscalYear, nextFiscalQuarter),
      });
    }
  }

  // Sort by estimated date (soonest first)
  upcoming.sort((a, b) => a.estimatedDate.getTime() - b.estimatedDate.getTime());

  return upcoming;
}
