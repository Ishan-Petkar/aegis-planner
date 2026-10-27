#!/usr/bin/env bash
# AEGIS launcher (macOS / Linux): checks prerequisites, installs dependencies, starts API + web app, opens the browser.
set -u
cd "$(dirname "$0")"
ROOT="$(pwd)"
API_PORT="${AEGIS_API_PORT:-8001}"
WEB_PORT="${AEGIS_WEB_PORT:-5173}"
RUN_DIR="$ROOT/.run"
VENV="$ROOT/backend/.venv"
mkdir -p "$RUN_DIR"

say()  { printf '\n\033[1m%s\033[0m\n' "$*"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
bad()  { printf '  \033[31m✗\033[0m %s\n' "$*"; }

# ---------- 1. prerequisites ----------
say "Checking prerequisites"
MISSING=()
OS="$(uname -s)"

PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then PY="$c"; break; fi
done
if [ -n "$PY" ]; then ok "Python $("$PY" -c 'import platform; print(platform.python_version())')"
else
  bad "Python 3.9 or newer"
  if [ "$OS" = "Darwin" ]; then MISSING+=("Python 3.9+  ->  brew install python   (or https://www.python.org/downloads/)")
  else MISSING+=("Python 3.9+  ->  sudo apt install python3 python3-venv python3-pip   (or https://www.python.org/downloads/)"); fi
fi

NODE_OK=0
if command -v node >/dev/null 2>&1; then
  NODE_MAJOR="$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || echo 0)"
  if [ "${NODE_MAJOR:-0}" -ge 18 ]; then ok "Node.js $(node -v)"; NODE_OK=1; fi
fi
if [ "$NODE_OK" -eq 0 ]; then
  bad "Node.js 18 or newer"
  if [ "$OS" = "Darwin" ]; then MISSING+=("Node.js 18+  ->  brew install node   (or https://nodejs.org)")
  else MISSING+=("Node.js 18+  ->  https://nodejs.org  (or: sudo apt install nodejs npm)"); fi
fi

if command -v npm >/dev/null 2>&1; then ok "npm $(npm -v)"
else bad "npm (comes with Node.js)"; MISSING+=("npm  ->  installed together with Node.js: https://nodejs.org"); fi

if [ ${#MISSING[@]} -gt 0 ]; then
  say "Please install the following, then run ./run.sh again:"
  for m in "${MISSING[@]}"; do echo "  - $m"; done
  exit 1
fi

port_busy() { "$PY" -c "import socket; socket.create_connection(('localhost', $1), 0.5)" >/dev/null 2>&1; }
open_browser() {
  [ "${AEGIS_NO_BROWSER:-0}" = "1" ] && return
  if command -v open >/dev/null 2>&1; then open "$1"
  elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$1" >/dev/null 2>&1 &
  else echo "  Open $1 in your browser."; fi
}

# ---------- 2. already running? ----------
if port_busy "$API_PORT" && port_busy "$WEB_PORT"; then
  say "AEGIS is already running"
  echo "  App: http://localhost:$WEB_PORT   (stop it with ./stop.sh)"
  open_browser "http://localhost:$WEB_PORT"
  exit 0
fi
for p in "$API_PORT" "$WEB_PORT"; do
  if port_busy "$p"; then
    bad "Port $p is in use by another program."
    echo "  Free it, or choose other ports: AEGIS_API_PORT=8002 AEGIS_WEB_PORT=5174 ./run.sh"
    exit 1
  fi
done

# ---------- 3. backend dependencies ----------
say "Preparing backend"
if [ ! -x "$VENV/bin/python" ] || ! "$VENV/bin/python" -c 'import sys' >/dev/null 2>&1; then
  echo "  Creating Python virtual environment..."
  rm -rf "$VENV"
  if ! "$PY" -m venv "$VENV"; then
    bad "Could not create a virtual environment."
    echo "  On Debian/Ubuntu install it with: sudo apt install python3-venv"
    exit 1
  fi
fi
if ! "$VENV/bin/python" -c 'import fastapi, uvicorn' >/dev/null 2>&1; then
  echo "  Installing Python packages (first run only)..."
  "$VENV/bin/python" -m pip install -q -r backend/requirements.txt || { bad "pip install failed (check your internet connection)"; exit 1; }
fi
ok "Backend ready"

# ---------- 4. frontend dependencies ----------
say "Preparing web app"
PLATFORM="unix-$OS-$(uname -m)"
STAMP="frontend/node_modules/.aegis-platform"
if [ ! -d frontend/node_modules ] || { [ -f "$STAMP" ] && [ "$(cat "$STAMP")" != "$PLATFORM" ]; }; then
  echo "  Installing web packages (first run only, ~1 minute)..."
  rm -rf frontend/node_modules
  (cd frontend && npm install --no-audit --no-fund) || { bad "npm install failed (check your internet connection)"; exit 1; }
  echo "$PLATFORM" > "$STAMP"
fi
ok "Web app ready"

# ---------- 5. start servers ----------
say "Starting AEGIS"
cd "$ROOT/backend"
nohup "$VENV/bin/python" -m uvicorn api:app --port "$API_PORT" > "$RUN_DIR/api.log" 2>&1 < /dev/null &
echo $! > "$RUN_DIR/api.pid"
cd "$ROOT/frontend"
AEGIS_API="http://127.0.0.1:$API_PORT" nohup npm run dev -- --port "$WEB_PORT" --strictPort > "$RUN_DIR/web.log" 2>&1 < /dev/null &
echo $! > "$RUN_DIR/web.pid"
cd "$ROOT"

printf '  Waiting for servers'
for _ in $(seq 1 60); do
  if "$VENV/bin/python" -c "import urllib.request as u; u.urlopen('http://localhost:$API_PORT/api/scenarios', timeout=2); u.urlopen('http://localhost:$WEB_PORT', timeout=2)" >/dev/null 2>&1; then READY=1; break; fi
  printf '.'; sleep 1
done
echo
if [ "${READY:-0}" != "1" ]; then
  bad "The servers did not start. Logs: $RUN_DIR/api.log and $RUN_DIR/web.log"
  tail -n 8 "$RUN_DIR/api.log" "$RUN_DIR/web.log" 2>/dev/null
  exit 1
fi
ok "AEGIS is running"
echo "  App: http://localhost:$WEB_PORT"
echo "  API: http://localhost:$API_PORT"
echo "  Stop with: ./stop.sh"
open_browser "http://localhost:$WEB_PORT"
