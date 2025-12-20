# Environment Variables

This document describes all environment variables supported by the Multi Output Player application, including their valid values, defaults, and validation rules.

## Overview

The application validates environment variables on startup to provide helpful error messages when misconfigured. Invalid values trigger warnings but don't crash the application - instead, sensible defaults are used.

## Squeezelite Configuration

### SQUEEZELITE_BUFFER_TIME

ALSA buffer time in milliseconds. Controls the ALSA period size.

- **Type:** Integer
- **Default:** `80`
- **Valid Range:** 1-1000 milliseconds
- **Typical Range:** 20-200 milliseconds
- **Description:** Lower values reduce latency but may cause audio dropouts on slower systems. Higher values increase latency but provide more stable playback.

**Examples:**
```bash
# Low latency (may cause dropouts on slower hardware)
SQUEEZELITE_BUFFER_TIME=20

# Default (balanced)
SQUEEZELITE_BUFFER_TIME=80

# High stability (higher latency)
SQUEEZELITE_BUFFER_TIME=200
```

### SQUEEZELITE_BUFFER_PARAMS

Internal stream and output buffer sizes in KB.

- **Type:** String (format: `stream:output`)
- **Default:** `500:2000`
- **Valid Range:** Each buffer 1-100000 KB
- **Description:**
  - `stream`: Size of internal stream buffer before audio processing
  - `output`: Size of output buffer after audio processing
  - Larger buffers provide more resilience against network/CPU issues but use more memory and increase latency
  - Smaller buffers reduce memory and latency but may cause underruns

**Examples:**
```bash
# Low memory/latency (may cause underruns)
SQUEEZELITE_BUFFER_PARAMS=250:1000

# Default (balanced)
SQUEEZELITE_BUFFER_PARAMS=500:2000

# High stability (more memory/latency)
SQUEEZELITE_BUFFER_PARAMS=1000:4000
```

### SQUEEZELITE_CLOSE_TIMEOUT

Output device close timeout in seconds.

- **Type:** Integer
- **Default:** `5`
- **Valid Range:** 0-3600 seconds
- **Description:** Number of seconds of silence before closing the audio output device. This allows the audio device to enter power-saving mode during inactivity. Set to 0 to keep device always open (prevents power-saving but reduces startup latency when playback resumes).

**Examples:**
```bash
# Always keep device open (no power saving, instant resume)
SQUEEZELITE_CLOSE_TIMEOUT=0

# Default (5 seconds of silence)
SQUEEZELITE_CLOSE_TIMEOUT=5

# Aggressive power saving (30 seconds of silence)
SQUEEZELITE_CLOSE_TIMEOUT=30
```

### SQUEEZELITE_SAMPLE_RATE

Default sample rate for null device output.

- **Type:** Integer
- **Default:** `44100`
- **Valid Range:** 8000-384000 Hz
- **Typical Values:**
  - 44100: CD quality
  - 48000: DVD quality
  - 96000: High-resolution audio
  - 192000: Studio quality
- **Description:** Used when outputting to the null device (no audio hardware). This must be specified explicitly for null device operation.

**Examples:**
```bash
# CD quality
SQUEEZELITE_SAMPLE_RATE=44100

# DVD quality
SQUEEZELITE_SAMPLE_RATE=48000

# High-resolution
SQUEEZELITE_SAMPLE_RATE=96000
```

### SQUEEZELITE_WINDOWS_MODE

Windows compatibility mode flag.

- **Type:** Boolean (0/1, true/false, yes/no)
- **Default:** `0` (disabled)
- **Valid Values:** `0`, `1`, `true`, `false`, `yes`, `no`, `on`, `off` (case-insensitive)
- **Description:** Enable Windows compatibility mode where audio device access is limited. This is automatically detected in most cases.

**Examples:**
```bash
# Disabled (default)
SQUEEZELITE_WINDOWS_MODE=0

# Enabled
SQUEEZELITE_WINDOWS_MODE=1

# Also valid
SQUEEZELITE_WINDOWS_MODE=true
SQUEEZELITE_WINDOWS_MODE=yes
```

## Application Configuration

### SECRET_KEY

Flask secret key for session security.

