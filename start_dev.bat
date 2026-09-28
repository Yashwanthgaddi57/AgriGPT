@echo off
rem Dev-mode launcher with hot reload (slower first click per page; use when
rem actively editing frontend code). For daily use prefer start_local.bat.
cd /d "%~dp0backend"
start "agrisphere-backend" /min .venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
cd /d "%~dp0frontend"
start "agrisphere-frontend" /min cmd /c "npm run dev"
echo AgriSphere AI running (dev frontend, hot reload):
echo   Frontend  http://localhost:3000
echo   Backend   http://localhost:8000/docs
