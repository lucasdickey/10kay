#!/usr/bin/env python3
"""Test script to analyze one filing and capture Bedrock response"""

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

# Get just one pending filing
cursor = conn.cursor()
cursor.execute('''SELECT id FROM filings WHERE status = 'pending' LIMIT 1''')
result = cursor.fetchone()
if not result:
    print("No pending filings found!")
    cursor.close()
    conn.close()
    exit(1)

filing_id = result[0]
cursor.close()

print(f'\nAnalyzing filing: {filing_id}')
print("=" * 80)

# Now analyze it
analyzer = ClaudeAnalyzer(config, conn, logger)
try:
    result = analyzer.analyze_filing(filing_id, AnalysisType.DEEP_ANALYSIS)
    print('\n✓ Analysis successful!')
    print(f"Headline: {result.tldr_headline}")
except Exception as e:
    print(f'\n✗ Error: {e}')
    import traceback
    traceback.print_exc()

conn.close()
