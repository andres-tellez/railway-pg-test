param([string]$envName)

$validEnvs = @("local", "staging", "production")

if ($validEnvs -contains $envName) {
    Copy-Item ".env.$envName" -Destination ".env" -Force
    Write-Host "✅ Switched to '$envName' environment"
} else {
    Write-Host "❌ Invalid environment. Use: local, staging, or production"
}
