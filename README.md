# Squeezelite Multi-Room Docker Controller

![Squeezelite Multi-Room Controller](screenshot.png)

A containerized multi-room audio solution that runs multiple [squeezelite](https://github.com/ralph-irving/squeezelite) players with an intuitive web management interface. Perfect for creating synchronized audio zones throughout your home using USB DACs, built-in audio, or network audio devices.

![Multi-Room Audio Controller](https://img.shields.io/badge/Multi--Room-Audio%20Controller-blue?style=for-the-badge&logo=music)
![Docker](https://img.shields.io/badge/Docker-Containerized-2496ED?style=for-the-badge&logo=docker)
![Music Assistant](https://img.shields.io/badge/Music%20Assistant-Compatible-green?style=for-the-badge)
![Real-time](https://img.shields.io/badge/Real--time-WebSocket%20Updates-orange?style=for-the-badge)

## 🎯 Project Goals

Transform any system with Docker into a powerful multi-room audio controller by:
- **Centralizing Control**: Manage all your audio zones from one elegant web interface
- **Simplifying Deployment**: One container handles multiple squeezelite players
- **Enabling Flexibility**: Support various audio outputs from USB DACs to network streams
- **Ensuring Reliability**: Persistent configuration with automatic player recovery
- **Providing Integration**: Seamless compatibility with Music Assistant and LMS servers

## ✨ Key Features

### 🏠 **Multi-Room Audio Management**
- Create unlimited squeezelite players in a single container
- Individual volume control for each audio zone
- Real-time status monitoring with WebSocket updates
- Automatic player discovery by Music Assistant

### 🎛️ **Intuitive Web Interface**
- Modern, responsive design that works on all devices
- Live status indicators and controls
- Drag-and-drop simplicity for player management
- Built-in audio device detection and selection

### 🔌 **Comprehensive Audio Support**
- **USB DACs**: Automatic detection of connected USB audio devices
- **Built-in Audio**: Support for motherboard audio outputs
- **HDMI Audio**: Multi-channel HDMI audio output support
- **Network Audio**: PulseAudio and network streaming compatibility
- **Virtual Devices**: Null and software mixing devices for testing

### 🔧 **Enterprise-Ready Features**
- **REST API**: Full programmatic control with Swagger documentation
- **Health Monitoring**: Built-in container health checks
- **Logging**: Comprehensive logging for troubleshooting
- **Backup/Restore**: Configuration persistence across container updates
- **Cross-Platform**: Runs on Linux, Windows (Docker Desktop), and container orchestration platforms

## 📦 Docker Hub Images

**Ready-to-deploy images available at**: https://hub.docker.com/r/chrisuthe/squeezelitemultiroom

### Quick Deployment
```bash
# Basic deployment
docker run -d \
  --name squeezelite-multiroom \
  -p 8080:8080 \
  -v squeezelite_config:/app/config \
  -v squeezelite_logs:/app/logs \
  --device /dev/snd:/dev/snd \
  chrisuthe/squeezelitemultiroom:latest

# Access web interface at http://localhost:8080
```

### Container Platform Deployment

#### TrueNAS Scale
1. **Apps** → **Available Applications** → **Custom App**
2. **Application Name**: `squeezelite-multiroom`
3. **Image Repository**: `chrisuthe/squeezelitemultiroom`
4. **Image Tag**: `latest`
5. **Port Mapping**: Host Port `8080` → Container Port `8080`
6. **Host Path Volumes**:
   - `/mnt/pool/squeezelite/config` → `/app/config`
   - `/mnt/pool/squeezelite/logs` → `/app/logs`
7. **Device Mapping**: Host `/dev/snd` → Container `/dev/snd` (for audio)

#### Portainer
1. **Containers** → **Add Container**
2. **Name**: `squeezelite-multiroom`
3. **Image**: `chrisuthe/squeezelitemultiroom:latest`
4. **Port Mapping**: `8080:8080`
5. **Volumes**:
   - `squeezelite_config:/app/config`
   - `squeezelite_logs:/app/logs`
6. **Runtime & Resources** → **Devices**: `/dev/snd:/dev/snd`

#### Dockge
Create a new stack with this `docker-compose.yml`:

```yaml
version: '3.8'
services:
  squeezelite-multiroom:
    image: chrisuthe/squeezelitemultiroom:latest
    container_name: squeezelite-multiroom
    restart: unless-stopped
    ports:
      - "8080:8080"
    devices:
      - /dev/snd:/dev/snd  # Audio device access
    volumes:
      - squeezelite_config:/app/config
      - squeezelite_logs:/app/logs
    environment:
      - SQUEEZELITE_NO_AUDIO_OK=1  # Allow startup without audio devices
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/api/players"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  squeezelite_config:
  squeezelite_logs:
```

## 🚀 Getting Started

### Prerequisites
- Docker environment (Linux/Windows/macOS)
- Music Assistant or Logitech Media Server
- Audio devices (USB DACs, built-in audio, or network audio)

### Step 1: Deploy Container
Use one of the deployment methods above based on your platform.

### Step 2: Access Web Interface
Navigate to `http://your-host-ip:8080`

### Step 3: Create Your First Player
1. Click **"Add Player"**
2. **Name**: Enter a descriptive name (e.g., "Living Room", "Kitchen")
3. **Audio Device**: Select from auto-detected devices
4. **Music Assistant Server**: Leave empty for auto-discovery, or enter IP manually
5. Click **"Create Player"**

### Step 4: Start Playing
1. Click **"Start"** on your new player
2. Player appears in Music Assistant as an available zone
3. Begin streaming music to your multi-room setup!

## 🔧 Configuration Options

### Environment Variables
Customize container behavior:

```yaml
environment:
  - SQUEEZELITE_NO_AUDIO_OK=1        # Allow startup without audio devices
  - SQUEEZELITE_SERVER_IP=192.168.1.100  # Default Music Assistant server
  - SQUEEZELITE_NAME_PREFIX=Docker    # Player name prefix
  - WEB_PORT=8080                    # Web interface port (default: 8080)
  - FLASK_ENV=production             # Production mode
```

### Volume Mounts
Essential for persistent configuration:

```yaml
volumes:
  - ./config:/app/config       # Player configurations
  - ./logs:/app/logs          # Application logs
  - /usr/share/alsa:/usr/share/alsa:ro  # ALSA configuration (Linux)
```

### Audio Device Access
For hardware audio device support:

```yaml
devices:
  - /dev/snd:/dev/snd          # All audio devices (Linux)

# Alternative for specific devices:
devices:
  - /dev/snd/controlC0:/dev/snd/controlC0
  - /dev/snd/pcmC0D0p:/dev/snd/pcmC0D0p
```

## 🎵 Usage Scenarios

### Home Theater Setup
```yaml
# Multiple zones with different audio outputs
Players:
  "Living Room": hw:1,0    # USB DAC for main system
  "Kitchen": hw:2,0        # Secondary USB DAC
  "Bedroom": default       # Built-in audio
  "Patio": pulse           # Network audio to outdoor speakers
```

### Apartment Setup
```yaml
# Synchronized audio with volume control
Players:
  "Main Room": hw:0,0      # Built-in audio
  "Study": null            # Silent player for phone/tablet sync
```

### Office Environment
```yaml
# Background music with individual control
Players:
  "Reception": hw:1,0      # Reception area speakers
  "Conference": hw:2,0     # Conference room audio
  "Break Room": dmix       # Shared audio device
```

## 📊 Advanced Features

### REST API Integration
Full programmatic control available:

```bash
# List all players
curl http://localhost:8080/api/players

# Create new player
curl -X POST http://localhost:8080/api/players \
  -H "Content-Type: application/json" \
  -d '{"name": "Patio", "device": "hw:3,0", "server_ip": "192.168.1.100"}'

# Control volume
curl -X POST http://localhost:8080/api/players/Patio/volume \
  -H "Content-Type: application/json" \
  -d '{"volume": 65}'

# Start/stop players
curl -X POST http://localhost:8080/api/players/Patio/start
curl -X POST http://localhost:8080/api/players/Patio/stop
```

### Home Assistant Integration
```yaml
# configuration.yaml
sensor:
  - platform: rest
    resource: http://squeezelite-host:8080/api/players
    name: "Audio Zones"
    json_attributes:
      - players
      - statuses
    scan_interval: 30

automation:
  - alias: "Morning Music"
    trigger:
      platform: time
      at: "07:00:00"
    action:
      service: rest_command.start_living_room_audio

rest_command:
  start_living_room_audio:
    url: http://squeezelite-host:8080/api/players/Living%20Room/start
    method: POST
```

### Monitoring and Alerts
The container provides comprehensive health monitoring:

```bash
# Container health status
docker inspect squeezelite-multiroom | grep Health -A 10

# Application logs
docker logs squeezelite-multiroom

# Player-specific logs
docker exec squeezelite-multiroom tail -f /app/logs/Living\ Room.log
```

## 🔍 Troubleshooting

### No Audio Devices Detected
**Linux**: Ensure audio devices are accessible
```bash
# Check available devices
aplay -l

# Verify device permissions
ls -la /dev/snd/

# Add user to audio group
sudo usermod -a -G audio $USER
```

**Windows**: Limited audio device passthrough
- Use virtual audio devices like VB-Cable
- Consider network audio streaming
- Enable WSL2 integration for better compatibility

### Players Won't Start
1. **Check audio device availability**:
   ```bash
   docker exec squeezelite-multiroom aplay -l
   ```

2. **Test with null device**:
   - Create player with device `null` for testing
   - Verify Music Assistant connectivity

3. **Review logs**:
   ```bash
   docker exec squeezelite-multiroom tail -f /app/logs/application.log
   ```

### Network Connectivity Issues
- Verify Music Assistant server IP and accessibility
- Check container network mode (host mode recommended)
- Ensure ports 8080 and audio streaming ports are open

## 🏗️ Development and Building

### Building from Source
```bash
# Clone repository
git clone https://github.com/yourusername/squeezelite-docker.git
cd squeezelite-docker

# Build container
docker build -t squeezelite-multiroom .

# Run development version
docker-compose -f docker-compose.dev.yml up
```

### Contributing
1. Fork the repository on GitHub
2. Create feature branch: `git checkout -b feature-name`
3. Test thoroughly with various audio devices
4. Submit pull request with clear description

## 📄 License and Credits

**License**: MIT License - see [LICENSE](LICENSE) file

**Credits**:
- **[Squeezelite](https://github.com/ralph-irving/squeezelite)** by Ralph Irving - The excellent audio player this project is built around
- **[Music Assistant](https://music-assistant.io/)** - Modern music library management and multi-room audio platform
- **Flask Ecosystem** - Web framework and real-time communication libraries

## 💬 Support and Community

- **Issues**: Report bugs and request features via [GitHub Issues](https://github.com/yourusername/squeezelite-docker/issues)
- **Discussions**: Community support and ideas via [GitHub Discussions](https://github.com/yourusername/squeezelite-docker/discussions)
- **Docker Hub**: Pre-built images at https://hub.docker.com/r/chrisuthe/squeezelitemultiroom

## 🎯 Use Cases

**Perfect for**:
- Home audio enthusiasts with multiple rooms
- Apartment dwellers wanting synchronized audio
- Office environments with background music needs
- Integration with existing Music Assistant setups
- Container-native deployments on NAS systems

**Works with**:
- Music Assistant (recommended)
- Logitech Media Server (LMS)
- Any SlimProto-compatible server
- Local audio files and streaming services

---

<div align="center">
  
**🎵 Transform your space into a connected audio experience 🎵**

*Built with ❤️ for the open-source community*

[![Docker Hub](https://img.shields.io/badge/Docker%20Hub-chrisuthe%2Fsqueezelitemultiroom-blue?style=flat-square&logo=docker)](https://hub.docker.com/r/chrisuthe/squeezelitemultiroom)
[![GitHub](https://img.shields.io/badge/GitHub-Source%20Code-black?style=flat-square&logo=github)](https://github.com/yourusername/squeezelite-docker)

</div>