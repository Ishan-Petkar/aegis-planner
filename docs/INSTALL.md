# Installation guide

## 1. Prerequisites

| Tool | Version | macOS | Windows | Linux (Debian/Ubuntu) |
|---|---|---|---|---|
| Python | 3.9 or newer | `brew install python` | [python.org](https://www.python.org/downloads/) (tick **Add python.exe to PATH**) | `sudo apt install python3 python3-venv python3-pip` |
| Node.js (includes npm) | 18 or newer | `brew install node` | [nodejs.org](https://nodejs.org) (LTS) | [nodejs.org](https://nodejs.org) or `sudo apt install nodejs npm` |
| Git | any | `brew install git` | [git-scm.com](https://git-scm.com/download/win) | `sudo apt install git` |

Check what you have:

```bash
python3 --version    # Windows: python --version
node --version
npm --version
```

You do not need an account, an API key or an internet connection after the first install. The only external request is the web fonts, and the app falls back to system fonts without them.

## 2. Get the code

```bash
git clone https://github.com/Ishan-Petkar/aegis-planner.git
cd aegis-planner
```

Or download the ZIP from the Releases page and unpack it.

## 3. Start with one command

| | Start | Stop |
|---|---|---|
| macOS / Linux | `./run.sh` | `./stop.sh` |
| Windows | double-click `run.bat` | double-click `stop.bat` |

The launcher:

1. checks Python, Node.js and npm, and lists anything missing with install links;
2. creates a virtual environment and installs the backend packages (first run only);
3. installs the web packages (first run only, about a minute);
4. starts the backend on port 8001 and the web app on port 5173;
5. opens http://localhost:5173.

If AEGIS is already running, `run` simply opens the browser.

### Custom ports

```bash
AEGIS_API_PORT=8002 AEGIS_WEB_PORT=5174 ./run.sh
```

On Windows (Command Prompt):

```bat
set AEGIS_API_PORT=8002 & set AEGIS_WEB_PORT=5174 & run.bat
```

Use the same variables when stopping.

## 4. Manual setup

If you prefer to run each part yourself:

```bash
# terminal 1: backend
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt
cd backend
../backend/.venv/bin/python -m uvicorn api:app --port 8001

# terminal 2: web app
cd frontend
npm install
npm run dev
```

Windows (Command Prompt):

```bat
python -m venv backend\.venv
backend\.venv\Scripts\pip install -r backend\requirements.txt
cd backend
..\backend\.venv\Scripts\python -m uvicorn api:app --port 8001
```

The web app proxies `/api` to `http://localhost:8001`. To point it elsewhere, set `AEGIS_API` before `npm run dev`.

## 5. Production build of the web app

```bash
cd frontend
npm run build      # output in frontend/dist
npm run preview
```

## 6. Run the tests

```bash
pip install -r backend/requirements.txt pytest httpx
python -m pytest backend/tests
```

## 7. Reproduce the experiment

```bash
cd backend
python experiments/run_ablation.py
```

This runs 6 scenarios × 3 planners × 5 seeds and writes `experiments/results.json` and `experiments/tables.md`.

## 8. Google Colab

Open `notebooks/AEGIS_Colab.ipynb` in [Colab](https://colab.research.google.com) and choose **Runtime → Run all**. It contains the whole model and needs no setup.

## Troubleshooting

| Symptom | Fix |
|---|---|
| "Port 8001 is in use" | Stop the other program, run `./stop.sh`, or choose other ports (see above). |
| `python3 -m venv` fails on Debian/Ubuntu | `sudo apt install python3-venv` |
| `npm install` fails | Check your internet connection, then run the launcher again. |
| The page loads but shows "Loading plan…" | The backend is not running. Check `.run/api.log`, or the "AEGIS API" window on Windows. |
| The page is blank after switching machines | Delete `frontend/node_modules` and run the launcher again. |
| Windows says scripts are blocked | Right-click `run.bat`, choose Properties, then Unblock. |
