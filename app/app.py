#!/usr/bin/env python3
"""
Multi-Room Audio Controller - Main Application

A Flask-based web application for managing multiple audio players with
support for different backends (Squeezelite, Sendspin, and more).
Provides a REST API and web interface for creating, configuring, and
controlling audio players across different rooms/zones.

Key Components:
    - PlayerManager: Coordinates player lifecycle using focused manager classes
    - ConfigManager: Handles configuration persistence
    - AudioManager: Handles device detection and volume control
    - ProcessManager: Handles subprocess lifecycle
    - ProviderRegistry: Manages player provider implementations
    - PlayerProvider: Abstract interface for audio backends
    - REST API: Endpoints for player CRUD operations, status, and volume control
    - WebSocket: Real-time status updates to connected browsers
    - Swagger UI: Interactive API documentation at /api/docs

Supported Providers:
    - Squeezelite: Logitech Media Server compatible player
    - Sendspin: Music Assistant synchronized audio protocol

Configuration:
    - Players stored in /app/config/players.yaml
    - Logs written to /app/logs/
    - Environment variables: SECRET_KEY, SUPERVISOR_USER, SUPERVISOR_PASSWORD

Usage:
    Run directly: python3 app.py
    Via supervisor: supervisord -c /etc/supervisor/conf.d/supervisord.conf
"""

import logging
import os
import sys
import traceback
from typing import Any

from common import create_flask_app, register_routes, register_websocket_handlers, run_server, start_status_monitor
from managers import AudioManager, ConfigManager, ProcessManager
from providers import ProviderRegistry, SendspinProvider, SqueezeliteProvider

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================

# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler("/app/logs/application.log")],
)
logger = logging.getLogger(__name__)

# Log startup information
logger.info("=" * 50)
logger.info("Starting Multi Output Player")
logger.info(f"Python version: {sys.version}")
logger.info(f"Working directory: {os.getcwd()}")
logger.info(f"Python path: {sys.path}")
logger.info("=" * 50)

try:
    # Test imports
    logger.info("Testing imports...")
    import flask

    logger.info(f"Flask version: {flask.__version__}")
    import flask_socketio

    try:
        logger.info(f"Flask-SocketIO version: {flask_socketio.__version__}")
    except AttributeError:
        logger.info("Flask-SocketIO imported successfully (version info not available)")
    logger.info("All imports successful")
except ImportError as e:
    logger.error(f"Import error: {e}")
    sys.exit(1)

# Detect if running in Windows mode
WINDOWS_MODE = os.environ.get("SQUEEZELITE_WINDOWS_MODE", "0") == "1"
if WINDOWS_MODE:
    logger.warning("Running in Windows compatibility mode - audio device access is limited")

# Ensure required directories exist
required_dirs = ["/app/config", "/app/logs", "/app/data"]
for directory in required_dirs:
    try:
        os.makedirs(directory, exist_ok=True)
        logger.info(f"Directory ensured: {directory}")
    except Exception as e:
        logger.error(f"Could not create directory {directory}: {e}")

# Create Flask app and SocketIO instance using common module
app, socketio = create_flask_app()

# Configuration paths
CONFIG_FILE = "/app/config/players.yaml"
PLAYERS_DIR = "/app/config/players"
LOG_DIR = "/app/logs"

# Ensure directories exist
os.makedirs("/app/config", exist_ok=True)
os.makedirs(PLAYERS_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)


