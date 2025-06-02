# Squeezelite Multi-Room Docker Management Script for Windows
# PowerShell version

param(
    [Parameter(Position=0)]
    [string]$Command = "help",
    [Parameter(Position=1)]
    [string]$ServiceName = ""
)

# Get script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

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

# Check if Docker and Docker Compose are available
function Test-Dependencies {
    Write-Status "Checking dependencies..."
    
    try {
        $dockerVersion = docker --version 2>$null
        if (-not $dockerVersion) {
            Write-Error "Docker is not installed or not in PATH"
            Write-Status "Please install Docker Desktop from https://www.docker.com/products/docker-desktop"
            exit 1
        }
    }
    catch {
        Write-Error "Docker is not installed or not in PATH"
        Write-Status "Please install Docker Desktop from https://www.docker.com/products/docker-desktop"
        exit 1
    }
    
    try {
        $composeVersion = docker-compose --version 2>$null
        if (-not $composeVersion) {
            Write-Error "Docker Compose is not available"
            Write-Status "Please ensure Docker Desktop is properly installed"
            exit 1
        }
    }
    catch {
        Write-Error "Docker Compose is not available"
        Write-Status "Please ensure Docker Desktop is properly installed"
        exit 1
    }
    
    Write-Success "Docker and Docker Compose are available"
    Write-Status "Docker version: $dockerVersion"
    Write-Status "Docker Compose version: $composeVersion"
}

# Create necessary directories
function New-ProjectDirectories {
    Write-Status "Creating necessary directories..."
    
    if (-not (Test-Path "config")) {
        New-Item -ItemType Directory -Path "config" -Force | Out-Null
    }
    
    if (-not (Test-Path "logs")) {
        New-Item -ItemType Directory -Path "logs" -Force | Out-Null
    }
    
    Write-Success "Directories created"
}

# Check Docker Desktop status
function Test-DockerStatus {
    Write-Status "Checking Docker Desktop status..."
    
    try {
        $dockerInfo = docker info 2>$null
        if (-not $dockerInfo) {
            Write-Warning "Docker Desktop may not be running"
            Write-Status "Please start Docker Desktop and try again"
            return $false
        }
        Write-Success "Docker Desktop is running"
        return $true
    }
    catch {
        Write-Warning "Docker Desktop may not be running"
        Write-Status "Please start Docker Desktop and try again"
        return $false
    }
}

# Windows audio device information
function Show-WindowsAudioInfo {
    Write-Status "Windows Audio Device Information:"
    Write-Warning "Note: This container is designed for Linux audio systems"
    Write-Status "For Windows hosts:"
    Write-Status "1. Audio device passthrough works differently on Windows"
    Write-Status "2. Consider using WSL2 for better Linux compatibility"
    Write-Status "3. Docker Desktop on Windows has limitations with audio devices"
    Write-Status "4. You may need to use network audio streaming instead"
    
    # Try to show Windows audio devices for reference
    try {
        Write-Status "Windows audio devices (for reference):"
        Get-WmiObject -Class Win32_SoundDevice | Select-Object Name, Status | Format-Table -AutoSize
    }
    catch {
        Write-Warning "Could not enumerate Windows audio devices"
    }
}

# Build the Docker image
function Start-Build {
    param(
        [string]$DockerfilePath = "Dockerfile"
    )
    
    Write-Status "Building Squeezelite Multi-Room Docker image (no cache)..."
    
    if (-not (Test-DockerStatus)) {
        exit 1
    }
    
    # Try building with specified Dockerfile
    Write-Status "Using $DockerfilePath for build"
    docker build -f $DockerfilePath -t squeezelite-multiroom --no-cache .
    
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Build completed successfully"
        return $true
    }
    else {
        Write-Error "Build failed with exit code $LASTEXITCODE"
        
        # If main Dockerfile failed, suggest alternatives
        if ($DockerfilePath -eq "Dockerfile") {
            Write-Warning "Main Dockerfile build failed. This is common on Windows due to network/package issues."
            Write-Status "Available alternatives:"
            Write-Status "1. Try minimal build: .\manage.ps1 build-minimal"
            Write-Status "2. See troubleshooting guide: WINDOWS-BUILD-TROUBLESHOOTING.md"
            Write-Status "3. Check Docker Desktop network settings"
            Write-Status "4. Try: .\manage.ps1 build-debug for step-by-step diagnosis"
            return $false
        }
        return $false
    }
}

# Build with minimal Dockerfile
function Start-MinimalBuild {
    Write-Status "Building with minimal Dockerfile (reduced dependencies, no cache)..."
    
    if (-not (Test-Path "Dockerfile.minimal")) {
        Write-Error "Dockerfile.minimal not found. Please ensure it exists in the project directory."
        exit 1
    }
    
    $result = Start-Build -DockerfilePath "Dockerfile.minimal"
    if ($result) {
        Write-Success "Minimal build completed successfully"
        Write-Status "Note: This build may have limited audio capabilities but will work for testing"
    }
    else {
        Write-Error "Even minimal build failed. Please check Docker Desktop configuration."
        Write-Status "See WINDOWS-BUILD-TROUBLESHOOTING.md for detailed solutions"
        exit 1
    }
}

