#!/usr/bin/env bash
# AEGIS stopper (macOS / Linux)
cd "$(dirname "$0")"
API_PORT="${AEGIS_API_PORT:-8001}"
WEB_PORT="${AEGIS_WEB_PORT:-5173}"
RUN_DIR=".run"

kill_port() {
  local pids=""
  if command -v lsof >/dev/null 2>&1; then pids="$(lsof -ti tcp:"$1" -sTCP:LISTEN 2>/dev/null)"
  elif command -v fuser >/dev/null 2>&1; then pids="$(fuser "$1"/tcp 2>/dev/null)"; fi
  [ -n "$pids" ] && kill $pids 2>/dev/null
}

echo "Stopping AEGIS..."
for name in api web; do
  if [ -f "$RUN_DIR/$name.pid" ]; then
    pid="$(cat "$RUN_DIR/$name.pid")"
    kill "$pid" 2>/dev/null
    pkill -P "$pid" 2>/dev/null
    rm -f "$RUN_DIR/$name.pid"
  fi
done
kill_port "$API_PORT"
kill_port "$WEB_PORT"
sleep 1
echo "Done. AEGIS is stopped."