class PlayerManager:
    """
    Manages multi-provider audio player instances.

    Coordinates player lifecycle using focused manager classes and
    provider abstraction for different audio backends:
    - ConfigManager: Configuration persistence
    - AudioManager: Device detection and volume control
    - ProcessManager: Subprocess lifecycle
    - ProviderRegistry: Provider implementations (Squeezelite, Sendspin, etc.)

    This class handles provider-agnostic player CRUD operations and
    delegates provider-specific logic to the appropriate provider.

    Attributes:
        config: ConfigManager instance for player configuration.
        audio: AudioManager instance for device/volume operations.
        process: ProcessManager instance for subprocess handling.
        providers: ProviderRegistry for provider lookup.
    """

    # Type alias for player configuration
    PlayerConfig = dict[str, Any]

    def __init__(
        self,
        config_manager: ConfigManager,
        audio_manager: AudioManager,
        process_manager: ProcessManager,
        provider_registry: ProviderRegistry,
    ) -> None:
        """
        Initialize the PlayerManager.

        Args:
            config_manager: ConfigManager instance for configuration.
            audio_manager: AudioManager instance for audio operations.
            process_manager: ProcessManager instance for process handling.
            provider_registry: ProviderRegistry for provider lookup.
        """
        self.config = config_manager
        self.audio = audio_manager
        self.process = process_manager
        self.providers = provider_registry

    @property
    def players(self) -> dict[str, PlayerConfig]:
        """Get all player configurations."""
        return self.config.players

    def load_config(self) -> None:
        """Load player configuration from file."""
        self.config.load()

    def save_config(self) -> None:
        """Save player configuration to file."""
        self.config.save()

    def get_audio_devices(self) -> list[dict[str, str]]:
        """Get list of available audio devices."""
        return self.audio.get_devices()

    def create_player(
        self,
        name: str,
        device: str,
        provider_type: str = "squeezelite",
        server_ip: str = "",
        server_url: str = "",
        mac_address: str = "",
        **extra_config: Any,
    ) -> tuple[bool, str]:
        """
        Create a new audio player.

        Args:
            name: Unique name for the player (used as identifier).
            device: Audio device ID (e.g., 'hw:0,0', 'null', 'default').
            provider_type: Provider type ('squeezelite', 'sendspin').
            server_ip: Optional server IP (for Squeezelite/LMS).
            server_url: Optional WebSocket URL (for Sendspin).
            mac_address: Optional MAC address (auto-generated if empty).
            **extra_config: Additional provider-specific configuration.

        Returns:
            Tuple of (success: bool, message: str).
        """
        if self.config.player_exists(name):
            return False, "Player with this name already exists"

        # Get the provider
        provider = self.providers.get(provider_type)
        if provider is None:
            return False, f"Unknown provider type: {provider_type}"

        # Build initial config
        player_config: PlayerManager.PlayerConfig = {
            "name": name,
            "device": device,
            "provider": provider_type,
            "server_ip": server_ip,
            "server_url": server_url,
            "mac_address": mac_address,
            "enabled": True,
            "volume": 75,
            **extra_config,
        }

        # Validate config with provider
        is_valid, error = provider.validate_config(player_config)
        if not is_valid:
            return False, error

        # Let provider prepare config (generate MAC, client_id, etc.)
        player_config = provider.prepare_config(player_config)

        self.config.set_player(name, player_config)
        self.config.save()
        return True, "Player created successfully"

    def update_player(
        self,
        old_name: str,
        new_name: str,
        device: str,
        provider_type: str | None = None,
        server_ip: str = "",
        server_url: str = "",
        mac_address: str = "",
        **extra_config: Any,
    ) -> tuple[bool, str]:
        """
        Update an existing audio player.

        Args:
            old_name: Current name of the player to update.
            new_name: New name for the player (can be same as old_name).
            device: Audio device ID (e.g., 'hw:0,0', 'null', 'default').
            provider_type: Provider type (if changing providers).
            server_ip: Optional server IP (for Squeezelite/LMS).
            server_url: Optional WebSocket URL (for Sendspin).
            mac_address: Optional new MAC address.
            **extra_config: Additional provider-specific configuration.

        Returns:
            Tuple of (success: bool, message: str).
        """
        if not self.config.player_exists(old_name):
            return False, "Player not found"

        # If name is changing, check if new name already exists
        if old_name != new_name and self.config.player_exists(new_name):
            return False, "Player with this name already exists"

        # Stop the player if it's running (we'll need to restart with new config)
        was_running = self.get_player_status(old_name)
        if was_running:
            self.stop_player(old_name)

        # Get current player config
        player_config = self.config.get_player(old_name).copy()

        # Update the configuration
        player_config["name"] = new_name
        player_config["device"] = device
        player_config["server_ip"] = server_ip
        player_config["server_url"] = server_url
        if mac_address:
            player_config["mac_address"] = mac_address

        # Update provider if specified
        if provider_type:
            player_config["provider"] = provider_type

        # Merge extra config
        player_config.update(extra_config)

        # Get provider and validate
        provider = self.providers.get_for_player(player_config)
        if provider:
            is_valid, error = provider.validate_config(player_config)
            if not is_valid:
                return False, error
            player_config = provider.prepare_config(player_config)

        # If name changed, rename in config
        if old_name != new_name:
            self.config.delete_player(old_name)

        # Save updated config
        self.config.set_player(new_name, player_config)
        self.config.save()

        # Restart the player if it was running
        if was_running:
            success, message = self.start_player(new_name)
            if success:
                return True, "Player updated and restarted successfully"
            else:
                return True, f"Player updated successfully, but failed to restart: {message}"

        return True, "Player updated successfully"

    def delete_player(self, name: str) -> tuple[bool, str]:
        """
        Delete a player.

        Stops the player process if running and removes from configuration.

        Args:
            name: Name of the player to delete.

        Returns:
            Tuple of (success: bool, message: str).
        """
        if not self.config.player_exists(name):
            return False, "Player not found"

        # Stop the player if running
        self.stop_player(name)

        # Remove from config
        self.config.delete_player(name)
        self.config.save()
        return True, "Player deleted successfully"

    def start_player(self, name: str) -> tuple[bool, str]:
        """
        Start an audio player process.

        Launches a new subprocess using the appropriate provider's command.
        If the provider supports fallback and the primary fails, tries fallback.

        Args:
            name: Name of the player to start.

        Returns:
            Tuple of (success: bool, message: str).
        """
        player = self.config.get_player(name)
        if not player:
            return False, "Player not found"

        if self.process.is_running(name):
            return False, "Player already running"

        # Get the provider for this player
        provider = self.providers.get_for_player(player)
        if provider is None:
            provider_type = player.get("provider", "squeezelite")
            return False, f"Unknown provider type: {provider_type}"

        # Get log path
        log_path = self.process.get_log_path(name)

        # Build command using provider
        cmd = provider.build_command(player, log_path)

        # Get fallback command if provider supports it
        fallback_cmd = None
        if provider.supports_fallback():
            fallback_cmd = provider.build_fallback_command(player, log_path)

        logger.info(f"Starting player {name} ({provider.display_name}) with command: {' '.join(cmd)}")

        success, message = self.process.start(name, cmd, fallback_cmd)

        if success and fallback_cmd and "fallback" in message.lower():
            return True, f"Player {name} started with fallback (audio device '{player.get('device')}' not available)"

        return success, message

    def stop_player(self, name: str) -> tuple[bool, str]:
        """
        Stop a squeezelite player process.

        Args:
            name: Name of the player to stop.

        Returns:
            Tuple of (success: bool, message: str).
        """
        return self.process.stop(name)

    def get_player_status(self, name: str) -> bool:
        """
        Get the running status of a player.

        Args:
            name: Name of the player to check.

        Returns:
            True if the player process is running, False otherwise.
        """
        return self.process.is_running(name)

    def get_all_statuses(self) -> dict[str, bool]:
        """
        Get running status of all configured players.

        Returns:
            Dictionary mapping player names to their running status.
        """
        return self.process.get_all_statuses(self.config.list_players())

    def get_mixer_controls(self, device: str) -> list[str]:
        """
        Get available ALSA mixer controls for a device.

        Args:
            device: ALSA device identifier (e.g., 'hw:0,0').

        Returns:
            List of control names.
        """
        return self.audio.get_mixer_controls(device)

    def get_device_volume(self, device: str, control: str = "Master") -> int:
        """
        Get the current volume for an audio device.

        Args:
            device: ALSA device identifier.
            control: Mixer control name.

        Returns:
            Volume level as integer percentage (0-100).
        """
        return self.audio.get_volume(device, control)

    def set_device_volume(self, device: str, volume: int, control: str = "Master") -> tuple[bool, str]:
        """
        Set the volume for an audio device.

        Args:
            device: ALSA device identifier.
            volume: Volume level as integer percentage (0-100).
            control: Mixer control name.

        Returns:
            Tuple of (success: bool, message: str).
        """
        return self.audio.set_volume(device, volume, control)

    def get_player_volume(self, name: str) -> int | None:
        """
        Get the current volume for a player.

        Uses the player's provider for volume control.

        Args:
            name: Name of the player.

        Returns:
            Volume level as integer percentage (0-100), or None if player not found.
        """
        player = self.config.get_player(name)
        if not player:
            return None

        # Get the provider for this player
        provider = self.providers.get_for_player(player)
        if provider is None:
            # Fall back to stored volume if provider not found
            return player.get("volume", 75)

        # Get actual volume via provider
        actual_volume = provider.get_volume(player)

        # Update stored volume to match actual volume
        if "volume" not in player:
            player["volume"] = actual_volume
            self.config.save()

        return actual_volume

    def set_player_volume(self, name: str, volume: int) -> tuple[bool, str]:
        """
        Set the volume for a player.

        Uses the player's provider for volume control.

        Args:
            name: Name of the player.
            volume: Volume level as integer percentage (0-100).

        Returns:
            Tuple of (success: bool, message: str).
        """
        player = self.config.get_player(name)
        if not player:
            return False, "Player not found"

        if not 0 <= volume <= 100:
            return False, "Volume must be between 0 and 100"

        # Get the provider for this player
        provider = self.providers.get_for_player(player)
        if provider is None:
            # Just store volume if provider not found
            player["volume"] = volume
            self.config.save()
            return True, f"Volume set to {volume}% (provider not available)"

        # Set volume via provider
        success, message = provider.set_volume(player, volume)

        # Always update stored volume regardless of hardware control success
        player["volume"] = volume
        self.config.save()

        return success, message

    def get_available_providers(self) -> list[dict[str, str]]:
        """
        Get list of available provider types.

        Returns:
            List of provider info dictionaries.
        """
        return self.providers.get_provider_info()

    def get_now_playing(self, name: str) -> Any:
        """
        Get now-playing metadata for a player.

        Currently only supported for Sendspin players with a server_url configured.

        Args:
            name: Name of the player.

        Returns:
            TrackMetadata object if available, None otherwise.
        """
        player = self.config.get_player(name)
        if not player:
            return None

        provider = self.providers.get_for_player(player)
        if provider is None:
            return None

        # Check if provider supports now playing
        if hasattr(provider, "get_now_playing"):
            return provider.get_now_playing(player)

        return None


