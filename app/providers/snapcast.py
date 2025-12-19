"""
Snapcast player provider implementation.

Handles Snapcast-specific command building, volume control via ALSA/PulseAudio,
and configuration validation for the Snapcast synchronized multiroom
audio system.

Supports both standalone Docker (ALSA) and HAOS (PulseAudio) environments.
"""

import hashlib
import logging
from typing import Any

from environment import get_player_backend_for_snapcast

from .base import PlayerConfig, PlayerProvider

logger = logging.getLogger(__name__)

# =============================================================================
# CONSTANTS
# =============================================================================

# Default latency compensation (milliseconds)
DEFAULT_LATENCY = 0

# Host ID prefix for generated IDs
HOST_ID_PREFIX = "snapcast"


class SnapcastProvider(PlayerProvider):
    """
    Provider for Snapcast audio client.

    Snapcast is a synchronous multiroom audio solution. The snapclient
    connects to a snapserver and plays synchronized audio streams.
    Volume control is handled via ALSA mixer (amixer).

    The snapclient can auto-discover the snapserver via Avahi/mDNS,
    or connect to a specific server IP address.

    Attributes:
        audio_manager: AudioManager instance for volume operations.
    """

    provider_type = "snapcast"
    display_name = "Snapcast"
    binary_name = "snapclient"

    def __init__(self, audio_manager: Any) -> None:
        """
        Initialize the Snapcast provider.

        Args:
            audio_manager: AudioManager instance for volume control.
        """
        self.audio_manager = audio_manager

    def build_command(self, player: PlayerConfig, log_path: str) -> list[str]:
        """
        Build the snapclient command.

        Args:
            player: Player configuration containing:
                - name: Player display name
                - device: ALSA output device (e.g., 'hw:0,0', 'default')
                - server_ip: Optional Snapserver address (auto-discovers if empty)
                - host_id: Unique client identifier for the server
                - latency: Optional PCM latency compensation in milliseconds
            log_path: Path to the log file.

        Returns:
            Command arguments list.
        """
        cmd = [self.binary_name]

        # Server address (optional - auto-discovers via Avahi if not set)
        if player.get("server_ip"):
            cmd.extend(["--host", player["server_ip"]])

        # Audio device (ALSA device name or index)
        device = player.get("device", "default")
        if device and device != "default":
            cmd.extend(["--soundcard", device])

        # Host ID for server identification
        host_id = player.get("host_id")
        if host_id:
            cmd.extend(["--hostID", host_id])

        # Latency compensation
        latency = player.get("latency", DEFAULT_LATENCY)
        if latency and latency != 0:
            cmd.extend(["--latency", str(latency)])

        # Audio backend: ALSA for standalone Docker, PulseAudio for HAOS
        player_backend = get_player_backend_for_snapcast()
        cmd.extend(["--player", player_backend])

        # Logging output
        cmd.extend(["--logsink", f"file:{log_path}"])

        return cmd

    def build_fallback_command(self, player: PlayerConfig, log_path: str) -> list[str] | None:
        """
        Snapcast doesn't have a fallback mechanism.

        Returns:
            None - no fallback supported.
        """
        return None

    def get_volume(self, player: PlayerConfig) -> int:
        """
        Get volume via ALSA mixer.

        Args:
            player: Player configuration with device info.

        Returns:
            Volume percentage (0-100).
        """
        device = player.get("device", "default")
        return self.audio_manager.get_volume(device)

    def set_volume(self, player: PlayerConfig, volume: int) -> tuple[bool, str]:
        """
        Set volume via ALSA mixer.

        Args:
            player: Player configuration with device info.
            volume: Target volume percentage (0-100).

        Returns:
            Tuple of (success, message).
        """
        device = player.get("device", "default")
        return self.audio_manager.set_volume(device, volume)

    def validate_config(self, config: dict[str, Any]) -> tuple[bool, str]:
        """
        Validate snapcast configuration.

        Required fields: name
        Optional fields: device, server_ip, host_id, latency

        Args:
            config: Configuration to validate.

        Returns:
            Tuple of (is_valid, error_message).
        """
        if not config.get("name"):
            return False, "Player name is required"

        # Name should be reasonable length
        name = config["name"]
        if len(name) > 64:
            return False, "Player name too long (max 64 characters)"

        # Check for invalid characters in name
        if "/" in name or "\\" in name or "\x00" in name:
            return False, "Player name contains invalid characters"

        # Validate latency if provided
        latency = config.get("latency")
        if latency is not None:
            try:
                int(latency)
            except (TypeError, ValueError):
                return False, "Latency must be an integer (milliseconds)"

        return True, ""

    def get_default_config(self) -> dict[str, Any]:
        """
        Get default snapcast configuration.

        Returns:
            Default configuration dictionary.
        """
        return {
            "provider": self.provider_type,
            "device": "default",
            "server_ip": "",  # Auto-discover via Avahi
            "host_id": "",  # Will be auto-generated from name
            "latency": 0,
            "volume": 75,
            "autostart": False,
        }

    def get_required_fields(self) -> list[str]:
        """Get required configuration fields."""
        return ["name"]

    def supports_fallback(self) -> bool:
        """Snapcast doesn't support fallback."""
        return False

    @staticmethod
    def generate_host_id(name: str) -> str:
        """
        Generate a unique host ID from player name.

        Uses MD5 hash to create a deterministic identifier that the
        Snapserver can use to recognize this client across restarts.

        Args:
            name: Player name to hash.

        Returns:
            Host ID string in format 'snapcast-<name>-<hash>'.
        """
        # Create a hash suffix for uniqueness
        hash_suffix = hashlib.md5(name.encode()).hexdigest()[:12]
        # Sanitize name for use in ID (lowercase, replace spaces)
        safe_name = name.lower().replace(" ", "-")[:20]
        return f"{HOST_ID_PREFIX}-{safe_name}-{hash_suffix}"

    def prepare_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """
        Prepare configuration with defaults and generated values.

        Merges user config with defaults and generates host_id
        if not provided.

        Args:
            config: User-provided configuration.

        Returns:
            Complete configuration dictionary.
        """
        # Start with defaults
        result = self.get_default_config()
        result.update(config)

        # Generate host_id if not provided
        if not result.get("host_id") and result.get("name"):
            result["host_id"] = self.generate_host_id(result["name"])

        return result

    def get_player_identifier(self, player: PlayerConfig) -> str:
        """
        Get unique identifier for tracking this player.

        Uses host_id if available, otherwise falls back to name.

        Args:
            player: Player configuration dictionary.

        Returns:
            Unique identifier string.
        """
        return player.get("host_id") or player.get("name", "unknown")
