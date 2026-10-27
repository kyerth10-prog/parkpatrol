#!/bin/bash
# Park Patrol public launcher
cd "$(dirname "$0")/.."

if ! tools/ngrok config check >/dev/null 2>&1; then
  echo "ngrok is not configured."
  exit 1
fi

DOMAIN=$(grep -E '^BASE_URL=https://' .env | sed -E 's#^BASE_URL=https://##; s#/.*$##')

# Web server
if ! curl -s -o /dev/null -m 2 http://localhost:8000; then
  .venv/bin/python main.py &
  SERVER_PID=$!
  trap 'kill $SERVER_PID 2>/dev/null' EXIT
  for i in $(seq 1 20); do curl -s -o /dev/null -m 1 http://localhost:8000 && break; sleep 0.5; done
fi

# Tunnel
if [ -n "$DOMAIN" ]; then
  tools/ngrok http 8000 --url="$DOMAIN"
else
  tools/ngrok http 8000
fi
