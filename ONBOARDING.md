# Multi-Room Audio Docker Controller - New Engineer Onboarding

Welcome! This guide will get you productive on this project as quickly as possible.

## What Is This Project?

A containerized multi-room audio controller supporting multiple player backends:
- **Squeezelite** - LMS/SlimProto protocol for Logitech Media Server
- **Sendspin** - Native Music Assistant protocol
- **Snapcast** - Synchronized multiroom audio

It provides:
- **Web UI** for managing audio players across multiple rooms/zones
- **REST API** for automation and integration
- **Real-time updates** via WebSocket
- **Hardware audio device support** via ALSA (Docker) or PulseAudio (HAOS)
- Integration with **Music Assistant** and **Logitech Media Server**
- **Home Assistant OS add-on** support

---

## Quick Start (5 minutes)

### 1. Clone and Run (No Audio - For Development)

```bash
docker-compose -f docker-compose.no-audio.yml up --build
```

Then open: http://localhost:8080

### 2. With Audio Hardware (Linux)

```bash
docker-compose up --build
```

---

## Project Structure

```
squeezelite-docker/
├── app/
│   ├── app.py                # Main Flask application factory
│   ├── common.py             # Shared Flask routes
│   ├── environment.py        # Environment detection (Docker vs HAOS)
│   ├── health_check.py       # Container health verification
│   ├── managers/
│   │   ├── audio_manager.py  # ALSA/PulseAudio device handling
│   │   ├── config_manager.py # YAML configuration persistence
│   │   ├── player_manager.py # High-level player orchestration
│   │   └── process_manager.py # Subprocess lifecycle management
│   ├── providers/
│   │   ├── base.py           # Abstract PlayerProvider interface
│   │   ├── squeezelite.py    # Squeezelite implementation
│   │   ├── sendspin.py       # Sendspin implementation
│   │   └── snapcast.py       # Snapcast implementation
│   ├── schemas/
│   │   └── player_config.py  # Pydantic validation schemas
│   ├── templates/
│   │   └── index.html        # Web UI (Bootstrap 5 + Socket.IO)
│   ├── static/
│   │   └── style.css         # Custom styling
│   └── swagger.yaml          # API documentation (OpenAPI 3.0)
├── hassio/                   # Home Assistant OS add-on
│   ├── config.yaml           # Add-on metadata
│   ├── Dockerfile            # Alpine-based build
│   └── DOCS.md               # Add-on documentation
├── tests/                    # Pytest test suite
├── Dockerfile                # Production container (Debian)
├── Dockerfile.slim           # Slim variant (Sendspin only)
└── docker-compose.yml        # Development/production config
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Docker Container                          │
├─────────────────────────────────────────────────────────────────┤
│  Flask App (app.py:8080)                                        │
│       │                                                          │
│  ┌────┴─────────────────────────────────────────────┐           │
│  │  PlayerManager                                    │           │
│  │       │                                           │           │
│  │  ┌────┴────────────────────────────────────┐     │           │
│  │  │  Provider Registry                       │     │           │
│  │  │  ├── SqueezeliteProvider                 │     │           │
│  │  │  ├── SendspinProvider                    │     │           │
│  │  │  └── SnapcastProvider                    │     │           │
│  │  └──────────────────────────────────────────┘     │           │
│  │       │                                           │           │
│  │  ┌────┴────────────────────────────────────┐     │           │
│  │  │  Managers                                │     │           │
│  │  │  ├── ConfigManager (YAML persistence)   │     │           │
│  │  │  ├── ProcessManager (subprocess)        │     │           │
│  │  │  └── AudioManager (ALSA/PulseAudio)     │     │           │
│  │  └──────────────────────────────────────────┘     │           │
│  └───────────────────────────────────────────────────┘           │
│       │                                                          │
│       ▼                                                          │
│  Player Processes (squeezelite, sendspin, snapclient)           │
│       │                                                          │
│       ▼                                                          │
│  Audio Devices (ALSA hw:X,Y or PulseAudio sinks)                │
└─────────────────────────────────────────────────────────────────┘
```

