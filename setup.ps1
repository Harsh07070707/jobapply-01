# JobApply One-Time Setup Script for Windows
# Usage: ./setup.ps1

Write-Host "JobApply Setup" -ForegroundColor Green
Write-Host "==============`n" -ForegroundColor Green

# Check Python
Write-Host "Checking Python..." -ForegroundColor Cyan
$pythonVersion = & python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Python not found. Install Python 3.11+ first." -ForegroundColor Red
    exit 1
}
Write-Host "✓ Found: $pythonVersion`n" -ForegroundColor Green

# Create virtual environment
if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Cyan
    python -m venv .venv
    Write-Host "✓ Virtual environment created`n" -ForegroundColor Green
} else {
    Write-Host "✓ Virtual environment already exists`n" -ForegroundColor Green
}

# Install Python dependencies
Write-Host "Installing Python dependencies..." -ForegroundColor Cyan
.\.venv\Scripts\python.exe -m pip install --upgrade pip --quiet
.\.venv\Scripts\python.exe -m pip install -e . --quiet
Write-Host "✓ Python dependencies installed`n" -ForegroundColor Green

# Check Node.js
Write-Host "Checking Node.js..." -ForegroundColor Cyan
$nodeVersion = & node --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "WARNING: Node.js not found. Web UI will not build." -ForegroundColor Yellow
    Write-Host "Install Node.js 18+ from https://nodejs.org`n" -ForegroundColor Yellow
} else {
    Write-Host "✓ Found: $nodeVersion`n" -ForegroundColor Green
    
    # Install frontend dependencies
    Write-Host "Installing frontend dependencies..." -ForegroundColor Cyan
    cd web
    npm install --silent
    Write-Host "✓ Frontend dependencies installed`n" -ForegroundColor Green
    
    # Build frontend
    Write-Host "Building frontend..." -ForegroundColor Cyan
    npm run build --silent
    Write-Host "✓ Frontend built`n" -ForegroundColor Green
    cd ..
}

# Create .env if missing
if (-not (Test-Path ".env")) {
    Write-Host "Creating .env file..." -ForegroundColor Cyan
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
    } else {
        @"
# JobApply Environment Configuration
SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(32))')
DATABASE_URL=sqlite:///./jobapply_dev.db
RESEND_API_KEY=
"@ | Out-File -FilePath ".env" -Encoding UTF8
    }
    Write-Host "✓ .env file created`n" -ForegroundColor Green
} else {
    Write-Host "✓ .env file already exists`n" -ForegroundColor Green
}

Write-Host "==============`n" -ForegroundColor Green
Write-Host "Setup complete! Run './start.ps1' to start the server." -ForegroundColor Green
