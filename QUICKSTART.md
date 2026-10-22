# JobApply Quick Start

## Prerequisites
- **Python 3.11+** — [Download here](https://www.python.org/downloads/)
- **Node.js 18+** (for web UI) — [Download here](https://nodejs.org/)

## Installation (One Time)

```powershell
cd d:\switch-learning\jobapply
./setup.ps1
```

## Running the App

```powershell
./start.ps1
```

Then open: **http://localhost:8000**

## First Time Setup

1. **Create an account** at http://localhost:8000/register
2. **Verify email** — the link prints in the terminal (or add RESEND_API_KEY to `.env` for real emails)
3. **Upload your resume** — click "Upload resume" button on dashboard
4. **Search for jobs** — enter job titles and click Search

## Commands Summary

| Command | What it does |
|---------|-------------|
| `./setup.ps1` | One-time installation (run once) |
| `./start.ps1` | Start the server |
| `Ctrl+C` | Stop the server |

## Getting Real Emails

1. Go to [resend.com/signup](https://resend.com/signup) (free, no card)
2. Get your API key (starts with `re_`)
3. Open `.env` and set: `RESEND_API_KEY=re_your_key_here`
4. Restart server (`Ctrl+C` then `./start.ps1`)

## Troubleshooting

**"Python not found"**
```powershell
# Add Python to PATH, then restart PowerShell
```

**"Module not found"**
```powershell
# Reinstall dependencies
.\.venv\Scripts\python.exe -m pip install -e .
```

**"Port 8000 already in use"**
```powershell
# Find and kill the process
Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess | Stop-Process
```

## What's Next?

- Configure AI providers in `jobapply.toml`
- Customize job boards in `jobapply.toml`
- Check full docs in `README.md`
