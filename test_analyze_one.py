#!/usr/bin/env python3
"""Test script to analyze one filing and capture Bedrock response"""

import json
from pipeline.db import connect
from pipeline.utils import get_config, PipelineLogger, setup_root_logger
from pipeline.analyzers import ClaudeAnalyzer, AnalysisType

# Setup
config = get_config()
setup_root_logger()
logger = PipelineLogger('test_analyze_one')

# Connect to database
conn = connect(config.database.url, application_name='10kay-test_analyze_one')

# Get just one pending filing
cursor = conn.cursor()
cursor.execute('''SELECT id FROM filings WHERE status = 'pending' LIMIT 1''')
result = cursor.fetchone()
if not result:
    print("No pending filings found!")
    cursor.close()
    logger.close()
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
    content_id = analyzer.save_to_database(result)
    print('\n✓ Analysis successful!')
    print(f"Headline: {result.tldr_headline}")
    print(f"Content ID: {content_id}")
except Exception as e:
    print(f'\n✗ Error: {e}')
    import traceback
    traceback.print_exc()

logger.close()
conn.close()
