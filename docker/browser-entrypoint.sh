#!/bin/bash
set -e

# Clean up any stale X server lock files
rm -f /tmp/.X99-lock /tmp/.X11-unix/X99

# Start Xvfb in the background
export DISPLAY=:99
Xvfb :99 -screen 0 1920x1080x24 &
XVFB_PID=$!

# Wait for X server to be ready
sleep 2

# Set Chrome to use internal port 9223, but expose via socat on port 9222
export CHROME_REMOTE_DEBUG_PORT="9223"

echo "Starting socat proxy from port 9222 to 127.0.0.1:9223..."
socat TCP-LISTEN:9222,fork,reuseaddr TCP:127.0.0.1:9223 &
SOCAT_PID=$!

# Run the browser server
/app/.venv/bin/browser &
BROWSER_PID=$!

# Handle shutdown gracefully
trap "kill $BROWSER_PID $SOCAT_PID $XVFB_PID 2>/dev/null; exit" SIGTERM SIGINT

# Wait for browser process
wait $BROWSER_PID
rm -rf /tmp/.X99-lock
