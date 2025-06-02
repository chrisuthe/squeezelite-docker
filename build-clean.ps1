# Comprehensive Squeezelite Docker Build Script (PowerShell)
# This script ensures clean builds with no cache and proper line endings

param(
    [Parameter(Position=0)]
    [string]$Mode = "no-audio"
)

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "Squeezelite Multi-Room Docker - Clean Build Script (PowerShell)" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""

# Colors for output
function Write-Status {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Blue
}

function Write-Success {
    param([string]$Message)
    Write-Host "[SUCCESS] $Message" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[WARNING] $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

# Check for Docker
Write-Status "Checking Docker availability..."
try {
    $dockerVersion = docker --version 2>$null
    if (-not $dockerVersion) {
        Write-Error "Docker is not available"
        Write-Host "Please ensure Docker Desktop is running"
        Read-Host "Press Enter to exit"
        exit 1
    }
} catch {
    Write-Error "Docker is not available"
    Write-Host "Please ensure Docker Desktop is running"
    Read-Host "Press Enter to exit"
    exit 1
}

try {
    $composeVersion = docker-compose --version 2>$null
    if (-not $composeVersion) {
        Write-Error "Docker Compose is not available"
        Write-Host "Please ensure Docker Desktop is running"
        Read-Host "Press Enter to exit"
        exit 1
    }
} catch {
    Write-Error "Docker Compose is not available"
    Write-Host "Please ensure Docker Desktop is running"
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Success "Docker is available"
Write-Status "Docker version: $dockerVersion"
Write-Status "Docker Compose version: $composeVersion"

# Fix line endings in entrypoint script
Write-Host ""
Write-Status "Fixing line endings in entrypoint.sh..."
if (Test-Path "entrypoint.sh") {
    $content = Get-Content "entrypoint.sh" -Raw
    $content = $content -replace "`r`n", "`n"
    [System.IO.File]::WriteAllText((Resolve-Path "entrypoint.sh"), $content, [System.Text.UTF8Encoding]::new($false))
    Write-Success "Line endings fixed"
} else {
    Write-Warning "entrypoint.sh not found"
}

# Stop any running containers
Write-Host ""
Write-Status "Stopping any running containers..."
docker-compose -f docker-compose.no-audio.yml down 2>$null
docker-compose down 2>$null

# Clean up old images and containers
Write-Status "Cleaning up old images and containers..."
docker system prune -f 2>$null

# Build with no cache
Write-Host ""
Write-Status "Building Docker image with no cache..."
Write-Host "This may take several minutes..." -ForegroundColor Yellow
Write-Host ""

# Determine which docker-compose file to use
$composeFile = switch ($Mode.ToLower()) {
    "full" { "docker-compose.yml" }
    "dev" { "docker-compose.dev.yml" }
    default { "docker-compose.no-audio.yml" }
}

Write-Status "Using compose file: $composeFile"

docker-compose -f $composeFile build --no-cache
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Error "Build failed!"
    Write-Host ""
    Write-Host "Common solutions:" -ForegroundColor Yellow
    Write-Host "1. Check Docker Desktop is running and has enough resources"
    Write-Host "2. Check internet connectivity for package downloads"
    Write-Host "3. Try running PowerShell as Administrator"
    Write-Host "4. Reset Docker Desktop to factory defaults if issues persist"
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Success "Build completed successfully!"

# Start the container
Write-Host ""
Write-Status "Starting container..."
docker-compose -f $composeFile up -d

if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to start container"
    Write-Host "Check logs with: docker-compose -f $composeFile logs"
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Success "Container started successfully!"
Write-Host ""
Write-Status "Web interface will be available at: http://localhost:8080"
Write-Status "Use 'docker-compose -f $composeFile logs -f' to view logs"
Write-Host ""

# Show container status
Write-Status "Container status:"
docker-compose -f $composeFile ps

Write-Host ""
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "Build and start completed!" -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Usage for different modes:" -ForegroundColor Yellow
Write-Host "  .\build-clean.ps1                 - Build no-audio version (default)"
Write-Host "  .\build-clean.ps1 full            - Build full version with audio"
Write-Host "  .\build-clean.ps1 dev             - Build development version"
Write-Host ""
Read-Host "Press Enter to exit"
