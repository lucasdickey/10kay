# Clerk Authentication Setup - Phase 3.1

This document describes the Clerk authentication integration for 10KAY.

## ✅ Completed Setup

### 1. Installation
- ✅ Installed `@clerk/nextjs` package
- ✅ Created [middleware.ts](middleware.ts) with `clerkMiddleware()`
- ✅ Updated [app/layout.tsx](app/layout.tsx) with `<ClerkProvider>`
- ✅ Created [components/Navigation.tsx](components/Navigation.tsx) with auth UI
- ✅ Created [app/dashboard/page.tsx](app/dashboard/page.tsx) for authenticated users

### 2. File Structure

```
10kay/
├── middleware.ts                    # Clerk middleware for route protection
├── app/
│   ├── layout.tsx                   # Wrapped with ClerkProvider
│   ├── page.tsx                     # Homepage with Navigation component
│   └── dashboard/
│       └── page.tsx                 # Protected dashboard page
└── components/
    └── Navigation.tsx               # Sign in/up buttons + UserButton
```

### 3. Environment Variables

The following environment variables are required in `.env.local`:

```bash
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
CLERK_SECRET_KEY=sk_test_...
```

## 🚀 Next Steps to Complete Phase 3.1

### Step 1: Create a Clerk Account

1. Go to [https://dashboard.clerk.com/sign-up](https://dashboard.clerk.com/sign-up)
2. Sign up for a free Clerk account
3. Create a new application (select "Next.js" as the framework)

### Step 2: Get Your API Keys

1. In the Clerk Dashboard, navigate to **API Keys** (or visit [https://dashboard.clerk.com/last-active?path=api-keys](https://dashboard.clerk.com/last-active?path=api-keys))
2. Copy your **Publishable Key** (starts with `pk_test_`)
3. Copy your **Secret Key** (starts with `sk_test_`)

### Step 3: Configure Environment Variables

Add your Clerk keys to `.env.local`:

```bash
# .env.local
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_YOUR_KEY_HERE
CLERK_SECRET_KEY=sk_test_YOUR_SECRET_HERE
```

⚠️ **Important:** Never commit `.env.local` to git! It's already in `.gitignore`.

### Step 4: Configure Clerk Settings (Optional but Recommended)

In the Clerk Dashboard:

1. **OAuth Providers** (Configure → Social Connections):
   - Enable Google OAuth for easier sign-ups
   - Enable GitHub OAuth (optional)

2. **Email & SMS** (Configure → Email, Phone, Username):
   - Ensure email is enabled and required
   - Configure email verification settings

3. **Appearance** (Configure → Customization → Appearance):
   - Customize the sign-in/sign-up modal to match 10KAY branding
   - Upload logo if desired

### Step 5: Test the Authentication Flow

1. Start the development server:
   ```bash
   npm run dev
   ```

2. Visit [http://localhost:3000](http://localhost:3000)

3. Test the following:
   - Click **Sign Up** and create a test account
   - Verify email (check your inbox)
   - Sign in with your new account
   - Click on the user avatar to see the UserButton menu
   - Navigate to `/dashboard` to see the protected page
   - Sign out

### Step 6: Verify User Creation

After signing up, you can verify users in multiple ways:

#### Method 1: Check Clerk Dashboard (Current)
1. Go to [Clerk Dashboard → Users](https://dashboard.clerk.com/last-active?path=users)
2. You should see your newly created user with email and timestamp
3. Click on the user to see full details

**✅ This works immediately after signup** - users are stored in Clerk's system

#### Method 2: Check Database (After Phase 3.5)
Currently, users are **NOT automatically synced to PostgreSQL**. This will be implemented in Phase 3.5 (Webhook Integration).

To check if users exist in your database:

**Option A: Run the TypeScript checker script**
```bash
npx tsx scripts/check-users.ts
```

This will show you:
- All users in Clerk
- All subscribers in PostgreSQL
- Which users are synced vs not synced
- Helpful next steps

**Option B: Run SQL directly**
```bash
psql $DATABASE_URL -f scripts/check-users.sql
```

**Option C: Manual SQL query**
```sql
SELECT email, clerk_user_id, subscription_tier, subscribed_at
FROM subscribers
ORDER BY subscribed_at DESC;
```

**Expected Result Before Phase 3.5:**
- ✅ Users exist in Clerk Dashboard
- ❌ Users do NOT exist in `subscribers` table
- ⏳ This is normal! Webhook integration (Phase 3.5) will sync them automatically

## 🔒 Security Features

- ✅ **Middleware Protection**: All routes run through `clerkMiddleware()`
- ✅ **Route Protection**: `/dashboard` redirects unauthenticated users to home
- ✅ **Server-Side Auth**: Uses `auth()` and `currentUser()` from `@clerk/nextjs/server`
- ✅ **Environment Variables**: Keys stored securely in `.env.local`

## 📋 Authentication UI Components

### Navigation Component
Located in [components/Navigation.tsx](components/Navigation.tsx)

**Features:**
- Shows "Sign In" and "Sign Up" buttons when logged out
- Shows "Dashboard" link and UserButton when logged in
- Modal-based sign-in/sign-up (no page redirects)

### Dashboard Page
Located in [app/dashboard/page.tsx](app/dashboard/page.tsx)

**Features:**
- Protected route (requires authentication)
- Displays user information from Clerk
- Shows account details and subscription status
- Placeholder for upcoming features (Phase 3.2)

## 🔗 Next Phase: Phase 3.2 - Subscriber Management UI

Once Phase 3.1 is complete, the next steps will be:
- Database migration for `user_preferences` table
- Subscriber management UI for selecting companies
- Email preference settings (frequency, delivery time, etc.)
- Webhook integration to sync Clerk users to PostgreSQL

## 📚 Resources

- [Clerk Next.js Quickstart](https://clerk.com/docs/quickstarts/nextjs)
- [Clerk Dashboard](https://dashboard.clerk.com)
- [GitHub Issue #9: Phase 3.1 Tracker](https://github.com/lucasdickey/10kay/issues/9)

## ✅ Acceptance Criteria Checklist

Track progress against [Issue #9](https://github.com/lucasdickey/10kay/issues/9):

- [x] Install and configure Clerk SDK for Next.js 15 App Router
- [ ] Set up Clerk application and obtain API keys ← **YOU ARE HERE**
- [ ] Configure environment variables
- [x] Add Clerk Provider to root layout
- [x] Implement sign-up flow with email/password and social providers
- [x] Implement sign-in flow
- [x] Create user profile page with account details
- [x] Add sign-out functionality
- [x] Protect authenticated routes with Clerk middleware
- [ ] Sync Clerk user data to PostgreSQL (deferred to Phase 3.5)
- [ ] Test end-to-end authentication flow

---

**Status:** Ready for API key configuration and testing
**Last Updated:** 2025-11-15
