import { NextResponse } from "next/server";
import { getEnabledCompanies } from "@/lib/db-preferences";

/**
 * GET /api/companies
 * Fetch all enabled companies for selection
 */
export async function GET() {
  try {
    const companies = await getEnabledCompanies();

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
