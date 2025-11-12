"""
Add slug column to content table and populate it
"""
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv('.env.local')

# Connect to database
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cursor = conn.cursor()

print("Adding slug column...")
cursor.execute("""
    ALTER TABLE content
    ADD COLUMN IF NOT EXISTS slug TEXT;
""")
conn.commit()

print("Creating unique index on slug...")
cursor.execute("""
    CREATE UNIQUE INDEX IF NOT EXISTS content_slug_idx ON content(slug);
""")
conn.commit()

print("Generating slugs for existing content...")
cursor.execute("""
    UPDATE content c
    SET slug = LOWER(co.ticker) || '/' ||
               CAST(f.fiscal_year AS TEXT) || '/' ||
               CASE
                   WHEN f.fiscal_quarter IS NOT NULL
                   THEN 'q' || CAST(f.fiscal_quarter AS TEXT)
                   ELSE 'fy'
               END || '/' ||
               LOWER(REPLACE(f.filing_type, '-', ''))
    FROM filings f
    JOIN companies co ON f.company_id = co.id
    WHERE c.filing_id = f.id
    AND c.slug IS NULL;
""")
rows_updated = cursor.rowcount
conn.commit()

print(f"✓ Updated {rows_updated} rows with slugs")

# Verify
cursor.execute("SELECT ticker, filing_type, fiscal_year, fiscal_quarter, slug FROM content c JOIN filings f ON c.filing_id = f.id JOIN companies co ON f.company_id = co.id LIMIT 5")
print("\nSample slugs:")
for row in cursor.fetchall():
    print(f"  {row[0]} {row[1]} {row[2]} Q{row[3] if row[3] else 'FY'} -> {row[4]}")

cursor.close()
conn.close()
print("\n✓ Migration complete!")
