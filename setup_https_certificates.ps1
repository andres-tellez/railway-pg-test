# Setup HTTPS Certificates for Local Development
# This script creates SSL certificates for localhost to enable HTTPS

Write-Host "Setting up HTTPS certificates for local development..." -ForegroundColor Green

# Check if mkcert is installed
try {
    $mkcertVersion = mkcert -version 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ mkcert is already installed: $mkcertVersion" -ForegroundColor Green
    } else {
        throw "mkcert not found"
    }
} catch {
    Write-Host "❌ mkcert is not installed. Installing..." -ForegroundColor Red
    Write-Host "Please install mkcert first:" -ForegroundColor Yellow
    Write-Host "1. Download from: https://github.com/FiloSottile/mkcert/releases" -ForegroundColor Yellow
    Write-Host "2. Or install via Chocolatey: choco install mkcert" -ForegroundColor Yellow
    Write-Host "3. Or install via Scoop: scoop install mkcert" -ForegroundColor Yellow
    exit 1
}

# Install local CA if not already done
Write-Host "Installing local CA..." -ForegroundColor Blue
mkcert -install

# Generate certificates for localhost
Write-Host "Generating SSL certificates for localhost..." -ForegroundColor Blue
mkcert localhost 127.0.0.1 ::1

# Check if certificates were created
if ((Test-Path "localhost+2.pem") -and (Test-Path "localhost+2-key.pem")) {
    Write-Host "✅ Certificates generated successfully!" -ForegroundColor Green

    # Rename to match what run.py expects
    if (Test-Path "localhost.pem") { Remove-Item "localhost.pem" }
    if (Test-Path "localhost-key.pem") { Remove-Item "localhost-key.pem" }

    Rename-Item "localhost+2.pem" "localhost.pem"
    Rename-Item "localhost+2-key.pem" "localhost-key.pem"

    Write-Host "✅ Certificates renamed to localhost.pem and localhost-key.pem" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "1. Restart your backend server: python run.py" -ForegroundColor White
    Write-Host "2. Your backend will now run with HTTPS on https://localhost:5000" -ForegroundColor White
    Write-Host "3. Your frontend should now be able to connect to the backend" -ForegroundColor White
} else {
    Write-Host "❌ Failed to generate certificates" -ForegroundColor Red
    exit 1
}
