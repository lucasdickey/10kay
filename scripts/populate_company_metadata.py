#!/usr/bin/env python3
"""
Populate company metadata for all companies in the database.
This script generates structured metadata including description, characteristics,
products, and geography for each company.
"""

import json
import os
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime

# Company metadata templates based on industry knowledge
COMPANY_METADATA = {
    "AAPL": {
        "description": "Apple designs and manufactures consumer electronics including iPhones, Mac computers, iPads, and wearables, along with software and digital services.",
        "website": "https://www.apple.com",
        "characteristics": {
            "sector": "Consumer Electronics & Software",
            "industry": "Consumer Electronics, Software & Services",
            "employee_count": 164000,
            "revenue_ttm": 383285,
            "revenue_prior_year": 383285,
            "r_and_d_spend_ttm": 28752,
            "r_and_d_spend_prior_year": 26251,
            "founded_year": 1976
        },
        "products": [
            {
                "name": "iPhone",
                "description": "Smartphone with iOS operating system, available in multiple sizes and price points.",
                "pricing": "$799-$1,199 per unit",
                "marketing": "Premium consumer smartphone brand with strong ecosystem integration",
                "customers": {
                    "direct": ["Consumers", "Enterprise customers"],
                    "indirect": ["App developers", "Content providers"],
                    "use_cases": ["Communications", "Photography", "Banking", "Entertainment"]
                }
            },
            {
                "name": "Mac Computers",
                "description": "Personal computers running macOS, including MacBook, iMac, Mac mini, and Mac Studio.",
                "pricing": "$999-$3,999+ per unit",
                "marketing": "Premium computers for creative professionals and consumers",
                "customers": {
                    "direct": ["Individual consumers", "Creative professionals", "Developers"],
                    "indirect": ["Content creators", "Students"],
                    "use_cases": ["Software development", "Content creation", "Design work"]
                }
            },
            {
                "name": "Services & Software",
                "description": "iCloud, App Store, Apple Music, Apple TV+, and other digital services.",
                "pricing": "Subscription-based ($0.99-$19.99/month)",
                "marketing": "Ecosystem services with seamless integration across devices",
                "customers": {
                    "direct": ["Apple device owners", "Developers"],
                    "indirect": ["Content creators", "Media companies"],
                    "use_cases": ["Cloud storage", "App distribution", "Media streaming"]
                }
            }
        ],
        "geography": {
            "headquarters": "Cupertino, California, USA",
            "operates_in": ["United States", "Europe", "Asia-Pacific", "Americas", "40+ countries"],
            "revenue_by_region": {
                "Americas": 46,
                "Europe": 26,
                "Greater China": 19,
                "Japan": 5,
                "Rest of Asia Pacific": 4
            }
        }
    },
    "MSFT": {
        "description": "Microsoft develops and publishes cloud computing, productivity software, gaming, and enterprise solutions including Azure, Office 365, and Xbox.",
        "website": "https://www.microsoft.com",
        "characteristics": {
            "sector": "Software & Cloud Computing",
            "industry": "Enterprise Software, Cloud Services & Gaming",
            "employee_count": 221000,
            "revenue_ttm": 245122,
            "revenue_prior_year": 198289,
            "r_and_d_spend_ttm": 28950,
            "r_and_d_spend_prior_year": 27187,
            "founded_year": 1975
        },
        "products": [
            {
                "name": "Azure Cloud Services",
                "description": "Cloud computing platform for computing, analytics, storage, and networking.",
                "pricing": "Pay-as-you-go pricing with volume discounts",
                "marketing": "Enterprise cloud infrastructure competing with AWS and GCP",
                "customers": {
                    "direct": ["Enterprises", "Startups", "Cloud developers"],
                    "indirect": ["End users of cloud applications"],
                    "use_cases": ["Infrastructure hosting", "Data analytics", "AI/ML workloads"]
                }
            },
            {
                "name": "Microsoft 365",
                "description": "Productivity suite including Word, Excel, Teams, Outlook with cloud collaboration.",
                "pricing": "$6-$30/user/month",
                "marketing": "Essential productivity tools for business collaboration",
                "customers": {
                    "direct": ["Enterprises", "Small/medium businesses", "Consumers"],
                    "indirect": ["Remote workers", "Teams"],
                    "use_cases": ["Document creation", "Communication", "Spreadsheets", "Email"]
                }
            },
            {
                "name": "Xbox Gaming",
                "description": "Gaming consoles, game subscription service, and cloud gaming platform.",
                "pricing": "$9.99-$16.99/month for Game Pass",
                "marketing": "Gaming ecosystem with exclusive titles and cloud gaming",
                "customers": {
                    "direct": ["Gamers", "Game developers", "Content creators"],
                    "indirect": ["Streamers", "Game studios"],
                    "use_cases": ["Gaming entertainment", "Game development", "Streaming"]
                }
            }
        ],
        "geography": {
            "headquarters": "Redmond, Washington, USA",
            "operates_in": ["United States", "Europe", "Asia-Pacific", "Rest of World"],
            "revenue_by_region": {
                "United States": 62,
                "International": 38
            }
        }
    },
    "GOOGL": {
        "description": "Alphabet's Google segment offers search, advertising, cloud services, hardware, and artificial intelligence technologies.",
        "website": "https://www.google.com",
        "characteristics": {
            "sector": "Internet & Software",
            "industry": "Search, Advertising & Cloud Services",
            "employee_count": 190234,
            "revenue_ttm": 307394,
            "revenue_prior_year": 282836,
            "r_and_d_spend_ttm": 48147,
            "r_and_d_spend_prior_year": 45433,
            "founded_year": 1998
        },
        "products": [
            {
                "name": "Google Search & Ads",
                "description": "Search engine and advertising platform generating majority of company revenue.",
                "pricing": "Auction-based advertising pricing (cost-per-click)",
                "marketing": "Dominant search advertising platform",
                "customers": {
                    "direct": ["Advertisers", "Businesses"],
                    "indirect": ["Search users", "Content consumers"],
                    "use_cases": ["Brand awareness", "Lead generation", "E-commerce sales"]
                }
            },
            {
                "name": "Google Cloud Platform",
                "description": "Cloud computing services including compute, storage, BigQuery, and AI tools.",
                "pricing": "Pay-as-you-go cloud infrastructure pricing",
                "marketing": "Enterprise cloud platform with strong data analytics capabilities",
                "customers": {
                    "direct": ["Enterprises", "Developers", "Data teams"],
                    "indirect": ["Business users"],
                    "use_cases": ["Data warehousing", "ML/AI", "Application hosting"]
                }
            },
            {
                "name": "YouTube",
                "description": "Video sharing platform with 2+ billion users and advertising/subscription model.",
                "pricing": "Free with ads or $13.99/month Premium",
                "marketing": "World's largest video platform with content creators",
                "customers": {
                    "direct": ["Content creators", "Advertisers", "Viewers"],
                    "indirect": ["Music labels", "Studios"],
                    "use_cases": ["Video streaming", "Content monetization", "Advertising"]
                }
            }
        ],
        "geography": {
            "headquarters": "Mountain View, California, USA",
            "operates_in": ["United States", "Europe", "Asia-Pacific", "Latin America", "Africa"],
            "revenue_by_region": {
                "United States": 58,
                "International": 42
            }
        }
    },
    "AMZN": {
        "description": "Amazon operates e-commerce marketplace, cloud computing (AWS), digital advertising, and entertainment services.",
        "website": "https://www.amazon.com",
        "characteristics": {
            "sector": "E-commerce & Cloud Computing",
            "industry": "Retail, Cloud Services & Digital Entertainment",
            "employee_count": 1608000,
            "revenue_ttm": 575177,
            "revenue_prior_year": 514389,
            "r_and_d_spend_ttm": 28976,
            "r_and_d_spend_prior_year": 24890,
            "founded_year": 1994
        },
        "products": [
            {
                "name": "Amazon Web Services (AWS)",
                "description": "Cloud computing platform providing compute, storage, databases, and AI services.",
                "pricing": "Pay-as-you-go with volume discounts",
                "marketing": "Market-leading cloud infrastructure provider",
                "customers": {
                    "direct": ["Enterprises", "Startups", "Developers"],
                    "indirect": ["End users"],
                    "use_cases": ["Infrastructure hosting", "AI/ML", "Data analytics", "Gaming"]
                }
            },
            {
                "name": "Amazon.com Retail",
                "description": "E-commerce marketplace for products across categories.",
                "pricing": "Retail product pricing with Prime membership ($139/year)",
                "marketing": "Largest e-commerce marketplace in North America",
                "customers": {
                    "direct": ["Consumers", "Sellers", "Vendors"],
                    "indirect": ["Manufacturers", "Logistics partners"],
                    "use_cases": ["Online shopping", "Seller platform", "Prime benefits"]
                }
            },
            {
                "name": "Amazon Advertising",
                "description": "Advertising platform for sellers on marketplace and external brands.",
                "pricing": "Cost-per-click and cost-per-thousand-impressions pricing",
                "marketing": "Growing advertising segment with shopper purchase intent",
                "customers": {
                    "direct": ["Brands", "Agencies", "Sellers"],
                    "indirect": ["Amazon shoppers"],
                    "use_cases": ["Product promotion", "Brand awareness", "Demand generation"]
                }
            }
        ],
        "geography": {
            "headquarters": "Seattle, Washington, USA",
            "operates_in": ["United States", "Europe", "Asia-Pacific", "Middle East"],
            "revenue_by_region": {
                "North America": 68,
                "International": 32
            }
        }
    },
    "NVDA": {
        "description": "NVIDIA designs and manufactures graphics processing units (GPUs) and AI computing platforms for gaming, data centers, and autonomous vehicles.",
        "website": "https://www.nvidia.com",
        "characteristics": {
            "sector": "Semiconductors & AI Computing",
            "industry": "Graphics Processors & AI Hardware",
            "employee_count": 29600,
            "revenue_ttm": 60922,
            "revenue_prior_year": 26974,
            "r_and_d_spend_ttm": 8675,
            "r_and_d_spend_prior_year": 7339,
            "founded_year": 1993
        },
        "products": [
            {
                "name": "Data Center GPUs (H100, A100)",
                "description": "High-performance GPUs for AI training, inference, and data center workloads.",
                "pricing": "$10,000-$40,000+ per GPU",
                "marketing": "Market-leading AI acceleration for enterprise data centers",
                "customers": {
                    "direct": ["Cloud providers", "Enterprises", "AI research labs"],
                    "indirect": ["Researchers", "Data scientists"],
                    "use_cases": ["LLM training", "AI inference", "High-performance computing"]
                }
            },
            {
                "name": "GeForce Gaming GPUs",
                "description": "Consumer graphics cards for gaming and content creation.",
                "pricing": "$300-$2,000+ per GPU",
                "marketing": "Premium gaming performance with ray tracing",
                "customers": {
                    "direct": ["PC gamers", "Content creators", "Developers"],
                    "indirect": ["Streamers", "3D artists"],
                    "use_cases": ["Gaming", "Video editing", "3D rendering"]
                }
            },
            {
                "name": "CUDA Platform",
                "description": "Parallel computing platform for GPU-accelerated general computing.",
                "pricing": "Free software (monetized through hardware)",
                "marketing": "Standard platform for GPU-accelerated computing",
                "customers": {
                    "direct": ["Developers", "Researchers", "Data scientists"],
                    "indirect": ["End users of GPU applications"],
                    "use_cases": ["GPU programming", "Scientific computing", "AI development"]
                }
            }
        ],
        "geography": {
            "headquarters": "Santa Clara, California, USA",
            "operates_in": ["United States", "Taiwan", "South Korea", "China", "Japan", "Europe"],
            "revenue_by_region": {
                "United States": 28,
                "Taiwan": 17,
                "China": 23,
                "Rest of World": 32
            }
        }
    }
}

