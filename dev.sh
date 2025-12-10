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
echo -e "${YELLOW}Visit your app at: ${GREEN}http://localhost:8000/${NC}"
echo -e "${CYAN}Component Library: http://localhost:8000/components/${NC}"
echo ""
echo -e "Press ${YELLOW}Ctrl+C${NC} to stop"
echo ""
echo "----------------------------------------"
echo ""

# Cleanup function to kill background processes
cleanup() {
  echo ""
  echo -e "${YELLOW}Shutting down...${NC}"
  kill $TAILWIND_PID 2>/dev/null
  kill $DJANGO_PID 2>/dev/null
  exit 0
}
trap cleanup SIGINT SIGTERM

# Activate virtual environment
source .venv/bin/activate

# Start Tailwind CSS watch in background
tailwindcss -i static/css/main.css -o static/css/main.built.css --watch &
TAILWIND_PID=$!
echo -e "${CYAN}[CSS]${NC} Tailwind watching..."

# Start Django in foreground
echo -e "${GREEN}[DJANGO]${NC} Starting server..."
python manage.py runserver &
DJANGO_PID=$!

# Wait for both processes
wait
