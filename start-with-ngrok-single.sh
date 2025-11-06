#!/bin/bash

# Startup script for running the app with a single ngrok tunnel
# Uses nginx to proxy both Django and Vite (free tier compatible)

set -e

echo "🚀 Starting development servers with ngrok (single tunnel via nginx)..."

# Check if ngrok is installed
if ! command -v ngrok &> /dev/null; then
    echo "❌ ngrok is not installed. Install it from https://ngrok.com/"
    exit 1
fi

# Check if nginx is installed
if ! command -v nginx &> /dev/null; then
    echo "❌ nginx is not installed. Install it with: brew install nginx"
    exit 1
fi

# Kill any existing processes
echo "🧹 Cleaning up existing processes..."
pkill -f ngrok || true
pkill -f nginx || true
pkill -f "manage.py runserver" || true
pkill -f "node.*vite" || true
# Also kill by port in case process name doesn't match
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
lsof -ti:5173 | xargs kill -9 2>/dev/null || true
lsof -ti:9000 | xargs kill -9 2>/dev/null || true
sleep 2

# Start Vite dev server first (localhost only)
echo ""
echo "🚀 Starting Vite dev server on localhost:5173..."
npm run dev > /tmp/vite-dev.log 2>&1 &
VITE_PID=$!
echo "   PID: $VITE_PID"

# Wait for Vite to start
sleep 3

# Start Django dev server
echo ""
echo "🚀 Starting Django dev server on localhost:8000..."
python3 manage.py runserver > /tmp/django-dev.log 2>&1 &
DJANGO_PID=$!
echo "   PID: $DJANGO_PID"

# Wait for Django to start
echo "⏳ Waiting for Django to be ready..."
sleep 5

# Verify Django is running
if ! lsof -i :8000 > /dev/null 2>&1; then
    echo "❌ Django failed to start. Check /tmp/django-dev.log"
    kill $VITE_PID 2>/dev/null
    exit 1
fi
echo "✅ Django is ready on port 8000"

# Start nginx
echo ""
echo "🚀 Starting nginx on localhost:9000..."
nginx -c "$(pwd)/nginx.conf" > /tmp/nginx.log 2>&1
if [ $? -ne 0 ]; then
    echo "❌ nginx failed to start. Check /tmp/nginx.log"
    kill $VITE_PID $DJANGO_PID 2>/dev/null
    exit 1
fi
echo "✅ nginx is ready on port 9000"

# Wait for nginx
sleep 2

# Start ngrok for nginx (port 9000)
echo ""
echo "📡 Starting ngrok tunnel for nginx (port 9000)..."
ngrok http 9000 --log=stdout > /tmp/ngrok.log 2>&1 &
NGROK_PID=$!

# Wait for ngrok to start
echo "⏳ Waiting for ngrok to initialize..."
sleep 4

# Get ngrok URL
echo ""
echo "🔗 Getting ngrok URL..."

NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | python3 -c "import sys, json; tunnels = json.load(sys.stdin)['tunnels']; print(tunnels[0]['public_url'] if tunnels else '')" 2>/dev/null)

if [ -z "$NGROK_URL" ]; then
    echo "❌ Failed to get ngrok URL. Check /tmp/ngrok.log"
    kill $VITE_PID $DJANGO_PID 2>/dev/null
    pkill -f nginx
    pkill -P $NGROK_PID
    exit 1
fi

echo ""
echo "✅ All servers running!"
echo ""
echo "┌─────────────────────────────────────────────────┐"
echo "│                 🌐 NGROK URL                    │"
echo "├─────────────────────────────────────────────────┤"
echo "│ $NGROK_URL"
echo "└─────────────────────────────────────────────────┘"
echo ""
echo "📱 Use this URL on your mobile device:"
echo "   $NGROK_URL/camera/"
echo ""
echo "ℹ️  nginx proxies both Django and Vite through a single port."
echo "   JavaScript and HMR should work on mobile!"
echo ""
echo "📋 Server logs:"
echo "   Django:        /tmp/django-dev.log"
echo "   Vite:          /tmp/vite-dev.log"
echo "   nginx access:  /tmp/nginx-access.log"
echo "   nginx error:   /tmp/nginx-error.log"
echo "   Ngrok:         /tmp/ngrok.log"
echo ""
echo "🛑 Press Ctrl+C to stop all servers..."

# Wait for user interrupt
trap "echo ''; echo '🛑 Stopping all servers...'; kill $VITE_PID $DJANGO_PID 2>/dev/null; pkill -f nginx; pkill -P $NGROK_PID; exit 0" INT

# Monitor logs
tail -f /tmp/django-dev.log /tmp/vite-dev.log
