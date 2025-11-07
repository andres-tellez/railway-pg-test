# Local Development Startup Script
# This script ensures a clean local development environment

Write-Host "🚀 Starting Local Development Environment..." -ForegroundColor Green

# Clear any Railway environment variables that might interfere
Write-Host "🧹 Cleaning Railway environment variables..." -ForegroundColor Yellow
Remove-Item Env:PORT -ErrorAction SilentlyContinue
Remove-Item Env:RAILWAY_* -ErrorAction SilentlyContinue

# Verify certificates exist
$certFile = "localhost.pem"
$keyFile = "localhost-key.pem"

if (-not (Test-Path $certFile) -or -not (Test-Path $keyFile)) {
    Write-Host "⚠️  HTTPS certificates not found. Running certificate setup..." -ForegroundColor Yellow
    powershell -ExecutionPolicy Bypass -File .\setup_https_certificates.ps1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Certificate setup failed!" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "✅ HTTPS certificates found" -ForegroundColor Green
}

# Verify port 5000 is available
Write-Host "🔍 Checking if port 5000 is available..." -ForegroundColor Yellow
$portCheck = Get-NetTCPConnection -LocalPort 5000 -ErrorAction SilentlyContinue
if ($portCheck) {
    Write-Host "⚠️  Port 5000 is in use. Attempting to free it..." -ForegroundColor Yellow
    Get-Process | Where-Object {$_.ProcessName -eq "python"} | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}

# Start the backend
Write-Host "🚀 Starting backend on https://localhost:5000..." -ForegroundColor Green
python run.py
