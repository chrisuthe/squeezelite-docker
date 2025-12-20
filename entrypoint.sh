#!/bin/bash

# Squeezelite Docker Entrypoint Script

echo "Starting Multi Output Player..."

# Set default values for environment variables (if not provided)
# Generate random secrets if not explicitly set
if [ -z "$SECRET_KEY" ]; then
    export SECRET_KEY=$(head -c 32 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9' | head -c 32)
    echo "WARNING: SECRET_KEY not set - using randomly generated key. This is not suitable for production."
fi

if [ -z "$SUPERVISOR_USER" ]; then
    export SUPERVISOR_USER="admin_$(head -c 8 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9' | head -c 8)"
    echo "WARNING: SUPERVISOR_USER not set - using randomly generated username: $SUPERVISOR_USER"
fi

if [ -z "$SUPERVISOR_PASSWORD" ]; then
    export SUPERVISOR_PASSWORD=$(head -c 24 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9' | head -c 24)
    echo "WARNING: SUPERVISOR_PASSWORD not set - using randomly generated password. This is not suitable for production."
fi

# Set permissions for audio devices (if they exist)
if [ -d "/dev/snd" ]; then
    echo "Audio devices found - setting up permissions..."
    chown -R root:audio /dev/snd 2>/dev/null || echo "Warning: Could not change audio device ownership"
    chmod -R 664 /dev/snd/* 2>/dev/null || echo "Warning: Could not change audio device permissions"
    chmod 755 /dev/snd 2>/dev/null || echo "Warning: Could not change /dev/snd permissions"
else
    echo "No /dev/snd directory found - audio devices not available"
    echo "Container will still work with virtual/null audio devices"
fi

# Ensure log directory exists and has correct permissions
mkdir -p /app/logs
chmod 755 /app/logs

# Ensure config directory exists
mkdir -p /app/config
chmod 755 /app/config

# Create a dummy ALSA config if no audio system is available
if [ ! -f "/usr/share/alsa/alsa.conf" ] && [ ! -f "/etc/asound.conf" ]; then
    echo "Creating minimal ALSA configuration for no-audio-device operation..."
    mkdir -p /etc
    cat > /etc/asound.conf << 'EOF'
# Minimal ALSA configuration for container without audio devices
pcm.!default {
    type null
}
ctl.!default {
    type null
}
EOF
fi

# Check for audio devices and provide helpful information
echo "Checking audio system availability..."
if command -v aplay >/dev/null 2>&1; then
    echo "ALSA utilities available"
    if aplay -l >/dev/null 2>&1; then
        echo "Audio devices detected:"
        aplay -l 2>/dev/null || echo "Could not list audio devices"
    else
        echo "No audio devices found - this is OK for testing/development"
        echo "Virtual devices (null, default) will be available"
    fi
else
    echo "ALSA utilities not available - this should not happen"
fi

# List ALSA cards (if available)
if [ -d "/proc/asound" ]; then
    echo "ALSA cards detected:"
    ls -la /proc/asound/ 2>/dev/null || echo "Could not list ALSA cards"
else
    echo "No ALSA cards found in /proc/asound"
    echo "This is normal in environments without audio hardware"
fi

# Test audio player binaries
echo "Testing audio player binaries..."
if [ "$SENDSPIN_CONTAINER" = "1" ]; then
    echo "  (Slim image - sendspin only)"
    if command -v sendspin >/dev/null 2>&1; then
        echo "✓ sendspin binary is available"
    else
        echo "✗ sendspin binary not found!"
        echo "Container build may have failed"
    fi
else
    echo "  (Full image - checking both players)"
    if command -v squeezelite >/dev/null 2>&1; then
        echo "✓ squeezelite binary is available"
    else
        echo "✗ squeezelite binary not found!"
    fi
    if command -v sendspin >/dev/null 2>&1; then
        echo "✓ sendspin binary is available"
    else
        echo "✗ sendspin binary not found!"
    fi
fi

# Test Python and dependencies
echo "Testing Python environment..."
if command -v python3 >/dev/null 2>&1; then
    echo "Python3 is available: $(python3 --version)"
    
    # Run health check
    echo "Running container health check..."
    if python3 /app/health_check.py; then
        echo "✅ Health check passed - container is ready"
    else
        echo "❌ Health check failed - see errors above"
        echo "Container will still attempt to start, but may have issues"
    fi
else
    echo "ERROR: Python3 not found!"
fi

# Show startup information
echo ""
echo "=== Multi Output Player Starting ==="
echo "Web interface will be available at: http://localhost:8080"
echo "Log location: /app/logs/"
echo "Config location: /app/config/"
echo ""
if [ ! -d "/dev/snd" ]; then
    echo "NOTE: No audio hardware detected"
    echo "- You can still create and test players"
    echo "- Use 'null' device for silent operation"
    echo "- Use 'default' device (may work with virtual audio)"
    echo ""
fi

# Start supervisord which will manage our services
echo "Starting services with supervisord..."
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
