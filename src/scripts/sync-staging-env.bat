@echo off
echo 📦 Syncing .env.staging to Railway...

:: Check if Railway CLI is installed
where railway >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
  echo ❌ Railway CLI not found. Install it: npm install -g railway
  exit /b 1
)

:: Link to your staging environment
railway link --environment staging

:: Read each line of .env.staging and set via CLI
for /F "usebackq tokens=1* delims==" %%A in ("src\scripts\.env.staging") do (
  echo ➕ Setting %%A...
  railway variables set "%%A" "%%B" --environment staging
)

echo ✅ .env.staging synced to Railway staging environment.