---

## Key Concepts

### 1. Providers
A provider is a player backend implementation:

| Provider | Binary | Protocol | Server |
|----------|--------|----------|--------|
| `squeezelite` | squeezelite | SlimProto | LMS / Music Assistant |
| `sendspin` | sendspin | Native | Music Assistant |
| `snapcast` | snapclient | Snapcast | Snapcast Server |

Each provider implements the `PlayerProvider` interface:
- `build_command()` - Generate CLI arguments
- `get_volume()` / `set_volume()` - Volume control
- `validate_config()` - Configuration validation
- `prepare_config()` - Default value generation

### 2. Players
A "player" is a configured audio zone that:
- Uses a specific provider (squeezelite, sendspin, or snapcast)
- Outputs to a specific audio device
- Has a unique name and identifier (MAC address or host ID)
- Can be started/stopped independently

### 3. Audio Devices
- **ALSA format**: `hw:X,Y` where X=card, Y=device
- **Virtual devices**: `null`, `pulse`, `dmix`, `default`
- **PulseAudio** (HAOS): Sink names from `pactl list sinks`

### 4. Environment Detection
The `environment.py` module detects runtime context:
- **Standalone Docker**: Uses ALSA directly
- **HAOS Add-on**: Uses PulseAudio via hassio_audio

### 5. Configuration Storage
Player configs stored in `/app/config/players.yaml`:
```yaml
LivingRoom:
  name: LivingRoom
  provider: squeezelite
  device: hw:1,0
  server_ip: 192.168.1.100
  mac_address: aa:bb:cc:dd:ee:ff
  enabled: true
  volume: 75

Kitchen:
  name: Kitchen
  provider: sendspin
  device: "0"
  volume: 80

Office:
  name: Office
  provider: snapcast
  device: hw:2,0
  server_ip: 192.168.1.50
  host_id: snapcast-office-abc123
```

---

## Data Flow

### Creating a Player
```
Web UI Form → POST /api/players → PlayerManager.create_player()
    → Provider.validate_config() → Provider.prepare_config()
    → ConfigManager.set_player() → ConfigManager.save() → Return success
```

### Starting a Player
```
Click Start → POST /api/players/{name}/start → PlayerManager.start_player()
    → Provider.build_command() → ProcessManager.start_process()
    → subprocess.Popen() → Status monitor → WebSocket update → UI updates
```

### Volume Control
```
Slider move → debounce 300ms → POST /api/players/{name}/volume
    → Provider.set_volume() → AudioManager.set_volume()
    → amixer/pactl command → Return success
```

---

## API Quick Reference

Full docs at http://localhost:8080/api/docs

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/api/players` | List all players |
| `POST` | `/api/players` | Create new player |
| `POST` | `/api/players/{name}/start` | Start a player |
| `POST` | `/api/players/{name}/stop` | Stop a player |
| `POST` | `/api/players/{name}/volume` | Set volume (0-100) |
| `DELETE` | `/api/players/{name}` | Delete a player |
| `GET` | `/api/devices` | List ALSA audio devices |
| `GET` | `/api/devices/portaudio` | List PortAudio devices (for Sendspin) |
| `POST` | `/api/devices/{device}/test` | Play test tone |

---

## Development Workflow

### Running Locally Without Docker

```bash
cd app
pip install -r ../requirements.txt
python -c "from app import create_app; create_app().run(host='0.0.0.0', port=8080)"
```

Note: Audio features require Linux (ALSA) or HAOS (PulseAudio).

### Running Tests

```bash
# All tests
pytest tests/ -v

# Specific test file
pytest tests/test_squeezelite_provider.py -v