# Industry-based templates for companies without specific data
INDUSTRY_TEMPLATES = {
    "Financial Technology": {
        "description": "Fintech company providing digital financial services and payments solutions.",
        "sector": "Financial Technology",
        "characteristics": {
            "industry": "Financial Services Technology",
            "employee_count": 2500,
            "revenue_ttm": 1500,
            "revenue_prior_year": 1200,
            "r_and_d_spend_ttm": 300,
            "r_and_d_spend_prior_year": 250,
            "founded_year": 2010
        }
    },
    "Enterprise Software": {
        "description": "Enterprise software company providing business solutions for digital transformation.",
        "sector": "Enterprise Software",
        "characteristics": {
            "industry": "Business Software & Services",
            "employee_count": 8000,
            "revenue_ttm": 5000,
            "revenue_prior_year": 4500,
            "r_and_d_spend_ttm": 800,
            "r_and_d_spend_prior_year": 700,
            "founded_year": 2005
        }
    },
    "Semiconductors": {
        "description": "Semiconductor company designing and manufacturing chips for computing and communications.",
        "sector": "Semiconductors",
        "characteristics": {
            "industry": "Semiconductor Manufacturing & Design",
            "employee_count": 15000,
            "revenue_ttm": 8000,
            "revenue_prior_year": 6000,
            "r_and_d_spend_ttm": 1500,
            "r_and_d_spend_prior_year": 1300,
            "founded_year": 1985
        }
    },
    "Cloud Computing": {
        "description": "Cloud infrastructure and platform services provider.",
        "sector": "Cloud Computing",
        "characteristics": {
            "industry": "Cloud Services",
            "employee_count": 6000,
            "revenue_ttm": 4000,
            "revenue_prior_year": 3000,
            "r_and_d_spend_ttm": 600,
            "r_and_d_spend_prior_year": 500,
            "founded_year": 2010
        }
    },
    "Cybersecurity": {
        "description": "Cybersecurity company providing threat detection and network security solutions.",
        "sector": "Cybersecurity",
        "characteristics": {
            "industry": "Information Security",
            "employee_count": 4000,
            "revenue_ttm": 2000,
            "revenue_prior_year": 1700,
            "r_and_d_spend_ttm": 400,
            "r_and_d_spend_prior_year": 350,
            "founded_year": 2005
        }
    },
    "E-commerce": {
        "description": "E-commerce platform providing digital marketplace and retail solutions.",
        "sector": "E-commerce & Retail",
        "characteristics": {
            "industry": "E-commerce & Digital Retail",
            "employee_count": 3000,
            "revenue_ttm": 2000,
            "revenue_prior_year": 1500,
            "r_and_d_spend_ttm": 250,
            "r_and_d_spend_prior_year": 200,
            "founded_year": 2010
        }
    },
    "Media & Entertainment": {
        "description": "Media and entertainment company producing and distributing digital content.",
        "sector": "Media & Entertainment",
        "characteristics": {
            "industry": "Digital Media & Content",
            "employee_count": 5000,
            "revenue_ttm": 3000,
            "revenue_prior_year": 2500,
            "r_and_d_spend_ttm": 400,
            "r_and_d_spend_prior_year": 350,
            "founded_year": 2010
        }
    },
    "Data & Analytics": {
        "description": "Data analytics and business intelligence platform company.",
        "sector": "Data & Analytics",
        "characteristics": {
            "industry": "Analytics & Data Science",
            "employee_count": 4000,
            "revenue_ttm": 2500,
            "revenue_prior_year": 2000,
            "r_and_d_spend_ttm": 500,
            "r_and_d_spend_prior_year": 400,
            "founded_year": 2010
        }
    }
}

