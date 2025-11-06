# Mobile Testing Guide

## Android Emulator (Local Testing)

### Setup
```bash
# Start emulator
emulator -avd Pixel_8_Play &

# Forward ports
adb reverse tcp:8000 tcp:8000
adb reverse tcp:5173 tcp:5173

# Open app
adb shell am start -a android.intent.action.VIEW -d "http://localhost:8000/camera/"
```

### Debug
```bash
# View logs
adb logcat | grep -i camera

# Take screenshot
adb shell screencap -p > screenshot.png

# Chrome DevTools
# Open chrome://inspect/#devices in Chrome
```

## Real Device (ngrok)

### Prerequisites
```bash
# Install nginx if you haven't already
brew install nginx
```

### Single Tunnel Setup (Free Tier Compatible)
```bash
# Start everything with one command
./start-with-ngrok-single.sh

# This starts:
# - Vite dev server (localhost:5173)
# - Django server (localhost:8000)
# - nginx proxy (localhost:9000)
# - ngrok tunnel pointing to nginx

# Open the displayed URL on your mobile device
# Example: https://abc.ngrok-free.app/camera/
```

**How it works:** nginx proxies both Django and Vite through a single port (9000). The `/static/` requests are forwarded to Vite, everything else goes to Django. This works with ngrok's free tier since we only need one tunnel.

### Manual Setup
```bash
# Terminal 1: Start Vite
npm run dev

# Terminal 2: Start Django
python3 manage.py runserver

# Terminal 3: Start nginx
nginx -c "$(pwd)/nginx.conf"

# Terminal 4: Start ngrok pointing to nginx
ngrok http 9000

# Open the ngrok URL on your device
```

## Troubleshooting

### Camera not working
- **Emulator**: Ensure ports 8000 and 5173 are forwarded
- **Real device**: Check HTTPS (camera requires secure context)
- **Both**: Check browser console for errors via chrome://inspect

### Alpine.js not loading
- **Emulator**: Port 5173 not forwarded
- **Real device**: Check that nginx is running and proxying correctly
- Verify `/static/` requests are reaching Vite (check /tmp/vite-dev.log)

### CSP errors
- Check browser console for violations
- All assets come from the same origin (ngrok URL) with nginx proxying

### nginx not starting
- Check if another process is using port 9000: `lsof -i :9000`
- View nginx logs: `cat /tmp/nginx.log`
- Kill existing nginx: `pkill -f nginx`
