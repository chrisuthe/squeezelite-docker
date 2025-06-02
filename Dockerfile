FROM ubuntu:22.04

# Avoid interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Set up retry mechanism for apt-get
RUN echo 'APT::Acquire::Retries "3";' > /etc/apt/apt.conf.d/80-retries

# Update package lists with retries
RUN apt-get update --fix-missing || apt-get update --fix-missing || apt-get update

# Install core system dependencies first
RUN apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    wget \
    gnupg \
    lsb-release \
    && rm -rf /var/lib/apt/lists/*

# Update package lists again after core packages
RUN apt-get update

# Install build dependencies
RUN apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install audio development libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    libasound2-dev \
    libflac-dev \
    libmad0-dev \
    libvorbis-dev \
    libfaad-dev \
    libmpg123-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Install runtime audio packages
RUN apt-get update && apt-get install -y \
    alsa-utils \
    alsa-base \
    libasound2 \
    libasound2-plugins \
    && rm -rf /var/lib/apt/lists/*

# Install Python and supervisor
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    supervisor \
    dos2unix \
    && rm -rf /var/lib/apt/lists/*

# Try to install pulseaudio-utils (optional, may fail on some systems)
RUN apt-get update && \
    (apt-get install -y --no-install-recommends pulseaudio-utils || echo "PulseAudio utils not available, skipping") && \
    rm -rf /var/lib/apt/lists/*

# Create application directory
WORKDIR /app

# Clone and build squeezelite with error handling
RUN git clone https://github.com/ralph-irving/squeezelite.git /tmp/squeezelite || \
    (echo "Failed to clone squeezelite repository. Trying alternative..." && \
     wget -O /tmp/squeezelite.tar.gz https://github.com/ralph-irving/squeezelite/archive/refs/heads/master.tar.gz && \
     cd /tmp && tar -xzf squeezelite.tar.gz && mv squeezelite-master squeezelite)

# Build squeezelite
RUN cd /tmp/squeezelite && \
    make && \
    cp squeezelite /usr/local/bin/ && \
    chmod +x /usr/local/bin/squeezelite && \
    rm -rf /tmp/squeezelite*

# Verify squeezelite installation
RUN squeezelite -? || echo "squeezelite installed successfully"

# Create directories for configuration and data
RUN mkdir -p /app/config /app/data /app/logs

# Create basic ALSA configuration for virtual devices
RUN mkdir -p /usr/share/alsa && \
    echo 'pcm.null { type null }' > /usr/share/alsa/99-docker-virtual.conf && \
    echo 'ctl.null { type null }' >> /usr/share/alsa/99-docker-virtual.conf

# Copy Python requirements and install dependencies
COPY requirements.txt /app/
RUN pip3 install --no-cache-dir --upgrade pip && \
    pip3 install --no-cache-dir -r requirements.txt

# Copy application files
COPY app/ /app/
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Copy entrypoint script and ensure Unix line endings
COPY entrypoint.sh /app/entrypoint.sh
RUN dos2unix /app/entrypoint.sh 2>/dev/null || sed -i 's/\r$//' /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh /app/health_check.py

# Create non-root user for squeezelite processes
RUN useradd -r -s /bin/false squeezelite || true

# Add audio group and add root to it (for development/testing)
RUN groupadd -f audio || true && \
    usermod -a -G audio root || true

# Set environment variable to indicate this is a container
ENV SQUEEZELITE_CONTAINER=1

# Expose web interface port
EXPOSE 8080

# Add healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/api/players || exit 1

# Use entrypoint script
ENTRYPOINT ["/app/entrypoint.sh"]