# Mapping of tickers to industries for template selection
TICKER_INDUSTRY_MAP = {
    "META": "Media & Entertainment",
    "TSLA": "Semiconductors",
    "AVGO": "Semiconductors",
    "ORCL": "Enterprise Software",
    "INTC": "Semiconductors",
    "TSM": "Semiconductors",
    "ASML": "Semiconductors",
    "ADBE": "Enterprise Software",
    "CRM": "Enterprise Software",
    "NOW": "Enterprise Software",
    "SNOW": "Data & Analytics",
    "SHOP": "E-commerce",
    "QCOM": "Semiconductors",
    "TXN": "Semiconductors",
    "MU": "Semiconductors",
    "AMD": "Semiconductors",
    "ADSK": "Enterprise Software",
    "PANW": "Cybersecurity",
    "CRWD": "Cybersecurity",
    "ZM": "Enterprise Software",
    "INTU": "Enterprise Software",
    "TEAM": "Enterprise Software",
    "MRVL": "Semiconductors",
    "CDNS": "Enterprise Software",
    "KLAC": "Semiconductors",
    "LRCX": "Semiconductors",
    "ADI": "Semiconductors",
    "PYPL": "Financial Technology",
    "SQ": "Financial Technology",
    "SPOT": "Media & Entertainment",
    "UBER": "E-commerce",
    "DASH": "E-commerce",
    "WDAY": "Enterprise Software",
    "ZS": "Cybersecurity",
    "MDB": "Data & Analytics",
    "SPLK": "Data & Analytics",
    "OKTA": "Cybersecurity",
    "ZI": "Enterprise Software",
    "PINS": "Media & Entertainment",
    "U": "Media & Entertainment",
    "FIG": "Enterprise Software",
    "GOOG": "Internet & Software",
}

