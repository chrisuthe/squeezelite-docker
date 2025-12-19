"""
Sendspin player provider implementation.

Handles Sendspin-specific command building, volume control,
and configuration validation for the Sendspin synchronized
multi-room audio protocol.
"""

import hashlib
import logging
from typing import Any

from .base import PlayerConfig, PlayerProvider

logger = logging.getLogger(__name__)

# =============================================================================
# CONSTANTS
# =============================================================================

# Default Sendspin settings
DEFAULT_LOG_LEVEL = "INFO"

# Client ID prefix for generated IDs
CLIENT_ID_PREFIX = "sendspin"


class SendspinProvider(PlayerProvider):
    """
    Provider for Sendspin audio player.

    Sendspin is an open protocol for synchronized multi-room audio,
    developed by the Music Assistant team. It uses WebSocket connections
    and supports mDNS server discovery.

    The sendspin-cli player can run headless and automatically discovers
    Sendspin servers on the local network.

    Attributes:
        audio_manager: AudioManager instance for volume operations.
    """

    provider_type = "sendspin"
    display_name = "Sendspin"
    binary_name = "sendspin"

    def __init__(self, audio_manager: Any) -> None:
        """
        Initialize the Sendspin provider.

        Args:
            audio_manager: AudioManager instance for volume control.
                          Used for ALSA-based volume control when
                          protocol-based control isn't available.
        """
        self.audio_manager = audio_manager

    def build_command(self, player: PlayerConfig, log_path: str) -> list[str]:
        """
        Build the sendspin command.

        Args:
            player: Player configuration containing:
                - name: Player display name
                - device: Audio output device (PortAudio index or name, NOT ALSA hw:X,Y)
                - client_id: Unique client identifier
                - delay_ms: Optional latency compensation
            log_path: Path to the log file (not directly used by sendspin,
                     but kept for consistency).

        Returns:
            Command arguments list.
        """
        cmd = [
            self.binary_name,
            "--headless",  # Always run headless in our context
            "--name",
            player["name"],
            "--id",
            player.get("client_id", self._generate_client_id(player["name"])),
        ]

        # Add audio device if specified and compatible with PortAudio
        # Note: Sendspin uses PortAudio, not ALSA - device can be:
        # - A number (PortAudio device index, e.g., "0", "1", "2")
        # - A device name prefix (e.g., "USB Audio", "MacBook")
        # - NOT ALSA format like "hw:1,0" - those are skipped
        device = player.get("device", "default")
        if device and device != "default" and device != "null":
            # Skip ALSA-style device names (hw:X,Y format) - not compatible with PortAudio
            if not device.startswith("hw:") and not device.startswith("plughw:"):
                cmd.extend(["--audio-device", device])
            else:
                logger.warning(
                    f"Sendspin player '{player['name']}' configured with ALSA device '{device}' "
                    "which is not compatible with PortAudio. Using system default audio device. "
                    "Use 'sendspin --list-audio-devices' to see available PortAudio devices."
                )

        # Add latency compensation if specified
        delay_ms = player.get("delay_ms")
        if delay_ms is not None and delay_ms != 0:
            cmd.extend(["--static-delay-ms", str(delay_ms)])

        # Set log level
        log_level = player.get("log_level", DEFAULT_LOG_LEVEL)
        cmd.extend(["--log-level", log_level])

        return cmd

    def build_fallback_command(self, player: PlayerConfig, log_path: str) -> list[str] | None:
        """
        Sendspin doesn't have a fallback mechanism like Squeezelite.

        Returns:
            None - no fallback supported.
        """
        return None

    def get_volume(self, player: PlayerConfig) -> int:
        """
        Get volume via ALSA mixer.

        Note: Sendspin has protocol-native volume control, but for
        local hardware control we use ALSA.

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

        Note: Sendspin has protocol-native volume control, but for
        local hardware control we use ALSA.

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
        Validate sendspin configuration.

        Required fields: name
        Optional fields: device, client_id, delay_ms

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

        # Validate delay_ms if provided
        delay_ms = config.get("delay_ms")
        if delay_ms is not None:
            try:
                int(delay_ms)
            except (TypeError, ValueError):
                return False, "Delay must be an integer (milliseconds)"

        return True, ""

    def get_default_config(self) -> dict[str, Any]:
        """
        Get default sendspin configuration.

        Returns:
            Default configuration dictionary.
        """
        return {
            "provider": self.provider_type,
            "device": "default",
            "client_id": "",  # Will be auto-generated from name
            "delay_ms": 0,
            "log_level": DEFAULT_LOG_LEVEL,
            "volume": 75,
            "autostart": False,
        }

    def get_required_fields(self) -> list[str]:
        """Get required configuration fields."""
        return ["name"]

    def supports_fallback(self) -> bool:
        """Sendspin doesn't have a fallback mechanism."""
        return False

    def _generate_client_id(self, name: str) -> str:
        """
        Generate a unique client ID from player name.

        Creates a deterministic ID based on the player name,
        prefixed with 'sendspin-' for clarity.

        Args:
            name: Player name to hash.

        Returns:
            Client ID string.
        """
        # Create a short hash suffix for uniqueness
        hash_suffix = hashlib.md5(name.encode()).hexdigest()[:8]
        # Sanitize name for use in ID (lowercase, replace spaces)
        safe_name = name.lower().replace(" ", "-")[:20]
        return f"{CLIENT_ID_PREFIX}-{safe_name}-{hash_suffix}"

    def prepare_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """
        Prepare configuration with defaults and generated values.

        Merges user config with defaults and generates client_id
        if not provided.

        Args:
            config: User-provided configuration.

        Returns:
            Complete configuration dictionary.
        """
        # Start with defaults
        result = self.get_default_config()
        result.update(config)

        # Generate client_id if not provided
        if not result.get("client_id") and result.get("name"):
            result["client_id"] = self._generate_client_id(result["name"])

        return result

    def get_player_identifier(self, player: PlayerConfig) -> str:
        """
        Get unique identifier for tracking this player.

        Uses client_id if available, otherwise falls back to name.

        Args:
            player: Player configuration dictionary.

        Returns:
            Unique identifier string.
        """
        return player.get("client_id") or player.get("name", "unknown")
