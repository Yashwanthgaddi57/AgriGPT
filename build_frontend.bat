@echo off
rem Rebuild the frontend production bundle (run after editing frontend code).
cd /d "%~dp0frontend"
echo Building production bundle...
call npx next build
echo Done. Restart the frontend (or start_local.bat) to serve the new build.
