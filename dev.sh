#!/bin/bash

# Start Django and Tailwind CSS watch
# Usage: ./dev.sh

# Colors for output
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting Litigant Portal development servers...${NC}"
echo ""
echo -e "${YELLOW}📱 Visit your app at: ${GREEN}http://localhost:8000/${NC}"
echo -e "${CYAN}   Pattern Library: http://localhost:8000/pattern-library/${NC}"
echo ""
echo -e "Press ${YELLOW}Ctrl+C${NC} to stop"
echo ""
echo "----------------------------------------"
echo ""

# Activate virtual environment and start Django + Tailwind watch
source .venv/bin/activate && \
npx concurrently \
  --names "CSS,DJANGO" \
  --prefix-colors "cyan,green" \
  "npm run watch:css" \
  "python manage.py runserver"
