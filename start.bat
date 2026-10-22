@echo off
echo Starting JobApply...
echo.

if not exist .venv (
    echo ERROR: Virtual environment not found. Run setup.bat first.
    pause
    exit /b 1
)

if not exist .env (
    echo Creating .env from template...
    copy .env.example .env
)

echo Server starting at http://localhost:8000
echo Press Ctrl+C to stop
echo.

.venv\Scripts\python.exe -m uvicorn jobapply.server:create_app --factory --host 0.0.0.0 --port 8000 --env-file .env --reload
