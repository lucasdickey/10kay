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
 * Detect the company's fiscal year-end month from the most recent filing
 * This determines how quarters are calculated
 */
function detectFiscalYearEnd(lastPeriodEnd: Date, lastQuarter: number | null, lastFilingType: string): number {
  // If it's a 10-K, the period end date IS the fiscal year end
  if (lastFilingType === '10-K') {
    return lastPeriodEnd.getMonth();
  }

  // For 10-Q, we need to infer the fiscal year end from the quarter
  // Standard calendar companies: FY-end in December (month 11)
  // June fiscal year: FY-end in June (month 5)
  // Other months are rare in tech but possible

  if (!lastQuarter) return 11; // Default to December

  // Map quarters to their fiscal year-end month assumptions
  // For companies with Dec fiscal year-end:
  //   Q1: Jan-Mar (month 2 = Mar)
  //   Q2: Apr-Jun (month 5 = Jun)
  //   Q3: Jul-Sep (month 8 = Sep)
  //   Q4: Oct-Dec (month 11 = Dec)

  // For companies with Jun fiscal year-end:
  //   Q1: Jul-Sep (month 8 = Sep)
  //   Q2: Oct-Dec (month 11 = Dec)
  //   Q3: Jan-Mar (month 2 = Mar)
  //   Q4: Apr-Jun (month 5 = Jun)

  const periodMonth = lastPeriodEnd.getMonth();

  // Use the actual period end month to infer fiscal year end
  // The quarter number is relative to the company's fiscal year, not calendar
  // So Q1 always ends 3 months after fiscal year end
  return periodMonth;
}

/**
 * Calculate the next quarter end date based on the last filing
 * Accounts for companies with different fiscal year-end dates
 */
function getNextQuarterEnd(lastPeriodEnd: Date, lastQuarter: number, lastFilingType: string): Date {
  const year = lastPeriodEnd.getFullYear();
  const lastPeriodMonth = lastPeriodEnd.getMonth();

  // Calculate months between last period end and next period end
  // Each quarter is 3 months apart
  const nextMonthOffset = lastQuarter === 4 ? 12 : 3; // Q4 to Q1 is 12 months, others are 3
  const nextMonth = (lastPeriodMonth + nextMonthOffset) % 12;
  const nextYear = year + (lastQuarter === 4 ? 1 : 0);

  // Determine the last day of the next month
  const result = new Date(nextYear, nextMonth + 1, 0);

  return result;
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

    let currentPeriodEnd = new Date(filing.period_end_date);
    let currentFilingType = filing.filing_type;
    let currentFiscalYear = filing.fiscal_year;
    let currentFiscalQuarter = filing.fiscal_quarter;

    // Keep iterating forward until we find the next future filing
    // Limit iterations to prevent infinite loops (max 20 quarters ~5 years)
    let iterations = 0;
    const MAX_ITERATIONS = 20;
    let nextFutureFiling: UpcomingFiling | null = null;

    while (iterations < MAX_ITERATIONS && !nextFutureFiling) {
      iterations++;

      let nextPeriodEnd: Date;
      let nextFilingType: string;
      let nextFiscalYear: number;
      let nextFiscalQuarter: number | undefined;

      // Determine the next filing based on the current filing
      if (currentFilingType === '10-Q') {
        // If current filing was Q4, next is 10-K for the same fiscal year
        if (currentFiscalQuarter === 4) {
          nextFilingType = '10-K';
          nextPeriodEnd = new Date(currentPeriodEnd); // Q4 end = year end
          nextFiscalYear = currentFiscalYear;
          nextFiscalQuarter = undefined;
        } else {
          // Next is the following quarter
          nextFilingType = '10-Q';
          nextPeriodEnd = getNextQuarterEnd(currentPeriodEnd, currentFiscalQuarter || 1, currentFilingType);
          nextFiscalYear = currentFiscalQuarter === 4 ? currentFiscalYear + 1 : currentFiscalYear;
          nextFiscalQuarter = currentFiscalQuarter ? (currentFiscalQuarter % 4) + 1 : 1;
        }
      } else {
        // If current filing was 10-K, next is Q1 of next fiscal year
        nextFilingType = '10-Q';
        nextPeriodEnd = getNextQuarterEnd(currentPeriodEnd, 1, currentFilingType); // Q1 is first quarter after 10-K
        nextFiscalYear = currentFiscalYear + 1;
        nextFiscalQuarter = 1;
      }

      // Calculate estimated filing date
      const estimatedDate = estimateFilingDate(nextPeriodEnd, nextFilingType);
      const daysUntil = getDaysUntil(estimatedDate);

      // If this filing is in the future, we found it!
      if (daysUntil > 0) {
        nextFutureFiling = {
          ticker: filing.ticker,
          name: filing.name,
          filingType: nextFilingType,
          estimatedDate,
          daysUntil,
          fiscalPeriod: formatFiscalPeriod(nextFilingType, nextFiscalYear, nextFiscalQuarter),
        };
      } else {
        // Still in the past, continue to the next cycle
        currentPeriodEnd = nextPeriodEnd;
        currentFilingType = nextFilingType;
        currentFiscalYear = nextFiscalYear;
        currentFiscalQuarter = nextFiscalQuarter ?? null;
      }
    }

    // Only add filings that are within the specified window
    if (nextFutureFiling && nextFutureFiling.daysUntil <= daysAhead) {
      upcoming.push(nextFutureFiling);
    }
  }

  // Sort by estimated date (soonest first)
  upcoming.sort((a, b) => a.estimatedDate.getTime() - b.estimatedDate.getTime());

  return upcoming;
}
