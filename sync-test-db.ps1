# Set prod and test DB URLs
$prod = "postgresql://postgres:zYJLECRKvHHXtSpQgCTAQGayEjBEjwCk@crossover.proxy.rlwy.net:31069/railway?sslmode=require"
$test = "postgresql://postgres:aMWqwxSwwLVIfIeJMtlhLdcteRMOLiIz@switchyard.proxy.rlwy.net:58403/railway?sslmode=require"

# Step 1: Dump prod DB to SQL
$dumpFile = "prod.sql"
$cleanedFile = "prod.cleaned.sql"

Write-Host "`n📦 Dumping production DB to $dumpFile..."
pg_dump --no-owner --no-acl -f $dumpFile $prod

if ($LASTEXITCODE -ne 0) {
    Write-Error "❌ Dump failed. Aborting."
    exit 1
}

# Step 2: Clean up dump
Write-Host "`n🧹 Removing unsupported SET commands..."
Get-Content $dumpFile | Where-Object { $_ -notmatch "SET (idle|transaction)_timeout" } | Set-Content $cleanedFile

# Step 3: Wipe test DB manually (optional safety)
Write-Host "`n🧨 Dropping existing objects in test DB..."
psql $test -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

# Step 4: Restore cleaned dump
Write-Host "`n🔁 Restoring clean SQL dump into test DB..."
psql $test -f $cleanedFile

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n✅ Test DB successfully synced with production."
} else {
    Write-Error "❌ Restore failed. Review SQL output for issues."
}
