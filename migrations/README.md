# Database Migrations

This directory contains SQL migration files for the 10KAY database schema.

## Running Migrations

### Automatic (Recommended)

Use the migration runner script from the project root:

```bash
python3 run_migrations.py
```

This will:
- Connect to the database specified in `.env.local`
- Track which migrations have been applied
- Run pending migrations in order
- Display the current schema status

### Manual

You can also run migrations manually with `psql`:

```bash
# Run a specific migration
psql $DATABASE_URL -f migrations/001_initial_schema.sql

# Or run all migrations in order
for migration in migrations/*.sql; do
  psql $DATABASE_URL -f "$migration"
done
```

## Migration Files

### 001_initial_schema.sql
**Core Application Tables**

- `companies` - Tracked companies (47 initial)
- `filings` - SEC 10-K and 10-Q filings
- `content` - AI-generated analysis and blog posts
- `processing_logs` - Audit trail for pipeline operations

Creates:
- UUID extension
- Timestamp triggers for `updated_at` columns

### 002_subscribers.sql
**User Management and Email Tracking**

- `subscribers` - Newsletter subscribers and paid users
- `email_deliveries` - Email delivery and engagement tracking

Links to:
- Clerk (authentication)
- Stripe (payments)
- Resend (email delivery)

### 003_indexes_and_rls.sql
**Performance and Security**

- **37 indexes** for query optimization
- **Row Level Security (RLS)** policies for access control
- **3 views** for common queries:
  - `latest_content` - Most recent analysis per company
  - `pending_filings` - Filings awaiting processing
  - `subscriber_stats` - Subscription metrics

Helper functions:
- `is_content_accessible()` - Check if user can view content
- `get_user_subscription_tier()` - Get user's subscription level

## Schema Overview

```
companies (8 cols, 4 indexes)
    ↓ has many
filings (15 cols, 7 indexes)
    ↓ has many
content (24 cols, 7 indexes)
    ↓ delivered via
email_deliveries (8 cols, 5 indexes)
    ↓ to
subscribers (14 cols, 8 indexes)

processing_logs (7 cols, 4 indexes) - audit trail
schema_migrations (3 cols, 2 indexes) - migration tracking
```

## Rollback

To rollback the last migration:

```bash
# Check which migrations are applied
psql $DATABASE_URL -c "SELECT * FROM schema_migrations ORDER BY id DESC LIMIT 5;"

# Manually drop tables/indexes from last migration
# (No automatic rollback - be careful!)
```

**⚠️ Warning:** There is no automatic rollback. Always backup before running migrations in production.

## Adding New Migrations

1. Create a new file: `004_description.sql`
2. Use the same naming convention: `NNN_description.sql`
3. Include comments and descriptions
4. Test locally before committing
5. Run `python3 run_migrations.py` to apply

## Verification

After running migrations, verify the schema:

```bash
python3 verify_schema.py
```

This shows:
- All tables and column counts
- Index counts per table
- Views
- Custom functions

## Current Schema Stats

- **7 tables** (6 application + 1 tracking)
- **37 indexes** for performance
- **3 views** for common queries
- **3 custom functions** for business logic
- **Row Level Security** enabled on `content` and `subscribers`

## Next Steps

After migrations are applied:
1. ✅ Schema is ready
2. ⏭️  Seed initial companies from `companies.json`
3. ⏭️  Build Python pipeline to fetch/process filings
4. ⏭️  Integrate with Next.js API routes

---

**Last Updated:** 2025-01-07
