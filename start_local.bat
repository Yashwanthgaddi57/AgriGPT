@echo off
rem Detached launcher: backend (uvicorn) + frontend (Next.js PRODUCTION mode).
rem Production mode = instant page navigation (no per-page compile).

rem ---- Frontend: build once if no production bundle exists ----
cd /d "%~dp0frontend"
if not exist ".next\BUILD_ID" (
  echo Building frontend production bundle ^(first run or after code changes^)...
  call npx next build
)

rem ---- Start servers ----
cd /d "%~dp0backend"
start "agrisphere-backend" /min .venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
cd /d "%~dp0frontend"
start "agrisphere-frontend" /min cmd /c "npx next start"

echo AgriSphere AI running (frontend in PRODUCTION mode):
echo   Frontend  http://localhost:3000
echo   Backend   http://localhost:8000/docs
echo.
echo Tip: run "build_frontend.bat" after editing frontend code.
