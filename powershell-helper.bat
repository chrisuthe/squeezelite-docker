@echo off
REM Windows PowerShell Execution Policy Helper
REM This batch file helps users run PowerShell scripts when execution policy is restricted

echo Squeezelite Multi-Room Docker - PowerShell Helper
echo.

REM Check if PowerShell is available
powershell -Command "Write-Host 'PowerShell is available'" >nul 2>&1
if errorlevel 1 (
    echo ERROR: PowerShell is not available on this system
    echo Please use manage.bat instead
    pause
    exit /b 1
)

REM Check current execution policy
echo Checking PowerShell execution policy...
for /f "tokens=*" %%i in ('powershell -Command "Get-ExecutionPolicy"') do set "POLICY=%%i"
echo Current policy: %POLICY%

if "%POLICY%"=="Restricted" (
    echo.
    echo WARNING: PowerShell execution policy is restricted
    echo This will prevent running manage.ps1 script
    echo.
    echo Options:
    echo 1. Change execution policy (recommended)
    echo 2. Run with bypass (one-time)
    echo 3. Use batch file instead
    echo.
    set /p "choice=Choose option (1-3): "
    
    if "!choice!"=="1" (
        echo.
        echo Changing execution policy for current user...
        powershell -Command "Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser -Force"
        if errorlevel 1 (
            echo ERROR: Failed to change execution policy
            echo You may need to run this as Administrator
            pause
            exit /b 1
        )
        echo SUCCESS: Execution policy changed
        echo You can now run: .\manage.ps1 setup
    ) else if "!choice!"=="2" (
        echo.
        echo Available commands for bypass:
        echo powershell -ExecutionPolicy Bypass -File .\manage.ps1 setup
        echo powershell -ExecutionPolicy Bypass -File .\manage.ps1 build
        echo powershell -ExecutionPolicy Bypass -File .\manage.ps1 start
    ) else if "!choice!"=="3" (
        echo.
        echo Use these commands instead:
        echo manage.bat setup
        echo manage.bat build
        echo manage.bat start
    ) else (
        echo Invalid choice
    )
) else (
    echo.
    echo PowerShell execution policy allows script execution
    echo You can run: .\manage.ps1 setup
)

echo.
pause
