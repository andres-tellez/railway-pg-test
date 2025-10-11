# Local Development Setup

## Quick Start
Simply run the backend - it will automatically handle Railway interference:
```powershell
python run.py
```

## Optional: Use the Local Development Script
For extra safety (automatically checks certificates and clears processes):
```powershell
.\start-local.ps1
```

## First Time Setup
If you haven't set up HTTPS certificates yet:
```powershell
.\setup_https_certificates.ps1
```

## Common Issues

### Railway CLI Interference
The backend automatically detects and fixes Railway CLI interference. You'll see:
```
[INFO] Railway CLI detected (PORT=54112) - auto-fixing for local development
[INFO] Cleared Railway environment variables
```

**If you want to completely avoid this:** Unlink Railway CLI
```powershell
railway unlink
```

### SSL Certificate Issues
If you get SSL protocol errors:

1. Run the certificate setup:
   ```powershell
   .\setup_https_certificates.ps1
   ```

2. Restart your browser (to clear certificate cache)

3. Verify certificates exist:
   ```powershell
   ls *.pem
   ```

## Environment Files
- `.env.local` - Local development settings
- `.env.staging` - Staging environment (don't modify)
- `.env.prod` - Production environment (don't modify)

## Port Configuration
- Backend always runs on port 5000 for local development
- Frontend runs on port 5173 (Vite default)
- HTTPS certificates are configured for localhost:5000

## Troubleshooting

### "Socket access forbidden" error
This usually means Railway CLI is setting a conflicting port. Use `.\start-local.ps1` to fix.

### Frontend can't connect to backend
1. Verify backend is running on https://localhost:5000
2. Check browser console for CORS errors
3. Ensure certificates are properly installed

### Certificate errors
1. Re-run `.\setup_https_certificates.ps1`
2. Restart your browser
3. Check that `mkcert` is installed: `mkcert -version`
