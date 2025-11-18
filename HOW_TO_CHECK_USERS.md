# How to Check if Users Were Created

Quick reference guide for verifying user creation in 10KAY.

## Current State (Phase 3.1)

✅ **Users ARE created in:** Clerk (authentication system)
❌ **Users are NOT yet in:** PostgreSQL database
⏳ **Database sync coming in:** Phase 3.5 (Webhook Integration)

---

## Method 1: Check Clerk Dashboard ✅ WORKS NOW

This is the easiest way to verify users after signup.

1. Go to your Clerk Dashboard: [https://dashboard.clerk.com](https://dashboard.clerk.com)
2. Click **Users** in the sidebar
3. You should see all signed-up users with:
   - Email address
   - Name (if provided)
   - Sign-up timestamp
   - Authentication methods

**This is the recommended method for Phase 3.1**

---

## Method 2: Run the User Checker Script

We've created a utility script that checks both Clerk and the database.

```bash
npm run check-users
```

This will show you:
- ✅ All users in Clerk
- ❌ All subscribers in PostgreSQL (currently none)
- 🔍 Comparison and sync status
- 💡 Next steps

---

## Method 3: Check Database Directly

### Using the SQL script:
```bash
psql $DATABASE_URL -f scripts/check-users.sql
```

### Using psql directly:
```bash
psql $DATABASE_URL
```

Then run:
```sql
-- Check if any subscribers exist
SELECT COUNT(*) FROM subscribers;

-- View all subscribers
SELECT email, clerk_user_id, subscription_tier, subscribed_at
FROM subscribers
ORDER BY subscribed_at DESC;
```

**Expected result:** 0 rows (until Phase 3.5 is complete)

---

## Understanding the Database Schema

The database has a `subscribers` table (from migration `002_subscribers.sql`) with these fields:

| Column | Type | Purpose |
|--------|------|---------|
| `id` | UUID | Primary key |
| `email` | VARCHAR(255) | User's email address |
| `clerk_user_id` | VARCHAR(255) | Link to Clerk user (NULL until Phase 3.5) |
| `subscription_tier` | VARCHAR(20) | 'free' or 'paid' |
| `email_frequency` | VARCHAR(20) | 'daily', 'weekly', or 'off' |
| `interested_companies` | UUID[] | Array of company IDs to follow |

---

## Testing User Creation

1. **Start the dev server:**
   ```bash
   npm run dev
   ```

2. **Sign up:**
   - Go to http://localhost:3000
   - Click "Sign Up"
   - Create an account with your email

3. **Verify in Clerk:**
   - Go to [Clerk Dashboard → Users](https://dashboard.clerk.com/last-active?path=users)
   - Your new user should appear immediately

4. **Check sync status:**
   ```bash
   npm run check-users
   ```

---

## Expected Behavior by Phase

### Phase 3.1 (Current) ✅
- ✅ Users created in Clerk
- ✅ Authentication works
- ✅ Dashboard accessible
- ❌ Users NOT in database

### Phase 3.5 (Webhook Integration)
- ✅ Users created in Clerk
- ✅ **Automatically synced to `subscribers` table**
- ✅ `clerk_user_id` populated
- ✅ Default preferences created

---

## Troubleshooting

### "No users in Clerk Dashboard"
- ✅ Make sure you completed signup
- ✅ Check that `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` is set in `.env.local`
- ✅ Make sure you're looking at the correct Clerk application

### "Error fetching Clerk users" when running script
- ✅ Make sure `CLERK_SECRET_KEY` is set in `.env.local`
- ✅ Verify the key starts with `sk_test_` or `sk_live_`

### "Error querying database"
- ✅ Make sure `DATABASE_URL` is set in `.env.local`
- ✅ Verify migration 002 was run: `psql $DATABASE_URL -c "\dt subscribers"`
- ✅ Check database connection: `psql $DATABASE_URL -c "SELECT 1"`

---

## Quick Commands Reference

```bash
# Check users in both Clerk and database
npm run check-users

# Check database only (SQL)
psql $DATABASE_URL -f scripts/check-users.sql

# Start dev server
npm run dev

# Check if subscribers table exists
psql $DATABASE_URL -c "\dt subscribers"

# Count users in database
psql $DATABASE_URL -c "SELECT COUNT(*) FROM subscribers;"
```

---

**Next Step:** Complete Phase 3.5 to enable automatic user sync via Clerk webhooks!
