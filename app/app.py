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
import subprocess
import sys
import threading
import time
import traceback
from typing import Any

from flask import Flask, jsonify, render_template, request, send_from_directory
from flask_socketio import SocketIO, emit
from flask_swagger_ui import get_swaggerui_blueprint
from managers import AudioManager, ConfigManager, ProcessManager
from providers import ProviderRegistry, SendspinProvider, SqueezeliteProvider

# =============================================================================
# CONSTANTS
# =============================================================================

# How often to poll player statuses and emit WebSocket updates
STATUS_MONITOR_INTERVAL_SECS = 2

# Delay before retrying after an error in status monitor loop
STATUS_MONITOR_ERROR_DELAY_SECS = 5

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
logger.info("Starting Squeezelite Multi-Room Controller")
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

try:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "squeezelite-multiroom-secret")
    socketio = SocketIO(app, cors_allowed_origins="*")

    # Configure Swagger UI
    SWAGGER_URL = "/api/docs"  # URL for exposing Swagger UI (without trailing '/')
    API_URL = "/api/swagger.yaml"  # Our API url (can of course be a local resource)

    # Call factory function to create our blueprint
    swaggerui_blueprint = get_swaggerui_blueprint(
        SWAGGER_URL,  # Swagger UI static files will be mapped to '{SWAGGER_URL}/dist/'
        API_URL,
        config={  # Swagger UI config overrides
            "app_name": "Squeezelite Multi-Room Controller API",
            "layout": "BaseLayout",
            "deepLinking": True,
            "showExtensions": True,
            "showCommonExtensions": True,
        },
    )

    # Register blueprint at URL
    app.register_blueprint(swaggerui_blueprint)

    logger.info("Flask app, SocketIO, and Swagger UI initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Flask app: {e}")
    traceback.print_exc()
    sys.exit(1)

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
# Flask Routes
# =============================================================================


@app.route("/")
def index():
    """Main page showing all players"""
    players = manager.players
    statuses = manager.get_all_statuses()
    devices = manager.get_audio_devices()
    return render_template("index.html", players=players, statuses=statuses, devices=devices)


@app.route("/api/swagger.yaml")
def swagger_yaml():
    """Serve the Swagger YAML specification"""
    try:
        return send_from_directory("/app", "swagger.yaml")
    except Exception as e:
        logger.error(f"Error serving swagger.yaml: {e}")
        return jsonify({"error": "Swagger specification not found"}), 404


@app.route("/api/players", methods=["GET"])
def get_players():
    """API endpoint to get all players"""
    return jsonify({"players": manager.players, "statuses": manager.get_all_statuses()})


@app.route("/api/devices", methods=["GET"])
def get_devices():
    """API endpoint to get audio devices (ALSA)"""
    return jsonify({"devices": manager.get_audio_devices()})


