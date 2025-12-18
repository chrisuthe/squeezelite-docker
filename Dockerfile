FROM ubuntu:24.04

# Ubuntu 24.04 LTS provides Python 3.12 (required for sendspin CLI)
# and includes up-to-date audio packages

# Avoid interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Update and install all dependencies in single layer to avoid caching issues
# Note: Ubuntu 24.04 has package name changes (time64 transition: libasound2 -> libasound2t64, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Core system dependencies
    ca-certificates \
    curl \
    wget \
    # Pre-built squeezelite with codec support (pulls in most audio deps)
    squeezelite \
    # Audio system (Ubuntu 24.04 package names)
    alsa-utils \
    alsa-base \
    libasound2t64 \
    libasound2-plugins \
    # PortAudio for sendspin (sounddevice dependency)
    libportaudio2 \
    # Additional codec libraries for full format support (Ubuntu 24.04 versions)
    libflac12t64 \
    libmad0 \
    libvorbis0a \
    libvorbisenc2 \
    libvorbisfile3 \
    libfaad2 \
    libmpg123-0t64 \
    libssl3t64 \
    libogg0 \
    libopus0 \
    # Python environment
    python3 \
    python3-pip \
    supervisor \
    dos2unix \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Verify squeezelite installation
RUN which squeezelite && echo "Squeezelite installed successfully"

# Create application directory and required directories
WORKDIR /app
RUN mkdir -p /app/config /app/data /app/logs

# Create basic ALSA configuration for virtual devices
RUN mkdir -p /usr/share/alsa && \
    echo 'pcm.null { type null }' > /usr/share/alsa/99-docker-virtual.conf && \
    echo 'ctl.null { type null }' >> /usr/share/alsa/99-docker-virtual.conf

# Copy and install Python requirements
# Note: --break-system-packages is required on Ubuntu 24.04 (PEP 668)
# Don't upgrade pip - system pip 24.0 is sufficient and can't be upgraded in-place
COPY requirements.txt /app/
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

# Verify sendspin installation (no --version flag, just check it runs)
RUN which sendspin && sendspin --help > /dev/null && echo "Sendspin installed successfully"

# Copy application files
COPY app/ /app/
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY entrypoint.sh /app/entrypoint.sh

# Fix line endings and permissions
RUN dos2unix /app/entrypoint.sh 2>/dev/null || sed -i 's/\r$//' /app/entrypoint.sh && \
    chmod +x /app/entrypoint.sh /app/health_check.py

# Create user and groups
RUN useradd -r -s /bin/false squeezelite || true && \
    groupadd -f audio || true && \
    usermod -a -G audio root || true

# Set environment variables
ENV SQUEEZELITE_CONTAINER=1

# Expose web interface port
EXPOSE 8080

# Add healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/api/players || exit 1

# Use entrypoint script
ENTRYPOINT ["/app/entrypoint.sh"]