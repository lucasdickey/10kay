-- Migration 008: Add Company Metadata
-- Adds comprehensive company information to the metadata JSONB field
-- This demonstrates the new company overview, products, and geography features

-- Example 1: Stripe (if exists in database)
-- Note: This will only update if the company ticker exists
UPDATE companies
SET metadata = jsonb_set(
  COALESCE(metadata, '{}'::jsonb),
  '{description}',
  '"Stripe is a financial infrastructure platform for businesses, providing payment processing and financial tools to help companies accept payments and manage their money online."'::jsonb
)
WHERE ticker = 'STRIPE';

UPDATE companies
SET metadata = jsonb_set(
  COALESCE(metadata, '{}'::jsonb),
  '{website}',
  '"https://stripe.com"'::jsonb
)
WHERE ticker = 'STRIPE';

UPDATE companies
SET metadata = jsonb_set(
  COALESCE(metadata, '{}'::jsonb),
  '{characteristics}',
  '{
    "sector": "Financial Technology (Payments)",
    "industry": "Payment Processing & Financial Infrastructure",
    "employee_count": 8000,
    "revenue_ttm": 17200,
    "revenue_prior_year": 14400,
    "r_and_d_spend_ttm": 2100,
    "r_and_d_spend_prior_year": 1800,
    "founded_year": 2010
  }'::jsonb
)
WHERE ticker = 'STRIPE';

UPDATE companies
SET metadata = jsonb_set(
  COALESCE(metadata, '{}'::jsonb),
  '{products}',
  '[
    {
      "name": "Stripe Payments",
      "description": "Online payment processing platform that enables businesses to accept credit cards, digital wallets, and local payment methods globally.",
      "pricing": "2.9% + $0.30 per successful card charge (standard pricing)",
      "marketing": "Developer-first platform marketed to startups, e-commerce, and SaaS companies",
      "customers": {
        "direct": ["E-commerce platforms", "SaaS companies", "Marketplaces", "Subscription businesses"],
        "indirect": ["Online shoppers", "App users", "Subscription service consumers"],
        "use_cases": ["Accept payments online", "Recurring billing", "Global payment acceptance", "Fraud prevention"]
      }
    },
    {
      "name": "Stripe Connect",
      "description": "Embedded payment and payout platform for marketplaces and platforms to handle money movement between multiple parties.",
      "pricing": "Additional 0.25% fee on top of standard processing fees",
      "marketing": "Positioned for multi-sided marketplaces, crowdfunding platforms, and gig economy apps",
      "customers": {
        "direct": ["Marketplaces", "On-demand platforms", "Crowdfunding sites", "Platform businesses"],
        "indirect": ["Sellers on marketplaces", "Freelancers", "Service providers"],
        "use_cases": ["Marketplace payments", "Seller payouts", "Platform monetization", "Multi-party transactions"]
      }
    },
    {
      "name": "Stripe Billing",
      "description": "Subscription and recurring billing platform with support for complex pricing models, invoicing, and revenue recognition.",
      "pricing": "0.5% of recurring revenue (in addition to payment processing fees)",
      "marketing": "Built for subscription businesses and usage-based pricing models",
      "customers": {
        "direct": ["SaaS companies", "Subscription box services", "Media streaming platforms", "B2B software providers"],
        "indirect": ["Business customers", "Subscription consumers"],
        "use_cases": ["Manage recurring subscriptions", "Usage-based billing", "Automated invoicing", "Revenue recognition"]
      }
    },
    {
      "name": "Stripe Terminal",
      "description": "In-person payment solution with card readers and point-of-sale hardware for physical retail.",
      "pricing": "Hardware costs ($59-$249) + standard payment processing fees",
      "marketing": "Unified payments for online and offline businesses",
      "customers": {
        "direct": ["Retail stores", "Restaurants", "Pop-up shops", "Omnichannel businesses"],
        "indirect": ["In-store shoppers", "Restaurant diners"],
        "use_cases": ["In-person card payments", "Omnichannel commerce", "Unified payment reporting"]
      }
    },
    {
      "name": "Stripe Treasury",
      "description": "Banking-as-a-service API that enables platforms to offer financial accounts, cards, and banking services to their users.",
      "pricing": "Custom pricing based on volume and features",
      "marketing": "Embedded finance for platforms looking to become financial service providers",
      "customers": {
        "direct": ["Fintech platforms", "Vertical SaaS companies", "Embedded finance businesses"],
        "indirect": ["Small businesses", "Freelancers", "Gig workers"],
        "use_cases": ["Embed banking services", "Issue debit cards", "Manage business finances", "Instant payouts"]
      }
    },
    {
      "name": "Stripe Radar",
      "description": "Machine learning-powered fraud detection and prevention tool built into Stripe payments.",
      "pricing": "$0.05 per screened transaction (included for some plans)",
      "marketing": "Built-in fraud protection for all Stripe users",
      "customers": {
        "direct": ["All Stripe payment users", "High-risk merchants", "E-commerce businesses"],
        "indirect": ["Customers making online purchases"],
        "use_cases": ["Prevent fraudulent transactions", "Reduce chargebacks", "Adaptive fraud scoring"]
      }
    }
  ]'::jsonb
)
WHERE ticker = 'STRIPE';

UPDATE companies
SET metadata = jsonb_set(
  COALESCE(metadata, '{}'::jsonb),
  '{geography}',
  '{
    "headquarters": "San Francisco, California, USA",
    "operates_in": ["United States", "Canada", "United Kingdom", "European Union", "Australia", "Singapore", "Japan", "40+ countries globally"],
    "revenue_by_region": {
      "North America": 55,
      "Europe": 30,
      "Asia Pacific": 10,
      "Rest of World": 5
    }
  }'::jsonb
)
WHERE ticker = 'STRIPE';

