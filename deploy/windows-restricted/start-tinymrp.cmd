@echo off
REM ===================================================================
REM  Start TinyMRP on a locked-down Windows host.
REM
REM  Uses only python.exe and run.py, which is normally the one command
REM  such a host has been approved for. No service, no new executable,
REM  no elevation.
REM
REM  Usage:
REM    start-tinymrp.cmd
REM    start-tinymrp.cmd C:\TinyMRP\config\.env.lan
REM    start-tinymrp.cmd C:\TinyMRP\config\.env.lan C:\TinyMRP\app\tinymrp_v2
REM
REM  Everything else - which interface, which port, which server - comes
REM  from the env file. See .env.restricted.example.
REM  Guide: docs/deployment/12-restricted-windows-flask.md
REM ===================================================================
setlocal

set "ENV_FILE=%~1"
if "%ENV_FILE%"=="" set "ENV_FILE=C:\TinyMRP\config\.env.lan"

set "APP_ROOT=%~2"
if "%APP_ROOT%"=="" (
  for %%I in ("%~dp0..\..") do set "APP_ROOT=%%~fI"
)

if not exist "%ENV_FILE%" (
  echo [TinyMRP] Environment file not found: %ENV_FILE%
  echo [TinyMRP] Copy deploy\windows-restricted\.env.restricted.example there and edit it.
  exit /b 2
)
if not exist "%APP_ROOT%\run.py" (
  echo [TinyMRP] run.py not found under: %APP_ROOT%
  echo [TinyMRP] Pass the repository folder as the second argument.
  exit /b 2
)

set "PYTHON=%APP_ROOT%\.venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"

REM PYTHONUNBUFFERED so the log is written as it happens rather than in
REM blocks, which matters when the only diagnosis you get is the log file.
set "PYTHONUNBUFFERED=1"

echo [TinyMRP] App root : %APP_ROOT%
echo [TinyMRP] Env file : %ENV_FILE%
echo [TinyMRP] Python   : %PYTHON%
echo [TinyMRP] Starting. Press Ctrl+C to stop.
echo.

cd /d "%APP_ROOT%"
"%PYTHON%" run.py
set "RC=%ERRORLEVEL%"

if not "%RC%"=="0" (
  echo.
  echo [TinyMRP] Exited with code %RC%.
  echo [TinyMRP] Run deploy\windows-restricted\check-restricted-install.ps1 for a diagnosis.
)
exit /b %RC%
