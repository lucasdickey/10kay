#!/bin/bash
# Complete 10KAY Pipeline Runner for New Companies
# This script runs all phases of the pipeline in sequence

set -e  # Exit on first error

echo "==========================================="
echo "10KAY Complete Pipeline Runner"
echo "==========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
LOG_LEVEL="${1:-INFO}"
ANALYZE_LIMIT="${2:-500}"
GENERATE_LIMIT="${3:-500}"

echo -e "${YELLOW}Configuration:${NC}"
echo "  Log Level: $LOG_LEVEL"
echo "  Analyze Limit: $ANALYZE_LIMIT"
echo "  Generate Limit: $GENERATE_LIMIT"
echo ""

# Phase 1: Fetch (optional - usually already done)
echo -e "${YELLOW}Phase 1: Fetching latest SEC filings...${NC}"
python3 pipeline/main.py --phase fetch --log-level "$LOG_LEVEL" || {
    echo -e "${RED}Fetch phase failed${NC}"
    exit 1
}
echo -e "${GREEN}✓ Fetch complete${NC}"
echo ""

# Phase 2: Analyze
echo -e "${YELLOW}Phase 2: Analyzing filings with Claude AI...${NC}"
python3 pipeline/main.py --phase analyze --log-level "$LOG_LEVEL" || {
    echo -e "${RED}Analyze phase failed${NC}"
    exit 1
}
echo -e "${GREEN}✓ Analysis complete${NC}"
echo ""

# Phase 3: Generate
echo -e "${YELLOW}Phase 3: Generating content formats...${NC}"
python3 pipeline/main.py --phase generate --log-level "$LOG_LEVEL" || {
    echo -e "${RED}Generate phase failed${NC}"
    exit 1
}
echo -e "${GREEN}✓ Content generation complete${NC}"
echo ""

# Phase 4: Publish (with dry-run option)
echo -e "${YELLOW}Phase 4: Publishing to subscribers...${NC}"
echo "  Running in DRY-RUN mode (no emails sent)"
python3 pipeline/main.py --phase publish --dry-run --log-level "$LOG_LEVEL" || {
    echo -e "${RED}Publish phase failed${NC}"
    exit 1
}
echo -e "${GREEN}✓ Publish validation complete${NC}"
echo ""

echo "==========================================="
echo -e "${GREEN}Pipeline Complete!${NC}"
echo "==========================================="
echo ""
echo "Next steps:"
echo "  1. Review the analysis results in the database"
echo "  2. Check the email preview from publish --dry-run"
echo "  3. Run without --dry-run to actually send emails:"
echo "     python3 pipeline/main.py --phase publish"
echo ""
