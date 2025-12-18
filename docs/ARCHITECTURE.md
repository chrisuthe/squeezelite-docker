# Multi-Room Audio Player Architecture

This document describes the architecture for supporting multiple audio player providers (Squeezelite, Snapcast, and future additions) in a maintainable, extensible way.

---

## Table of Contents

1. [Current State](#current-state)
2. [Goals](#goals)
3. [Proposed Architecture](#proposed-architecture)
4. [Component Responsibilities](#component-responsibilities)
5. [Provider Abstraction](#provider-abstraction)
6. [Configuration Schema](#configuration-schema)
7. [Volume Control Strategy](#volume-control-strategy)
8. [Migration Plan](#migration-plan)
9. [API Changes](#api-changes)
10. [Future Considerations](#future-considerations)

---

## Current State

The application currently has a monolithic `SqueezeliteManager` class (~800 lines) that handles:

- Configuration persistence (YAML load/save)
- Process management (subprocess start/stop/status)
- Audio device detection (aplay parsing)
- Volume control (amixer commands)
- Player CRUD operations
- Squeezelite-specific command building

### Problems with Current Design

1. **Single Responsibility Violation**: One class does too many things
2. **Not Extensible**: Adding a new player type requires modifying the core class
3. **Hard to Test**: Tightly coupled components make unit testing difficult
4. **Squeezelite-Specific**: Logic is hardcoded for one player type

---

## Goals

1. **Support Multiple Providers**: Squeezelite, Snapcast, and future additions
2. **Maintainability**: Each component has a single responsibility
3. **Testability**: Components can be unit tested in isolation
4. **Backward Compatibility**: Existing configurations continue to work
5. **Minimal API Changes**: Preserve existing REST API where possible

---

## Proposed Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        PlayerManager                             │
│  Orchestrates players, handles API requests, coordinates components │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│ ConfigManager │    │ AudioManager  │    │ ProcessManager│
│               │    │               │    │               │
│ - load()      │    │ - get_devices │    │ - start()     │
│ - save()      │    │ - get_volume  │    │ - stop()      │
│ - validate()  │    │ - set_volume  │    │ - status()    │
│ - migrate()   │    │ - get_controls│    │ - list()      │
└───────────────┘    └───────────────┘    └───────────────┘
                              │
                              ▼
                    ┌───────────────────┐
                    │  VolumeBackend    │
                    │  (per provider)   │
                    └───────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│ AlsaVolume    │    │SnapcastVolume │    │ SoftwareVolume│
│ (amixer)      │    │ (JSON-RPC)    │    │ (stored only) │
└───────────────┘    └───────────────┘    └───────────────┘

                    ┌───────────────────┐
                    │ ProviderRegistry  │
                    │                   │
                    │ - register()      │
                    │ - get()           │
                    │ - list()          │
                    └───────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ SqueezeliteProvider │  │ SnapcastProvider │  │ (Future)       │
│                 │  │                 │  │                 │
│ - build_cmd()   │  │ - build_cmd()   │  │ - build_cmd()   │
│ - schema()      │  │ - schema()      │  │ - schema()      │
│ - validate()    │  │ - validate()    │  │ - validate()    │
│ - volume_backend│  │ - volume_backend│  │ - volume_backend│
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

---

## Component Responsibilities

### PlayerManager

The main orchestrator that coordinates all other components.

```python
class PlayerManager:
    """
    Central coordinator for multi-room audio players.

    Delegates specialized tasks to focused manager classes while
    maintaining the high-level player lifecycle operations.
    """

    def __init__(
        self,
        config: ConfigManager,
        audio: AudioManager,
        process: ProcessManager,
        providers: ProviderRegistry,
    ) -> None: ...

    # Player CRUD
    def create_player(self, name: str, provider: str, device: str, **config) -> tuple[bool, str]
    def update_player(self, name: str, **updates) -> tuple[bool, str]
    def delete_player(self, name: str) -> tuple[bool, str]
    def get_player(self, name: str) -> PlayerConfig | None
    def list_players(self) -> dict[str, PlayerConfig]

    # Player lifecycle
    def start_player(self, name: str) -> tuple[bool, str]
    def stop_player(self, name: str) -> tuple[bool, str]
    def restart_player(self, name: str) -> tuple[bool, str]
    def get_status(self, name: str) -> bool
    def get_all_statuses(self) -> dict[str, bool]

    # Volume (delegates to provider's volume backend)
    def get_volume(self, name: str) -> int | None
    def set_volume(self, name: str, volume: int) -> tuple[bool, str]
```

### ConfigManager

Handles configuration persistence and validation.

```python
class ConfigManager:
    """
    Manages player configuration persistence.

    Responsibilities:
    - Load/save configuration from YAML files
    - Validate configuration against provider schemas
    - Handle configuration migrations between versions
    """

    def __init__(self, config_path: str, providers: ProviderRegistry) -> None: ...

    def load(self) -> dict[str, PlayerConfig]
    def save(self, players: dict[str, PlayerConfig]) -> None
    def validate(self, config: PlayerConfig) -> tuple[bool, list[str]]
    def migrate(self, config: dict) -> dict  # Handle schema changes
```

### AudioManager

Handles audio device detection (provider-agnostic).

```python
class AudioManager:
    """
    Manages audio device detection and enumeration.

    This is provider-agnostic - it detects what ALSA devices
    are available on the system.
    """

    def get_devices(self) -> list[AudioDevice]
    def get_device_info(self, device_id: str) -> AudioDevice | None
    def get_mixer_controls(self, device_id: str) -> list[str]
```

### ProcessManager

Handles subprocess lifecycle (provider-agnostic).

```python
class ProcessManager:
    """
    Manages subprocess lifecycle for audio players.

    Provider-agnostic - just starts/stops/monitors processes
    given a command to run.
    """

    def start(self, name: str, command: list[str]) -> tuple[bool, str]
    def stop(self, name: str, timeout: float = 5.0) -> tuple[bool, str]
    def is_running(self, name: str) -> bool
    def get_all_statuses(self) -> dict[str, bool]
    def get_process(self, name: str) -> subprocess.Popen | None
```

### VolumeBackend (Abstract)

Interface for provider-specific volume control.

```python
class VolumeBackend(ABC):
    """
    Abstract interface for volume control.

    Different providers control volume differently:
    - Squeezelite: Local ALSA mixer (amixer)
    - Snapcast: Server-side via JSON-RPC API
    - Others: May be software-only (stored value)
    """

    @abstractmethod
    def get_volume(self, player: PlayerConfig) -> int: ...

    @abstractmethod
    def set_volume(self, player: PlayerConfig, volume: int) -> tuple[bool, str]: ...

    @property
    @abstractmethod
    def supports_hardware_control(self) -> bool: ...
```

---

## Provider Abstraction

### PlayerProvider (Abstract Base Class)

```python
class PlayerProvider(ABC):
    """
    Base class for audio player providers.

    Each provider (Squeezelite, Snapcast, etc.) implements this
    interface to define how to build commands, validate config,
    and control volume.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique provider identifier (e.g., 'squeezelite', 'snapcast')."""
        ...

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable name for UI."""
        ...

    @property
    @abstractmethod
    def binary(self) -> str:
        """Binary/executable name to run."""
        ...

    @abstractmethod
    def build_command(self, config: PlayerConfig) -> list[str]:
        """Build the command line to start this player."""
        ...

    @abstractmethod
    def get_config_schema(self) -> dict:
        """
        Return JSON Schema for provider-specific config fields.

        Example for Squeezelite:
        {
            "server_ip": {"type": "string", "format": "ipv4", "required": False},
            "mac_address": {"type": "string", "pattern": "^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$"}
        }
        """
        ...

    @abstractmethod
    def validate_config(self, config: dict) -> tuple[bool, list[str]]:
        """Validate provider-specific configuration."""
        ...

    @abstractmethod
    def get_volume_backend(self) -> VolumeBackend:
        """Return the volume control backend for this provider."""
        ...

    def get_default_config(self) -> dict:
        """Default values for new players of this type."""
        return {}

    def generate_unique_id(self, name: str) -> str:
        """Generate a unique identifier (e.g., MAC address) for this player."""
        import hashlib
        hash_obj = hashlib.md5(name.encode())
        mac_hex = hash_obj.hexdigest()[:12]
        return ":".join([mac_hex[i:i+2] for i in range(0, 12, 2)])
```

### SqueezeliteProvider

```python
class SqueezeliteProvider(PlayerProvider):
    """Provider for Squeezelite audio players."""

    name = "squeezelite"
    display_name = "Squeezelite"
    binary = "squeezelite"

    def build_command(self, config: PlayerConfig) -> list[str]:
        cmd = [
            "squeezelite",
            "-n", config["name"],
            "-o", config["device"],
            "-m", config["config"]["mac_address"],
        ]

        if config["config"].get("server_ip"):
            cmd.extend(["-s", config["config"]["server_ip"]])

        # Standard options
        cmd.extend(["-a", "80", "-b", "500:2000", "-C", "5"])

        if config["device"] == "null":
            cmd.extend(["-r", "44100"])

        return cmd

    def get_config_schema(self) -> dict:
        return {
            "server_ip": {
                "type": "string",
                "description": "Logitech Media Server IP address",
                "required": False,
            },
            "mac_address": {
                "type": "string",
                "description": "Unique MAC address for this player",
                "pattern": r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$",
                "required": True,
                "auto_generate": True,
            },
        }

    def get_volume_backend(self) -> VolumeBackend:
        return AlsaVolumeBackend()
```

### SnapcastProvider

```python
class SnapcastProvider(PlayerProvider):
    """Provider for Snapcast synchronized audio clients."""

    name = "snapcast"
    display_name = "Snapcast"
    binary = "snapclient"

    def build_command(self, config: PlayerConfig) -> list[str]:
        cmd = [
            "snapclient",
            "-s", config["device"],
            "--hostID", config["config"].get("host_id", config["name"]),
        ]

        if config["config"].get("server_ip"):
            cmd.extend(["-h", config["config"]["server_ip"]])
        # else: auto-discover via Avahi

        if config["config"].get("latency"):
            cmd.extend(["--latency", str(config["config"]["latency"])])

        # Daemon mode
        cmd.extend(["-d"])

        return cmd

    def get_config_schema(self) -> dict:
        return {
            "server_ip": {
                "type": "string",
                "description": "Snapserver IP address (optional, uses Avahi discovery if not set)",
                "required": False,
            },
            "host_id": {
                "type": "string",
                "description": "Unique host identifier (defaults to player name)",
                "required": False,
            },
            "latency": {
                "type": "integer",
                "description": "Audio latency compensation in milliseconds",
                "default": 0,
                "required": False,
            },
        }

    def get_volume_backend(self) -> VolumeBackend:
        return SnapcastVolumeBackend()
```

### ProviderRegistry

```python
class ProviderRegistry:
    """
    Registry of available player providers.

    Allows dynamic registration and lookup of providers.
    """

    def __init__(self) -> None:
        self._providers: dict[str, PlayerProvider] = {}

    def register(self, provider: PlayerProvider) -> None:
        self._providers[provider.name] = provider

    def get(self, name: str) -> PlayerProvider | None:
        return self._providers.get(name)

    def list(self) -> list[PlayerProvider]:
        return list(self._providers.values())

    def names(self) -> list[str]:
        return list(self._providers.keys())
```

---

## Configuration Schema

### Current Schema (v1)

```yaml
# /app/config/players.yaml
living-room:
  name: living-room
  device: hw:0,0
  server_ip: 192.168.1.100
  mac_address: aa:bb:cc:dd:ee:ff
  enabled: true
  volume: 75
```

### Proposed Schema (v2)

```yaml
# /app/config/players.yaml
version: 2

players:
  living-room-squeeze:
    name: living-room-squeeze
    provider: squeezelite          # NEW: identifies provider
    device: hw:0,0
    enabled: true
    volume: 75
    config:                        # NEW: provider-specific config
      server_ip: 192.168.1.100
      mac_address: aa:bb:cc:dd:ee:ff

  kitchen-sync:
    name: kitchen-sync
    provider: snapcast
    device: hw:1,0
    enabled: true
    volume: 75
    config:
      server_ip: 192.168.1.100     # Snapserver address
      host_id: kitchen-speaker
      latency: 0
```

### Migration Strategy

```python
def migrate_v1_to_v2(old_config: dict) -> dict:
    """
    Migrate v1 config (squeezelite-only) to v2 (multi-provider).

    All existing players are assumed to be Squeezelite.
    """
    new_config = {"version": 2, "players": {}}

    for name, player in old_config.items():
        new_config["players"][name] = {
            "name": player["name"],
            "provider": "squeezelite",  # Default for migrated players
            "device": player["device"],
            "enabled": player.get("enabled", True),
            "volume": player.get("volume", 75),
            "config": {
                "server_ip": player.get("server_ip", ""),
                "mac_address": player.get("mac_address", ""),
            },
        }

    return new_config
```

---

## Volume Control Strategy

### Provider Volume Backends

| Provider | Backend | How It Works |
|----------|---------|--------------|
| **Squeezelite** | `AlsaVolumeBackend` | Local `amixer` commands to hardware mixer |
| **Snapcast** | `SnapcastVolumeBackend` | JSON-RPC API call to Snapserver (port 1780) |
| **Virtual** | `SoftwareVolumeBackend` | Stored value only (no hardware control) |

### AlsaVolumeBackend

```python
class AlsaVolumeBackend(VolumeBackend):
    """Volume control via ALSA mixer (amixer)."""

    supports_hardware_control = True

    def get_volume(self, player: PlayerConfig) -> int:
        # Extract card from device (e.g., "hw:0,0" -> "0")
        # Run: amixer -c 0 sget Master
        # Parse: [75%]
        ...

    def set_volume(self, player: PlayerConfig, volume: int) -> tuple[bool, str]:
        # Run: amixer -c 0 sset Master 75%
        ...
```

### SnapcastVolumeBackend

```python
class SnapcastVolumeBackend(VolumeBackend):
    """Volume control via Snapserver JSON-RPC API."""

    supports_hardware_control = False  # Controlled by server

    def get_volume(self, player: PlayerConfig) -> int:
        """
        Get volume from Snapserver.

        JSON-RPC call to http://{server_ip}:1780/jsonrpc
        Method: Client.GetStatus
        """
        server_ip = player["config"].get("server_ip", "localhost")
        host_id = player["config"].get("host_id", player["name"])

        # Call Snapserver API
        response = self._call_jsonrpc(server_ip, "Client.GetStatus", {"id": host_id})
        return response.get("client", {}).get("config", {}).get("volume", {}).get("percent", 75)

    def set_volume(self, player: PlayerConfig, volume: int) -> tuple[bool, str]:
        """
        Set volume via Snapserver.

        JSON-RPC call to http://{server_ip}:1780/jsonrpc
        Method: Client.SetVolume
        """
        server_ip = player["config"].get("server_ip", "localhost")
        host_id = player["config"].get("host_id", player["name"])

        self._call_jsonrpc(server_ip, "Client.SetVolume", {
            "id": host_id,
            "volume": {"percent": volume, "muted": False}
        })
        return True, f"Volume set to {volume}%"
```

---

## Migration Plan

### Phase 1: Extract Helper Classes (Non-Breaking)

1. Create `app/managers/` directory
2. Extract `ConfigManager` from `SqueezeliteManager`
3. Extract `AudioManager` from `SqueezeliteManager`
4. Extract `ProcessManager` from `SqueezeliteManager`
5. Refactor `SqueezeliteManager` to use these classes
6. **All existing functionality preserved**

### Phase 2: Add Provider Abstraction

1. Create `app/providers/` directory
2. Create `PlayerProvider` abstract base class
3. Create `SqueezeliteProvider` implementing current behavior
4. Create `ProviderRegistry`
5. Update `PlayerManager` to use providers
6. **Still backward compatible** (only squeezelite provider exists)

### Phase 3: Add Snapcast Support

1. Create `SnapcastProvider`
2. Create `SnapcastVolumeBackend`
3. Update config schema to v2
4. Add config migration
5. Update UI to show provider selection
6. **New feature, existing configs auto-migrated**

### Phase 4: UI Updates

1. Add provider dropdown to player creation form
2. Show provider-specific config fields dynamically
3. Display provider type in player list
4. Update status indicators for different providers

---

## API Changes

### Existing Endpoints (Preserved)

All existing endpoints continue to work unchanged:

```
GET  /api/players
POST /api/players
PUT  /api/players/<name>
DELETE /api/players/<name>
POST /api/players/<name>/start
POST /api/players/<name>/stop
GET  /api/players/<name>/status
GET  /api/players/<name>/volume
POST /api/players/<name>/volume
GET  /api/devices
```

### New Endpoints

```
GET /api/providers
    Returns list of available providers with their schemas

    Response:
    {
        "providers": [
            {
                "name": "squeezelite",
                "display_name": "Squeezelite",
                "config_schema": {...}
            },
            {
                "name": "snapcast",
                "display_name": "Snapcast",
                "config_schema": {...}
            }
        ]
    }
```

### Modified Request/Response

Player creation now accepts optional `provider` field:

```json
POST /api/players
{
    "name": "kitchen",
    "provider": "snapcast",    // NEW: optional, defaults to "squeezelite"
    "device": "hw:1,0",
    "config": {                // NEW: provider-specific config
        "server_ip": "192.168.1.100",
        "host_id": "kitchen-speaker"
    }
}
```

Player responses include provider info:

```json
GET /api/players
{
    "players": {
        "kitchen": {
            "name": "kitchen",
            "provider": "snapcast",    // NEW
            "device": "hw:1,0",
            "enabled": true,
            "volume": 75,
            "config": {                // NEW
                "server_ip": "192.168.1.100",
                "host_id": "kitchen-speaker"
            }
        }
    }
}
```

---

## Future Considerations

### Potential Future Providers

| Provider | Binary | Use Case |
|----------|--------|----------|
| **MPD Client** | `mpc` | Direct MPD control |
| **Bluetooth** | `bluealsa-aplay` | Bluetooth speaker output |
| **AirPlay** | `shairport-sync` | AirPlay receiver |
| **PulseAudio** | `paplay` | Network PulseAudio |

### Plugin Architecture

Future enhancement could allow external provider plugins:

```python
# /app/providers/custom/my_provider.py
class MyCustomProvider(PlayerProvider):
    name = "my_custom"
    ...

# Auto-discovered at startup
```

### Multi-Container Support

Future versions might support:
- Running providers in separate containers
- Remote player management via API
- Kubernetes/Docker Swarm deployments

---

## File Structure

```
app/
├── __init__.py
├── app.py                    # Flask routes (minimal, delegates to managers)
├── managers/
│   ├── __init__.py
│   ├── player_manager.py     # Main orchestrator
│   ├── config_manager.py     # Configuration persistence
│   ├── audio_manager.py      # Device detection
│   └── process_manager.py    # Subprocess lifecycle
├── providers/
│   ├── __init__.py
│   ├── base.py               # PlayerProvider ABC
│   ├── registry.py           # ProviderRegistry
│   ├── squeezelite.py        # SqueezeliteProvider
│   └── snapcast.py           # SnapcastProvider
├── volume/
│   ├── __init__.py
│   ├── base.py               # VolumeBackend ABC
│   ├── alsa.py               # AlsaVolumeBackend
│   ├── snapcast.py           # SnapcastVolumeBackend
│   └── software.py           # SoftwareVolumeBackend
├── templates/
│   └── index.html
└── swagger.yaml

docs/
├── ARCHITECTURE.md           # This document
└── API.md                    # API documentation
```

---

## Decision Log

| Decision | Rationale | Date |
|----------|-----------|------|
| Use provider abstraction | Enables multiple player types without modifying core | 2024-12 |
| Volume backends per provider | Snapcast controls volume server-side, Squeezelite locally | 2024-12 |
| Config v2 with migration | Backward compatible, existing installs auto-upgrade | 2024-12 |
| Drop FCast consideration | Electron-based, not suitable for headless audio | 2024-12 |
| Keep existing API structure | Minimize breaking changes for existing integrations | 2024-12 |