# With coverage
pytest tests/ --cov=app --cov-report=html
```

### Linting

```bash
ruff check .
ruff format .
```

### Testing Without Hardware

Use `docker-compose.no-audio.yml` or set `WINDOWS_MODE=true`:
- Skips audio device detection
- Allows player creation with `null` device
- Simulates player start/stop

---

## Code Organization

### Managers (`app/managers/`)

| Manager | Responsibility |
|---------|----------------|
| `AudioManager` | ALSA device enumeration, volume control, test tones |
| `ConfigManager` | YAML file read/write, player config CRUD |
| `ProcessManager` | Subprocess lifecycle, PID tracking, log management |
| `PlayerManager` | High-level orchestration, provider coordination |

### Providers (`app/providers/`)

| Provider | Key Methods |
|----------|-------------|
| `SqueezeliteProvider` | `build_command()`, `generate_mac_address()` |
| `SendspinProvider` | `build_command()`, PortAudio device handling |
| `SnapcastProvider` | `build_command()`, `generate_host_id()` |

### Schemas (`app/schemas/`)

Pydantic models for configuration validation:
- `SqueezelitePlayerConfig`
- `SendspinPlayerConfig`
- `SnapcastPlayerConfig`

---

## Adding a New Provider

1. Create `app/providers/newplayer.py`:
```python
from .base import PlayerProvider, PlayerConfig

class NewPlayerProvider(PlayerProvider):
    provider_type = "newplayer"
    display_name = "New Player"
    binary_name = "newplayer-binary"

    def build_command(self, player: PlayerConfig, log_path: str) -> list[str]:
        return [self.binary_name, "-o", player["device"]]

    # Implement other abstract methods...
```

2. Register in `app/providers/__init__.py`
3. Register in `app/app.py` (provider_registry)
4. Add schema in `app/schemas/player_config.py`
5. Update `health_check.py` to check binary
6. Update Dockerfile to install binary
7. Add tests in `tests/test_newplayer_provider.py`

---

## HAOS Add-on Development

The `hassio/` directory contains Home Assistant OS add-on files:

```bash
# Build locally
cd hassio
docker build --build-arg BUILD_FROM=ghcr.io/home-assistant/amd64-base-python:3.11 -t multiroom-addon .

# Test in HAOS
# Copy hassio/ folder to /addons/multiroom-audio on your HA instance
# Go to Settings → Add-ons → Local add-ons → Refresh → Install
```

Key differences from standalone Docker:
- Uses PulseAudio instead of ALSA
- Config stored in `/data` instead of `/app/config`
- Alpine Linux base instead of Debian

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Backend** | Python 3.11+, Flask, Pydantic |
| **Real-time** | Flask-SocketIO, Socket.IO |
| **Frontend** | Bootstrap 5, Vanilla JS |
| **Audio** | Squeezelite, Sendspin, Snapcast, ALSA, PulseAudio |
| **Container** | Docker (Debian/Alpine) |
| **Testing** | pytest, pytest-mock |
| **Linting** | Ruff |

---

## Gotchas & Tips

1. **Provider determines device format**:
   - Squeezelite/Snapcast: ALSA (`hw:0,0`)
   - Sendspin: PortAudio index (`0`, `1`, `2`)

2. **MAC addresses auto-generated** from player name hash (Squeezelite)

3. **Host IDs auto-generated** from player name hash (Snapcast)

4. **Environment detection** happens at import time - restart needed for changes

5. **HAOS uses PulseAudio** - ALSA device names get converted to `pulse`

6. **Test tones** use speaker-test (ALSA) or sounddevice (PortAudio)

7. **Status updates every 2 seconds** via WebSocket

---

## Getting Help

- [README.md](README.md) - User documentation
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - Detailed architecture
- [BUILD-GUIDE.md](BUILD-GUIDE.md) - Build troubleshooting
- [hassio/DOCS.md](hassio/DOCS.md) - HAOS add-on documentation
- API docs at http://localhost:8080/api/docs
