@echo off
REM Squeezelite Multi-Room Docker Management Script for Windows
REM Batch file version for broader compatibility

setlocal enabledelayedexpansion

REM Get script directory and change to it
cd /d "%~dp0"

REM Colors (limited in batch)
set "COLOR_INFO=[94m"
set "COLOR_SUCCESS=[92m"
set "COLOR_WARNING=[93m"
set "COLOR_ERROR=[91m"
set "COLOR_RESET=[0m"

REM Default command
if "%1"=="" set "COMMAND=help"
if not "%1"=="" set "COMMAND=%1"

goto :%COMMAND% 2>nul || goto :unknown_command

:build
echo %COLOR_INFO%[INFO]%COLOR_RESET% Building Squeezelite Multi-Room Docker image (no cache)...
call :check_dependencies
if errorlevel 1 exit /b 1
call :setup_directories
docker-compose build --no-cache
if errorlevel 1 (
    echo %COLOR_ERROR%[ERROR]%COLOR_RESET% Build failed
    exit /b 1
)
echo %COLOR_SUCCESS%[SUCCESS]%COLOR_RESET% Build completed
goto :eof

:start
echo %COLOR_INFO%[INFO]%COLOR_RESET% Starting Squeezelite Multi-Room services...
call :check_dependencies
if errorlevel 1 exit /b 1
call :setup_directories
call :check_docker_status
if errorlevel 1 exit /b 1
docker-compose up -d
if errorlevel 1 (
    echo %COLOR_ERROR%[ERROR]%COLOR_RESET% Failed to start services
    exit /b 1
)
echo %COLOR_SUCCESS%[SUCCESS]%COLOR_RESET% Services started
echo %COLOR_INFO%[INFO]%COLOR_RESET% Web interface available at: http://localhost:8080
echo %COLOR_INFO%[INFO]%COLOR_RESET% Use 'manage.bat logs' to view logs
goto :eof

:stop
echo %COLOR_INFO%[INFO]%COLOR_RESET% Stopping Squeezelite Multi-Room services...
docker-compose down
if errorlevel 1 (
    echo %COLOR_WARNING%[WARNING]%COLOR_RESET% Some issues occurred while stopping
) else (
    echo %COLOR_SUCCESS%[SUCCESS]%COLOR_RESET% Services stopped
)
goto :eof

:restart
echo %COLOR_INFO%[INFO]%COLOR_RESET% Restarting Squeezelite Multi-Room services...
call :stop
call :start
goto :eof

:status
echo %COLOR_INFO%[INFO]%COLOR_RESET% Service status:
docker-compose ps
echo.
if exist "logs" (
    echo %COLOR_INFO%[INFO]%COLOR_RESET% Log files:
    dir /b logs
) else (
    echo %COLOR_WARNING%[WARNING]%COLOR_RESET% No logs directory found
)
goto :eof

:logs
if "%2"=="" (
    docker-compose logs -f
) else (
    docker-compose logs -f %2
)
goto :eof

:clean
echo %COLOR_WARNING%[WARNING]%COLOR_RESET% This will remove all containers, images, and data.
set /p "response=Are you sure? (y/N): "
if /i "!response!"=="y" (
    echo %COLOR_INFO%[INFO]%COLOR_RESET% Cleaning up...
    docker-compose down -v --rmi all
    docker system prune -f
    echo %COLOR_SUCCESS%[SUCCESS]%COLOR_RESET% Cleanup completed
) else (
    echo %COLOR_INFO%[INFO]%COLOR_RESET% Cleanup cancelled
)
goto :eof

:dev
echo %COLOR_INFO%[INFO]%COLOR_RESET% Starting in development mode (no cache build)...
call :check_dependencies
if errorlevel 1 exit /b 1
call :setup_directories
set COMPOSE_FILE=docker-compose.yml;docker-compose.dev.yml
docker-compose up --build --no-cache
goto :eof

:no-audio
echo %COLOR_INFO%[INFO]%COLOR_RESET% Starting in no-audio mode (virtual devices only)...
call :check_dependencies
if errorlevel 1 exit /b 1
call :setup_directories
call :check_docker_status
if errorlevel 1 exit /b 1
set COMPOSE_FILE=docker-compose.no-audio.yml
docker-compose up -d
if errorlevel 1 (
    echo %COLOR_ERROR%[ERROR]%COLOR_RESET% Failed to start services in no-audio mode
    exit /b 1
)
echo %COLOR_SUCCESS%[SUCCESS]%COLOR_RESET% Services started in no-audio mode
echo %COLOR_INFO%[INFO]%COLOR_RESET% Web interface available at: http://localhost:8080
echo %COLOR_INFO%[INFO]%COLOR_RESET% Note: Only virtual audio devices will be available
goto :eof