# =============================================================================
# Initialize managers and the main PlayerManager
# =============================================================================

try:
    logger.info("Initializing managers...")

    config_manager = ConfigManager(CONFIG_FILE)
    logger.info(f"ConfigManager initialized with {len(config_manager.players)} players")

    audio_manager = AudioManager(windows_mode=WINDOWS_MODE)
    logger.info("AudioManager initialized")

    process_manager = ProcessManager(log_dir=LOG_DIR)
    logger.info("ProcessManager initialized")

    # Initialize provider registry and register providers
    provider_registry = ProviderRegistry()
    provider_registry.register_instance("squeezelite", SqueezeliteProvider(audio_manager))
    provider_registry.register_instance("sendspin", SendspinProvider(audio_manager))
    logger.info(f"ProviderRegistry initialized with providers: {provider_registry.list_providers()}")

    manager = PlayerManager(config_manager, audio_manager, process_manager, provider_registry)
    logger.info("PlayerManager initialized successfully")

except Exception as e:
    logger.error(f"Failed to initialize managers: {e}")
    traceback.print_exc()
    sys.exit(1)


# =============================================================================
# Register Routes and WebSocket Handlers
# =============================================================================

# Register all Flask routes using the common module
register_routes(app, manager)

# Register WebSocket handlers using the common module
register_websocket_handlers(socketio, manager)

# Start status monitoring thread using the common module
start_status_monitor(socketio, manager)


# =============================================================================
# Main entry point
# =============================================================================

if __name__ == "__main__":
    # Start the Flask-SocketIO server using the common module
    run_server(app, socketio)
