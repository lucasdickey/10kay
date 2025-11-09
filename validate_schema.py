#!/usr/bin/env python3
"""
Schema Validation Script

Validates that database schema matches code expectations.
Run this before deploying or after schema changes.

Usage:
    python3 validate_schema.py
"""

import psycopg2
import os
from dotenv import load_dotenv
from typing import Dict, List, Set

# Expected schema - what the code assumes exists
EXPECTED_SCHEMA = {
    'companies': {
        'columns': {'id', 'ticker', 'name', 'exchange', 'sector', 'enabled', 'added_at', 'metadata'},
        'foreign_keys': {}
    },
    'filings': {
        'columns': {'id', 'company_id', 'filing_type', 'accession_number', 'filing_date',
                   'period_end_date', 'fiscal_year', 'fiscal_quarter', 'edgar_url',
                   'raw_document_url', 'status', 'processed_at', 'error_message',
                   'created_at', 'updated_at'},
        'foreign_keys': {'company_id': ('companies', 'id')}
    },
    'content': {
        'columns': {'id', 'filing_id', 'company_id', 'version', 'is_current',
                   'executive_summary', 'key_takeaways', 'deep_dive_opportunities',
                   'deep_dive_risks', 'deep_dive_strategy', 'implications',
                   'tweet_draft', 'email_subject', 'email_preview',
                   'audio_script', 'audio_url', 'audio_duration_seconds',
                   'published_at', 'slug', 'created_at', 'updated_at', 'created_by',
                   'meta_description', 'meta_keywords', 'blog_html', 'email_html'},
        'foreign_keys': {
            'filing_id': ('filings', 'id'),
            'company_id': ('companies', 'id')
        }
    },
    'subscribers': {
        'columns': {'id', 'email', 'clerk_user_id', 'subscription_tier',
                   'stripe_customer_id', 'stripe_subscription_id', 'subscription_status',
                   'email_frequency', 'interested_companies', 'subscribed_at',
                   'unsubscribed_at', 'last_email_sent_at', 'created_at', 'updated_at'},
        'foreign_keys': {}
    },
    'email_deliveries': {
        'columns': {'id', 'subscriber_id', 'content_id', 'sent_at', 'resend_email_id',
                   'opened_at', 'clicked_at', 'status'},
        'foreign_keys': {
            'subscriber_id': ('subscribers', 'id'),
            'content_id': ('content', 'id')
        }
    },
    'processing_logs': {
        'columns': {'id', 'filing_id', 'step', 'status', 'message', 'metadata',
                   'created_at', 'level'},
        'foreign_keys': {
            'filing_id': ('filings', 'id')
        }
    }
}

# Required JSONB structures
EXPECTED_JSONB = {
    'content.key_takeaways': {
        'required_keys': {'headline', 'model', 'tokens'},
        'optional_keys': {'points', 'sentiment', 'metrics', 'duration'}
    }
}


def get_actual_schema(conn) -> Dict:
    """Query database for actual schema"""
    cursor = conn.cursor()

    # Get all tables
    cursor.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_type = 'BASE TABLE'
        AND table_name != 'schema_migrations'
        ORDER BY table_name
    """)
    tables = [row[0] for row in cursor.fetchall()]

    schema = {}

    for table in tables:
        # Get columns
        cursor.execute(f"""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = '{table}'
        """)
        columns = {row[0] for row in cursor.fetchall()}

        # Get foreign keys
        cursor.execute(f"""
            SELECT
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
            AND tc.table_name = '{table}'
        """)

        foreign_keys = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}

        schema[table] = {
            'columns': columns,
            'foreign_keys': foreign_keys
        }

    cursor.close()
    return schema


def validate_schema(actual: Dict, expected: Dict) -> List[str]:
    """Compare actual vs expected schema, return list of issues"""
    issues = []

    # Check for missing tables
    expected_tables = set(expected.keys())
    actual_tables = set(actual.keys())

    missing_tables = expected_tables - actual_tables
    extra_tables = actual_tables - expected_tables

    if missing_tables:
        issues.append(f"❌ Missing tables: {', '.join(missing_tables)}")

    if extra_tables:
        issues.append(f"ℹ️  Extra tables (not used by code): {', '.join(extra_tables)}")

    # Check each table
    for table in expected_tables & actual_tables:
        exp_cols = expected[table]['columns']
        act_cols = actual[table]['columns']

        missing_cols = exp_cols - act_cols
        extra_cols = act_cols - exp_cols

        if missing_cols:
            issues.append(f"❌ Table '{table}' missing columns: {', '.join(missing_cols)}")

        if extra_cols:
            issues.append(f"ℹ️  Table '{table}' has extra columns: {', '.join(extra_cols)}")

        # Check foreign keys
        exp_fks = expected[table]['foreign_keys']
        act_fks = actual[table]['foreign_keys']

        for col, (ref_table, ref_col) in exp_fks.items():
            if col not in act_fks:
                issues.append(f"❌ Table '{table}' missing FK: {col} → {ref_table}.{ref_col}")
            elif act_fks[col] != (ref_table, ref_col):
                issues.append(f"❌ Table '{table}' FK mismatch on '{col}': "
                            f"expected {ref_table}.{ref_col}, got {act_fks[col][0]}.{act_fks[col][1]}")

    return issues


def validate_jsonb_sample(conn) -> List[str]:
    """Validate JSONB structures have expected keys"""
    issues = []
    cursor = conn.cursor()

    # Check key_takeaways structure
    cursor.execute("""
        SELECT key_takeaways
        FROM content
        WHERE key_takeaways IS NOT NULL
        LIMIT 1
    """)

    row = cursor.fetchone()
    if row:
        key_takeaways = row[0]
        required = EXPECTED_JSONB['content.key_takeaways']['required_keys']

        missing = required - set(key_takeaways.keys())
        if missing:
            issues.append(f"⚠️  content.key_takeaways missing required keys: {', '.join(missing)}")
    else:
        issues.append("ℹ️  No content records to validate key_takeaways structure")

    cursor.close()
    return issues


def main():
    load_dotenv('.env.local')

    print("="* 80)
    print("10KAY SCHEMA VALIDATION")
    print("="* 80)
    print()

    # Connect to database
    try:
        conn = psycopg2.connect(os.getenv('DATABASE_URL'))
        print("✓ Connected to database")
    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")
        return 1

    # Get actual schema
    print("✓ Reading database schema...")
    actual_schema = get_actual_schema(conn)

    # Validate schema
    print("✓ Validating schema...")
    issues = validate_schema(actual_schema, EXPECTED_SCHEMA)

    # Validate JSONB structures
    print("✓ Validating JSONB structures...")
    jsonb_issues = validate_jsonb_sample(conn)
    issues.extend(jsonb_issues)

    conn.close()

    # Report results
    print()
    print("="* 80)
    print("VALIDATION RESULTS")
    print("="* 80)
    print()

    if not issues:
        print("✅ Schema validation PASSED - all expectations met!")
        return 0
    else:
        print(f"Found {len(issues)} issues:\n")
        for issue in issues:
            print(f"  {issue}")

        # Count errors vs info
        errors = sum(1 for i in issues if i.startswith('❌'))
        warnings = sum(1 for i in issues if i.startswith('⚠️'))
        info = sum(1 for i in issues if i.startswith('ℹ️'))

        print()
        print(f"Summary: {errors} errors, {warnings} warnings, {info} info")

        if errors > 0:
            print("\n❌ Schema validation FAILED - fix errors before deploying")
            return 1
        else:
            print("\n⚠️  Schema validation PASSED with warnings")
            return 0


if __name__ == '__main__':
    exit(main())
