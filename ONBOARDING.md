# Squeezelite Multi-Room Docker Controller - New Engineer Onboarding

Welcome! This guide will get you productive on this project as quickly as possible.

## What Is This Project?

A containerized multi-room audio controller built around **Squeezelite**, a lightweight audio player. It provides:
- **Web UI** for managing audio players across multiple rooms/zones
- **REST API** for automation and integration
- **Real-time updates** via WebSocket
- **Hardware audio device support** via ALSA
- Integration with **Music Assistant** and **Logitech Media Server**

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

## Project Structure at a Glance

```
squeezelite-docker/
├── app/
│   ├── app.py              # Main Flask app (USE THIS)
│   ├── app_enhanced.py     # Extended version with state persistence
│   ├── health_check.py     # Container health verification
│   ├── templates/
│   │   └── index.html      # Web UI (Bootstrap 5 + Socket.IO)
│   ├── static/
│   │   └── style.css       # Custom styling
│   └── swagger.yaml        # API documentation (OpenAPI 3.0)
├── config/
│   └── players.yaml        # Player configurations (auto-generated)
├── Dockerfile              # Container definition
├── docker-compose.yml      # Production config
├── entrypoint.sh           # Container startup script
└── supervisord.conf        # Process management
```

---

## Key Files to Understand First

### Priority 1: Core Application Logic

| File | Purpose | Lines | Read This For |
|------|---------|-------|---------------|
| [app/app.py](app/app.py) | Main Flask application | 826 | Everything: API routes, player management, audio control |
| [app/templates/index.html](app/templates/index.html) | Web interface | ~700 | UI logic, WebSocket handling, API calls |

### Priority 2: Configuration & Infrastructure

| File | Purpose | Read This For |
|------|---------|---------------|
| [swagger.yaml](app/swagger.yaml) | API specification | Understanding all REST endpoints |
| [Dockerfile](Dockerfile) | Container build | System dependencies, audio libraries |
| [supervisord.conf](supervisord.conf) | Process supervision | How the app is started/managed |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Docker Container                          │
├─────────────────────────────────────────────────────────────────┤
│  supervisord                                                     │
│       │                                                          │
│       ▼                                                          │
│  Flask App (app.py:8080)                                        │
│       │                                                          │
│  ┌────┴─────────────────────────────────────────────┐           │
│  │  SqueezeliteManager                              │           │
│  │  ├── Player Configuration (YAML)                 │           │
│  │  ├── Process Management (subprocess)             │           │
│  │  ├── Audio Device Detection (aplay)              │           │
│  │  └── Volume Control (amixer)                     │           │
│  └──────────────────────────────────────────────────┘           │
│       │                                                          │
│       ▼                                                          │
│  Squeezelite Processes (one per audio player)                   │
│       │                                                          │
│       ▼                                                          │
│  ALSA Audio Devices                                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## Key Concepts

### 1. Players
A "player" is a Squeezelite instance that:
- Connects to a Logitech Media Server (or Music Assistant)
- Outputs audio to a specific device (soundcard, virtual device, etc.)
- Has a unique name and MAC address

### 2. Audio Devices
Identified as `hw:X,Y` format:
- `X` = Card number
- `Y` = Device number
- Special devices: `null` (testing), `pulse` (PulseAudio), `default`

### 3. Configuration Storage
All player configs stored in `/app/config/players.yaml`:
```yaml
LivingRoom:
  name: LivingRoom
  device: hw:1,0
  server_ip: 192.168.1.100
  mac_address: aa:bb:cc:dd:ee:ff
  enabled: true
  volume: 75
```

---

## Data Flow: How Things Work

### Creating a Player
```
Web UI Form → POST /api/players → SqueezeliteManager.create_player()
    → Generate MAC if needed → Save to players.yaml → Return success
```

### Starting a Player
```
Click Start → POST /api/players/{name}/start → subprocess.Popen(squeezelite ...)
    → Process starts → Status monitor detects → WebSocket update → UI updates
```

### Volume Control
```
Slider move → debounce 300ms → POST /api/players/{name}/volume
    → amixer command → Update config → Return success
```