-- Example 2: NVIDIA (likely to exist in database as NVDA)
UPDATE companies
SET metadata = jsonb_set(
  COALESCE(metadata, '{}'::jsonb),
  '{description}',
  '"NVIDIA designs and manufactures graphics processing units (GPUs) and system-on-chip (SoC) units for gaming, professional visualization, data centers, and automotive markets."'::jsonb
)
WHERE ticker = 'NVDA';

UPDATE companies
SET metadata = jsonb_set(
  COALESCE(metadata, '{}'::jsonb),
  '{website}',
  '"https://www.nvidia.com"'::jsonb
)
WHERE ticker = 'NVDA';

UPDATE companies
SET metadata = jsonb_set(
  COALESCE(metadata, '{}'::jsonb),
  '{characteristics}',
  '{
    "sector": "Semiconductors / AI Computing",
    "industry": "Graphics Processing Units & AI Hardware",
    "employee_count": 29600,
    "revenue_ttm": 60922,
    "revenue_prior_year": 26974,
    "r_and_d_spend_ttm": 8675,
    "r_and_d_spend_prior_year": 7339,
    "founded_year": 1993
  }'::jsonb
)
WHERE ticker = 'NVDA';

UPDATE companies
SET metadata = jsonb_set(
  COALESCE(metadata, '{}'::jsonb),
  '{products}',
  '[
    {
      "name": "NVIDIA GeForce (Gaming GPUs)",
      "description": "Consumer graphics cards designed for PC gaming, content creation, and enthusiast computing.",
      "pricing": "Hardware sales ($300-$2000+ per GPU)",
      "marketing": "Premium gaming performance and ray tracing capabilities for gamers and creators",
      "customers": {
        "direct": ["PC gamers", "Content creators", "Game developers", "OEM partners"],
        "indirect": ["Gamers purchasing pre-built PCs", "Laptop consumers"],
        "use_cases": ["High-performance gaming", "Video editing", "3D rendering", "Live streaming"]
      }
    },
    {
      "name": "NVIDIA Data Center (A100, H100 GPUs)",
      "description": "High-performance GPUs designed for AI training, inference, and data center workloads.",
      "pricing": "Enterprise pricing ($10,000-$40,000+ per GPU, typically sold in bulk)",
      "marketing": "AI and HPC acceleration for cloud providers and enterprises",
      "customers": {
        "direct": ["Cloud service providers", "AI research labs", "Enterprise data centers", "Supercomputing facilities"],
        "indirect": ["AI developers", "Data scientists", "Researchers"],
        "use_cases": ["AI model training", "Large language models", "Scientific computing", "Deep learning inference"]
      }
    },
    {
      "name": "NVIDIA CUDA Platform",
      "description": "Parallel computing platform and API that enables developers to use NVIDIA GPUs for general-purpose processing.",
      "pricing": "Free software platform (monetized through hardware sales)",
      "marketing": "Developer ecosystem and standard for GPU-accelerated computing",
      "customers": {
        "direct": ["Software developers", "AI researchers", "Scientific computing users"],
        "indirect": ["End users of GPU-accelerated applications"],
        "use_cases": ["GPU programming", "Accelerated computing", "AI development", "Scientific simulations"]
      }
    },
    {
      "name": "NVIDIA DGX Systems",
      "description": "Integrated AI supercomputers combining GPUs, software, and infrastructure for enterprise AI development.",
      "pricing": "Turnkey systems ($200,000-$500,000+ per system)",
      "marketing": "Enterprise AI infrastructure for companies building AI solutions",
      "customers": {
        "direct": ["Large enterprises", "AI research organizations", "Government institutions"],
        "indirect": ["Data science teams", "ML engineers"],
        "use_cases": ["Enterprise AI development", "Training large models", "AI research", "Conversational AI"]
      }
    }
  ]'::jsonb
)
WHERE ticker = 'NVDA';

UPDATE companies
SET metadata = jsonb_set(
  COALESCE(metadata, '{}'::jsonb),
  '{geography}',
  '{
    "headquarters": "Santa Clara, California, USA",
    "operates_in": ["United States", "Taiwan", "China", "Europe", "Japan", "India", "Worldwide"],
    "revenue_by_region": {
      "United States": 22,
      "Taiwan": 17,
      "China/Hong Kong": 14,
      "Singapore": 11,
      "Other": 36
    }
  }'::jsonb
)
WHERE ticker = 'NVDA';

-- Add domain to metadata if not already present for both companies
UPDATE companies
SET metadata = jsonb_set(
  COALESCE(metadata, '{}'::jsonb),
  '{domain}',
  '"stripe.com"'::jsonb
)
WHERE ticker = 'STRIPE' AND (metadata->>'domain' IS NULL OR metadata->>'domain' = '');

UPDATE companies
SET metadata = jsonb_set(
  COALESCE(metadata, '{}'::jsonb),
  '{domain}',
  '"nvidia.com"'::jsonb
)
WHERE ticker = 'NVDA' AND (metadata->>'domain' IS NULL OR metadata->>'domain' = '');

-- Verification query (comment out when running migration)
-- SELECT ticker, name, metadata FROM companies WHERE ticker IN ('STRIPE', 'NVDA');

COMMENT ON COLUMN companies.metadata IS 'Company metadata including description, website, characteristics, products, and geography';
