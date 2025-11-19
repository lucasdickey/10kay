/**
 * Check subscriber record for debugging
 * Usage: npx tsx scripts/check-subscriber.ts
 */

import { query } from '../lib/db';

async function checkSubscriber() {
  console.log('═══════════════════════════════════════════════════════');
  console.log('  Checking Subscriber Record');
  console.log('═══════════════════════════════════════════════════════\n');

  try {
    const email = 'jvanlente.e3@gmail.com';

    console.log(`Checking for subscriber with email: ${email}\n`);

    const result = await query(
      `SELECT
        id,
        email,
        clerk_user_id,
        subscription_tier,
        email_frequency,
        created_at,
        updated_at
      FROM subscribers
      WHERE email = $1`,
      [email]
    );

    if (result.length === 0) {
      console.log('❌ No subscriber found with that email');
    } else {
      console.log('✅ Subscriber found:\n');
      const sub = result[0];
      console.log(`ID: ${sub.id}`);
      console.log(`Email: ${sub.email}`);
      console.log(`Clerk User ID: ${sub.clerk_user_id || '(NULL)'}`);
      console.log(`Subscription Tier: ${sub.subscription_tier}`);
      console.log(`Email Frequency: ${sub.email_frequency}`);
      console.log(`Created: ${sub.created_at}`);
      console.log(`Updated: ${sub.updated_at}`);
    }

    console.log('\n═══════════════════════════════════════════════════════');
  } catch (error) {
    console.error('❌ Error checking subscriber:', error);
    process.exit(1);
  }

  process.exit(0);
}

checkSubscriber();
