@echo off
setlocal
rem AEGIS stopper (Windows)
if "%AEGIS_API_PORT%"=="" set "AEGIS_API_PORT=8001"
if "%AEGIS_WEB_PORT%"=="" set "AEGIS_WEB_PORT=5173"
echo Stopping AEGIS...
for %%P in (%AEGIS_API_PORT% %AEGIS_WEB_PORT%) do (
  for /f "tokens=5" %%I in ('netstat -ano ^| findstr /R /C:":%%P .*LISTENING"') do taskkill /PID %%I /T /F >nul 2>nul
)
taskkill /FI "WINDOWTITLE eq AEGIS API*" /T /F >nul 2>nul
taskkill /FI "WINDOWTITLE eq AEGIS Web*" /T /F >nul 2>nul
echo Done. AEGIS is stopped.
