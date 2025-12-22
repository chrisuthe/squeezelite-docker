# Home Assistant Add-on Dockerfile
# Based on official HA base images (Alpine Linux)

ARG BUILD_FROM
FROM ${BUILD_FROM}

# Build arguments
ARG BUILD_ARCH
ARG BUILD_DATE
ARG BUILD_REF
ARG BUILD_VERSION

# Install system dependencies
RUN apk add --no-cache \
    python3 \
    py3-pip \
    py3-numpy \
    # Audio libraries
    alsa-utils \
    alsa-lib \
    pulseaudio-utils \
    portaudio \
    # Build dependencies for Python packages
    gcc \
    python3-dev \
    musl-dev \
    portaudio-dev \
    # Curl for health checks
    curl

# Install snapclient from edge/community
RUN apk add --no-cache --repository=http://dl-cdn.alpinelinux.org/alpine/edge/community \
    snapcast-client || echo "snapclient not available"

# Build squeezelite from source (not in Alpine repos)
RUN apk add --no-cache --virtual .build-deps \
        git make linux-headers flac-dev libvorbis-dev \
        libmad-dev faad2-dev mpg123-dev alsa-lib-dev \
        opusfile-dev soxr-dev && \
    git clone --depth 1 https://github.com/ralph-irving/squeezelite.git /tmp/squeezelite && \
    cd /tmp/squeezelite && \
    make OPTS="-DRESAMPLE -DDSD -DLINKALL" && \
    cp squeezelite /usr/local/bin/ && \
    chmod +x /usr/local/bin/squeezelite && \
    cd / && rm -rf /tmp/squeezelite && \
    apk del .build-deps

# Create app directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

# Copy application code from parent directory
COPY app/ /app/

# Copy static assets
COPY app/static/ /app/static/
COPY app/templates/ /app/templates/

# Create data directories
RUN mkdir -p /data /data/logs

# Copy run script
COPY multiroom-audio/run.sh /run.sh
RUN chmod +x /run.sh

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/api/players || exit 1

# Labels
LABEL \
    io.hass.name="Multi-Room Audio Controller" \
    io.hass.description="Manage multiple audio players for whole-home audio" \
    io.hass.arch="${BUILD_ARCH}" \
    io.hass.type="addon" \
    io.hass.version="${BUILD_VERSION}" \
    maintainer="Chris Uthe" \
    org.opencontainers.image.title="Multi-Room Audio Controller" \
    org.opencontainers.image.description="Multi-room audio management for Home Assistant" \
    org.opencontainers.image.source="https://github.com/chrisuthe/squeezelite-docker" \
    org.opencontainers.image.created="${BUILD_DATE}" \
    org.opencontainers.image.revision="${BUILD_REF}"

# Run the application
CMD ["/run.sh"]