- **Type:** String
- **Default:** Auto-generated random key
- **Minimum Length:** 32 characters recommended
- **Description:** Used for securing Flask sessions. If not set, a random key is generated on each startup (sessions won't persist across restarts). Set this to a secure random value in production.

**Examples:**
```bash
# Generate secure random key (Linux/macOS)
SECRET_KEY=$(openssl rand -hex 32)

# Generate secure random key (Python)
SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
```

**Warning:** The validation will warn if SECRET_KEY is set but shorter than 32 characters.

### AUDIO_BACKEND

Audio backend selection.

- **Type:** String (enum)
- **Default:** `alsa`
- **Valid Values:** `alsa`, `pulse`, `pulseaudio`, `pipewire` (case-insensitive)
- **Description:** Override the auto-detected audio backend. Normally detected based on environment (ALSA for standalone Docker, PulseAudio for Home Assistant OS).

**Examples:**
```bash
# ALSA (default for standalone Docker)
AUDIO_BACKEND=alsa

# PulseAudio (default for Home Assistant OS)
AUDIO_BACKEND=pulse

# PipeWire
AUDIO_BACKEND=pipewire
```

### CONFIG_PATH

Configuration directory path.

- **Type:** String (directory path)
- **Default:** `/app/config`
- **Description:** Directory where player configurations are stored. Automatically set to `/data` in Home Assistant OS.

### LOG_PATH

Log directory path.

- **Type:** String (directory path)
- **Default:** `/app/logs`
- **Description:** Directory where application and player logs are written. Automatically set to `/data/logs` in Home Assistant OS.

### SUPERVISOR_TOKEN

Home Assistant supervisor authentication token.

- **Type:** String
- **Default:** Not set
- **Description:** Automatically set by Home Assistant OS when running as an add-on. Indicates HAOS mode when present.

### SENDSPIN_CONTAINER

Sendspin container mode flag.

- **Type:** Boolean (0/1, true/false, yes/no)
- **Default:** `0` (disabled)
- **Valid Values:** `0`, `1`, `true`, `false`, `yes`, `no`, `on`, `off` (case-insensitive)
- **Description:** Internal flag for health check to detect sendspin-specific container mode.

## Validation Behavior

### Startup Validation

On application startup, all environment variables are validated:

1. **Valid Configuration:** Application starts normally with no warnings
2. **Invalid Configuration:** Application logs warnings but continues with defaults

### Example Output

When environment variables are invalid, you'll see warnings like:

```
==================================================
CONFIGURATION WARNINGS DETECTED
The following environment variables have invalid values:
  - Invalid value for SQUEEZELITE_BUFFER_TIME='abc': must be an integer. Using default value: 80
  - Value for SQUEEZELITE_SAMPLE_RATE=1000 is below minimum 8000. Using default value: 44100
  - Invalid value for SQUEEZELITE_BUFFER_PARAMS='500': must be in format 'stream:output' (e.g., '500:2000'). Using default value: 500:2000
Application will continue with default values.
==================================================
```

### Testing Your Configuration

To verify your environment variables are configured correctly, check the application logs on startup. Valid configurations will show:

```
Environment variable validation: PASSED (all variables valid)
```

Invalid configurations will show specific warnings about which variables need correction.

## Docker Compose Example

Here's a complete example showing all environment variables:

```yaml
version: '3.8'

services:
  squeezelite-docker:
    image: your-image:latest
    environment:
      # Squeezelite Configuration
      SQUEEZELITE_BUFFER_TIME: "80"              # ALSA buffer time (ms)
      SQUEEZELITE_BUFFER_PARAMS: "500:2000"      # Stream:output buffers (KB)
      SQUEEZELITE_CLOSE_TIMEOUT: "5"             # Device close timeout (seconds)
      SQUEEZELITE_SAMPLE_RATE: "44100"           # Sample rate for null device (Hz)
      SQUEEZELITE_WINDOWS_MODE: "0"              # Windows compatibility mode

      # Application Configuration
      SECRET_KEY: "your-secret-key-here-at-least-32-chars-long"
      AUDIO_BACKEND: "alsa"                       # Audio backend (alsa/pulse/pipewire)
      CONFIG_PATH: "/app/config"                  # Config directory
      LOG_PATH: "/app/logs"                       # Log directory
    volumes:
      - ./config:/app/config
      - ./logs:/app/logs
    devices:
      - /dev/snd:/dev/snd
    ports:
      - "8080:8080"
```

## Common Issues

### Issue: "Volume control not working"

**Possible causes:**
- AUDIO_BACKEND set incorrectly
- SQUEEZELITE_WINDOWS_MODE enabled when not needed

**Solution:** Let the application auto-detect the audio backend (don't set AUDIO_BACKEND unless necessary).

### Issue: "Audio dropouts/stuttering"

**Possible causes:**
- SQUEEZELITE_BUFFER_TIME too low
- SQUEEZELITE_BUFFER_PARAMS too small

**Solution:** Increase buffer sizes:
```bash
SQUEEZELITE_BUFFER_TIME=120
SQUEEZELITE_BUFFER_PARAMS=1000:3000
```

### Issue: "High latency/delay"

**Possible causes:**
- SQUEEZELITE_BUFFER_TIME too high
- SQUEEZELITE_BUFFER_PARAMS too large

**Solution:** Decrease buffer sizes (but watch for dropouts):
```bash
SQUEEZELITE_BUFFER_TIME=40
SQUEEZELITE_BUFFER_PARAMS=250:1000
```

### Issue: "Device busy" errors

**Possible causes:**
- SQUEEZELITE_CLOSE_TIMEOUT=0 keeps device always open

**Solution:** Use non-zero timeout to allow device to close:
```bash
SQUEEZELITE_CLOSE_TIMEOUT=5
```

## Development and Testing

To test the validation system, you can run the test suite:

```bash
python app/test_env_validation.py
```

This will test various valid and invalid configurations to ensure proper validation and error messages.
