/**
 * Admin endpoint to fetch and store company logos
 * POST: Fetch missing logos from Clearbit API and store locally
 */

import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import https from 'https';
import { query } from '@/lib/db';

export const dynamic = 'force-dynamic';

interface Company {
  ticker: string;
  metadata?: Record<string, any> | null;
}

async function downloadLogo(domain: string, ticker: string): Promise<boolean> {
  return new Promise((resolve) => {
    const logosDir = path.join(process.cwd(), 'public', 'company-logos');
    const logoPath = path.join(logosDir, `${ticker.toLowerCase()}.png`);

    // Skip if logo already exists
    if (fs.existsSync(logoPath)) {
      resolve(true);
      return;
    }

    // Ensure directory exists
    if (!fs.existsSync(logosDir)) {
      fs.mkdirSync(logosDir, { recursive: true });
    }

    https
      .get(`https://logo.clearbit.com/${domain}`, (response) => {
        if (response.statusCode === 200) {
          const fileStream = fs.createWriteStream(logoPath);
          response.pipe(fileStream);

          fileStream.on('finish', () => {
            fileStream.close();
            resolve(true);
          });

          fileStream.on('error', () => {
            fs.unlink(logoPath, () => {});
            resolve(false);
          });
        } else {
          resolve(false);
        }
      })
      .on('error', () => {
        resolve(false);
      });
  });
}

export async function POST() {
  try {
    console.log('Fetching logos for companies...');

    // Get all companies with domains
    const companies = await query<Company>(
      `SELECT ticker, metadata
       FROM companies
       WHERE enabled = true
       ORDER BY ticker ASC`
    );

    console.log(`Found ${companies.length} companies\n`);

    let downloaded = 0;
    let skipped = 0;
    let failed = 0;

    // Fetch logos with rate limiting (Clearbit allows ~10 requests/sec)
    for (const company of companies) {
      const { ticker } = company;
      const domain = company.metadata?.domain;

      if (!domain) {
        console.log(`⊘ ${ticker} has no domain in metadata, skipping`);
        failed++;
        continue;
      }

      const logosDir = path.join(process.cwd(), 'public', 'company-logos');
      const logoPath = path.join(logosDir, `${ticker.toLowerCase()}.png`);

      // Check if already exists
      if (fs.existsSync(logoPath)) {
        const stats = fs.statSync(logoPath);
        if (stats.size > 0) {
          console.log(`✓ ${ticker} logo already exists`);
          skipped++;
          continue;
        }
      }

      const success = await downloadLogo(domain, ticker);

      if (success) {
        if (fs.existsSync(logoPath)) {
          const stats = fs.statSync(logoPath);
          if (stats.size === 0) {
            skipped++;
          } else {
            downloaded++;
            console.log(`✓ Downloaded ${ticker} logo from ${domain}`);
          }
        } else {
          skipped++;
        }
      } else {
        failed++;
        console.log(`✗ Failed to download ${ticker} logo`);
      }

      // Rate limiting: wait 150ms between requests (safe for Clearbit)
      await new Promise((resolve) => setTimeout(resolve, 150));
    }

    const result = {
      success: true,
      message: 'Logo fetch complete',
      stats: {
        total: companies.length,
        downloaded,
        skipped,
        failed,
      },
    };

    console.log(
      `\n✅ Complete! Downloaded: ${downloaded}, Already existing: ${skipped}, Failed: ${failed}`
    );

    return NextResponse.json(result);
  } catch (error) {
    console.error('Error:', error);
    return NextResponse.json(
      {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 500 }
    );
  }
}
