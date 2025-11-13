// Quick test of the upcoming filings algorithm
const now = new Date();
console.log("Today:", now.toISOString());
console.log("Today (local):", now.toLocaleDateString());

// Test quarter end calculation
function getNextQuarterEnd(lastPeriodEnd, lastQuarter) {
  const year = lastPeriodEnd.getFullYear();
  const nextQuarter = lastQuarter === 4 ? 1 : lastQuarter + 1;
  const nextYear = lastQuarter === 4 ? year + 1 : year;

  const quarterEndMonths = [2, 5, 8, 11]; // Mar, Jun, Sep, Dec (0-indexed)
  const quarterEndDays = [31, 30, 30, 31];

  const endMonth = quarterEndMonths[nextQuarter - 1];
  const endDay = quarterEndDays[nextQuarter - 1];

  const result = new Date(nextYear, endMonth, endDay);
  console.log(`  getNextQuarterEnd(Q${lastQuarter} ${year}) -> Q${nextQuarter} ${nextYear}`);
  console.log(`    Created: new Date(${nextYear}, ${endMonth}, ${endDay}) = ${result.toISOString()}`);
  console.log(`    Expected: ${nextYear}-${String(endMonth + 1).padStart(2, '0')}-${endDay}`);
  return result;
}

// Test: If last filing was Q3 2024 (Sept 30, 2024)
console.log("\nTest: Last filing Q3 2024");
const q3_2024_end = new Date(2024, 8, 30); // Sept 30, 2024 (month is 0-indexed!)
console.log("Q3 2024 period end:", q3_2024_end.toISOString());

const q4_2024_end = getNextQuarterEnd(q3_2024_end, 3);
console.log("Result:", q4_2024_end.toLocaleDateString());

// Test filing date estimation
function estimateFilingDate(periodEnd, filingType) {
  const estimatedDate = new Date(periodEnd);
  if (filingType === '10-Q') {
    estimatedDate.setDate(estimatedDate.getDate() + 42);
  } else if (filingType === '10-K') {
    estimatedDate.setDate(estimatedDate.getDate() + 67);
  }
  return estimatedDate;
}

console.log("\nFiling date estimates:");
const q4Filing = estimateFilingDate(q4_2024_end, '10-K');
console.log("Q4 2024 10-K estimated filing:", q4Filing.toLocaleDateString());

const daysUntil = Math.ceil((q4Filing - now) / (1000 * 60 * 60 * 24));
console.log("Days until:", daysUntil);
console.log("In 60-day window?", daysUntil > 0 && daysUntil <= 60);
