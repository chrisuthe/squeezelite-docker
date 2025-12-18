"""
Abstract base class for player providers.

Defines the interface that all player providers must implement,
enabling a pluggable architecture for different audio backends.
"""

import shutil
from abc import ABC, abstractmethod
from typing import Any

# Type alias for player configuration
PlayerConfig = dict[str, Any]


class PlayerProvider(ABC):
    """
    Abstract base class for audio player providers.

    Each provider implementation handles the specifics of a particular
    audio player backend (Squeezelite, Sendspin, Snapcast, etc.) while
    exposing a consistent interface for the manager layer.

    Providers are responsible for:
    - Building command-line arguments for their player binary
    - Handling volume control (either via external tools or protocol)
    - Validating provider-specific configuration
    - Providing default values for optional settings
    """

    # Provider identification
    provider_type: str = "unknown"
    display_name: str = "Unknown Provider"

    # Binary/executable name
    binary_name: str = "unknown"

    @abstractmethod
    def build_command(self, player: PlayerConfig, log_path: str) -> list[str]:
        """
        Build the command to start the player process.

        Args:
            player: Player configuration dictionary containing at minimum:
                - name: Player display name
                - device: Audio output device
                - Additional provider-specific settings
            log_path: Path to the log file for this player.

        Returns:
            List of command arguments to spawn the player process.
        """
        pass

    @abstractmethod
    def build_fallback_command(self, player: PlayerConfig, log_path: str) -> list[str] | None:
        """
        Build a fallback command if the primary fails.

        Some providers may not support fallback commands (return None).
        For example, Squeezelite can fall back to the null device.

        Args:
            player: Player configuration dictionary.
            log_path: Path to the log file for this player.

        Returns:
            List of command arguments for fallback, or None if not supported.
        """
        pass

    @abstractmethod
    def get_volume(self, player: PlayerConfig) -> int:
        """
        Get the current volume for a player.

        Implementation varies by provider:
        - Squeezelite: Uses amixer to query ALSA mixer
        - Sendspin: May use protocol or fall back to amixer
        - Snapcast: Queries server via JSON-RPC

        Args:
            player: Player configuration dictionary.

        Returns:
            Volume level as integer percentage (0-100).
        """
        pass

    @abstractmethod
    def set_volume(self, player: PlayerConfig, volume: int) -> tuple[bool, str]:
        """
        Set the volume for a player.

        Args:
            player: Player configuration dictionary.
            volume: Volume level as integer percentage (0-100).

        Returns:
            Tuple of (success: bool, message: str).
        """
        pass

    @abstractmethod
    def validate_config(self, config: dict[str, Any]) -> tuple[bool, str]:
        """
        Validate provider-specific configuration.

        Checks that all required fields are present and valid
        for this provider type.

        Args:
            config: Configuration dictionary to validate.

        Returns:
            Tuple of (is_valid: bool, error_message: str).
            If valid, error_message is empty.
        """
        pass

    @abstractmethod
    def get_default_config(self) -> dict[str, Any]:
        """
        Get default configuration values for this provider.

        Returns a dictionary of default values that can be merged
        with user-provided configuration.

        Returns:
            Dictionary of default configuration values.
        """
        pass

    def get_required_fields(self) -> list[str]:
        """
        Get list of required configuration fields.

        Returns:
            List of field names that must be present in config.
        """
        return ["name", "device"]

    def supports_volume_control(self) -> bool:
        """
        Check if this provider supports volume control.

        Returns:
            True if volume can be controlled, False otherwise.
        """
        return True

    def supports_fallback(self) -> bool:
        """
        Check if this provider supports fallback commands.

        Returns:
            True if fallback is supported, False otherwise.
        """
        return False

    def is_available(self) -> bool:
        """
        Check if this provider's binary is available on the system.

        Uses shutil.which() to check if the binary can be found in PATH.
        Providers can override this for custom availability checks.

        Returns:
            True if the provider's binary is available, False otherwise.
        """
        return shutil.which(self.binary_name) is not None

    def get_player_identifier(self, player: PlayerConfig) -> str:
        """
        Get a unique identifier for tracking this player.

        By default, uses the player name. Providers can override
        this to use different identification schemes.

        Args:
            player: Player configuration dictionary.

        Returns:
            Unique identifier string for this player.
        """
        return player.get("name", "unknown")
