#!/usr/bin/env pwsh
# Start PramaIA Google OAuth2 Service

Write-Host "[*] Starting PramaIA Google OAuth2 Service..." -ForegroundColor Cyan
Write-Host ""

# Check if .env exists
if (-not (Test-Path ".env")) {
    Write-Host "[!] .env file not found!" -ForegroundColor Yellow
    Write-Host "Creating .env from .env.example..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host ""
    Write-Host "[!] IMPORTANT: Edit .env file and configure:" -ForegroundColor Red
    Write-Host "   - GOOGLE_CLIENT_ID" -ForegroundColor Yellow
    Write-Host "   - GOOGLE_CLIENT_SECRET" -ForegroundColor Yellow
    Write-Host "   - ENCRYPTION_KEY (run: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Press any key to continue after editing .env..." -ForegroundColor Cyan
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}

# Check if virtual environment exists
if (-not (Test-Path "venv")) {
    Write-Host "[+] Creating virtual environment..." -ForegroundColor Cyan
    python -m venv venv
}

# Activate virtual environment
Write-Host "[+] Activating virtual environment..." -ForegroundColor Cyan
& .\venv\Scripts\Activate.ps1

# Install dependencies
Write-Host "[+] Installing dependencies..." -ForegroundColor Cyan
pip install -r requirements.txt --quiet

# Create storage directory
if (-not (Test-Path "storage")) {
    New-Item -ItemType Directory -Path "storage" | Out-Null
}

Write-Host ""
Write-Host "[OK] Starting service on port 8085..." -ForegroundColor Green
Write-Host "   - Health: http://localhost:8085/health" -ForegroundColor Gray
Write-Host "   - Docs: http://localhost:8085/docs" -ForegroundColor Gray
Write-Host "   - Authorize: http://localhost:8085/oauth/authorize?userId=USER_ID&service=gmail" -ForegroundColor Gray
Write-Host ""

# Start service
python main.py
