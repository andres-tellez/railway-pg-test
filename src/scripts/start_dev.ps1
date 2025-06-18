# Kill any previous ngrok or Python processes
Get-Process ngrok, python -ErrorAction SilentlyContinue | Stop-Process -Force

# Start ngrok in the background
Start-Process -FilePath "$env:USERPROFILE\OneDrive\Desktop\ngrok.exe" -ArgumentList "http 8080" -WindowStyle Hidden

# Wait for ngrok to be ready
Write-Host "⏳ Waiting for ngrok..."
$ngrokUrl = $null
for ($i = 0; $i -lt 10; $i++) {
    Start-Sleep -Seconds 1
    try {
        $response = Invoke-RestMethod -Uri "http://127.0.0.1:4040/api/tunnels"
        $ngrokUrl = $response.tunnels[0].public_url
        break
    } catch {}
}

if (-not $ngrokUrl) {
    Write-Host "❌ Ngrok failed to start. Check ngrok.exe path or network."
    exit 1
}

# Update .env with new redirect URI
(Get-Content .env) -replace 'STRAVA_REDIRECT_URI=.*', "STRAVA_REDIRECT_URI=$ngrokUrl/auth/callback" | Set-Content .env
Write-Host "`n🌍 Ngrok URL: $ngrokUrl"
Write-Host "✅ .env updated"

# Start Flask app
python run.py
