# Multi-Room Audio Docker Controller

<p align="center">
  <img src="multiroom.jpg" alt="Multi-Room Audio Controller" width="400">
</p>

## The Core Concept

**One server. Multiple audio outputs. Whole-home audio.**

This project enables you to run a single centralized server (like a NAS, Raspberry Pi, or any Docker host) with multiple USB DACs or audio devices connected, creating independent audio zones throughout your home. Instead of buying expensive multi-room audio hardware, connect affordable USB DACs to a central machine and stream synchronized audio to every room.

```
┌─────────────────────────────────────────────────────────────────┐
│                     CENTRAL SERVER (Docker Host)                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Multi-Room Audio Container                  │   │
│  │                                                          │   │
│  │   ┌──────────┐  ┌──────────┐  ┌──────────┐             │   │
│  │   │ Player 1 │  │ Player 2 │  │ Player 3 │  ...        │   │
│  │   │(Kitchen) │  │(Bedroom) │  │ (Patio)  │             │   │
│  │   └────┬─────┘  └────┬─────┘  └────┬─────┘             │   │
│  └────────┼─────────────┼─────────────┼────────────────────┘   │
│           │             │             │                         │
│      ┌────▼────┐   ┌────▼────┐   ┌────▼────┐                   │
│      │USB DAC 1│   │USB DAC 2│   │USB DAC 3│                   │
│      └────┬────┘   └────┬────┘   └────┬────┘                   │
└───────────┼─────────────┼─────────────┼─────────────────────────┘
            │             │             │
       ┌────▼────┐   ┌────▼────┐   ┌────▼────┐
       │ Kitchen │   │ Bedroom │   │  Patio  │
       │Speakers │   │Speakers │   │Speakers │
       └─────────┘   └─────────┘   └─────────┘
```

