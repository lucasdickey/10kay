/**
 * Company Metadata Type Definitions
 *
 * These interfaces define the structure of the companies.metadata JSONB field
 * for storing comprehensive company information.
 */

export interface CompanyProduct {
  name: string;
  description: string;
  pricing?: string; // e.g., "Usage-based", "Subscription", "Transaction fees"
  marketing?: string; // How it's marketed, target positioning
  customers?: {
    direct?: string[]; // Direct customer segments (e.g., "E-commerce platforms", "SaaS companies")
    indirect?: string[]; // Indirect/end customers (e.g., "Online shoppers", "App users")
    use_cases?: string[]; // What problems are being solved (e.g., "Accept payments online", "Prevent fraud")
  };
}

export interface CompanyCharacteristics {
  sector?: string; // e.g., "Payments", "AI", "Logistics", "Semiconductor"
  industry?: string; // More specific categorization
  employee_count?: number;
  revenue_ttm?: number; // Trailing twelve months revenue in millions USD
  revenue_prior_year?: number; // Prior fiscal year revenue in millions USD
  r_and_d_spend_ttm?: number; // R&D spend TTM in millions USD
  r_and_d_spend_prior_year?: number; // R&D spend prior year in millions USD
  founded_year?: number;
}

export interface CompanyGeography {
  headquarters?: string; // e.g., "San Francisco, CA"
  operates_in?: string[]; // Countries/regions where services are offered
  revenue_by_region?: Record<string, number>; // Optional: percentage breakdown by region
}

export interface CompanyMetadata {
  // Existing field
  domain?: string;

  // New fields for comprehensive company information
  description?: string; // Brief company description (max 50 words)
  website?: string; // Full website URL
  characteristics?: CompanyCharacteristics;
  products?: CompanyProduct[];
  geography?: CompanyGeography;
}

/**
 * Helper function to format large numbers as millions/billions
 */
export function formatCurrency(value: number | undefined, decimals: number = 1): string {
  if (value === undefined || value === null) return 'N/A';

  if (value >= 1000) {
    return `$${(value / 1000).toFixed(decimals)}B`;
  }
  return `$${value.toFixed(decimals)}M`;
}

/**
 * Helper function to format employee count with commas
 */
export function formatEmployeeCount(count: number | undefined): string {
  if (count === undefined || count === null) return 'N/A';
  return count.toLocaleString();
}
