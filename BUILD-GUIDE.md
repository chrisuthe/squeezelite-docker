# Squeezelite Docker Build Guide

This document explains all the build and start options available for the Squeezelite Multi-Room Docker project.

## Quick Start (Recommended)

For the fastest resolution of your current issue, use one of these clean build scripts:

### Windows Batch (Recommended for Windows)
```cmd
build-clean.bat
```

### PowerShell (Alternative for Windows)
```powershell
.\build-clean.ps1
```

### Linux/macOS
```bash
./manage.sh build
./manage.sh start
```

## All Build Scripts Use --no-cache

All build scripts have been updated to use `--no-cache` to ensure fresh, reliable builds without cached layer issues.

## Available Scripts

### 1. Clean Build Scripts (New)
- **`build-clean.bat`** - Comprehensive Windows batch script
- **`build-clean.ps1`** - Comprehensive PowerShell script

Features:
- ✅ Fixes line ending issues automatically
- ✅ Always uses `--no-cache` for clean builds
- ✅ Cleans up old containers/images first
- ✅ Provides detailed status messages
- ✅ Supports different build modes

Usage:
```cmd
build-clean.bat           # No-audio mode (default)
build-clean.bat full      # Full audio mode
build-clean.bat dev       # Development mode
```

### 2. Management Scripts (Updated)
- **`manage.bat`** - Windows batch management
- **`manage.ps1`** - PowerShell management  
- **`manage.sh`** - Linux/Unix management

All now use `--no-cache` by default for builds.

Commands:
```cmd
manage.bat build         # Build with no cache
manage.bat start         # Start services
manage.bat no-audio      # Start in no-audio mode
manage.bat dev           # Development mode with no cache
manage.bat logs          # View logs
manage.bat clean         # Clean up everything
```

### 3. Quick Fix Scripts
- **`fix-entrypoint.bat`** - Fixes line endings + builds
- **`fix-entrypoint.ps1`** - PowerShell version

Use these if you specifically have the "no such file or directory" error.

## Build Modes

### No-Audio Mode (Default)
Best for development and testing without audio hardware:
- Uses `docker-compose.no-audio.yml`
- No audio device passthrough
- Virtual/null audio devices only
- Works reliably on all systems

### Full Mode
For production with audio hardware:
- Uses `docker-compose.yml`
- Requires audio device passthrough
- May need special permissions on Windows

### Development Mode
For active development:
- Uses `docker-compose.dev.yml`
- May include volume mounts for live editing
- Always rebuilds with `--no-cache`

## Troubleshooting

### "exec /app/entrypoint.sh: no such file or directory"
This is a line ending issue. Solutions:
1. Run `build-clean.bat` or `fix-entrypoint.bat`
2. Or manually fix: PowerShell command in project root:
   ```powershell
   (Get-Content entrypoint.sh -Raw) -replace "`r`n", "`n" | Set-Content entrypoint.sh -Encoding UTF8 -NoNewline
   ```

### Build Failures
All scripts now use `--no-cache` to prevent:
- Stale cached layers
- Partial build artifacts
- Network/package version issues

### Container Won't Start
1. Check Docker Desktop is running
2. Use `docker-compose logs` to see errors
3. Try the clean build scripts
4. Check available disk space

## Container Access

Once running:
- **Web Interface**: http://localhost:8080
- **Logs**: `docker-compose -f [compose-file] logs -f`
- **Shell Access**: `docker exec -it squeezelite-multiroom-no-audio bash`

## File Structure

```
squeezelite-docker/
├── build-clean.bat          # ← New comprehensive build script
├── build-clean.ps1          # ← New PowerShell build script
├── fix-entrypoint.bat       # ← Quick fix for line endings
├── fix-entrypoint.ps1       # ← PowerShell quick fix
├── manage.bat               # ← Updated with --no-cache
├── manage.ps1               # ← Updated with --no-cache  
├── manage.sh                # ← Updated with --no-cache
├── docker-compose.yml       # Full mode
├── docker-compose.no-audio.yml  # No-audio mode (default)
├── docker-compose.dev.yml   # Development mode
├── Dockerfile               # Main Dockerfile (updated)
├── entrypoint.sh            # Fixed line endings
└── app/                     # Application code
```

## Best Practices

1. **Always use clean builds** - Scripts now do this automatically
2. **Test with no-audio first** - More reliable for development
3. **Check Docker Desktop** - Ensure it's running with enough resources
4. **Use appropriate script** - Batch for simplicity, PowerShell for features
5. **Check logs** - When issues occur, logs provide key information

## Next Steps

1. Run `build-clean.bat` to resolve the current issue
2. Access http://localhost:8080 to configure players
3. Use `manage.bat logs` to monitor operation
4. Proceed with multi-room audio configuration
