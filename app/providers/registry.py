"""
Provider registry for managing player providers.

Handles registration, lookup, and lifecycle of provider instances.
"""

import logging
from typing import Any

from .base import PlayerProvider

logger = logging.getLogger(__name__)

# Default provider type when not specified in config
DEFAULT_PROVIDER = "squeezelite"


class ProviderRegistry:
    """
    Registry for managing player provider instances.

    Provides a central place to register, lookup, and manage
    provider implementations. Supports lazy initialization
    and dependency injection for providers.

    Attributes:
        providers: Dictionary mapping provider types to instances.
        default_provider: The default provider type to use.
    """

    def __init__(self) -> None:
        """Initialize an empty provider registry."""
        self._providers: dict[str, PlayerProvider] = {}
        self._provider_classes: dict[str, type[PlayerProvider]] = {}
        self.default_provider = DEFAULT_PROVIDER

    def register_class(
        self,
        provider_type: str,
        provider_class: type[PlayerProvider],
    ) -> None:
        """
        Register a provider class for later instantiation.

        Args:
            provider_type: String identifier for this provider.
            provider_class: The provider class to register.
        """
        self._provider_classes[provider_type] = provider_class
        logger.debug(f"Registered provider class: {provider_type}")

    def register_instance(
        self,
        provider_type: str,
        provider: PlayerProvider,
    ) -> None:
        """
        Register an already-instantiated provider.

        Args:
            provider_type: String identifier for this provider.
            provider: The provider instance to register.
        """
        self._providers[provider_type] = provider
        logger.debug(f"Registered provider instance: {provider_type}")

    def get(self, provider_type: str) -> PlayerProvider | None:
        """
        Get a provider by type.

        Args:
            provider_type: The provider type to look up.

        Returns:
            The provider instance, or None if not found.
        """
        return self._providers.get(provider_type)

    def get_or_default(self, provider_type: str | None) -> PlayerProvider | None:
        """
        Get a provider by type, falling back to default.

        Args:
            provider_type: The provider type to look up, or None for default.

        Returns:
            The provider instance, or None if neither found.
        """
        if provider_type is None:
            provider_type = self.default_provider
        return self.get(provider_type)

    def get_for_player(self, player_config: dict[str, Any]) -> PlayerProvider | None:
        """
        Get the appropriate provider for a player configuration.

        Looks up the provider type from the player config and returns
        the corresponding provider instance.

        Args:
            player_config: Player configuration dictionary.

        Returns:
            The provider instance for this player, or None if not found.
        """
        provider_type = player_config.get("provider", self.default_provider)
        return self.get(provider_type)

    def has_provider(self, provider_type: str) -> bool:
        """
        Check if a provider type is registered.

        Args:
            provider_type: The provider type to check.

        Returns:
            True if the provider is registered.
        """
        return provider_type in self._providers

    def list_providers(self, available_only: bool = False) -> list[str]:
        """
        Get list of registered provider types.

        Args:
            available_only: If True, only return providers whose binary is available.

        Returns:
            List of provider type strings.
        """
        if available_only:
            return [ptype for ptype, provider in self._providers.items() if provider.is_available()]
        return list(self._providers.keys())

    def get_default_available_provider(self) -> str | None:
        """
        Get the default provider type, ensuring it's available.

        If the configured default provider isn't available, returns
        the first available provider instead.

        Returns:
            Provider type string, or None if no providers are available.
        """
        # Check if default is available
        default = self._providers.get(self.default_provider)
        if default and default.is_available():
            return self.default_provider

        # Fall back to first available provider
        for provider_type, provider in self._providers.items():
            if provider.is_available():
                return provider_type

        return None

    def get_provider_info(self, available_only: bool = True) -> list[dict[str, str | bool]]:
        """
        Get information about registered providers.

        Args:
            available_only: If True (default), only return providers whose
                binary is available on the system. Set to False to return all.

        Returns:
            List of dictionaries with provider info (type, display_name, available).
        """
        info: list[dict[str, str | bool]] = []
        for provider_type, provider in self._providers.items():
            is_available = provider.is_available()
            if available_only and not is_available:
                continue
            info.append(
                {
                    "type": provider_type,
                    "display_name": provider.display_name,
                    "binary": provider.binary_name,
                    "available": is_available,
                }
            )
        return info

    def validate_player_config(
        self,
        player_config: dict[str, Any],
    ) -> tuple[bool, str]:
        """
        Validate a player configuration using its provider.

        Args:
            player_config: Player configuration to validate.

        Returns:
            Tuple of (is_valid, error_message).
        """
        provider = self.get_for_player(player_config)
        if provider is None:
            provider_type = player_config.get("provider", self.default_provider)
            return False, f"Unknown provider type: {provider_type}"

        return provider.validate_config(player_config)

    def prepare_player_config(
        self,
        player_config: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Prepare a player configuration with provider defaults.

        Merges user config with provider defaults and generates
        any auto-generated fields (like MAC addresses, client IDs).

        Args:
            player_config: User-provided configuration.

        Returns:
            Complete configuration dictionary.
        """
        provider = self.get_for_player(player_config)
        if provider is None:
            # Return as-is if provider not found
            return player_config

        # Use provider's prepare method if available
        if hasattr(provider, "prepare_config"):
            return provider.prepare_config(player_config)

        # Fallback: just merge with defaults
        defaults = provider.get_default_config()
        defaults.update(player_config)
        return defaults

    def clear(self) -> None:
        """Remove all registered providers."""
        self._providers.clear()
        logger.debug("Cleared all providers from registry")