def get_company_metadata(ticker, name):
    """Get or generate metadata for a company."""
    # Use specific metadata if available
    if ticker in COMPANY_METADATA:
        metadata = COMPANY_METADATA[ticker].copy()
        metadata["domain"] = metadata.get("website", "").split("//")[-1].rstrip("/")
        return metadata

    # Use industry template if available
    industry = TICKER_INDUSTRY_MAP.get(ticker, "Enterprise Software")
    template = INDUSTRY_TEMPLATES.get(industry, INDUSTRY_TEMPLATES["Enterprise Software"])

    metadata = {
        "description": template["description"],
        "website": f"https://www.{name.lower().replace(' ', '')}.com",
        "characteristics": template["characteristics"].copy(),
        "domain": name.lower().replace(" ", "") + ".com",
        "products": [
            {
                "name": f"{name} Core Product",
                "description": f"Primary product/service offering from {name}.",
                "pricing": "Contact for pricing",
                "marketing": f"Main offering from {name}",
                "customers": {
                    "direct": ["Businesses", "Enterprises"],
                    "indirect": ["End users"],
                    "use_cases": ["Business operations", "Digital transformation"]
                }
            }
        ],
        "geography": {
            "headquarters": "United States",
            "operates_in": ["United States", "Europe", "Asia-Pacific"],
            "revenue_by_region": {
                "North America": 60,
                "Europe": 25,
                "Asia-Pacific": 15
            }
        }
    }

    return metadata

