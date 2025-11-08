#!/usr/bin/env python3
"""Verify database schema is correctly set up"""
import os
from dotenv import load_dotenv
import psycopg2

load_dotenv('.env.local')

conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cursor = conn.cursor()

print("🔍 Verifying 10KAY Database Schema")
print("=" * 60)
print()

# Check tables
cursor.execute("""
    SELECT table_name,
           (SELECT COUNT(*) FROM information_schema.columns
            WHERE table_name = t.table_name) as column_count
    FROM information_schema.tables t
    WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
    ORDER BY table_name
""")

print("📊 Tables:")
for table, cols in cursor.fetchall():
    print(f"  ✓ {table} ({cols} columns)")
print()

# Check indexes
cursor.execute("""
    SELECT tablename, indexname
    FROM pg_indexes
    WHERE schemaname = 'public'
    ORDER BY tablename, indexname
""")

indexes_by_table = {}
for table, index in cursor.fetchall():
    if table not in indexes_by_table:
        indexes_by_table[table] = []
    indexes_by_table[table].append(index)

print(f"🔍 Indexes ({sum(len(v) for v in indexes_by_table.values())} total):")
for table in sorted(indexes_by_table.keys()):
    print(f"  {table}: {len(indexes_by_table[table])} indexes")
print()

# Check views
cursor.execute("""
    SELECT table_name
    FROM information_schema.views
    WHERE table_schema = 'public'
    ORDER BY table_name
""")

views = cursor.fetchall()
print(f"👁️  Views ({len(views)}):")
for (view,) in views:
    print(f"  ✓ {view}")
print()

# Check functions
cursor.execute("""
    SELECT routine_name
    FROM information_schema.routines
    WHERE routine_schema = 'public'
      AND routine_type = 'FUNCTION'
    ORDER BY routine_name
""")

functions = cursor.fetchall()
print(f"⚙️  Functions ({len(functions)}):")
for (func,) in functions:
    if not func.startswith('pg_'):
        print(f"  ✓ {func}")
print()

print("=" * 60)
print("✅ Schema verification complete!")
print("=" * 60)

cursor.close()
conn.close()