![Multi-Room Audio Controller](https://img.shields.io/badge/Multi--Room-Audio%20Controller-blue?style=for-the-badge&logo=music)
![Docker](https://img.shields.io/badge/Docker-Containerized-2496ED?style=for-the-badge&logo=docker)
![Music Assistant](https://img.shields.io/badge/Music%20Assistant-Compatible-green?style=for-the-badge)
![Real-time](https://img.shields.io/badge/Real--time-WebSocket%20Updates-orange?style=for-the-badge)
![Sendspin](https://img.shields.io/badge/Sendspin-Native%20Support-purple?style=for-the-badge)
![Snapcast](https://img.shields.io/badge/Snapcast-Synchronized%20Audio-red?style=for-the-badge)

## Why This Approach?

| Traditional Setup | This Solution |
|-------------------|---------------|
| Expensive wireless speakers per room | Affordable USB DACs + any speakers |
| Vendor lock-in (Sonos, Bose, etc.) | Open source, works with any hardware |
| Complex network configuration | Single Docker container |
| Limited integration options | Full API + Music Assistant/LMS support |
| Separate apps per brand | One web interface for all zones |

## Supported Player Backends

- **[Squeezelite](https://github.com/ralph-irving/squeezelite)**: LMS/SlimProto protocol for Logitech Media Server
- **[Sendspin](https://pypi.org/project/sendspin/)**: Native Music Assistant protocol with synchronized playback
- **[Snapcast](https://github.com/badaix/snapcast)**: Synchronized multiroom audio with low-latency streaming

## ✨ Key Features

- **Unlimited Players**: Create as many audio zones as you have outputs
- **Individual Volume Control**: Adjust each zone independently
- **Real-time Monitoring**: WebSocket-based live status updates
- **Auto-Discovery**: Players automatically appear in Music Assistant/LMS
- **Persistent Config**: Survives container restarts and updates

### 🎛️ **Intuitive Web Interface**
- Modern, responsive design that works on all devices
- Live status indicators and controls
- Audio device test tones for easy setup
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

### Image Variants

| Tag | Description | Size | Use Case |
|-----|-------------|------|----------|
| `latest` | Full image with Squeezelite + Sendspin + Snapcast | ~200MB | LMS users, mixed environments |
| `slim` | Sendspin only (no Squeezelite/Snapcast) | ~150MB | Music Assistant native users |
| `X.Y.Z` | Version-tagged full image | ~200MB | Production deployments |
| `X.Y.Z-slim` | Version-tagged slim image | ~150MB | Production MA deployments |

### Quick Deployment

**Full Image (Squeezelite + Sendspin + Snapcast)**
```bash
docker run -d \
  --name multiroom-audio \
  -p 8080:8080 \
  -v audio_config:/app/config \
  -v audio_logs:/app/logs \
  --device /dev/snd:/dev/snd \
  chrisuthe/squeezelitemultiroom:latest
```

**Slim Image (Sendspin Only - Music Assistant)**
```bash
docker run -d \
  --name sendspin-audio \
  -p 8080:8080 \
  -v audio_config:/app/config \
  -v audio_logs:/app/logs \
  --device /dev/snd:/dev/snd \
  chrisuthe/squeezelitemultiroom:slim
```

Access web interface at `http://localhost:8080`

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
3. **Player Type**: Choose your backend:
   - **Squeezelite**: For LMS/Logitech Media Server
   - **Sendspin**: For Music Assistant native protocol
   - **Snapcast**: For Snapcast synchronized multiroom audio
4. **Audio Device**: Select from auto-detected devices
5. **Server IP** (Squeezelite/Snapcast): Leave empty for auto-discovery, or enter IP manually
6. Click **"Create Player"**

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

# Create Squeezelite player
curl -X POST http://localhost:8080/api/players \
  -H "Content-Type: application/json" \
  -d '{"name": "Patio", "provider": "squeezelite", "device": "hw:3,0", "server_ip": "192.168.1.100"}'

# Create Sendspin player (Music Assistant native)
curl -X POST http://localhost:8080/api/players \
  -H "Content-Type: application/json" \
  -d '{"name": "Kitchen", "provider": "sendspin", "device": "hw:2,0"}'

# Create Snapcast player (synchronized multiroom)
curl -X POST http://localhost:8080/api/players \
  -H "Content-Type: application/json" \
  -d '{"name": "Office", "provider": "snapcast", "device": "hw:1,0", "server_ip": "192.168.1.50"}'

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
- **[Snapcast](https://github.com/badaix/snapcast)** by Johannes Pohl - Synchronous multiroom audio solution
- **[Music Assistant](https://music-assistant.io/)** - Modern music library management and multi-room audio platform
- **Flask Ecosystem** - Web framework and real-time communication libraries

For detailed license information, see [LICENSES.md](LICENSES.md).

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
- Music Assistant (recommended) - via Squeezelite or Sendspin
- Logitech Media Server (LMS) - via Squeezelite
- Snapcast Server - via Snapcast client
- Any SlimProto-compatible server - via Squeezelite
- Local audio files and streaming services

## 🔄 Player Type Comparison

| Feature | Squeezelite | Sendspin | Snapcast |
|---------|-------------|----------|----------|
| Protocol | SlimProto | Music Assistant Native | Snapcast |
| Server | LMS / Music Assistant | Music Assistant only | Snapcast Server |
| Sync | Yes (via server) | Yes (native) | Yes (native) |
| Latency | Low | Very low | Very low |
| Setup | Server IP optional | Auto-discovery | Server IP optional |
| Image | `latest` only | `latest` or `slim` | `latest` only |

---

<div align="center">
  
**🎵 Transform your space into a connected audio experience 🎵**

*Built with ❤️ for the open-source community*

[![Docker Hub](https://img.shields.io/badge/Docker%20Hub-chrisuthe%2Fsqueezelitemultiroom-blue?style=flat-square&logo=docker)](https://hub.docker.com/r/chrisuthe/squeezelitemultiroom)
[![GitHub](https://img.shields.io/badge/GitHub-Source%20Code-black?style=flat-square&logo=github)](https://github.com/yourusername/squeezelite-docker)

</div>