# Debug build process
function Start-BuildDebug {
    Write-Status "Running build diagnosis..."
    
    if (-not (Test-DockerStatus)) {
        exit 1
    }
    
    Write-Status "Testing basic Docker functionality..."
    
    # Test basic Docker operations
    Write-Status "Testing hello-world container..."
    docker run --rm hello-world
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Basic Docker operations failed. Please check Docker Desktop installation."
        return
    }
    
    # Test Ubuntu base image
    Write-Status "Testing Ubuntu base image..."
    docker run --rm ubuntu:22.04 echo "Ubuntu test successful"
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Ubuntu base image failed. Check Docker Desktop network connectivity."
        return
    }
    
    # Test package installation
    Write-Status "Testing package installation in Ubuntu..."
    docker run --rm ubuntu:22.04 bash -c "apt-get update && apt-get install -y curl"
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Package installation failed. This is likely a network connectivity issue."
        Write-Status "Solutions:"
        Write-Status "1. Check Docker Desktop DNS settings (try 8.8.8.8, 8.8.4.4)"
        Write-Status "2. Reset Docker Desktop to factory defaults"
        Write-Status "3. Check Windows firewall/antivirus settings"
        Write-Status "4. See WINDOWS-BUILD-TROUBLESHOOTING.md for more solutions"
        return
    }
    
    Write-Success "Docker diagnostics completed successfully"
    Write-Status "Your Docker setup appears to be working. Try building again:"
    Write-Status ".\manage.ps1 build"
}

# Start the services
function Start-Services {
    Write-Status "Starting Squeezelite Multi-Room services..."
    
    if (-not (Test-DockerStatus)) {
        exit 1
    }
    
    docker-compose up -d
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Services started successfully"
        
        # Wait for services to initialize
        Start-Sleep -Seconds 3
        
        # Check if services are running
        $runningServices = docker-compose ps --services --filter "status=running"
        if ($runningServices) {
            Write-Success "Services are running successfully"
            Write-Status "Web interface available at: http://localhost:8080"
            Write-Status "Use 'manage.ps1 logs' to view real-time logs"
        }
        else {
            Write-Error "Services failed to start properly"
            Write-Status "Check logs with: .\manage.ps1 logs"
            exit 1
        }
    }
    else {
        Write-Error "Failed to start services"
        exit 1
    }
}

# Stop the services
function Stop-Services {
    Write-Status "Stopping Squeezelite Multi-Room services..."
    docker-compose down
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Services stopped successfully"
    }
    else {
        Write-Warning "Some issues occurred while stopping services"
    }
}

# Restart the services
function Restart-Services {
    Write-Status "Restarting Squeezelite Multi-Room services..."
    Stop-Services
    Start-Services
}

# Show logs
function Show-Logs {
    if ($ServiceName) {
        docker-compose logs -f $ServiceName
    }
    else {
        docker-compose logs -f
    }
}

# Show status
function Show-Status {
    Write-Status "Service status:"
    docker-compose ps
    
    Write-Status ""
    Write-Status "Container information:"
    docker-compose ps --format "table {{.Name}}\t{{.State}}\t{{.Status}}"
    
    if (Test-Path "logs") {
        Write-Status ""
        Write-Status "Available log files:"
        Get-ChildItem "logs" -File | Format-Table Name, Length, LastWriteTime -AutoSize
    }
    else {
        Write-Warning "No logs directory found"
    }
}

# Clean up
function Remove-All {
    Write-Warning "This will remove all containers, images, and data."
    $response = Read-Host "Are you sure? (y/N)"
    
    if ($response -match "^[Yy]$") {
        Write-Status "Cleaning up..."
        docker-compose down -v --rmi all
        docker system prune -f
        Write-Success "Cleanup completed"
    }
    else {
        Write-Status "Cleanup cancelled"
    }
}

# Development mode
function Start-Development {
    Write-Status "Starting in development mode (no cache build)..."
    $env:COMPOSE_FILE = "docker-compose.yml;docker-compose.dev.yml"
    docker-compose up --build --no-cache
}

# Start services in no-audio mode
function Start-NoAudioServices {
    Write-Status "Starting Squeezelite Multi-Room services (no audio devices)..."
    
    if (-not (Test-DockerStatus)) {
        exit 1
    }
    
    Write-Status "Using no-audio configuration - virtual/null devices only"
    $env:COMPOSE_FILE = "docker-compose.no-audio.yml"
    docker-compose up -d
    
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Services started successfully in no-audio mode"
        
        # Wait for services to initialize
        Start-Sleep -Seconds 3
        
        Write-Success "Services are running in no-audio mode"
        Write-Status "Web interface available at: http://localhost:8080"
        Write-Status "Note: Only virtual audio devices (null, default) will be available"
        Write-Status "Use 'manage.ps1 logs' to view real-time logs"
    }
    else {
        Write-Error "Failed to start services in no-audio mode"
        exit 1
    }
}

