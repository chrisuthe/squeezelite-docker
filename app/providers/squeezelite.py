"""
Squeezelite player provider implementation.

Handles Squeezelite-specific command building, volume control via ALSA,
and configuration validation.
"""

import hashlib
import logging
import os
from typing import Any

from .base import PlayerConfig, PlayerProvider

logger = logging.getLogger(__name__)

# =============================================================================
# CONSTANTS
# =============================================================================

# Squeezelite Audio Buffer Configuration
# These parameters control audio buffering and device behavior in squeezelite.
# All values can be overridden via environment variables.

# ALSA buffer time in milliseconds (squeezelite -a parameter)
# Controls the ALSA period size. Lower values reduce latency but may cause
# audio dropouts on slower systems. Higher values increase latency but provide
# more stable playback. Typical range: 20-200ms.
# Default: 80ms
# Environment variable: SQUEEZELITE_BUFFER_TIME
DEFAULT_BUFFER_SIZE = os.environ.get("SQUEEZELITE_BUFFER_TIME", "80")

# Internal stream and output buffer sizes in KB (squeezelite -b parameter)
# Format: "stream_buffer:output_buffer"
# - stream_buffer: Size of internal stream buffer before audio processing
# - output_buffer: Size of output buffer after audio processing
# Larger buffers provide more resilience against network/CPU issues but use
# more memory and increase latency. Smaller buffers reduce memory and latency
# but may cause underruns.
# Default: 500KB stream, 2000KB output
# Environment variable: SQUEEZELITE_BUFFER_PARAMS
DEFAULT_BUFFER_PARAMS = os.environ.get("SQUEEZELITE_BUFFER_PARAMS", "500:2000")

# Output device close timeout in seconds (squeezelite -C parameter)
# Number of seconds of silence before closing the audio output device.
# This allows the audio device to enter power-saving mode during inactivity.
# Set to 0 to keep device always open (prevents power-saving but reduces
# startup latency when playback resumes).
# Default: 5 seconds
# Environment variable: SQUEEZELITE_CLOSE_TIMEOUT
DEFAULT_CLOSE_TIMEOUT = os.environ.get("SQUEEZELITE_CLOSE_TIMEOUT", "5")

# Default sample rate for null device output (squeezelite -r parameter)
# Used when outputting to the null device (no audio hardware). This must be
# specified explicitly for null device operation.
# Default: 44100Hz (CD quality)
# Environment variable: SQUEEZELITE_SAMPLE_RATE
DEFAULT_SAMPLE_RATE = os.environ.get("SQUEEZELITE_SAMPLE_RATE", "44100")

# Null device identifier for fallback
# When the configured audio device is unavailable, squeezelite falls back to
# this null device to maintain LMS connection without audio output.
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

        Why MD5 is used:
            MD5 provides a simple, deterministic hashing mechanism that ensures
            the same player name will always generate the same MAC address across
            restarts and reconfigurations. While MD5 is cryptographically broken
            for security purposes, it remains perfectly suitable for generating
            non-security-critical identifiers like MAC addresses. The hash spreads
            player names uniformly across the MAC address space, minimizing the
            chance of accidental collisions.

        MAC Address Format:
            The generated MAC address follows the IEEE 802 standard format:
            XX:XX:XX:XX:XX:XX (6 octets separated by colons, lowercase hex).

            The first octet is specially formatted with:
            - Bit 1 (0x02) SET: Marks this as a locally-administered address
              (not assigned by a manufacturer), which is appropriate for
              software-generated MACs.
            - Bit 0 (0x01) CLEARED: Ensures this is a unicast address (not
              multicast/broadcast), which is required for individual device
              identification in LMS.

        Uniqueness per player name:
            Each unique player name produces a unique 128-bit MD5 hash. The first
            48 bits (6 bytes) of this hash become the MAC address. With MD5's
            uniform distribution, the probability of two different player names
            producing the same MAC address is extremely low (approximately
            1 in 2^48, or 1 in 281 trillion). In practice, this ensures each
            player gets a unique identifier that Logitech Media Server can use
            to distinguish and remember individual players.

        Args:
            name: Player name to hash.

        Returns:
            MAC address string in format XX:XX:XX:XX:XX:XX.
        """
        # Generate MD5 hash of the player name
        # MD5 produces a 128-bit (16-byte) digest that is deterministic -
        # the same input always produces the same output
        hash_bytes = hashlib.md5(name.encode()).digest()

        # Extract first 6 bytes from the hash for the MAC address
        # Use first 6 bytes, set locally administered bit (0x02)
        # and clear multicast bit (0x01) on first octet
        mac_bytes = list(hash_bytes[:6])

        # Modify the first octet to comply with IEEE 802 MAC address standards:
        # - OR with 0x02: Sets the locally-administered bit (bit 1)
        # - AND with 0xFE: Clears the multicast bit (bit 0)
        # This creates a locally-administered unicast MAC address
        mac_bytes[0] = (mac_bytes[0] | 0x02) & 0xFE

        # Format as standard colon-separated hex string (e.g., "a2:3f:4d:1e:8c:9b")
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
