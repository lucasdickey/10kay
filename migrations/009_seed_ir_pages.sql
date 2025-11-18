-- Seed ir_pages table with investor relations URLs for tracked companies
-- This migration populates the ir_pages table with known IR URLs for all 47 tech companies

-- Helper function to upsert IR page
CREATE OR REPLACE FUNCTION upsert_ir_page(
    p_ticker VARCHAR,
    p_ir_url TEXT
) RETURNS VOID AS $$
DECLARE
    v_company_id UUID;
BEGIN
    -- Get company_id from ticker
    SELECT id INTO v_company_id
    FROM companies
    WHERE ticker = p_ticker;

    -- Skip if company not found
    IF v_company_id IS NULL THEN
        RAISE NOTICE 'Company % not found, skipping', p_ticker;
        RETURN;
    END IF;

    -- Upsert IR page
    INSERT INTO ir_pages (
        company_id,
        ticker,
        ir_url,
        scraping_enabled,
        scraping_frequency,
        status,
        created_at,
        updated_at
    ) VALUES (
        v_company_id,
        p_ticker,
        p_ir_url,
        true,
        'on_filing',  -- Scrape when new filings are published
        'active',
        now(),
        now()
    )
    ON CONFLICT (company_id)
    DO UPDATE SET
        ir_url = EXCLUDED.ir_url,
        updated_at = now();
END;
$$ LANGUAGE plpgsql;

-- Seed IR pages for all companies
SELECT upsert_ir_page('AAPL', 'https://investor.apple.com/investor-relations/default.aspx');
SELECT upsert_ir_page('MSFT', 'https://www.microsoft.com/en-us/investor');
SELECT upsert_ir_page('GOOGL', 'https://abc.xyz/investor/');
SELECT upsert_ir_page('GOOG', 'https://abc.xyz/investor/');
SELECT upsert_ir_page('AMZN', 'https://ir.aboutamazon.com/overview/default.aspx');
SELECT upsert_ir_page('NVDA', 'https://investor.nvidia.com/home/default.aspx');
SELECT upsert_ir_page('META', 'https://investor.fb.com/');
SELECT upsert_ir_page('TSLA', 'https://ir.tesla.com/');
SELECT upsert_ir_page('BRK.B', 'https://www.berkshirehathaway.com/reports.html');
SELECT upsert_ir_page('UNH', 'https://www.unitedhealthgroup.com/investors.html');
SELECT upsert_ir_page('XOM', 'https://corporate.exxonmobil.com/investors');
SELECT upsert_ir_page('JNJ', 'https://www.investor.jnj.com/');
SELECT upsert_ir_page('JPM', 'https://www.jpmorganchase.com/ir/investor-relations');
SELECT upsert_ir_page('V', 'https://investor.visa.com/');
SELECT upsert_ir_page('PG', 'https://www.pginvestor.com/');
SELECT upsert_ir_page('MA', 'https://investor.mastercard.com/');
SELECT upsert_ir_page('HD', 'https://ir.homedepot.com/');
SELECT upsert_ir_page('CVX', 'https://www.chevron.com/investors');
SELECT upsert_ir_page('MRK', 'https://www.merck.com/company-overview/investors/');
SELECT upsert_ir_page('ABBV', 'https://investors.abbvie.com/');
SELECT upsert_ir_page('KO', 'https://investors.coca-colacompany.com/');
SELECT upsert_ir_page('PEP', 'https://www.pepsico.com/investors');
SELECT upsert_ir_page('COST', 'https://investor.costco.com/');
SELECT upsert_ir_page('AVGO', 'https://investors.broadcom.com/');
SELECT upsert_ir_page('TMO', 'https://ir.thermofisher.com/');
SELECT upsert_ir_page('MCD', 'https://corporate.mcdonalds.com/corpmcd/investors.html');
SELECT upsert_ir_page('ABT', 'https://investors.abbott.com/');
SELECT upsert_ir_page('CSCO', 'https://investor.cisco.com/');
SELECT upsert_ir_page('ACN', 'https://investor.accenture.com/');
SELECT upsert_ir_page('LLY', 'https://investor.lilly.com/');
SELECT upsert_ir_page('ORCL', 'https://investor.oracle.com/');
SELECT upsert_ir_page('WMT', 'https://stock.walmart.com/');
SELECT upsert_ir_page('DHR', 'https://investors.danaher.com/');
SELECT upsert_ir_page('ADBE', 'https://www.adobe.com/investor-relations.html');
SELECT upsert_ir_page('CRM', 'https://investor.salesforce.com/');
SELECT upsert_ir_page('NKE', 'https://investors.nike.com/');
SELECT upsert_ir_page('TXN', 'https://investor.ti.com/');
SELECT upsert_ir_page('NEE', 'https://www.investor.nexteraenergy.com/');
SELECT upsert_ir_page('PM', 'https://www.pmi.com/investor-relations');
SELECT upsert_ir_page('RTX', 'https://investors.rtx.com/');
SELECT upsert_ir_page('UNP', 'https://www.up.com/investors/');
SELECT upsert_ir_page('QCOM', 'https://investor.qualcomm.com/');
SELECT upsert_ir_page('LOW', 'https://corporate.lowes.com/investors');
SELECT upsert_ir_page('HON', 'https://investor.honeywell.com/');
SELECT upsert_ir_page('UPS', 'https://investors.ups.com/');
SELECT upsert_ir_page('INTC', 'https://www.intc.com/investor-relations');
SELECT upsert_ir_page('AMD', 'https://ir.amd.com/');

-- Drop the helper function
DROP FUNCTION upsert_ir_page(VARCHAR, TEXT);

-- Record migration
INSERT INTO schema_migrations (migration_name, applied_at)
VALUES ('009_seed_ir_pages.sql', now());
