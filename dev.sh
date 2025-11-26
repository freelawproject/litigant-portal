#!/bin/bash

# Start Django and Vite dev servers
# Usage: ./dev.sh

# Colors for output
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting Litigant Portal development servers...${NC}"
echo ""
echo -e "${YELLOW}📱 Visit your app at: ${GREEN}http://localhost:8000/components/${NC}"
echo -e "${CYAN}   (Vite assets served from: http://localhost:5173)${NC}"
echo ""
echo -e "Press ${YELLOW}Ctrl+C${NC} to stop both servers"
echo ""
echo "----------------------------------------"
echo ""

# Activate virtual environment and start both servers
source .venv/bin/activate && \
npx concurrently \
  --names "VITE,DJANGO" \
  --prefix-colors "cyan,green" \
  "npm run vite" \
  "python manage.py runserver"
