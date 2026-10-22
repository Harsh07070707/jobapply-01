# JobApply Startup Script for Windows
# Usage: ./start.ps1

Write-Host "Starting JobApply..." -ForegroundColor Green

# Check if .venv exists
if (-not (Test-Path ".venv")) {
    Write-Host "ERROR: Virtual environment not found. Run setup.ps1 first." -ForegroundColor Red
    exit 1
}

# Check if .env exists
if (-not (Test-Path ".env")) {
    Write-Host "Creating .env from template..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env" -ErrorAction Stop
}

# Start the server
Write-Host "`nStarting server at http://localhost:8000" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop`n" -ForegroundColor Yellow

.\.venv\Scripts\python.exe -m uvicorn jobapply.server:create_app --factory --host 0.0.0.0 --port 8000 --env-file .env --reload
