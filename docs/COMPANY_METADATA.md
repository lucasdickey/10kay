# Company Metadata Feature

This document describes the comprehensive company information components added to the Company page.

## Overview

The Company page now displays rich company information including:
- **Company Description** - Brief overview (max 50 words)
- **Company Website** - Official company URL
- **Company Characteristics** - Sector, employee count, revenue, R&D spend
- **Company Products** - Detailed product/service listings with pricing, marketing, and customer information
- **Company Geography** - Headquarters, operating regions, and revenue breakdown

## Architecture

### Data Model

Company information is stored in the `companies.metadata` JSONB field in PostgreSQL. This flexible structure allows for rich, semi-structured data without schema migrations.

**TypeScript Interface:**
```typescript
interface CompanyMetadata {
  domain?: string;
  description?: string;
  website?: string;
  characteristics?: {
    sector?: string;
    industry?: string;
    employee_count?: number;
    revenue_ttm?: number;              // In millions USD
    revenue_prior_year?: number;        // In millions USD
    r_and_d_spend_ttm?: number;         // In millions USD
    r_and_d_spend_prior_year?: number;  // In millions USD
    founded_year?: number;
  };
  products?: Array<{
    name: string;
    description: string;
    pricing?: string;
    marketing?: string;
    customers?: {
      direct?: string[];      // Direct customer segments
      indirect?: string[];    // Indirect/end customers
      use_cases?: string[];   // Problems solved
    };
  }>;
  geography?: {
    headquarters?: string;
    operates_in?: string[];
    revenue_by_region?: Record<string, number>; // Percentage breakdown
  };
}
```

### Components

#### 1. CompanyOverview (`/components/CompanyOverview.tsx`)
Displays company description, website, and financial characteristics.

**Features:**
- Responsive grid layout (1-3 columns)
- Color-coded cards (blue for revenue, purple for R&D)
- Automatic number formatting ($1.5B, $250M)
- Conditional rendering (only shows if data available)

#### 2. CompanyProducts (`/components/CompanyProducts.tsx`)
Displays detailed product information with customer segments.

**Features:**
- Blue left border for visual hierarchy
- Expandable product cards
- Separate sections for direct/indirect customers
- Use case highlighting with checkmarks
- Product count summary

#### 3. CompanyGeography (`/components/CompanyGeography.tsx`)
Shows geographic presence and revenue distribution.

**Features:**
- Headquarters with building icon
- Operating regions as pills/badges
- Revenue breakdown with progress bars
- Regional percentage visualization

## Usage

### Adding Company Data

**Option 1: SQL Update**
```sql
UPDATE companies
SET metadata = '{
  "description": "Brief company description here",
  "website": "https://example.com",
  "characteristics": {
    "sector": "Technology",
    "employee_count": 5000,
    "revenue_ttm": 1200,
    "r_and_d_spend_ttm": 300
  },
  "products": [...],
  "geography": {...}
}'::jsonb
WHERE ticker = 'EXAMPLE';
```

**Option 2: Incremental Updates**
```sql
-- Add just description
UPDATE companies
SET metadata = jsonb_set(
  COALESCE(metadata, '{}'::jsonb),
  '{description}',
  '"Your description here"'::jsonb
)
WHERE ticker = 'EXAMPLE';
```

### Sample Data

Run the migration to add sample data for Stripe and NVIDIA:
```bash
psql $DATABASE_URL -f migrations/008_add_company_metadata.sql
```

### Using in Components

The Company page (`/app/[ticker]/page.tsx`) automatically fetches and displays this data:

```tsx
<CompanyOverview
  ticker={companyData.ticker}
  name={companyData.name}
  metadata={companyData.metadata}
/>
<CompanyProducts products={companyData.metadata?.products} />
<CompanyGeography geography={companyData.metadata?.geography} />
```

## Data Guidelines

### Description
- Keep under 50 words
- Focus on what the company does, not history
- Avoid marketing fluff

### Products
- Limit to 2-3 bullet points per product
- Include what, how it's priced, and how it's marketed
- Distinguish between direct and indirect customers
- Clearly state problems being solved

### Example: Stripe
Stripe has 20+ products, each documented with:
- Product name (e.g., "Stripe Payments", "Stripe Connect")
- Clear description of functionality
- Pricing model (e.g., "2.9% + $0.30 per transaction")
- Target market positioning
- Customer segments (direct: e-commerce platforms, indirect: online shoppers)
- Use cases (e.g., "Accept payments online", "Prevent fraud")

### Financial Data
- All amounts in **millions USD**
- TTM = Trailing Twelve Months
- Prior Year = Most recent completed fiscal year
- R&D Spend is separate from other operating expenses

### Geography
- Headquarters: City, State/Province, Country
- Operates in: List countries or regions
- Revenue by region: Percentage breakdown (must sum to 100%)

## Design System

### Colors
- **Gray** (`bg-gray-50`, `text-gray-600`): General information
- **Blue** (`bg-blue-50`, `text-blue-600`): Revenue metrics, primary actions
- **Purple** (`bg-purple-50`, `text-purple-600`): R&D and innovation metrics
- **Green** (`text-green-600`): Direct customers
- **Blue (dark)** (`text-blue-600`): Indirect customers, use cases

### Layout
- Components use `space-y-6` for vertical spacing
- Cards have `rounded-lg` borders with shadows
- Grid layouts are responsive: 1 column (mobile) → 2-3 columns (desktop)

## Future Enhancements

Potential additions:
1. **Competitors** - List key competitors and market positioning
2. **Key Partnerships** - Strategic partnerships and integrations
3. **Awards & Recognition** - Industry awards and certifications
4. **Timeline** - Key company milestones
5. **Management Team** - Leadership profiles
6. **Investor Information** - Market cap, PE ratio, analyst ratings

## File Reference

| File | Purpose |
|------|---------|
| `/lib/company-types.ts` | TypeScript interfaces and helper functions |
| `/components/CompanyOverview.tsx` | Overview component with characteristics |
| `/components/CompanyProducts.tsx` | Product listing with customer details |
| `/components/CompanyGeography.tsx` | Geographic presence visualization |
| `/app/[ticker]/page.tsx` | Company page integration |
| `/migrations/008_add_company_metadata.sql` | Sample data migration |

## Questions?

For questions or issues with the company metadata feature, please refer to:
- TypeScript types in `/lib/company-types.ts`
- Sample data in `/migrations/008_add_company_metadata.sql`
- Component implementations in `/components/Company*.tsx`