@app.route("/api/devices/portaudio", methods=["GET"])
def get_portaudio_devices():
    """API endpoint to get PortAudio devices (for Sendspin)"""
    import re

    try:
        result = subprocess.run(
            ["sendspin", "--list-audio-devices"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        # Parse the output - sendspin lists devices as "[0] Device Name"
        # Only include lines that match the device format
        devices = []
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            # Match lines like "[0] HDA NVidia: HDMI 0 (hw:1,3) (default)"
            match = re.match(r"^\[(\d+)\]\s*(.+)$", line)
            if match:
                index = match.group(1)
                name = match.group(2)
                devices.append({"index": index, "name": name, "raw": line})
        return jsonify(
            {
                "success": True,
                "devices": devices,
                "raw_output": result.stdout,
                "note": "Use device index (0, 1, 2) with --audio-device for sendspin",
            }
        )
    except FileNotFoundError:
        return jsonify(
            {
                "success": False,
                "message": "sendspin binary not found",
                "devices": [],
            }
        )
    except subprocess.TimeoutExpired:
        return jsonify(
            {
                "success": False,
                "message": "Timeout listing audio devices",
                "devices": [],
            }
        )
    except Exception as e:
        return jsonify(
            {
                "success": False,
                "message": str(e),
                "devices": [],
            }
        )


@app.route("/api/providers", methods=["GET"])
def get_providers():
    """API endpoint to get available player providers"""
    return jsonify({"providers": manager.get_available_providers()})


@app.route("/api/players", methods=["POST"])
def create_player():
    """API endpoint to create a new player"""
    data = request.json
    name = data.get("name")
    device = data.get("device", "default")
    provider_type = data.get("provider", "squeezelite")
    server_ip = data.get("server_ip", "")
    server_url = data.get("server_url", "")
    mac_address = data.get("mac_address", "")

    if not name:
        return jsonify({"success": False, "message": "Name is required"}), 400

    # Extract any extra provider-specific config
    extra_config = {
        k: v
        for k, v in data.items()
        if k not in ("name", "device", "provider", "server_ip", "server_url", "mac_address")
    }

    success, message = manager.create_player(
        name=name,
        device=device,
        provider_type=provider_type,
        server_ip=server_ip,
        server_url=server_url,
        mac_address=mac_address,
        **extra_config,
    )
    return jsonify({"success": success, "message": message})


@app.route("/api/players/<name>", methods=["PUT"])
def update_player(name):
    """API endpoint to update a player"""
    data = request.json
    new_name = data.get("name", name)
    device = data.get("device", "default")
    provider_type = data.get("provider")
    server_ip = data.get("server_ip", "")
    server_url = data.get("server_url", "")
    mac_address = data.get("mac_address", "")

    # Extract any extra provider-specific config
    extra_config = {
        k: v
        for k, v in data.items()
        if k not in ("name", "device", "provider", "server_ip", "server_url", "mac_address")
    }

    success, message = manager.update_player(
        old_name=name,
        new_name=new_name,
        device=device,
        provider_type=provider_type,
        server_ip=server_ip,
        server_url=server_url,
        mac_address=mac_address,
        **extra_config,
    )
    if success:
        return jsonify({"success": success, "message": message, "new_name": new_name})
    else:
        return jsonify({"success": success, "message": message}), 400


@app.route("/api/players/<name>", methods=["DELETE"])
def delete_player(name):
    """API endpoint to delete a player"""
    success, message = manager.delete_player(name)
    return jsonify({"success": success, "message": message})


@app.route("/api/players/<name>/start", methods=["POST"])
def start_player(name):
    """API endpoint to start a player"""
    success, message = manager.start_player(name)
    return jsonify({"success": success, "message": message})


@app.route("/api/players/<name>/stop", methods=["POST"])
def stop_player(name):
    """API endpoint to stop a player"""
    success, message = manager.stop_player(name)
    return jsonify({"success": success, "message": message})


@app.route("/api/players/<name>/status", methods=["GET"])
def get_player_status(name):
    """API endpoint to get player status"""
    status = manager.get_player_status(name)
    return jsonify({"running": status})


@app.route("/api/players/<n>/volume", methods=["GET"])
def get_player_volume(n):
    """API endpoint to get player volume"""
    try:
        volume = manager.get_player_volume(n)
        if volume is None:
            return jsonify({"success": False, "message": "Player not found"}), 404
        return jsonify({"success": True, "volume": volume})
    except Exception as e:
        logger.error(f"Error in get_player_volume for {n}: {e}")
        return jsonify({"success": False, "message": f"Server error: {str(e)}"}), 500


@app.route("/api/players/<n>/volume", methods=["POST"])
def set_player_volume(n):
    """API endpoint to set player volume"""
    try:
        data = request.json
        volume = data.get("volume")

        if volume is None:
            return jsonify({"success": False, "message": "Volume is required"}), 400

        try:
            volume = int(volume)
        except (ValueError, TypeError):
            return jsonify({"success": False, "message": "Volume must be a number"}), 400

        success, message = manager.set_player_volume(n, volume)
        return jsonify({"success": success, "message": message})
    except Exception as e:
        logger.error(f"Error in set_player_volume for {n}: {e}")
        logger.error(f"Request data: {request.get_data()}")
        return jsonify({"success": False, "message": f"Server error: {str(e)}"}), 500


@app.route("/api/debug/audio", methods=["GET"])
def debug_audio():
    """Debug endpoint to check audio device detection"""
    try:
        debug_info = {
            "container_mode": WINDOWS_MODE,
            "detected_devices": manager.get_audio_devices(),
            "aplay_available": False,
            "amixer_available": False,
            "aplay_output": "",
            "amixer_cards_output": "",
            "mixer_controls": {},
        }

        # Test aplay command
        try:
            result = subprocess.run(["aplay", "-l"], capture_output=True, text=True, check=True)
            debug_info["aplay_available"] = True
            debug_info["aplay_output"] = result.stdout
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            debug_info["aplay_output"] = str(e)

        # Test amixer command
        try:
            result = subprocess.run(["amixer"], capture_output=True, text=True, check=True)
            debug_info["amixer_available"] = True
            debug_info["amixer_cards_output"] = result.stdout
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            debug_info["amixer_cards_output"] = str(e)

        # Test mixer controls for each detected hardware device
        for device in debug_info["detected_devices"]:
            if device["id"].startswith("hw:"):
                device_id = device["id"]
                try:
                    controls = manager.get_mixer_controls(device_id)
                    debug_info["mixer_controls"][device_id] = controls
                except Exception as e:
                    debug_info["mixer_controls"][device_id] = f"Error: {e}"

        return jsonify(debug_info)
    except Exception as e:
        logger.error(f"Error in debug_audio: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# WebSocket handlers
# =============================================================================


@socketio.on("connect")
def handle_connect():
    """Handle WebSocket connection"""
    emit("status_update", manager.get_all_statuses())


def status_monitor():
    """Background thread to monitor player statuses"""
    logger.info("Starting status monitor thread")
    while True:
        try:
            statuses = manager.get_all_statuses()
            socketio.emit("status_update", statuses)
            time.sleep(STATUS_MONITOR_INTERVAL_SECS)
        except Exception as e:
            logger.error(f"Error in status monitor: {e}")
            time.sleep(STATUS_MONITOR_ERROR_DELAY_SECS)


# Start status monitoring thread
try:
    logger.info("Starting status monitoring thread...")
    status_thread = threading.Thread(target=status_monitor, daemon=True)
    status_thread.start()
    logger.info("Status monitoring thread started successfully")
except Exception as e:
    logger.error(f"Failed to start status monitoring thread: {e}")
    # Continue without status monitoring


# =============================================================================
# Main entry point
# =============================================================================

if __name__ == "__main__":
    try:
        logger.info("Starting Flask-SocketIO server...")
        logger.info("Server will be available at: http://0.0.0.0:8080")

        # Test if port is available
        import socket

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(("localhost", 8080))
        if result == 0:
            logger.warning("Port 8080 appears to be in use, but will try to bind anyway")
        sock.close()

        socketio.run(app, host="0.0.0.0", port=8080, debug=False, allow_unsafe_werkzeug=True)
    except Exception as e:
        logger.error(f"Failed to start Flask-SocketIO server: {e}")
        traceback.print_exc()
        sys.exit(1)
