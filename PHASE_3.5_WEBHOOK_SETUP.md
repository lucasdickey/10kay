# Phase 3.5: Clerk Webhook Integration

Automatically sync Clerk users to the database when they sign up, update their profile, or delete their account.

## Overview

This phase implements Clerk webhooks to handle user lifecycle events:

- **`user.created`**: Create a subscriber record when a user signs up
- **`user.updated`**: Update subscriber email if the user changes it
- **`user.deleted`**: Soft-delete the subscriber (set `unsubscribed_at`)

## Prerequisites

- Phase 3.1 (Clerk Authentication) must be complete
- Phase 3.2 (Subscriber Management UI) must be complete
- Migration 007 must be run (`npx tsx scripts/run-migration-007.ts`)

## Setup Instructions

### 1. Deploy Your Application

The webhook endpoint needs to be publicly accessible. Deploy to Vercel or your production environment first.

**Webhook Endpoint URL:**
```
https://your-domain.com/api/webhooks/clerk
```

For local testing, use a tool like [ngrok](https://ngrok.com/) or [Clerk's local testing feature](https://clerk.com/docs/testing/webhooks).

### 2. Create Webhook in Clerk Dashboard

1. Go to [Clerk Dashboard](https://dashboard.clerk.com/)
2. Select your application
3. Navigate to **Webhooks** in the sidebar
4. Click **+ Add Endpoint**

### 3. Configure the Webhook

**Endpoint URL:**
```
https://your-domain.com/api/webhooks/clerk
```

**Subscribe to Events:**
- ✅ `user.created`
- ✅ `user.updated`
- ✅ `user.deleted`

### 4. Get the Signing Secret

After creating the webhook:

1. Click on your webhook endpoint
2. Copy the **Signing Secret** (starts with `whsec_`)
3. Add it to your environment variables

### 5. Add Environment Variable

Add the webhook secret to your environment:

**`.env.local` (Development):**
```bash
CLERK_WEBHOOK_SECRET=whsec_your_signing_secret_here
```

**Vercel (Production):**
```bash
vercel env add CLERK_WEBHOOK_SECRET
# Paste your signing secret when prompted
# Select: Production, Preview, Development (all environments)
```

Or via Vercel Dashboard:
1. Go to your project settings
2. Navigate to **Environment Variables**
3. Add `CLERK_WEBHOOK_SECRET` with your signing secret

### 6. Restart Your Application

**Development:**
```bash
# Stop your dev server (Ctrl+C) and restart
npm run dev
```

**Production:**
```bash
# Redeploy to pick up new environment variable
git push  # If auto-deploy is enabled
# OR
vercel --prod
```

## Testing the Webhook

### Option 1: Test in Clerk Dashboard

1. Go to your webhook in Clerk Dashboard
2. Click **Testing** tab
3. Click **Send Example** for `user.created` event
4. Check the **Recent Deliveries** to see if it succeeded

### Option 2: Sign Up a New User

1. Sign out of your application (if signed in)
2. Sign up with a new email address
3. Check your database to verify the subscriber was created:

```bash
npx tsx scripts/check-users.ts
```

You should see the new user in both Clerk and the database with matching `clerk_user_id`.

### Option 3: Local Testing with ngrok

```bash
# Install ngrok (if not installed)
brew install ngrok  # macOS
# or download from https://ngrok.com/download

# Start your local dev server
npm run dev

# In another terminal, create a tunnel
ngrok http 3000

# Copy the HTTPS URL (e.g., https://abc123.ngrok.io)
# Use this URL in Clerk webhook configuration:
# https://abc123.ngrok.io/api/webhooks/clerk
```

## Webhook Behavior

### user.created
- **Trigger**: User signs up or is created
- **Action**: Creates a new row in `subscribers` table
- **Fields Set**:
  - `email`: Primary email from Clerk
  - `clerk_user_id`: Clerk user ID
  - `subscription_tier`: `'free'` (default)
  - `email_frequency`: `'daily'` (default)
  - `interested_companies`: `[]` (empty array)
  - All other preference columns use defaults from migration 007

### user.updated
- **Trigger**: User updates their profile (especially email)
- **Action**: Updates `email` field in `subscribers` table
- **Note**: Only updates email if the primary email changes

### user.deleted
- **Trigger**: User deletes their account in Clerk
- **Action**: Soft delete - sets `unsubscribed_at` to current timestamp
- **Note**: Does NOT actually delete the row (for data retention/analytics)

## Troubleshooting

### Webhook Failing (500 Error)

**Check environment variable:**
```bash
# In your terminal
echo $CLERK_WEBHOOK_SECRET

# Should output: whsec_...
# If empty, the variable isn't set
```

**Check Vercel logs:**
```bash
vercel logs
# Look for errors related to webhooks
```

### Webhook Returns 400 (Bad Request)

**Missing Svix headers** - Make sure the request is coming from Clerk, not a manual curl/Postman test.

**Invalid signature** - Your `CLERK_WEBHOOK_SECRET` doesn't match the webhook endpoint's signing secret in Clerk Dashboard.

### User Created but Not in Database

1. Check webhook delivery status in Clerk Dashboard
2. Look at the webhook response - did it return 200 OK?
3. Check application logs for errors
4. Verify migration 007 was run successfully

### Testing Locally Not Working

If using ngrok or similar:
1. Make sure the HTTPS URL is used (not HTTP)
2. Verify the tunnel is still active
3. Check that the endpoint URL in Clerk includes `/api/webhooks/clerk`

## Verification Checklist

- [ ] Webhook endpoint created in Clerk Dashboard
- [ ] Subscribed to `user.created`, `user.updated`, `user.deleted` events
- [ ] Signing secret copied to environment variables
- [ ] Application restarted/redeployed
- [ ] Test user creation successful
- [ ] `check-users.ts` shows user in both Clerk and database
- [ ] `clerk_user_id` matches between Clerk and database

## Cleanup

### Remove Development-Only Code

After Phase 3.5 is complete and tested:

1. **Delete dev sync endpoint:**
   ```bash
   rm app/api/dev/sync-user/route.ts
   ```

2. The dev sync banner in settings page is already environment-gated and will not show in production.

## Security Notes

- **Never commit** `CLERK_WEBHOOK_SECRET` to git
- Webhook uses Svix signature verification to prevent spoofing
- Only Clerk with the correct signing secret can trigger the webhook
- Soft delete preserves data while respecting user deletion requests

## Next Steps

After Phase 3.5 is complete:
- **Phase 3.3**: Resend Email Integration (sending actual emails)
- **Phase 3.4**: Email Templates (HTML email designs)
- **Phase 4**: Stripe Integration (paid subscriptions)

## Related Files

- **Webhook Handler**: `app/api/webhooks/clerk/route.ts`
- **Database Helpers**: `lib/db-preferences.ts`
- **User Sync Script**: `scripts/check-users.ts`
- **Settings Page**: `app/settings/page.tsx`
