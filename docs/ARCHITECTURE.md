# Multi-Room Audio Player Architecture

This document describes the architecture for supporting multiple audio player providers (Squeezelite, Sendspin, Snapcast) in a maintainable, extensible way.

---

## Table of Contents

1. [Current State](#current-state)
2. [Goals](#goals)
3. [Architecture Overview](#architecture-overview)
4. [Component Responsibilities](#component-responsibilities)
5. [Provider Abstraction](#provider-abstraction)
6. [Environment Detection](#environment-detection)
7. [Configuration Schema](#configuration-schema)
8. [Volume Control Strategy](#volume-control-strategy)
9. [API Reference](#api-reference)
10. [File Structure](#file-structure)
11. [Future Considerations](#future-considerations)

---

## Current State

The application uses a modular architecture with focused manager classes and a provider abstraction:

**Manager Classes** (`app/managers/`):
- `ConfigManager`: Configuration persistence (YAML load/save)
- `AudioManager`: Device detection and volume control (ALSA/PulseAudio)
- `ProcessManager`: Subprocess lifecycle (start/stop/status)
- `PlayerManager`: High-level orchestration (optional, coordinates managers)

**Provider Classes** (`app/providers/`):
- `PlayerProvider`: Abstract base class for audio backends
- `SqueezeliteProvider`: Logitech Media Server / Music Assistant (SlimProto)
- `SendspinProvider`: Music Assistant (native protocol)
- `SnapcastProvider`: Snapcast synchronized multiroom audio
- `ProviderRegistry`: Provider discovery and lookup

**Environment Detection** (`app/environment.py`):
- Detects standalone Docker vs. HAOS add-on environment
- Configures audio backend (ALSA vs PulseAudio) accordingly

**Schema Validation** (`app/schemas/`):
- Pydantic models for type-safe configuration validation
- Provider-specific schemas with field validation

---

## Goals

1. **Support Multiple Providers**: Squeezelite, Sendspin, Snapcast, and future additions
2. **Multi-Environment**: Works in standalone Docker and Home Assistant OS
3. **Maintainability**: Each component has a single responsibility
4. **Testability**: Components can be unit tested in isolation
5. **Backward Compatibility**: Existing configurations continue to work

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Flask Application                         │
│                           (app.py)                               │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│ ConfigManager │    │ AudioManager  │    │ ProcessManager│
│               │    │               │    │               │
│ - load()      │    │ - get_devices │    │ - start()     │
│ - save()      │    │ - get_volume  │    │ - stop()      │
│ - get/set     │    │ - set_volume  │    │ - is_running  │
│ - validate()  │    │ - test_tone   │    │ - cleanup()   │
└───────────────┘    └───────────────┘    └───────────────┘
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
            ┌─────────────┐     ┌─────────────┐
            │    ALSA     │     │ PulseAudio  │
            │  (Docker)   │     │   (HAOS)    │
            └─────────────┘     └─────────────┘

┌───────────────────────────────────────────────────────────────┐
│                     ProviderRegistry                           │
│                                                                 │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐  │
│  │ Squeezelite     │ │ Sendspin        │ │ Snapcast        │  │
│  │ Provider        │ │ Provider        │ │ Provider        │  │
│  │                 │ │                 │ │                 │  │
│  │ - build_cmd()   │ │ - build_cmd()   │ │ - build_cmd()   │  │
│  │ - validate()    │ │ - validate()    │ │ - validate()    │  │
│  │ - get_volume()  │ │ - get_volume()  │ │ - get_volume()  │  │
│  │ - set_volume()  │ │ - set_volume()  │ │ - set_volume()  │  │
│  └─────────────────┘ └─────────────────┘ └─────────────────┘  │
└───────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────┐
│                   Environment Detection                        │
│                    (environment.py)                            │
│                                                                 │
│  - is_hassio()           - Detect HAOS environment            │
│  - get_audio_backend()   - Return 'alsa' or 'pulse'           │
│  - get_config_path()     - Return appropriate config dir       │
│  - get_player_backend()  - Return Snapcast --player arg        │
└───────────────────────────────────────────────────────────────┘
```

---

## Component Responsibilities

### ConfigManager

Handles configuration persistence and validation.

```python
class ConfigManager:
    def __init__(self, config_path: str, validate_on_load: bool = True)
    def load(self) -> dict[str, PlayerConfig]
    def save(self) -> bool
    def get_player(self, name: str) -> PlayerConfig | None
    def set_player(self, name: str, config: PlayerConfig) -> tuple[bool, str]
    def delete_player(self, name: str) -> bool
    def rename_player(self, old: str, new: str) -> bool
    def validate_config(self, config: dict, name: str = None) -> tuple[bool, str]
```

### AudioManager

Handles audio device detection and volume control.

```python
class AudioManager:
    def __init__(self, windows_mode: bool = False)
    def get_audio_devices(self) -> list[dict]
    def get_volume(self, device: str) -> int
    def set_volume(self, device: str, volume: int) -> tuple[bool, str]
    def get_mixer_controls(self, device: str) -> list[str]
    def is_virtual_device(self, device: str) -> bool
    def play_test_tone(self, device: str, duration: float, frequency: int) -> tuple[bool, str]
```

### ProcessManager

Handles subprocess lifecycle.

```python
class ProcessManager:
    def __init__(self, log_dir: str = "/app/logs")
    def start_process(self, name: str, command: list[str]) -> tuple[bool, str]
    def stop_process(self, name: str, timeout: float = 5.0) -> tuple[bool, str]
    def is_running(self, name: str) -> bool
    def get_all_statuses(self) -> dict[str, bool]
    def cleanup(self) -> None
```

### PlayerProvider (Abstract)

Base interface for audio player backends.

```python
class PlayerProvider(ABC):
    provider_type: str      # Unique identifier
    display_name: str       # Human-readable name
    binary_name: str        # Executable name

    def build_command(self, player: PlayerConfig, log_path: str) -> list[str]
    def build_fallback_command(self, player: PlayerConfig, log_path: str) -> list[str] | None
    def get_volume(self, player: PlayerConfig) -> int
    def set_volume(self, player: PlayerConfig, volume: int) -> tuple[bool, str]
    def validate_config(self, config: dict) -> tuple[bool, str]
    def get_default_config(self) -> dict
    def prepare_config(self, config: dict) -> dict
```

---

## Provider Abstraction

### Implemented Providers

| Provider | Binary | Protocol | Server | Audio Backend |
|----------|--------|----------|--------|---------------|
| `SqueezeliteProvider` | squeezelite | SlimProto | LMS / Music Assistant | ALSA / PulseAudio |
| `SendspinProvider` | sendspin | Native | Music Assistant | PortAudio |
| `SnapcastProvider` | snapclient | Snapcast | Snapcast Server | ALSA / PulseAudio |

### SqueezeliteProvider

```python
class SqueezeliteProvider(PlayerProvider):
    provider_type = "squeezelite"
    display_name = "Squeezelite"
    binary_name = "squeezelite"

    def build_command(self, player, log_path):
        # Uses environment detection for output device
        output_device = get_squeezelite_output_device(player["device"])
        return [
            "squeezelite",
            "-n", player["name"],
            "-o", output_device,
            "-m", player["mac_address"],
            "-s", player.get("server_ip", ""),
            "-f", log_path,
            "-a", "80", "-b", "500:2000", "-C", "5"
        ]

    @staticmethod
    def generate_mac_address(name: str) -> str:
        # MD5-based deterministic MAC generation
        ...
```

### SendspinProvider

```python
class SendspinProvider(PlayerProvider):
    provider_type = "sendspin"
    display_name = "Sendspin"
    binary_name = "sendspin"

    def build_command(self, player, log_path):
        cmd = ["sendspin", "--name", player["name"]]
        # Sendspin uses PortAudio device indices, not ALSA
        device = player.get("device", "")
        if device and not device.startswith("hw:"):
            cmd.extend(["--audio-device", device])
        return cmd
```

### SnapcastProvider

```python
class SnapcastProvider(PlayerProvider):
    provider_type = "snapcast"
    display_name = "Snapcast"
    binary_name = "snapclient"

    def build_command(self, player, log_path):
        # Uses environment detection for player backend
        player_backend = get_player_backend_for_snapcast()  # 'alsa' or 'pulse'
        return [
            "snapclient",
            "--host", player.get("server_ip", ""),
            "--soundcard", player.get("device", "default"),
            "--hostID", player.get("host_id", ""),
            "--player", player_backend,
            "--logsink", f"file:{log_path}"
        ]

    @staticmethod
    def generate_host_id(name: str) -> str:
        # MD5-based deterministic host ID generation
        ...
```

---

## Environment Detection

The `environment.py` module enables the application to run in multiple contexts:

### Supported Environments

| Environment | Detection | Audio Backend | Config Path |
|-------------|-----------|---------------|-------------|
| Standalone Docker | Default | ALSA | `/app/config` |
| HAOS Add-on | `/data/options.json` exists | PulseAudio | `/data` |

### Key Functions

```python
def is_hassio() -> bool:
    """Check if running inside Home Assistant OS."""
    return os.path.exists("/data/options.json")

def get_audio_backend() -> str:
    """Return 'pulse' for HAOS, 'alsa' for standalone."""
    return "pulse" if is_hassio() else "alsa"

def get_player_backend_for_snapcast() -> str:
    """Return appropriate --player argument for snapclient."""
    return "pulse" if is_hassio() else "alsa"

def get_squeezelite_output_device(device: str) -> str:
    """Convert ALSA device to PulseAudio if in HAOS."""
    if is_hassio() and device.startswith("hw:"):
        return "pulse"
    return device
```

---

## Configuration Schema

### Player Configuration

```yaml
# /app/config/players.yaml
LivingRoom:
  name: LivingRoom
  provider: squeezelite
  device: hw:0,0
  server_ip: 192.168.1.100
  mac_address: aa:bb:cc:dd:ee:ff
  enabled: true
  volume: 75
  autostart: false

Kitchen:
  name: Kitchen
  provider: sendspin
  device: "0"
  volume: 80
  autostart: true

Office:
  name: Office
  provider: snapcast
  device: hw:1,0
  server_ip: 192.168.1.50
  host_id: snapcast-office-abc123
  latency: 0
  volume: 75
```

### Pydantic Schemas

```python
# app/schemas/player_config.py

class SqueezelitePlayerConfig(BaseModel):
    name: str
    device: str
    provider: Literal["squeezelite"] = "squeezelite"
    server_ip: str = ""
    mac_address: str = ""
    volume: int = Field(ge=0, le=100, default=75)
    enabled: bool = True
    autostart: bool = False

class SendspinPlayerConfig(BaseModel):
    name: str
    device: str = ""
    provider: Literal["sendspin"] = "sendspin"
    volume: int = Field(ge=0, le=100, default=75)
    enabled: bool = True
    autostart: bool = False

class SnapcastPlayerConfig(BaseModel):
    name: str
    device: str = "default"
    provider: Literal["snapcast"] = "snapcast"
    server_ip: str = ""
    host_id: str = ""
    latency: int = 0
    volume: int = Field(ge=0, le=100, default=75)
    enabled: bool = True
    autostart: bool = False
```

---

## Volume Control Strategy

### Per-Provider Volume Control

| Provider | Method | Implementation |
|----------|--------|----------------|
| Squeezelite | ALSA amixer | `amixer -c {card} sset {control} {volume}%` |
| Sendspin | ALSA amixer | Same as Squeezelite |
| Snapcast | ALSA amixer | Same as Squeezelite (JSON-RPC optional future) |

All providers currently delegate to `AudioManager` for volume control, which uses ALSA amixer commands. In HAOS environments, PulseAudio is used instead.

---

## API Reference

### Core Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/api/players` | List all players with status |
| `POST` | `/api/players` | Create new player |
| `GET` | `/api/players/{name}` | Get player details |
| `PUT` | `/api/players/{name}` | Update player |
| `DELETE` | `/api/players/{name}` | Delete player |
| `POST` | `/api/players/{name}/start` | Start player |
| `POST` | `/api/players/{name}/stop` | Stop player |
| `POST` | `/api/players/{name}/volume` | Set volume |
| `GET` | `/api/providers` | List available providers |
| `GET` | `/api/devices` | List ALSA audio devices |
| `GET` | `/api/devices/portaudio` | List PortAudio devices |
| `POST` | `/api/devices/{device}/test` | Play test tone |

### Provider Response

```json
GET /api/providers
{
    "providers": [
        {
            "type": "squeezelite",
            "display_name": "Squeezelite",
            "binary": "squeezelite",
            "available": true
        },
        {
            "type": "sendspin",
            "display_name": "Sendspin",
            "binary": "sendspin",
            "available": true
        },
        {
            "type": "snapcast",
            "display_name": "Snapcast",
            "binary": "snapclient",
            "available": true
        }
    ]
}
```

---

## File Structure

```
app/
├── __init__.py
├── app.py                    # Flask application factory & routes
├── common.py                 # Shared route registration
├── environment.py            # Environment detection (Docker vs HAOS)
├── health_check.py           # Container health verification
├── managers/
│   ├── __init__.py
│   ├── audio_manager.py      # Device detection, volume, test tones
│   ├── config_manager.py     # YAML configuration persistence
│   ├── player_manager.py     # High-level player orchestration
│   └── process_manager.py    # Subprocess lifecycle
├── providers/
│   ├── __init__.py           # Provider exports
│   ├── base.py               # PlayerProvider ABC, ProviderRegistry
│   ├── squeezelite.py        # SqueezeliteProvider
│   ├── sendspin.py           # SendspinProvider
│   └── snapcast.py           # SnapcastProvider
├── schemas/
│   ├── __init__.py
│   └── player_config.py      # Pydantic validation models
├── templates/
│   └── index.html            # Web UI
├── static/
│   └── style.css             # Custom styling
└── swagger.yaml              # OpenAPI specification

hassio/                       # Home Assistant OS add-on
├── config.yaml               # Add-on metadata
├── Dockerfile                # Alpine-based build
├── run.sh                    # Startup script (bashio)
├── DOCS.md                   # Add-on documentation
├── CHANGELOG.md              # Version history
└── translations/
    └── en.yaml               # Option descriptions

tests/
├── conftest.py               # Pytest fixtures
├── test_audio_manager.py
├── test_config_manager.py
├── test_process_manager.py
├── test_squeezelite_provider.py
├── test_sendspin_provider.py
├── test_snapcast_provider.py
└── test_player_config_schema.py
```

---

## Future Considerations

### Potential Future Providers

| Provider | Binary | Use Case |
|----------|--------|----------|
| **MPD Client** | `mpc` | Direct MPD control |
| **Bluetooth** | `bluealsa-aplay` | Bluetooth speaker output |
| **AirPlay** | `shairport-sync` | AirPlay receiver |
| **PipeWire** | `pw-play` | Modern Linux audio |

### Snapcast JSON-RPC Volume Control

Future enhancement to control Snapcast volume via server API instead of ALSA:

```python
class SnapcastVolumeBackend:
    def set_volume(self, player, volume):
        # JSON-RPC call to http://{server_ip}:1705/jsonrpc
        # Method: Client.SetVolume
        ...
```

### Plugin Architecture

Future enhancement for external provider plugins:

```python
# Auto-discover providers from /app/providers/custom/*.py
for module in discover_custom_providers():
    provider_registry.register(module.Provider())
```

---

## Decision Log

| Decision | Rationale | Date |
|----------|-----------|------|
| Provider abstraction | Enables multiple player types without modifying core | 2024-12 |
| Environment detection | Support both Docker and HAOS without code changes | 2024-12 |
| ALSA volume for all providers | Consistent, simple; JSON-RPC optional later | 2024-12 |
| Pydantic for validation | Type safety, clear error messages | 2024-12 |
| MD5 for ID generation | Deterministic, fast, suitable for non-crypto use | 2024-12 |
| Sendspin for Music Assistant | Native protocol, better sync than SlimProto | 2024-12 |
| Snapcast support | Popular synchronized audio solution | 2024-12 |
| HAOS add-on in monorepo | Shared code, easier maintenance | 2024-12 |
