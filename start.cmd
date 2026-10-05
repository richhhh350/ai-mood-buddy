@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment missing. Follow README.md setup steps first.
    pause
    exit /b 1
)
echo Open http://127.0.0.1:8000/ in your browser. Press Ctrl+C to stop.
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
