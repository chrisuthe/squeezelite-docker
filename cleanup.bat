@echo off
REM Cleanup script to remove fragmented documentation files (Windows)

echo Cleaning up fragmented documentation files...

REM Remove fragmented documentation files
if exist DEBUG-SOLUTION-COMPLETE.md del DEBUG-SOLUTION-COMPLETE.md
if exist DEBUG-STARTUP-ISSUES.md del DEBUG-STARTUP-ISSUES.md
if exist MUSIC-ASSISTANT-UPDATE-COMPLETE.md del MUSIC-ASSISTANT-UPDATE-COMPLETE.md
if exist NO-AUDIO-COMPLETE.md del NO-AUDIO-COMPLETE.md
if exist NO-AUDIO-GUIDE.md del NO-AUDIO-GUIDE.md
if exist QUICK-FIX-WINDOWS.md del QUICK-FIX-WINDOWS.md
if exist QUICKSTART.md del QUICKSTART.md
if exist WINDOWS-BUILD-TROUBLESHOOTING.md del WINDOWS-BUILD-TROUBLESHOOTING.md
if exist WINDOWS-COMPLETE.md del WINDOWS-COMPLETE.md
if exist WINDOWS-SETUP.md del WINDOWS-SETUP.md

echo.
echo ✅ Cleanup complete!
echo 📁 Clean project structure ready for GitHub upload
echo.
echo Essential files remaining:
echo 📄 README.md (comprehensive documentation)
echo 📄 LICENSE
echo 🐳 Docker files (Dockerfile, docker-compose.yml, etc.)
echo 🔧 Management scripts (manage.sh, manage.ps1, manage.bat)
echo 🐍 Application code (app/ directory)
echo 📁 Configuration templates (config/ directory)
echo.
pause
