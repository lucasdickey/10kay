import { NextResponse } from "next/server";
import { getAllCompaniesPerformance } from "@/lib/performance";

/**
 * GET /api/companies
 * Fetch all enabled companies with 7-day performance metrics and comparisons
 */
export async function GET() {
  try {
    const companies = await getAllCompaniesPerformance();

    return NextResponse.json({
      success: true,
      data: companies,
    });
  } catch (error) {
    console.error("Error fetching companies:", error);
    return NextResponse.json(
      { success: false, error: "Internal server error" },
      { status: 500 }
    );
  }
}