### Real-time Status Updates
```
Background thread (2s interval) → Check all processes → WebSocket emit
    → Browser receives → Update all status indicators
```

---

## API Quick Reference

The API is fully documented in Swagger UI: http://localhost:8080/api/docs

### Most Used Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/api/players` | List all players |
| `POST` | `/api/players` | Create new player |
| `POST` | `/api/players/{name}/start` | Start a player |
| `POST` | `/api/players/{name}/stop` | Stop a player |
| `POST` | `/api/players/{name}/volume` | Set volume (0-100) |
| `DELETE` | `/api/players/{name}` | Delete a player |
| `GET` | `/api/devices` | List audio devices |

---

## Development Workflow

### Running Locally Without Docker

```bash
cd app
pip install -r ../requirements.txt
python app.py
```

Note: Audio features won't work on Windows/Mac (ALSA is Linux-only).

### Making Changes

1. Edit `app/app.py` for backend changes
2. Edit `app/templates/index.html` for UI changes
3. Changes to static files (`style.css`) apply immediately
4. Python changes require restart (or use Flask debug mode)

### Testing Without Hardware

Use `docker-compose.no-audio.yml` - it sets `WINDOWS_MODE=true` which:
- Skips audio device detection
- Allows player creation with `null` device
- Simulates player start/stop

---

## Common Tasks

### Add a New API Endpoint

1. Add route in `app/app.py`:
```python
@app.route('/api/my-endpoint', methods=['GET'])
def my_endpoint():
    """Short description for Swagger."""
    return jsonify({'status': 'success'})
```

2. Document in `app/swagger.yaml`

### Add a New Player Setting

1. Update `create_player()` in `app/app.py` to accept the new field
2. Update `update_player()` similarly
3. Add UI input in `index.html` (in the add/edit modals)
4. Update `swagger.yaml`

### Debug Audio Issues

1. Check available devices: `GET /api/devices`
2. Check debug info: `GET /api/debug/audio`
3. View container logs: `docker logs squeezelite-docker`
4. Shell into container: `docker exec -it squeezelite-docker bash`

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Backend** | Python 3.10, Flask 2.3.3 |
| **Real-time** | Flask-SocketIO, Socket.IO |
| **Frontend** | Bootstrap 5, Vanilla JS |
| **Audio** | Squeezelite, ALSA |
| **Container** | Docker, Ubuntu 22.04 |
| **Process Mgmt** | Supervisor |

---

## Code Locations for Specific Tasks

| Task | Where to Look |
|------|---------------|
| Player lifecycle | `app.py:600-750` (create/update/delete) |
| Process management | `app.py:380-500` (start/stop) |
| Audio device detection | `app.py:240-280` (get_audio_devices) |
| Volume control | `app.py:500-550` (amixer integration) |
| Real-time updates | `app.py:730-750` (status_monitor thread) |
| WebSocket handling | `index.html:300+` (socket.on events) |
| Form handling | `index.html:400+` (handleAddPlayerForm) |

---

## Gotchas & Tips

1. **MAC addresses are auto-generated** using MD5 hash of player name if not provided

2. **Volume control tries multiple ALSA controls** in order: Master, PCM, Speaker, Headphone, etc.

3. **Two versions of app.py exist**:
   - `app.py` - Standard version
   - `app_enhanced.py` - Adds state persistence (players restart after container restart)

4. **Status updates are every 2 seconds** - don't expect instant UI updates

5. **Audio devices must be passed through** to Docker container via `--device` flag

6. **Windows/Mac can only test UI** - audio features require Linux ALSA

---

## Getting Help

- Check [README.md](README.md) for deployment options
- Check [BUILD-GUIDE.md](BUILD-GUIDE.md) for build troubleshooting
- API docs at http://localhost:8080/api/docs
- Container health: `GET /api/health`

---

## Next Steps

1. Run the project with `docker-compose.no-audio.yml`
2. Create a test player through the UI
3. Explore the API via Swagger UI
4. Read through `app.py` focusing on `SqueezeliteManager` class
5. Make a small change (e.g., add a log message) and rebuild
