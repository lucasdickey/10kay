/**
 * Update existing companies in database with domain information from companies.json
 *
 * This script updates the metadata field of existing companies to include the domain.
 * Run with: npx tsx scripts/update-company-domains.ts
 */

import { readFileSync } from 'fs';
import { join } from 'path';
import pg from 'pg';

const { Pool } = pg;

interface Company {
  ticker: string;
  name: string;
  domain?: string;
  enabled: boolean;
}

interface CompaniesData {
  companies: Company[];
}

async function main() {
  console.log('='.repeat(60));
  console.log('10KAY Company Domain Updater');
  console.log('='.repeat(60));
  console.log();

  // Load companies.json
  const companiesPath = join(process.cwd(), 'companies.json');
  const companiesData: CompaniesData = JSON.parse(readFileSync(companiesPath, 'utf-8'));
  const companies = companiesData.companies;

  console.log(`📋 Updating ${companies.length} companies with domain information`);
  console.log();

  // Connect to database
  const pool = new Pool({
    connectionString: process.env.DATABASE_URL,
  });

  try {
    console.log('🔌 Connecting to database...');
    const client = await pool.connect();
    console.log('✓ Connected');
    console.log();

    let updateCount = 0;

    for (const company of companies) {
      const { ticker, domain } = company;

      if (!domain) {
        console.log(`   ⚠️  No domain for ${ticker}, skipping`);
        continue;
      }

      // Update the metadata field with the complete company object
      const result = await client.query(
        `UPDATE companies
         SET metadata = $1
         WHERE ticker = $2`,
        [JSON.stringify(company), ticker]
      );

      if (result.rowCount && result.rowCount > 0) {
        updateCount++;
        console.log(`   ✓ Updated ${ticker} with domain ${domain}`);
      }
    }

    client.release();

    console.log();
    console.log(`✅ Successfully updated ${updateCount} companies!`);
    console.log();
    console.log('='.repeat(60));
    console.log(`✅ Update complete! Updated ${updateCount} companies.`);
    console.log('='.repeat(60));

  } catch (error) {
    console.error('✗ Error:', error);
    process.exit(1);
  } finally {
    await pool.end();
  }
}

main();
