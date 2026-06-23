# Smoke-test Cloud Run Celery worker entrypoint locally (requires Docker running).
# Usage: .\scripts\docker-test-cloudrun-worker.ps1
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $RepoRoot

$envFile = Join-Path $RepoRoot ".env"
if (-not (Test-Path $envFile)) {
    Write-Error ".env not found - need REDIS_URL / CELERY_* for Celery to stay up."
}

Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
        $name = $matches[1].Trim()
        $value = $matches[2].Trim()
        if ($name -match '^(REDIS_URL|CELERY_BROKER_URL|CELERY_RESULT_BACKEND|API_KEY_ADMIN_SECRET)$') {
            Set-Item -Path "env:$name" -Value $value
        }
    }
}

foreach ($var in @('REDIS_URL', 'CELERY_BROKER_URL', 'CELERY_RESULT_BACKEND')) {
    if (-not (Get-Item "env:$var" -ErrorAction SilentlyContinue)) {
        Write-Error "Missing $var in .env"
    }
}

Write-Host "Building image..."
docker build -t rag-document-processor:worker-test .

$container = "rag-worker-test-$(Get-Random)"
Write-Host "Starting worker container on http://localhost:18080 ..."
docker run -d --name $container `
    -p 18080:8080 `
    -e PORT=8080 `
    -e ENV=production `
    -e REDIS_URL=$env:REDIS_URL `
    -e CELERY_BROKER_URL=$env:CELERY_BROKER_URL `
    -e CELERY_RESULT_BACKEND=$env:CELERY_RESULT_BACKEND `
    -e API_KEY_ADMIN_SECRET=$env:API_KEY_ADMIN_SECRET `
    rag-document-processor:worker-test `
    sh scripts/cloudrun_celery_worker.sh

try {
    $ok = $false
    for ($i = 1; $i -le 30; $i++) {
        Start-Sleep -Seconds 2
        try {
            $resp = Invoke-WebRequest -Uri "http://localhost:18080/" -UseBasicParsing -TimeoutSec 5
            if ($resp.StatusCode -eq 200 -and $resp.Content -eq "ok") {
                $ok = $true
                Write-Host "Health check passed (HTTP 200, body=ok)"
                break
            }
        } catch {
            Write-Host "  [$i] waiting for health endpoint..."
        }
    }
    if (-not $ok) {
        Write-Host "Container logs:"
        docker logs $container 2>&1 | Select-Object -Last 40
        throw "Health check failed"
    }
    Write-Host "Worker entrypoint OK for Cloud Run."
} finally {
    docker rm -f $container | Out-Null
}
