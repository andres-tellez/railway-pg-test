# Quick guide to get Railway DATABASE_URL

## Option 1: Railway CLI (Recommended)

```bash
# Install Railway CLI if not already installed
npm i -g @railway/cli

# Login to Railway
railway login

# Get DATABASE_URL
railway variables --service <your-service-name>

# Or get all variables as JSON
railway variables --json | grep DATABASE_URL
```

## Option 2: Railway Dashboard

1. Go to https://railway.app
2. Select your project
3. Select your database service
4. Go to "Variables" tab
5. Copy the `DATABASE_URL` value

## Option 3: Use the script

```bash
# The script will automatically fetch from Railway
python diagnose_railway_prod.py andres.tellez@gmail.com
```

## Option 4: Manual export

```bash
# Copy DATABASE_URL from Railway dashboard and export it
export PROD_DATABASE_URL="postgres://user:pass@host:port/dbname"

# Then run diagnostic
python diagnose_missing_activity.py andres.tellez@gmail.com
```

## Option 5: Direct SQL queries (Easiest!)

Since you're already in the production database browser, just run the SQL queries directly:

See: `production_diagnostic_347085.sql`
