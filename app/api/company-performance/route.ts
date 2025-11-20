import { NextResponse } from "next/server";
import { getAllCompaniesPerformance } from "@/lib/performance";

/**
 * GET /api/company-performance
 *
 * Returns performance data for all tracked companies including:
 * - Market cap
 * - 7-day price change
 * - Comparison to aggregate performance
 * - Comparison to sector performance
 */
export async function GET() {
  try {
    const performance = await getAllCompaniesPerformance();

    return NextResponse.json({
      success: true,
      data: performance,
      timestamp: new Date().toISOString(),
    });
  } catch (error) {
    console.error("Error fetching company performance:", error);
    return NextResponse.json(
      {
        success: false,
        error: "Failed to fetch company performance data",
      },
      { status: 500 }
    );
  }
}
