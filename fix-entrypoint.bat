@echo off
echo Fixing Docker entrypoint line ending issues...
echo.

REM Convert line endings from CRLF to LF using PowerShell
echo Converting entrypoint.sh line endings to Unix format...
powershell -Command "(Get-Content entrypoint.sh -Raw) -replace \"`r`n\", \"`n\" | Set-Content entrypoint.sh -Encoding UTF8 -NoNewline"

echo.
echo Cleaning up any existing containers and images...
docker-compose -f docker-compose.no-audio.yml down 2>nul
docker system prune -f 2>nul

echo.
echo Rebuilding Docker image...
docker-compose -f docker-compose.no-audio.yml build --no-cache

echo.
echo Starting container...
docker-compose -f docker-compose.no-audio.yml up

echo.
echo Done! If you still have issues, try running this script as Administrator.
pause
