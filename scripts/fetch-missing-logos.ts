/**
 * Fetch and store company logos for companies missing them
 * Uses Clearbit API to fetch logos by domain
 */

import fs from 'fs';
import path from 'path';
import https from 'https';
import { Pool } from 'pg';

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
});

const LOGOS_DIR = path.join(process.cwd(), 'public', 'company-logos');
const CLEARBIT_API = 'https://logo.clearbit.com/';

// Ensure logos directory exists
if (!fs.existsSync(LOGOS_DIR)) {
  fs.mkdirSync(LOGOS_DIR, { recursive: true });
}

async function downloadLogo(domain: string, ticker: string): Promise<boolean> {
  return new Promise((resolve) => {
    const logoPath = path.join(LOGOS_DIR, `${ticker.toLowerCase()}.png`);

    // Skip if logo already exists
    if (fs.existsSync(logoPath)) {
      console.log(`✓ ${ticker} logo already exists`);
      resolve(true);
      return;
    }

    https
      .get(`${CLEARBIT_API}${domain}`, (response) => {
        if (response.statusCode === 200) {
          const fileStream = fs.createWriteStream(logoPath);
          response.pipe(fileStream);

          fileStream.on('finish', () => {
            fileStream.close();
            console.log(`✓ Downloaded ${ticker} logo from ${domain}`);
            resolve(true);
          });

          fileStream.on('error', () => {
            fs.unlink(logoPath, () => {});
            console.log(`✗ Failed to save ${ticker} logo`);
            resolve(false);
          });
        } else {
          console.log(`✗ ${ticker} logo not found (HTTP ${response.statusCode})`);
          resolve(false);
        }
      })
      .on('error', () => {
        console.log(`✗ Error fetching ${ticker} logo`);
        resolve(false);
      });
  });
}

async function main() {
  try {
    console.log('Fetching list of all companies from database...\n');

    const result = await pool.query(
      `SELECT ticker, metadata->>'domain' as domain
       FROM companies
       WHERE enabled = true
       ORDER BY ticker ASC`
    );

    const companies = result.rows;
    console.log(`Found ${companies.length} companies\n`);

    let downloaded = 0;
    let skipped = 0;
    let failed = 0;

    // Fetch logos with rate limiting (Clearbit allows ~10 requests/sec)
    for (const company of companies) {
      const { ticker, domain } = company;

      if (!domain) {
        console.log(`✗ ${ticker} has no domain in metadata, skipping`);
        failed++;
        continue;
      }

      const success = await downloadLogo(domain, ticker);

      if (success) {
        if (fs.existsSync(path.join(LOGOS_DIR, `${ticker.toLowerCase()}.png`))) {
          const stats = fs.statSync(
            path.join(LOGOS_DIR, `${ticker.toLowerCase()}.png`)
          );
          if (stats.size === 0) {
            skipped++;
          } else {
            downloaded++;
          }
        } else {
          skipped++;
        }
      } else {
        failed++;
      }

      // Rate limiting: wait 150ms between requests (safe for Clearbit)
      await new Promise((resolve) => setTimeout(resolve, 150));
    }

    console.log(
      `\n✅ Complete! Downloaded: ${downloaded}, Already existing: ${skipped}, Failed: ${failed}`
    );

    process.exit(0);
  } catch (error) {
    console.error('Error:', error);
    process.exit(1);
  } finally {
    await pool.end();
  }
}

main();
