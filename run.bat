@echo off
setlocal EnableDelayedExpansion
rem AEGIS launcher (Windows): checks prerequisites, installs dependencies, starts API + web app, opens the browser.
cd /d "%~dp0"
set "ROOT=%CD%"
if "%AEGIS_API_PORT%"=="" set "AEGIS_API_PORT=8001"
if "%AEGIS_WEB_PORT%"=="" set "AEGIS_WEB_PORT=5173"
set "VENV=%ROOT%\backend\.venv-win"

echo.
echo Checking prerequisites
set "M1=" & set "M2=" & set "M3="

set "PY="
py -3 -c "import sys; sys.exit(0 if sys.version_info>=(3,9) else 1)" >nul 2>nul && set "PY=py -3"
if not defined PY (
  python -c "import sys; sys.exit(0 if sys.version_info>=(3,9) else 1)" >nul 2>nul && set "PY=python"
)
if defined PY (
  echo   [OK] Python 3.9 or newer
) else (
  echo   [X]  Python 3.9 or newer
  set "M1=Python 3.9+  -^>  https://www.python.org/downloads/  (tick 'Add python.exe to PATH' in the installer)"
)

set "NODEMAJOR=0"
where node >nul 2>nul
if not errorlevel 1 (
  for /f "tokens=1 delims=v." %%a in ('node -v') do set "NODEMAJOR=%%a"
)
if !NODEMAJOR! GEQ 18 (
  echo   [OK] Node.js 18 or newer
) else (
  echo   [X]  Node.js 18 or newer
  set "M2=Node.js 18+  -^>  https://nodejs.org  (LTS version)"
)

where npm >nul 2>nul
if errorlevel 1 (
  echo   [X]  npm ^(comes with Node.js^)
  set "M3=npm  -^>  installed together with Node.js: https://nodejs.org"
) else (
  echo   [OK] npm
)

if defined M1 goto :missing
if defined M2 goto :missing
if defined M3 goto :missing
goto :prereq_ok

:missing
echo.
echo Please install the following, then run run.bat again:
if defined M1 echo   - !M1!
if defined M2 echo   - !M2!
if defined M3 echo   - !M3!
echo.
pause
exit /b 1

:prereq_ok
set "API_BUSY=0"
set "WEB_BUSY=0"
call :port_busy %AEGIS_API_PORT%
if not errorlevel 1 set "API_BUSY=1"
call :port_busy %AEGIS_WEB_PORT%
if not errorlevel 1 set "WEB_BUSY=1"

if "!API_BUSY!!WEB_BUSY!"=="11" (
  echo.
  echo AEGIS is already running: http://localhost:%AEGIS_WEB_PORT%   ^(stop it with stop.bat^)
  if not "%AEGIS_NO_BROWSER%"=="1" start "" "http://localhost:%AEGIS_WEB_PORT%"
  exit /b 0
)
if "!API_BUSY!"=="1" goto :port_in_use
if "!WEB_BUSY!"=="1" goto :port_in_use
goto :prepare_backend

:port_in_use
echo.
echo   [X]  A port is already in use by another program (API %AEGIS_API_PORT% / web %AEGIS_WEB_PORT%).
echo        Free it, or choose other ports:  set AEGIS_API_PORT=8002 ^& set AEGIS_WEB_PORT=5174 ^& run.bat
pause
exit /b 1

:prepare_backend
echo.
echo Preparing backend
if not exist "%VENV%\Scripts\python.exe" (
  echo   Creating Python virtual environment...
  %PY% -m venv "%VENV%"
  if errorlevel 1 (
    echo   [X]  Could not create a virtual environment.
    pause
    exit /b 1
  )
)
"%VENV%\Scripts\python.exe" -c "import fastapi, uvicorn" >nul 2>nul
if errorlevel 1 (
  echo   Installing Python packages ^(first run only^)...
  "%VENV%\Scripts\python.exe" -m pip install -q -r backend\requirements.txt
  if errorlevel 1 (
    echo   [X]  pip install failed. Check your internet connection.
    pause
    exit /b 1
  )
)
echo   [OK] Backend ready

echo.
echo Preparing web app
set "NEED_NPM=0"
if not exist "frontend\node_modules" set "NEED_NPM=1"
if not exist "frontend\node_modules\.aegis-win" set "NEED_NPM=1"
if "!NEED_NPM!"=="1" (
  echo   Installing web packages ^(first run only, about a minute^)...
  if exist "frontend\node_modules" rmdir /s /q "frontend\node_modules"
  pushd frontend
  call npm install --no-audit --no-fund
  set "NPM_RC=!errorlevel!"
  popd
  if not "!NPM_RC!"=="0" (
    echo   [X]  npm install failed. Check your internet connection.
    pause
    exit /b 1
  )
  echo win> "frontend\node_modules\.aegis-win"
)
echo   [OK] Web app ready

echo.
echo Starting AEGIS
set "AEGIS_API=http://127.0.0.1:%AEGIS_API_PORT%"
start "AEGIS API" /min /D "%ROOT%\backend" "%VENV%\Scripts\python.exe" -m uvicorn api:app --port %AEGIS_API_PORT%
start "AEGIS Web" /min /D "%ROOT%\frontend" cmd /c npm run dev -- --port %AEGIS_WEB_PORT% --strictPort

<nul set /p "=  Waiting for servers"
set /a TRIES=0
:wait_loop
"%VENV%\Scripts\python.exe" -c "import urllib.request as u; u.urlopen('http://127.0.0.1:%AEGIS_API_PORT%/api/scenarios', timeout=2); u.urlopen('http://localhost:%AEGIS_WEB_PORT%', timeout=2)" >nul 2>nul
if not errorlevel 1 goto :ready
set /a TRIES+=1
if !TRIES! GEQ 60 goto :failed
<nul set /p "=."
ping -n 2 127.0.0.1 >nul
goto :wait_loop

:failed
echo.
echo   [X]  The servers did not start. Look at the two minimized windows "AEGIS API" and "AEGIS Web" for the error.
pause
exit /b 1

:ready
echo.
echo   [OK] AEGIS is running
echo        App: http://localhost:%AEGIS_WEB_PORT%
echo        API: http://127.0.0.1:%AEGIS_API_PORT%
echo        Stop with: stop.bat
if not "%AEGIS_NO_BROWSER%"=="1" start "" "http://localhost:%AEGIS_WEB_PORT%"
echo.
echo You can close this window; AEGIS keeps running until you run stop.bat.
if not "%AEGIS_NO_BROWSER%"=="1" pause
exit /b 0

:port_busy
%PY% -c "import socket; socket.create_connection(('localhost',%~1),0.5)" >nul 2>nul
exit /b %errorlevel%
