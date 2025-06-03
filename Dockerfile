FROM ubuntu:22.04

# Avoid interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Update and install all dependencies in single layer to avoid caching issues
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Core system dependencies
    ca-certificates \
    curl \
    wget \
    # Pre-built squeezelite with codec support
    squeezelite \
    # Audio system
    alsa-utils \
    alsa-base \
    libasound2 \
    libasound2-plugins \
    # Additional codec libraries for full format support
    libflac8 \
    libmad0 \
    libvorbis0a \
    libvorbisenc2 \
    libvorbisfile3 \
    libfaad2 \
    libmpg123-0 \
    libssl3 \
    libogg0 \
    libopus0 \
    # Python environment
    python3 \
    python3-pip \
    supervisor \
    dos2unix \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Simple verification that squeezelite exists and works
RUN which squeezelite && echo "Squeezelite installed successfully"

# Create application directory and required directories
WORKDIR /app
RUN mkdir -p /app/config /app/data /app/logs

# Create basic ALSA configuration for virtual devices
RUN mkdir -p /usr/share/alsa && \
    echo 'pcm.null { type null }' > /usr/share/alsa/99-docker-virtual.conf && \
    echo 'ctl.null { type null }' >> /usr/share/alsa/99-docker-virtual.conf

# Copy and install Python requirements
COPY requirements.txt /app/
RUN pip3 install --no-cache-dir --upgrade pip && \
    pip3 install --no-cache-dir -r requirements.txt

# Copy application files
COPY app/ /app/
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY entrypoint.sh /app/entrypoint.sh

# Copy codec test script
COPY quick-codec-test.sh /app/
RUN chmod +x /app/quick-codec-test.sh

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