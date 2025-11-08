#!/usr/bin/env python3
"""
Test RDS PostgreSQL connection
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')

DATABASE_URL = os.getenv('DATABASE_URL')

print("🔍 Testing RDS PostgreSQL connection...")
print(f"📍 Endpoint: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'N/A'}")
print()

try:
    import psycopg2

    # Connect to database
    print("🔌 Connecting to database...")
    conn = psycopg2.connect(DATABASE_URL)

    # Test query
    cursor = conn.cursor()
    cursor.execute("SELECT version();")
    version = cursor.fetchone()[0]

    print("✅ Connection successful!")
    print(f"📊 PostgreSQL version: {version[:80]}...")
    print()

    # List databases
    cursor.execute("SELECT datname FROM pg_database WHERE datistemplate = false;")
    databases = cursor.fetchall()
    print("📁 Available databases:")
    for db in databases:
        print(f"   - {db[0]}")
    print()

    # Close connection
    cursor.close()
    conn.close()

    print("=" * 60)
    print("✅ Database connection test PASSED!")
    print("=" * 60)

except ImportError:
    print("❌ psycopg2 not installed!")
    print("   Install it with: pip install psycopg2-binary")
    exit(1)

except Exception as e:
    print(f"❌ Connection failed: {e}")
    print()
    print("Common issues:")
    print("  1. Check password in DATABASE_URL")
    print("  2. Verify security group allows your IP")
    print("  3. Confirm database name is correct")
    exit(1)
