/**
 * Run migration 007 and fix existing subscribers
 * Usage: npx tsx scripts/run-migration-007.ts
 */

import { readFileSync } from 'fs';
import { query } from '../lib/db';

async function runMigration() {
  console.log('═══════════════════════════════════════════════════════');
  console.log('  Running Migration 007');
  console.log('═══════════════════════════════════════════════════════\n');

  try {
    // Read and run migration 007
    console.log('📄 Reading migration file...');
    const migrationSQL = readFileSync('migrations/007_enhance_subscriber_preferences.sql', 'utf-8');

    console.log('🔄 Running migration...');
    await query(migrationSQL);
    console.log('✅ Migration 007 completed successfully!\n');

    // Fix existing subscribers
    console.log('🔄 Fixing existing subscriber records...');
    const fixSQL = readFileSync('scripts/fix-existing-subscribers.sql', 'utf-8');

    await query(fixSQL);
    console.log('✅ Existing subscribers fixed!\n');

    // Verify the changes
    console.log('🔍 Verifying changes...');
    const subscribers = await query(
      `SELECT email, interested_companies, email_enabled, content_preference, delivery_time
       FROM subscribers`
    );

    console.log(`\n📊 Found ${subscribers.length} subscriber(s):\n`);
    subscribers.forEach((sub: any, index: number) => {
      console.log(`${index + 1}. ${sub.email}`);
      console.log(`   interested_companies: ${sub.interested_companies || '[]'} (${Array.isArray(sub.interested_companies) ? 'Array' : 'NULL'})`);
      console.log(`   email_enabled: ${sub.email_enabled}`);
      console.log(`   content_preference: ${sub.content_preference}`);
      console.log(`   delivery_time: ${sub.delivery_time}`);
      console.log('');
    });

    console.log('═══════════════════════════════════════════════════════');
    console.log('✅ All done! Company selections should now work.');
    console.log('═══════════════════════════════════════════════════════\n');

  } catch (error) {
    console.error('❌ Error running migration:', error);
    process.exit(1);
  }

  process.exit(0);
}

runMigration();
