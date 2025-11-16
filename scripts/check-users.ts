/**
 * Check Users Script
 *
 * Utility to check if users exist in:
 * 1. Clerk (via API)
 * 2. PostgreSQL subscribers table
 *
 * Usage:
 *   npx tsx scripts/check-users.ts
 */

import { clerkClient } from "@clerk/nextjs/server";
import { query } from '../lib/db';

interface Subscriber {
  id: string;
  email: string;
  clerk_user_id: string | null;
  subscription_tier: string;
  subscribed_at: Date;
}

async function checkClerkUsers() {
  console.log('\n📊 Checking Clerk Users...\n');

  try {
    const client = await clerkClient();
    const users = await client.users.getUserList({ limit: 100 });

    console.log(`✅ Found ${users.data.length} users in Clerk:\n`);

    users.data.forEach((user, index) => {
      console.log(`${index + 1}. ${user.firstName || 'No name'} ${user.lastName || ''}`);
      console.log(`   Email: ${user.emailAddresses[0]?.emailAddress || 'No email'}`);
      console.log(`   Clerk ID: ${user.id}`);
      console.log(`   Created: ${new Date(user.createdAt).toLocaleString()}`);
      console.log('');
    });

    return users.data;
  } catch (error) {
    console.error('❌ Error fetching Clerk users:', error);
    console.log('\n💡 Make sure you have set CLERK_SECRET_KEY in .env.local\n');
    return [];
  }
}

async function checkDatabaseUsers() {
  console.log('\n📊 Checking PostgreSQL subscribers table...\n');

  try {
    const subscribers = await query<Subscriber>(
      `SELECT id, email, clerk_user_id, subscription_tier, subscribed_at
       FROM subscribers
       ORDER BY subscribed_at DESC`
    );

    console.log(`✅ Found ${subscribers.length} subscribers in database:\n`);

    if (subscribers.length === 0) {
      console.log('   (No subscribers yet - this is normal before Phase 3.5 webhook integration)\n');
    } else {
      subscribers.forEach((sub, index) => {
        console.log(`${index + 1}. ${sub.email}`);
        console.log(`   Clerk ID: ${sub.clerk_user_id || 'NULL (not synced)'}`);
        console.log(`   Tier: ${sub.subscription_tier}`);
        console.log(`   Subscribed: ${new Date(sub.subscribed_at).toLocaleString()}`);
        console.log('');
      });
    }

    return subscribers;
  } catch (error) {
    console.error('❌ Error querying database:', error);
    console.log('\n💡 Make sure you have set DATABASE_URL in .env.local');
    console.log('💡 Make sure migration 002_subscribers.sql has been run\n');
    return [];
  }
}

async function compareUsers(clerkUsers: any[], dbSubscribers: Subscriber[]) {
  console.log('\n🔍 Comparing Clerk vs Database...\n');

  const clerkEmails = new Set(clerkUsers.map(u => u.emailAddresses[0]?.emailAddress));
  const dbEmails = new Set(dbSubscribers.map(s => s.email));

  const inClerkOnly = clerkUsers.filter(u => !dbEmails.has(u.emailAddresses[0]?.emailAddress));
  const inDbOnly = dbSubscribers.filter(s => !clerkEmails.has(s.email));

  if (inClerkOnly.length > 0) {
    console.log(`⚠️  ${inClerkOnly.length} user(s) in Clerk but NOT in database:`);
    inClerkOnly.forEach(u => console.log(`   - ${u.emailAddresses[0]?.emailAddress}`));
    console.log('');
    console.log('   This is EXPECTED before Phase 3.5 webhook integration.');
    console.log('   Users will automatically sync once webhooks are configured.\n');
  }

  if (inDbOnly.length > 0) {
    console.log(`⚠️  ${inDbOnly.length} subscriber(s) in database but NOT in Clerk:`);
    inDbOnly.forEach(s => console.log(`   - ${s.email}`));
    console.log('');
  }

  const synced = dbSubscribers.filter(s => s.clerk_user_id !== null);
  console.log(`✅ ${synced.length} user(s) properly synced (have clerk_user_id)\n`);
}

async function main() {
  console.log('═══════════════════════════════════════════════════════');
  console.log('  10KAY User Sync Status Checker');
  console.log('═══════════════════════════════════════════════════════');

  const clerkUsers = await checkClerkUsers();
  const dbSubscribers = await checkDatabaseUsers();

  if (clerkUsers.length > 0 || dbSubscribers.length > 0) {
    await compareUsers(clerkUsers, dbSubscribers);
  }

  console.log('═══════════════════════════════════════════════════════');
  console.log('\n📝 Next Steps:');
  console.log('   1. Sign up at http://localhost:3000');
  console.log('   2. Run this script again to verify user creation in Clerk');
  console.log('   3. For database sync, complete Phase 3.5 (Webhook Integration)');
  console.log('');

  process.exit(0);
}

main();