# Update
function Update-Project {
    Write-Status "Updating Squeezelite Multi-Room..."
    
    # Check if git is available and this is a git repository
    try {
        git pull 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Git pull completed"
        }
        else {
            Write-Warning "Git pull failed or not a git repository"
        }
    }
    catch {
        Write-Warning "Git not available or not a git repository"
    }
    
    Start-Build
    Restart-Services
    Write-Success "Update completed"
}

# Show help
function Show-Help {
    Write-Host ""
    Write-Host "Squeezelite Multi-Room Docker Management Script (Windows)" -ForegroundColor Cyan
    Write-Host "PowerShell version" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Usage: .\manage.ps1 [COMMAND] [SERVICE]" -ForegroundColor White
    Write-Host ""
    Write-Host "Commands:" -ForegroundColor Yellow
    Write-Host "  build        Build the Docker image"
    Write-Host "  build-minimal Build with minimal dependencies (Windows fallback)"
    Write-Host "  build-debug  Diagnose Docker build issues"
    Write-Host "  start        Start the services"
    Write-Host "  stop         Stop the services"
    Write-Host "  restart      Restart the services"
    Write-Host "  status       Show service status"
    Write-Host "  logs         Show logs (optionally specify service name)"
    Write-Host "  clean        Clean up all containers and images"
    Write-Host "  dev          Start in development mode"
    Write-Host "  no-audio     Start without audio devices (testing/dev)"
    Write-Host "  update       Update and restart services"
    Write-Host "  setup        Initial setup and checks"
    Write-Host "  help         Show this help message"
    Write-Host ""
    Write-Host "Examples:" -ForegroundColor Green
    Write-Host "  .\manage.ps1 build                   # Build Docker image"
    Write-Host "  .\manage.ps1 build-minimal           # Build with minimal dependencies"
    Write-Host "  .\manage.ps1 build-debug             # Diagnose build issues"
    Write-Host "  .\manage.ps1 start                   # Start all services"
    Write-Host "  .\manage.ps1 no-audio                # Start without audio devices"
    Write-Host "  .\manage.ps1 logs squeezelite-web    # Show web service logs"
    Write-Host "  .\manage.ps1 restart                 # Restart all services"
    Write-Host ""
    Write-Host "Windows Build Troubleshooting:" -ForegroundColor Yellow
    Write-Host "- If 'build' fails with exit code 100, try 'build-minimal'"
    Write-Host "- Use 'build-debug' to diagnose Docker connectivity issues"
    Write-Host "- Check Docker Desktop DNS settings (try 8.8.8.8, 8.8.4.4)"
    Write-Host "- See WINDOWS-BUILD-TROUBLESHOOTING.md for detailed solutions"
    Write-Host "- Temporarily disable antivirus during build if needed"
    Write-Host ""
    Write-Host "Windows Notes:" -ForegroundColor Yellow
    Write-Host "- Ensure Docker Desktop is running before using commands"
    Write-Host "- Audio device passthrough is limited on Windows"
    Write-Host "- Consider using WSL2 for better Linux compatibility"
    Write-Host "- Run PowerShell as Administrator if you encounter permission issues"
}

# Check execution policy
function Test-ExecutionPolicy {
    $policy = Get-ExecutionPolicy
    if ($policy -eq "Restricted") {
        Write-Warning "PowerShell execution policy is restricted"
        Write-Status "Run this command to allow script execution:"
        Write-Status "Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser"
        return $false
    }
    return $true
}

# Main script logic
function Invoke-Main {
    # Check execution policy first
    if (-not (Test-ExecutionPolicy)) {
        exit 1
    }
    
    switch ($Command.ToLower()) {
        "build" {
            Test-Dependencies
            New-ProjectDirectories
            Start-Build
        }
        "build-minimal" {
            Test-Dependencies
            New-ProjectDirectories
            Start-MinimalBuild
        }
        "build-debug" {
            Test-Dependencies
            New-ProjectDirectories
            Start-BuildDebug
        }
        "start" {
            Test-Dependencies
            New-ProjectDirectories
            Start-Services
        }
        "stop" {
            Stop-Services
        }
        "restart" {
            Restart-Services
        }
        "status" {
            Show-Status
        }
        "logs" {
            Show-Logs
        }
        "clean" {
            Remove-All
        }
        "dev" {
            Test-Dependencies
            New-ProjectDirectories
            Start-Development
        }
        "no-audio" {
            Test-Dependencies
            New-ProjectDirectories
            Start-NoAudioServices
        }
        "update" {
            Update-Project
        }
        "setup" {
            Test-Dependencies
            New-ProjectDirectories
            Show-WindowsAudioInfo
            Write-Success "Setup completed. Run '.\manage.ps1 build' to build the image."
        }
        "help" {
            Show-Help
        }
        default {
            Write-Error "Unknown command: $Command"
            Show-Help
            exit 1
        }
    }
}

# Run main function
Invoke-Main
