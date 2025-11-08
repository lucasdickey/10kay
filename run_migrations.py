#!/usr/bin/env python3
"""
Database Migration Runner for 10KAY

Runs SQL migration files in order and tracks applied migrations.
Usage: python run_migrations.py
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Load environment variables
load_dotenv('.env.local')

DATABASE_URL = os.getenv('DATABASE_URL')
MIGRATIONS_DIR = Path(__file__).parent / 'migrations'

def create_migrations_table(conn):
    """Create migrations tracking table if it doesn't exist"""
    with conn.cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                id SERIAL PRIMARY KEY,
                migration_name VARCHAR(255) UNIQUE NOT NULL,
                applied_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)
    conn.commit()
    print("✓ Migrations tracking table ready")

def get_applied_migrations(conn):
    """Get list of already applied migrations"""
    with conn.cursor() as cursor:
        cursor.execute("SELECT migration_name FROM schema_migrations ORDER BY id")
        return set(row[0] for row in cursor.fetchall())

def get_pending_migrations(applied_migrations):
    """Get list of migration files that haven't been applied yet"""
    all_migrations = sorted([
        f.name for f in MIGRATIONS_DIR.glob('*.sql')
        if f.is_file()
    ])

    pending = [m for m in all_migrations if m not in applied_migrations]
    return pending

def run_migration(conn, migration_file):
    """Run a single migration file"""
    migration_path = MIGRATIONS_DIR / migration_file

    print(f"\n📄 Running migration: {migration_file}")

    try:
        with open(migration_path, 'r') as f:
            sql = f.read()

        # Execute the migration
        with conn.cursor() as cursor:
            cursor.execute(sql)

        # Record the migration
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO schema_migrations (migration_name) VALUES (%s)",
                (migration_file,)
            )

        conn.commit()
        print(f"✓ Successfully applied: {migration_file}")
        return True

    except Exception as e:
        conn.rollback()
        print(f"✗ Failed to apply {migration_file}")
        print(f"  Error: {e}")
        return False

def main():
    """Main migration runner"""
    print("="* 60)
    print("10KAY Database Migration Runner")
    print("="* 60)
    print()

    if not DATABASE_URL:
        print("✗ DATABASE_URL not found in environment variables")
        print("  Make sure .env.local is configured correctly")
        sys.exit(1)

    # Redact password in display
    display_url = DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'N/A'
    print(f"📍 Database: {display_url}")
    print()

    try:
        # Connect to database
        print("🔌 Connecting to database...")
        conn = psycopg2.connect(DATABASE_URL)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        print("✓ Connected successfully")
        print()

        # Create migrations tracking table
        create_migrations_table(conn)

        # Get migration status
        applied = get_applied_migrations(conn)
        pending = get_pending_migrations(applied)

        print(f"📊 Migration Status:")
        print(f"  Applied: {len(applied)}")
        print(f"  Pending: {len(pending)}")
        print()

        if not pending:
            print("✅ All migrations are up to date!")
            print()
            print("Applied migrations:")
            for migration in sorted(applied):
                print(f"  ✓ {migration}")
            return

        # Run pending migrations
        print(f"🚀 Running {len(pending)} pending migration(s)...")

        success_count = 0
        for migration in pending:
            if run_migration(conn, migration):
                success_count += 1
            else:
                print()
                print("⚠️  Migration failed. Stopping here.")
                print("   Fix the error and run again.")
                sys.exit(1)

        print()
        print("="* 60)
        print(f"✅ Successfully applied {success_count} migration(s)!")
        print("="* 60)
        print()

        # Show current schema status
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """)
            tables = [row[0] for row in cursor.fetchall()]

        print(f"📁 Database tables ({len(tables)}):")
        for table in tables:
            print(f"  • {table}")
        print()

    except psycopg2.Error as e:
        print(f"✗ Database error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        sys.exit(1)
    finally:
        if 'conn' in locals():
            conn.close()
            print("🔌 Database connection closed")

if __name__ == '__main__':
    main()
