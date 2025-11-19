/**
 * Diagnose database connection
 * Usage: npx tsx scripts/diagnose-db.ts
 */

console.log('═══════════════════════════════════════════════════════');
console.log('  Database Connection Diagnostic');
console.log('═══════════════════════════════════════════════════════\n');

const connectionString = process.env.DATABASE_URL;

if (!connectionString) {
  console.error('❌ DATABASE_URL not found in environment');
  process.exit(1);
}

// Mask password for security
const maskedUrl = connectionString.replace(/:([^:@]+)@/, ':****@');
console.log(`Connection String: ${maskedUrl}\n`);

const isLocal =
  connectionString.includes('localhost') ||
  connectionString.includes('127.0.0.1');

console.log(`Is Local: ${isLocal}`);
console.log(`SSL Enabled: ${!isLocal}`);

if (connectionString.includes('rds.amazonaws.com')) {
  console.log('Database Type: AWS RDS');
} else if (connectionString.includes('supabase')) {
  console.log('Database Type: Supabase');
} else if (isLocal) {
  console.log('Database Type: Local PostgreSQL');
} else {
  console.log('Database Type: Unknown');
}

// Check for SSL parameters in URL
if (connectionString.includes('sslmode=')) {
  const sslMode = connectionString.match(/sslmode=([^&]+)/)?.[1];
  console.log(`SSL Mode in URL: ${sslMode}`);
} else {
  console.log('SSL Mode in URL: Not specified');
}

console.log('\n═══════════════════════════════════════════════════════');
