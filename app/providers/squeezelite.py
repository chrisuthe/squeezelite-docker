"""
Squeezelite player provider implementation.

Handles Squeezelite-specific command building, volume control via ALSA,
and configuration validation.
"""

import hashlib
import logging
from typing import Any

from .base import PlayerConfig, PlayerProvider

logger = logging.getLogger(__name__)

# =============================================================================
# CONSTANTS
# =============================================================================

# Default squeezelite audio parameters
DEFAULT_BUFFER_SIZE = "80"
DEFAULT_BUFFER_PARAMS = "500:2000"
DEFAULT_CLOSE_TIMEOUT = "5"
DEFAULT_SAMPLE_RATE = "44100"

# Null device identifier for fallback
NULL_DEVICE = "null"


class SqueezeliteProvider(PlayerProvider):
    """
    Provider for Squeezelite audio player.

    Squeezelite is a lightweight headless Squeezebox emulator that
    connects to Logitech Media Server (LMS). Volume control is handled
    externally via ALSA mixer (amixer).

    Attributes:
        audio_manager: AudioManager instance for volume operations.
    """

    provider_type = "squeezelite"
    display_name = "Squeezelite"
    binary_name = "squeezelite"

    def __init__(self, audio_manager: Any) -> None:
        """
        Initialize the Squeezelite provider.

        Args:
            audio_manager: AudioManager instance for volume control.
        """
        self.audio_manager = audio_manager

    def build_command(self, player: PlayerConfig, log_path: str) -> list[str]:
        """
        Build the squeezelite command.

        Args:
            player: Player configuration containing:
                - name: Player name for LMS
                - device: ALSA output device
                - mac_address: MAC address for LMS identification
                - server_ip: Optional LMS server address
            log_path: Path to the log file.

        Returns:
            Command arguments list.
        """
        cmd = [
            self.binary_name,
            "-n",
            player["name"],
            "-o",
            player["device"],
            "-m",
            player["mac_address"],
        ]

        # Add server if specified
        if player.get("server_ip"):
            cmd.extend(["-s", player["server_ip"]])

        # Add logging
        cmd.extend(["-f", log_path])

        # Add buffer and compatibility options
        cmd.extend(
            [
                "-a",
                DEFAULT_BUFFER_SIZE,
                "-b",
                DEFAULT_BUFFER_PARAMS,
                "-C",
                DEFAULT_CLOSE_TIMEOUT,
            ]
        )

        # Null device needs explicit sample rate
        if player["device"] == NULL_DEVICE:
            cmd.extend(["-r", DEFAULT_SAMPLE_RATE])

        return cmd

    def build_fallback_command(self, player: PlayerConfig, log_path: str) -> list[str]:
        """
        Build fallback command using null device.

        When the configured audio device fails, fall back to the null
        device to keep the player registered with LMS.

        Args:
            player: Player configuration.
            log_path: Path to the log file.

        Returns:
            Command arguments for null device fallback.
        """
        cmd = [
            self.binary_name,
            "-n",
            player["name"],
            "-o",
            NULL_DEVICE,
            "-m",
            player["mac_address"],
        ]

        if player.get("server_ip"):
            cmd.extend(["-s", player["server_ip"]])

        cmd.extend(["-f", log_path])

        cmd.extend(
            [
                "-a",
                DEFAULT_BUFFER_SIZE,
                "-b",
                DEFAULT_BUFFER_PARAMS,
                "-C",
                DEFAULT_CLOSE_TIMEOUT,
                "-r",
                DEFAULT_SAMPLE_RATE,
            ]
        )

        return cmd

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
        Validate squeezelite configuration.

        Required fields: name, device
        Optional fields: server_ip, mac_address (auto-generated if missing)

        Args:
            config: Configuration to validate.

        Returns:
            Tuple of (is_valid, error_message).
        """
        if not config.get("name"):
            return False, "Player name is required"

        if not config.get("device"):
            return False, "Audio device is required"

        # Name should be reasonable length
        name = config["name"]
        if len(name) > 64:
            return False, "Player name too long (max 64 characters)"

        # Check for invalid characters in name
        if "/" in name or "\\" in name or "\x00" in name:
            return False, "Player name contains invalid characters"

        return True, ""

    def get_default_config(self) -> dict[str, Any]:
        """
        Get default squeezelite configuration.

        Returns:
            Default configuration dictionary.
        """
        return {
            "provider": self.provider_type,
            "device": "default",
            "server_ip": "",
            "mac_address": "",  # Will be auto-generated
            "volume": 75,
            "autostart": False,
        }

    def get_required_fields(self) -> list[str]:
        """Get required configuration fields."""
        return ["name", "device"]

    def supports_fallback(self) -> bool:
        """Squeezelite supports null device fallback."""
        return True

    @staticmethod
    def generate_mac_address(name: str) -> str:
        """
        Generate a consistent MAC address from player name.

        Uses MD5 hash to generate a locally-administered unicast MAC
        that is deterministic for the same player name.

        Args:
            name: Player name to hash.

        Returns:
            MAC address string in format XX:XX:XX:XX:XX:XX.
        """
        hash_bytes = hashlib.md5(name.encode()).digest()

        # Use first 6 bytes, set locally administered bit (0x02)
        # and clear multicast bit (0x01) on first octet
        mac_bytes = list(hash_bytes[:6])
        mac_bytes[0] = (mac_bytes[0] | 0x02) & 0xFE

        return ":".join(f"{b:02x}" for b in mac_bytes)

    def prepare_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """
        Prepare configuration with defaults and generated values.

        Merges user config with defaults and generates MAC address
        if not provided.

        Args:
            config: User-provided configuration.

        Returns:
            Complete configuration dictionary.
        """
        # Start with defaults
        result = self.get_default_config()
        result.update(config)

        # Generate MAC if not provided
        if not result.get("mac_address") and result.get("name"):
            result["mac_address"] = self.generate_mac_address(result["name"])

        return result