:update
echo %COLOR_INFO%[INFO]%COLOR_RESET% Updating Squeezelite Multi-Room...
git pull >nul 2>&1
if errorlevel 1 (
    echo %COLOR_WARNING%[WARNING]%COLOR_RESET% Git pull failed or not a git repository
)
call :build
call :restart
echo %COLOR_SUCCESS%[SUCCESS]%COLOR_RESET% Update completed
goto :eof

:setup
echo %COLOR_INFO%[INFO]%COLOR_RESET% Running initial setup...
call :check_dependencies
if errorlevel 1 exit /b 1
call :setup_directories
call :show_windows_audio_info
echo %COLOR_SUCCESS%[SUCCESS]%COLOR_RESET% Setup completed. Run 'manage.bat build' to build the image.
goto :eof

:help
echo.
echo Squeezelite Multi-Room Docker Management Script (Windows)
echo Batch file version
echo.
echo Usage: manage.bat [COMMAND]
echo.
echo Commands:
echo   build     Build the Docker image
echo   start     Start the services
echo   stop      Stop the services
echo   restart   Restart the services
echo   status    Show service status
echo   logs      Show logs (optionally specify service name)
echo   clean     Clean up all containers and images
echo   dev       Start in development mode
echo   no-audio  Start without audio devices (testing/dev)
echo   update    Update and restart services
echo   setup     Initial setup and checks
echo   help      Show this help message
echo.
echo Examples:
echo   manage.bat start                    # Start all services
echo   manage.bat logs squeezelite-web     # Show web service logs
echo   manage.bat restart                  # Restart all services
echo   manage.bat no-audio                 # Start without audio devices
echo.
echo Windows Notes:
echo - Ensure Docker Desktop is running before using commands
echo - Audio device passthrough is limited on Windows
echo - Consider using WSL2 for better Linux compatibility
echo - Run as Administrator if you encounter permission issues
echo - Use 'no-audio' command for testing without audio hardware
echo.
goto :eof

:unknown_command
echo %COLOR_ERROR%[ERROR]%COLOR_RESET% Unknown command: %COMMAND%
call :help
exit /b 1

REM Helper functions

:check_dependencies
echo %COLOR_INFO%[INFO]%COLOR_RESET% Checking dependencies...
docker --version >nul 2>&1
if errorlevel 1 (
    echo %COLOR_ERROR%[ERROR]%COLOR_RESET% Docker is not installed or not in PATH
    echo %COLOR_INFO%[INFO]%COLOR_RESET% Please install Docker Desktop from https://www.docker.com/products/docker-desktop
    exit /b 1
)

docker-compose --version >nul 2>&1
if errorlevel 1 (
    echo %COLOR_ERROR%[ERROR]%COLOR_RESET% Docker Compose is not available
    echo %COLOR_INFO%[INFO]%COLOR_RESET% Please ensure Docker Desktop is properly installed
    exit /b 1
)

echo %COLOR_SUCCESS%[SUCCESS]%COLOR_RESET% Docker and Docker Compose are available
goto :eof

:check_docker_status
echo %COLOR_INFO%[INFO]%COLOR_RESET% Checking Docker Desktop status...
docker info >nul 2>&1
if errorlevel 1 (
    echo %COLOR_WARNING%[WARNING]%COLOR_RESET% Docker Desktop may not be running
    echo %COLOR_INFO%[INFO]%COLOR_RESET% Please start Docker Desktop and try again
    exit /b 1
)
echo %COLOR_SUCCESS%[SUCCESS]%COLOR_RESET% Docker Desktop is running
goto :eof

:setup_directories
echo %COLOR_INFO%[INFO]%COLOR_RESET% Creating necessary directories...
if not exist "config" mkdir config
if not exist "logs" mkdir logs
echo %COLOR_SUCCESS%[SUCCESS]%COLOR_RESET% Directories created
goto :eof

:show_windows_audio_info
echo %COLOR_INFO%[INFO]%COLOR_RESET% Windows Audio Device Information:
echo %COLOR_WARNING%[WARNING]%COLOR_RESET% Note: This container is designed for Linux audio systems
echo %COLOR_INFO%[INFO]%COLOR_RESET% For Windows hosts:
echo %COLOR_INFO%[INFO]%COLOR_RESET% 1. Audio device passthrough works differently on Windows
echo %COLOR_INFO%[INFO]%COLOR_RESET% 2. Consider using WSL2 for better Linux compatibility
echo %COLOR_INFO%[INFO]%COLOR_RESET% 3. Docker Desktop on Windows has limitations with audio devices
echo %COLOR_INFO%[INFO]%COLOR_RESET% 4. You may need to use network audio streaming instead
echo %COLOR_INFO%[INFO]%COLOR_RESET% 5. Use 'manage.bat no-audio' to test without audio hardware
echo.
echo %COLOR_INFO%[INFO]%COLOR_RESET% Windows audio devices (for reference):
wmic sounddev get name,status 2>nul || echo %COLOR_WARNING%[WARNING]%COLOR_RESET% Could not enumerate audio devices
goto :eof
