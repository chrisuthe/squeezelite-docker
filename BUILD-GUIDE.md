# Multi-Room Audio Docker Build Guide

This document explains all the build and start options available for the Multi-Room Audio Docker project, including standalone Docker and Home Assistant OS add-on builds.

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

---

## Build Targets

This project supports two build targets:

| Target | Base Image | Audio System | Use Case |
|--------|------------|--------------|----------|
| **Standalone Docker** | Debian | ALSA | Direct Docker deployment |
| **HAOS Add-on** | Alpine | PulseAudio | Home Assistant OS integration |

---

## Standalone Docker Build

### All Build Scripts Use --no-cache

All build scripts have been updated to use `--no-cache` to ensure fresh, reliable builds without cached layer issues.

### Available Scripts

#### 1. Clean Build Scripts (New)
- **`build-clean.bat`** - Comprehensive Windows batch script
- **`build-clean.ps1`** - Comprehensive PowerShell script

Features:
- Fixes line ending issues automatically
- Always uses `--no-cache` for clean builds
- Cleans up old containers/images first
- Provides detailed status messages
- Supports different build modes

Usage:
```cmd
build-clean.bat           # No-audio mode (default)
build-clean.bat full      # Full audio mode
build-clean.bat dev       # Development mode
```

#### 2. Management Scripts (Updated)
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

#### 3. Quick Fix Scripts
- **`fix-entrypoint.bat`** - Fixes line endings + builds
- **`fix-entrypoint.ps1`** - PowerShell version

Use these if you specifically have the "no such file or directory" error.

### Build Modes

#### No-Audio Mode (Default)
Best for development and testing without audio hardware:
- Uses `docker-compose.no-audio.yml`
- No audio device passthrough
- Virtual/null audio devices only
- Works reliably on all systems

#### Full Mode
For production with audio hardware:
- Uses `docker-compose.yml`
- Requires audio device passthrough
- May need special permissions on Windows

#### Development Mode
For active development:
- Uses `docker-compose.dev.yml`
- May include volume mounts for live editing
- Always rebuilds with `--no-cache`

---

## Home Assistant OS Add-on Build

The HAOS add-on lives in the `hassio/` subdirectory and uses a separate Alpine-based Dockerfile.

### Building Locally

```bash
cd hassio

# Build for AMD64 (most common)
docker build \
  --build-arg BUILD_FROM=ghcr.io/home-assistant/amd64-base-python:3.11 \
  -t multiroom-audio-addon:local .

# Build for ARM64 (Raspberry Pi 4/5)
docker build \
  --build-arg BUILD_FROM=ghcr.io/home-assistant/aarch64-base-python:3.11 \
  -t multiroom-audio-addon:local .

# Build for ARMv7 (Raspberry Pi 3)
docker build \
  --build-arg BUILD_FROM=ghcr.io/home-assistant/armv7-base-python:3.11 \
  -t multiroom-audio-addon:local .
```

### Testing the Add-on Locally

```bash
# Run the built image locally (without HAOS integration)
docker run --rm -it \
  -p 8080:8080 \
  -e AUDIO_BACKEND=alsa \
  multiroom-audio-addon:local
```

Note: Full audio functionality requires the HAOS PulseAudio system.

### Installing in Home Assistant

#### Method 1: Local Add-on (Development)
1. Copy the `hassio/` folder to `/addons/multiroom-audio` on your Home Assistant system
2. Go to **Settings → Add-ons → Add-on Store**
3. Click the three-dot menu → **Check for updates**
4. Find "Multi-Room Audio Controller" in **Local add-ons**
5. Click **Install**

#### Method 2: Custom Repository (Production)
1. Go to **Settings → Add-ons → Add-on Store**
2. Click the three-dot menu → **Repositories**
3. Add your repository URL
4. Click **Check for updates**
5. Install from the repository

### HAOS Build Architecture

The add-on uses environment detection to adapt to HAOS:

