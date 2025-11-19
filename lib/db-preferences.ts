/**
 * Database helpers for user preferences
 */

import { query, queryOne } from './db';
import { UserPreferences, UpdateUserPreferences, CompanyInfo } from './types';

/**
 * Get user preferences by Clerk user ID
 */
export async function getUserPreferencesByClerkId(
  clerkUserId: string
): Promise<UserPreferences | null> {
  return await queryOne<UserPreferences>(
    `SELECT * FROM subscribers WHERE clerk_user_id = $1`,
    [clerkUserId]
  );
}

/**
 * Get user preferences by email
 */
export async function getUserPreferencesByEmail(
  email: string
): Promise<UserPreferences | null> {
  return await queryOne<UserPreferences>(
    `SELECT * FROM subscribers WHERE email = $1`,
    [email]
  );
}

/**
 * Create a new subscriber record
 */
export async function createSubscriber(
  email: string,
  clerkUserId: string
): Promise<UserPreferences> {
  const result = await queryOne<UserPreferences>(
    `INSERT INTO subscribers (email, clerk_user_id)
     VALUES ($1, $2)
     RETURNING *`,
    [email, clerkUserId]
  );

  if (!result) {
    throw new Error('Failed to create subscriber');
  }

  return result;
}

/**
 * Update user preferences
 */
export async function updateUserPreferences(
  clerkUserId: string,
  updates: UpdateUserPreferences
): Promise<UserPreferences> {
  const sets: string[] = [];
  const values: any[] = [];
  let paramIndex = 1;

  // Build dynamic SET clause
  if (updates.email_frequency !== undefined) {
    sets.push(`email_frequency = $${paramIndex++}`);
    values.push(updates.email_frequency);
  }

  if (updates.interested_companies !== undefined) {
    sets.push(`interested_companies = $${paramIndex++}`);
    values.push(updates.interested_companies);
  }

  if (updates.email_enabled !== undefined) {
    sets.push(`email_enabled = $${paramIndex++}`);
    values.push(updates.email_enabled);
  }

  if (updates.content_preference !== undefined) {
    sets.push(`content_preference = $${paramIndex++}`);
    values.push(updates.content_preference);
  }

  if (updates.delivery_time !== undefined) {
    sets.push(`delivery_time = $${paramIndex++}`);
    values.push(updates.delivery_time);
  }

  // Always update updated_at
  sets.push(`updated_at = NOW()`);

  // Add clerk_user_id to WHERE clause
  values.push(clerkUserId);

  const sql = `
    UPDATE subscribers
    SET ${sets.join(', ')}
    WHERE clerk_user_id = $${paramIndex}
    RETURNING *
  `;

  const result = await queryOne<UserPreferences>(sql, values);

  if (!result) {
    throw new Error('Failed to update user preferences');
  }

  return result;
}

/**
 * Get all enabled companies for selection UI
 */
export async function getEnabledCompanies(): Promise<CompanyInfo[]> {
  return await query<CompanyInfo>(
    `SELECT id, ticker, name, sector, enabled, metadata
     FROM companies
     WHERE enabled = true
     ORDER BY name ASC`
  );
}

/**
 * Get subscribers for a specific company (for email sending)
 */
export async function getCompanySubscribers(
  companyId: string
): Promise<Array<{ email: string; content_preference: string }>> {
  return await query<{ email: string; content_preference: string }>(
    `SELECT email, content_preference
     FROM subscribers
     WHERE email_enabled = true
       AND $1 = ANY(interested_companies)
       AND email_frequency != 'disabled'`,
    [companyId]
  );
}

/**
 * Get all subscribers for daily digest
 */
export async function getDailyDigestRecipients(): Promise<UserPreferences[]> {
  return await query<UserPreferences>(
    `SELECT *
     FROM subscribers
     WHERE email_enabled = true
       AND email_frequency = 'daily'
       AND array_length(interested_companies, 1) > 0
     ORDER BY delivery_time ASC`
  );
}

/**
 * Get subscribers for per-filing emails
 */
export async function getPerFilingRecipients(
  companyId: string
): Promise<UserPreferences[]> {
  return await query<UserPreferences>(
    `SELECT *
     FROM subscribers
     WHERE email_enabled = true
       AND email_frequency = 'per_filing'
       AND $1 = ANY(interested_companies)`,
    [companyId]
  );
}

/**
 * Update last email sent timestamp
 */
export async function updateLastEmailSent(subscriberId: string): Promise<void> {
  await query(
    `UPDATE subscribers
     SET last_email_sent_at = NOW()
     WHERE id = $1`,
    [subscriberId]
  );
}
