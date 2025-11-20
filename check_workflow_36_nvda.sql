-- Query to diagnose why NVDA isn't showing up after workflow #36

-- 1. Check if NVDA company exists and is enabled
SELECT 'NVDA Company Status:' as check_name;
SELECT id, ticker, name, enabled, added_at
FROM companies
WHERE ticker = 'NVDA';

-- 2. Check all NVDA filings (recent ones)
SELECT '' as separator;
SELECT 'Recent NVDA Filings (last 5):' as check_name;
SELECT
    f.id,
    f.filing_type,
    f.filing_date,
    f.period_end_date,
    f.fiscal_year,
    f.fiscal_quarter,
    f.status,
    f.created_at,
    f.updated_at
FROM filings f
JOIN companies c ON f.company_id = c.id
WHERE c.ticker = 'NVDA'
ORDER BY f.filing_date DESC
LIMIT 5;

-- 3. Check content for NVDA filings
SELECT '' as separator;
SELECT 'NVDA Content (all):' as check_name;
SELECT
    c.id as content_id,
    f.filing_type,
    f.filing_date,
    c.format,
    c.executive_summary IS NOT NULL as has_summary,
    c.key_takeaways IS NOT NULL as has_takeaways,
    c.blog_html IS NOT NULL as has_blog_html,
    c.email_html IS NOT NULL as has_email_html,
    c.published_at,
    c.slug,
    c.created_at,
    c.updated_at
FROM content c
JOIN filings f ON c.filing_id = f.id
JOIN companies co ON c.company_id = co.id
WHERE co.ticker = 'NVDA'
ORDER BY f.filing_date DESC;

-- 4. Check what would be visible on the website (blog_html not null)
SELECT '' as separator;
SELECT 'NVDA Content Visible on Website (blog_html IS NOT NULL):' as check_name;
SELECT
    c.id,
    co.ticker,
    f.filing_type,
    f.filing_date,
    LEFT(c.executive_summary, 100) as summary_preview,
    c.published_at,
    c.slug
FROM content c
JOIN filings f ON c.filing_id = f.id
JOIN companies co ON c.company_id = co.id
WHERE co.ticker = 'NVDA'
    AND c.blog_html IS NOT NULL
ORDER BY f.filing_date DESC;

-- 5. Check what's missing blog_html
SELECT '' as separator;
SELECT 'NVDA Content MISSING blog_html:' as check_name;
SELECT
    c.id,
    f.filing_type,
    f.filing_date,
    c.format,
    c.executive_summary IS NOT NULL as has_summary,
    c.blog_html IS NOT NULL as has_blog_html,
    c.created_at
FROM content c
JOIN filings f ON c.filing_id = f.id
JOIN companies co ON c.company_id = co.id
WHERE co.ticker = 'NVDA'
    AND c.blog_html IS NULL;

-- 6. Check recently created content (within last 24 hours)
SELECT '' as separator;
SELECT 'All Content Created in Last 24 Hours:' as check_name;
SELECT
    co.ticker,
    f.filing_type,
    f.filing_date,
    c.blog_html IS NOT NULL as has_blog_html,
    c.created_at
FROM content c
JOIN filings f ON c.filing_id = f.id
JOIN companies co ON c.company_id = co.id
WHERE c.created_at > NOW() - INTERVAL '24 hours'
ORDER BY c.created_at DESC;

-- 7. Check recently updated content (within last 24 hours)
SELECT '' as separator;
SELECT 'All Content Updated in Last 24 Hours:' as check_name;
SELECT
    co.ticker,
    f.filing_type,
    f.filing_date,
    c.blog_html IS NOT NULL as has_blog_html,
    c.updated_at
FROM content c
JOIN filings f ON c.filing_id = f.id
JOIN companies co ON c.company_id = co.id
WHERE c.updated_at > NOW() - INTERVAL '24 hours'
ORDER BY c.updated_at DESC;