```
hassio/
├── config.yaml           # Add-on metadata and permissions
├── Dockerfile            # Alpine-based build (references ../app)
├── run.sh                # Bashio startup script
├── DOCS.md               # User documentation
├── CHANGELOG.md          # Version history
├── translations/
│   └── en.yaml           # Option descriptions for HA config UI
└── repository.yaml       # Repository metadata
```

Key differences from standalone Docker:
- **Base image**: Alpine (smaller) instead of Debian
- **Audio system**: PulseAudio via hassio_audio instead of ALSA
- **Config storage**: `/data` instead of `/app/config`
- **Startup**: bashio script instead of gunicorn directly

---

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

### HAOS Add-on Won't Start
1. Check add-on logs in Home Assistant
2. Verify `full_access` permission is enabled
3. Ensure hassio_audio is running (required for PulseAudio)
4. Check that no other add-on is using the same audio devices

### Audio Not Working in HAOS
1. Verify PulseAudio devices are available:
   - SSH into Home Assistant
   - Run: `docker exec -it addon_local_multiroom_audio pactl list sinks short`
2. Check that the correct audio output is selected in Home Assistant audio settings
3. Restart the hassio_audio container if needed

---

## Container Access

### Standalone Docker
Once running:
- **Web Interface**: http://localhost:8080
- **Logs**: `docker-compose -f [compose-file] logs -f`
- **Shell Access**: `docker exec -it squeezelite-multiroom-no-audio bash`

### HAOS Add-on
- **Web Interface**: Via Home Assistant sidebar (Ingress) or `http://[HA_IP]:8080`
- **Logs**: Settings → Add-ons → Multi-Room Audio Controller → Logs
- **Shell Access**: Not recommended; use add-on logs for debugging

---

## File Structure

```
squeezelite-docker/
├── build-clean.bat              # Comprehensive build script
├── build-clean.ps1              # PowerShell build script
├── fix-entrypoint.bat           # Quick fix for line endings
├── fix-entrypoint.ps1           # PowerShell quick fix
├── manage.bat                   # Windows management
├── manage.ps1                   # PowerShell management
├── manage.sh                    # Linux/Unix management
├── docker-compose.yml           # Full mode (with audio)
├── docker-compose.no-audio.yml  # No-audio mode (default)
├── docker-compose.dev.yml       # Development mode
├── Dockerfile                   # Main Dockerfile (Debian)
├── Dockerfile.slim              # Slim variant (Sendspin only)
├── entrypoint.sh                # Container entrypoint
├── app/                         # Application code
│   ├── app.py                   # Flask application
│   ├── environment.py           # Environment detection (Docker/HAOS)
│   ├── managers/                # Business logic managers
│   └── providers/               # Player backend implementations
└── hassio/                      # Home Assistant OS add-on
    ├── config.yaml              # Add-on metadata
    ├── Dockerfile               # Alpine-based build
    ├── run.sh                   # Bashio startup script
    ├── DOCS.md                  # Add-on documentation
    └── translations/en.yaml     # Config UI translations
```

---

## Best Practices

1. **Always use clean builds** - Scripts now do this automatically
2. **Test with no-audio first** - More reliable for development
3. **Check Docker Desktop** - Ensure it's running with enough resources
4. **Use appropriate script** - Batch for simplicity, PowerShell for features
5. **Check logs** - When issues occur, logs provide key information
6. **Test HAOS builds locally** - Use `docker build` before deploying to HA

---

## Next Steps

### For Standalone Docker
1. Run `build-clean.bat` to resolve the current issue
2. Access http://localhost:8080 to configure players
3. Use `manage.bat logs` to monitor operation
4. Proceed with multi-room audio configuration

### For HAOS Add-on
1. Build locally with `docker build` in `hassio/` directory
2. Copy to Home Assistant `/addons/` directory
3. Install via Add-on Store → Local add-ons
4. Configure via the add-on configuration panel
5. Access via Home Assistant sidebar