def populate_metadata():
    """Populate metadata for all companies."""
    # Connect to database
    conn = psycopg2.connect(
        host="tenkay-db.c41o8ksoi5bt.us-east-1.rds.amazonaws.com",
        database="tenkai",
        user="postgres",
        password=os.environ.get("DB_PASSWORD", "Nicolebday0831_NIC")
    )

    cursor = conn.cursor()

    try:
        # Get all companies
        cursor.execute("SELECT id, ticker, name FROM companies ORDER BY ticker;")
        companies = cursor.fetchall()

        print(f"Found {len(companies)} companies. Populating metadata...")

        updated_count = 0
        for company_id, ticker, name in companies:
            metadata = get_company_metadata(ticker, name)

            # Convert to JSON and update database
            cursor.execute(
                """UPDATE companies
                   SET metadata = %s
                   WHERE id = %s;""",
                (json.dumps(metadata), company_id)
            )
            updated_count += 1

            if updated_count % 10 == 0:
                print(f"  Updated {updated_count}/{len(companies)} companies...")

        conn.commit()
        print(f"\n✓ Successfully updated {updated_count} companies with metadata!")

        # Verify updates
        cursor.execute("SELECT COUNT(*) FROM companies WHERE metadata IS NOT NULL AND metadata != '{}'::jsonb;")
        count_with_metadata = cursor.fetchone()[0]
        print(f"✓ Validation: {count_with_metadata}/{len(companies)} companies have metadata")

        # Show sample
        print("\n Sample metadata (AAPL):")
        cursor.execute("SELECT metadata FROM companies WHERE ticker = 'AAPL';")
        result = cursor.fetchone()
        if result:
            metadata = json.loads(result[0]) if result[0] else {}
            print(f"  - Description: {metadata.get('description', 'N/A')[:80]}...")
            print(f"  - Website: {metadata.get('website', 'N/A')}")
            print(f"  - Products: {len(metadata.get('products', []))} products")
            print(f"  - Characteristics: {metadata.get('characteristics', {}).get('sector', 'N/A')}")

    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    populate_metadata()
