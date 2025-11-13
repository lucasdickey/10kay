#!/usr/bin/env python3
"""Test script to debug FIG filing analysis"""

import psycopg2
import json
from pipeline.utils import get_config, PipelineLogger, setup_root_logger
from pipeline.analyzers import ClaudeAnalyzer, AnalysisType

# Setup
config = get_config()
root_logger = setup_root_logger()
logger = PipelineLogger(root_logger, 'test')

# Connect to database
conn = psycopg2.connect(config.database.url)

# Get FIG pending filing
cursor = conn.cursor()
cursor.execute('''
    SELECT f.id FROM filings f
    JOIN companies c ON f.company_id = c.id
    WHERE c.ticker = 'FIG' AND f.status = 'pending'
    LIMIT 1
''')
result = cursor.fetchone()
if not result:
    print("No pending FIG filings found!")
    cursor.close()
    conn.close()
    exit(1)

filing_id = result[0]
cursor.close()

print(f'\nAnalyzing FIG filing: {filing_id}')
print("=" * 80)

# Now analyze it
analyzer = ClaudeAnalyzer(config, conn, logger)
try:
    result = analyzer.analyze_filing(filing_id, AnalysisType.DEEP_ANALYSIS)
    print('✓ Analysis successful!')
    print(f"Headline: {result.tldr_headline}")
except Exception as e:
    print(f'✗ Error: {e}')
    import traceback
    traceback.print_exc()

conn.close()
