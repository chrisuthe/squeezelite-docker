@echo off
REM Comprehensive Squeezelite Docker Build Script
REM This script ensures clean builds with no cache and proper line endings

setlocal enabledelayedexpansion

echo ======================================================================
echo Squeezelite Multi-Room Docker - Clean Build Script
echo ======================================================================
echo.

REM Colors for output
set "COLOR_INFO=[94m"
set "COLOR_SUCCESS=[92m"
set "COLOR_WARNING=[93m"
set "COLOR_ERROR=[91m"
set "COLOR_RESET=[0m"

REM Check for Docker
echo %COLOR_INFO%[INFO]%COLOR_RESET% Checking Docker availability...
docker --version >nul 2>&1
if errorlevel 1 (
    echo %COLOR_ERROR%[ERROR]%COLOR_RESET% Docker is not available
    echo Please ensure Docker Desktop is running
    pause
    exit /b 1
)

docker-compose --version >nul 2>&1
if errorlevel 1 (
    echo %COLOR_ERROR%[ERROR]%COLOR_RESET% Docker Compose is not available
    echo Please ensure Docker Desktop is running
    pause
    exit /b 1
)

echo %COLOR_SUCCESS%[SUCCESS]%COLOR_RESET% Docker is available

REM Fix line endings in entrypoint script
echo.
echo %COLOR_INFO%[INFO]%COLOR_RESET% Fixing line endings in entrypoint.sh...
if exist "entrypoint.sh" (
    powershell -Command "(Get-Content entrypoint.sh -Raw) -replace \"`r`n\", \"`n\" | Set-Content entrypoint.sh -Encoding UTF8 -NoNewline"
    echo %COLOR_SUCCESS%[SUCCESS]%COLOR_RESET% Line endings fixed
) else (
    echo %COLOR_WARNING%[WARNING]%COLOR_RESET% entrypoint.sh not found
)

REM Stop any running containers
echo.
echo %COLOR_INFO%[INFO]%COLOR_RESET% Stopping any running containers...
docker-compose -f docker-compose.no-audio.yml down 2>nul
docker-compose down 2>nul

REM Clean up old images and containers
echo %COLOR_INFO%[INFO]%COLOR_RESET% Cleaning up old images and containers...
docker system prune -f 2>nul

REM Build with no cache
echo.
echo %COLOR_INFO%[INFO]%COLOR_RESET% Building Docker image with no cache...
echo This may take several minutes...
echo.

REM Determine which docker-compose file to use
set "COMPOSE_FILE=docker-compose.no-audio.yml"
if "%1"=="full" set "COMPOSE_FILE=docker-compose.yml"
if "%1"=="dev" set "COMPOSE_FILE=docker-compose.dev.yml"

echo %COLOR_INFO%[INFO]%COLOR_RESET% Using compose file: %COMPOSE_FILE%

docker-compose -f %COMPOSE_FILE% build --no-cache
if errorlevel 1 (
    echo.
    echo %COLOR_ERROR%[ERROR]%COLOR_RESET% Build failed!
    echo.
    echo Common solutions:
    echo 1. Check Docker Desktop is running and has enough resources
    echo 2. Check internet connectivity for package downloads
    echo 3. Try running as Administrator
    echo 4. Reset Docker Desktop to factory defaults if issues persist
    echo.
    pause
    exit /b 1
)

echo.
echo %COLOR_SUCCESS%[SUCCESS]%COLOR_RESET% Build completed successfully!

REM Start the container
echo.
echo %COLOR_INFO%[INFO]%COLOR_RESET% Starting container...
docker-compose -f %COMPOSE_FILE% up -d

if errorlevel 1 (
    echo %COLOR_ERROR%[ERROR]%COLOR_RESET% Failed to start container
    echo Check logs with: docker-compose -f %COMPOSE_FILE% logs
    pause
    exit /b 1
)

echo.
echo %COLOR_SUCCESS%[SUCCESS]%COLOR_RESET% Container started successfully!
echo.
echo %COLOR_INFO%[INFO]%COLOR_RESET% Web interface will be available at: http://localhost:8080
echo %COLOR_INFO%[INFO]%COLOR_RESET% Use 'docker-compose -f %COMPOSE_FILE% logs -f' to view logs
echo.

REM Show container status
echo %COLOR_INFO%[INFO]%COLOR_RESET% Container status:
docker-compose -f %COMPOSE_FILE% ps

echo.
echo ======================================================================
echo Build and start completed!
echo ======================================================================
echo.
echo Usage for different modes:
echo   build-clean.bat          - Build no-audio version (default)
echo   build-clean.bat full     - Build full version with audio
echo   build-clean.bat dev      - Build development version
echo.
pause
