param(
    [Parameter(Mandatory = $false)]
    [ValidateSet("local", "cloudrun", "prod")]
    [string]$Target = "cloudrun",

    [string]$ImageName = "obol:local",
    [string]$ContainerName = "obol-local",
    [int]$Port = 8080,

    [string]$Project = "gnosis-459403",
    [string]$Region = "us-central1",
    [string]$Service = "obol",
    [string]$GcsBucket = "gnosis-459403-obol",

    [switch]$Force
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

function Require-Command {
    param([string]$Name)

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command not found: $Name"
    }
}

function Test-Http {
    param(
        [string]$Url,
        [int[]]$AllowedStatus = @(200)
    )

    Require-Command "curl.exe"

    $status = & curl.exe -sS -o NUL -w "%{http_code}" --max-time 15 $Url
    if ($LASTEXITCODE -ne 0) {
        throw "curl failed for $Url"
    }

    $statusCode = [int]$status
    if ($AllowedStatus -notcontains $statusCode) {
        throw "Unexpected status for $Url`: $statusCode"
    }

    Write-Host "$statusCode $Url"
}

if ($Target -eq "local") {
    Require-Command "docker"

    Write-Host "Building local Docker image: $ImageName"
    docker build -t $ImageName .

    Write-Host "Replacing local container: $ContainerName"
    docker rm -f $ContainerName 2>$null | Out-Null
    docker run -d --name $ContainerName -p "${Port}:8080" $ImageName | Out-Null

    Start-Sleep -Seconds 2

    docker ps --filter "name=$ContainerName" --format "table {{.Names}}\t{{.Image}}\t{{.Ports}}"

    $BaseUrl = "http://localhost:$Port"
    Test-Http "$BaseUrl/health"
    Test-Http "$BaseUrl/.well-known/ahp.json"
    Test-Http "$BaseUrl/tools"

    Write-Host "Local Obol service is running at $BaseUrl"
    exit 0
}

if ($Target -eq "cloudrun" -or $Target -eq "prod") {
    Require-Command "gcloud"
    Require-Command "git"

    $sha = (git rev-parse --short HEAD).Trim()
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($sha)) {
        throw "git rev-parse failed — not a repo, or no commits yet."
    }

    # Check / Ensure GCS Bucket exists
    Write-Host "Checking GCS bucket gs://$GcsBucket..." -ForegroundColor Cyan
    $bucketExists = & gcloud storage buckets list --project=$Project --filter="name=$GcsBucket" --format="value(name)" 2>$null
    if (-not $bucketExists) {
        Write-Host "Creating GCS bucket gs://$GcsBucket in region $Region..." -ForegroundColor Yellow
        & gcloud storage buckets create "gs://$GcsBucket" --project=$Project --location=$Region --uniform-bucket-level-access
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Could not create bucket $GcsBucket; will continue with Cloud Run deploy."
        } else {
            Write-Host "GCS bucket created successfully." -ForegroundColor Green
        }
    } else {
        Write-Host "GCS bucket gs://$GcsBucket exists." -ForegroundColor Green
    }

    # Fast no-op check
    if (-not $Force) {
        $envOut = & gcloud run services describe $Service `
            --region=$Region --project=$Project `
            --format="value(spec.template.spec.containers[0].env)" 2>$null
        if ($envOut -match "DEPLOYED_SHA[^,}]*$sha") {
            Write-Host "Already up to date at $sha — skipping deploy." -ForegroundColor Green
            Write-Host "(Pass -Force to deploy anyway.)" -ForegroundColor DarkGray
            exit 0
        }
    }

    Write-Host "Deploying $Service @ $sha to Cloud Run project=$Project region=$Region..." -ForegroundColor Cyan
    & gcloud run deploy $Service `
        --source . `
        --region $Region `
        --project $Project `
        --allow-unauthenticated `
        --port 8080 `
        --set-env-vars "AUTH_SERVICE_URL=https://auth.nuts.services,JWKS_URL=https://auth.nuts.services/.well-known/jwks.json,GCS_BUCKET_NAME=$GcsBucket,GCP_PROJECT=$Project,ENVIRONMENT=production,HOST=0.0.0.0,DISABLE_AUTH=false,DEPLOYED_SHA=$sha"

    Write-Host "Checking Cloud Run revision status..." -ForegroundColor Cyan
    $serviceUrl = & gcloud run services describe $Service `
        --region $Region `
        --project $Project `
        --format "value(status.url)"

    Write-Host "Service live URL: $serviceUrl" -ForegroundColor Green

    Test-Http "$serviceUrl/health"
    Test-Http "$serviceUrl/.well-known/ahp.json"
    Test-Http "$serviceUrl/tools"

    Write-Host "Obol Cloud Run deployment complete: $serviceUrl" -ForegroundColor Green
    exit 0
}
