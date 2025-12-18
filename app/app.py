#!/usr/bin/env python3
"""
Squeezelite Multi-Room Controller - Main Application

A Flask-based web application for managing multiple Squeezelite audio players.
Provides a REST API and web interface for creating, configuring, and controlling
audio players across different rooms/zones.

Key Components:
    - SqueezeliteManager: Core class handling player lifecycle, audio devices,
      and volume control via ALSA
    - REST API: Endpoints for player CRUD operations, status, and volume control
    - WebSocket: Real-time status updates to connected browsers
    - Swagger UI: Interactive API documentation at /api/docs

Configuration:
    - Players stored in /app/config/players.yaml
    - Logs written to /app/logs/
    - Environment variables: SECRET_KEY, SUPERVISOR_USER, SUPERVISOR_PASSWORD

Usage:
    Run directly: python3 app.py
    Via supervisor: supervisord -c /etc/supervisor/conf.d/supervisord.conf
"""

import os
import sys
import json
import subprocess
import signal
import yaml
import traceback
import re
from typing import Dict, List, Optional, Tuple, Any
from flask import Flask, render_template, request, jsonify, redirect, url_for, send_from_directory
from flask_socketio import SocketIO, emit
from flask_swagger_ui import get_swaggerui_blueprint
import threading
import time
import logging

# =============================================================================
# CONSTANTS
# =============================================================================

# -----------------------------------------------------------------------------
# ALSA Mixer Control Names
# -----------------------------------------------------------------------------
# These arrays define which ALSA mixer controls to check when reading/setting
# volume. ALSA sound cards expose different controls depending on the hardware.
# Common control names include:
#   - Master: Main output volume (most common)
#   - PCM: Digital audio volume
#   - Speaker: Built-in speaker output
#   - Headphone: Headphone jack output
#   - Digital: Digital/SPDIF output
#   - Capture: Input/recording level (read-only for our purposes)
#
# The code tries each control in order until one works.

# Default fallback when no controls can be detected
DEFAULT_MIXER_CONTROLS = ['Master', 'PCM']

# Controls to try when reading volume (includes Capture for status reporting)
VOLUME_READ_CONTROLS = ['Master', 'PCM', 'Speaker', 'Headphone', 'Digital', 'Capture']

# Controls to try when setting volume (excludes Capture - it's for input levels)
VOLUME_WRITE_CONTROLS = ['Master', 'PCM', 'Speaker', 'Headphone', 'Digital']

# Virtual/software devices that don't support hardware volume control
VIRTUAL_AUDIO_DEVICES = ['null', 'pulse', 'dmix', 'default']

# -----------------------------------------------------------------------------
# Timing Constants (in seconds)
# -----------------------------------------------------------------------------

# Delay after starting a process to check if it failed immediately
PROCESS_STARTUP_DELAY_SECS = 0.5

# Timeout when waiting for process to stop gracefully (SIGTERM)
PROCESS_STOP_TIMEOUT_SECS = 5

# Timeout when waiting for process to be killed forcefully (SIGKILL)
PROCESS_KILL_TIMEOUT_SECS = 2

# How often to poll player statuses and emit WebSocket updates
STATUS_MONITOR_INTERVAL_SECS = 2

# Delay before retrying after an error in status monitor loop
STATUS_MONITOR_ERROR_DELAY_SECS = 5

# -----------------------------------------------------------------------------
# Default Values
# -----------------------------------------------------------------------------

# Default volume percentage for virtual devices or when detection fails
DEFAULT_VOLUME_PERCENT = 75

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================

# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/app/logs/application.log')
    ]
)
logger = logging.getLogger(__name__)

# Log startup information
logger.info("="*50)
logger.info("Starting Squeezelite Multi-Room Controller")
logger.info(f"Python version: {sys.version}")
logger.info(f"Working directory: {os.getcwd()}")
logger.info(f"Python path: {sys.path}")
logger.info("="*50)

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
WINDOWS_MODE = os.environ.get('SQUEEZELITE_WINDOWS_MODE', '0') == '1'
if WINDOWS_MODE:
    logger.warning("Running in Windows compatibility mode - audio device access is limited")

# Ensure required directories exist
required_dirs = ['/app/config', '/app/logs', '/app/data']
for directory in required_dirs:
    try:
        os.makedirs(directory, exist_ok=True)
        logger.info(f"Directory ensured: {directory}")
    except Exception as e:
        logger.error(f"Could not create directory {directory}: {e}")

try:
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'squeezelite-multiroom-secret')
    socketio = SocketIO(app, cors_allowed_origins="*")
    
    # Configure Swagger UI
    SWAGGER_URL = '/api/docs'  # URL for exposing Swagger UI (without trailing '/')
    API_URL = '/api/swagger.yaml'  # Our API url (can of course be a local resource)
    
    # Call factory function to create our blueprint
    swaggerui_blueprint = get_swaggerui_blueprint(
        SWAGGER_URL,  # Swagger UI static files will be mapped to '{SWAGGER_URL}/dist/'
        API_URL,
        config={  # Swagger UI config overrides
            'app_name': "Squeezelite Multi-Room Controller API",
            'layout': 'BaseLayout',
            'deepLinking': True,
            'showExtensions': True,
            'showCommonExtensions': True
        }
    )
    
    # Register blueprint at URL
    app.register_blueprint(swaggerui_blueprint)
    
    logger.info("Flask app, SocketIO, and Swagger UI initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Flask app: {e}")
    traceback.print_exc()
    sys.exit(1)

CONFIG_FILE = '/app/config/players.yaml'
PLAYERS_DIR = '/app/config/players'

# Ensure directories exist
os.makedirs('/app/config', exist_ok=True)
os.makedirs(PLAYERS_DIR, exist_ok=True)
os.makedirs('/app/logs', exist_ok=True)

class SqueezeliteManager:
    """
    Manages Squeezelite audio player instances.

    Handles player lifecycle (create, start, stop, delete), configuration
    persistence, audio device detection, and volume control via ALSA.

    Attributes:
        players: Dictionary mapping player names to their configuration dicts.
                 Each config contains: name, device, server_ip, mac_address, enabled, volume
        processes: Dictionary mapping player names to their subprocess.Popen instances.
    """

    # Type aliases for clarity
    PlayerConfig = Dict[str, Any]  # Keys: name, device, server_ip, mac_address, enabled, volume
    AudioDevice = Dict[str, str]   # Keys: id, name, card, device

    def __init__(self) -> None:
        self.players: Dict[str, SqueezeliteManager.PlayerConfig] = {}
        self.processes: Dict[str, subprocess.Popen[bytes]] = {}
        self.load_config()
    
    def load_config(self) -> None:
        """
        Load player configuration from the YAML configuration file.

        Reads CONFIG_FILE (/app/config/players.yaml) and populates self.players
        with stored player configurations. If the file doesn't exist or contains
        invalid YAML, initializes with an empty dictionary.

        Side Effects:
            - Modifies self.players dictionary
            - Logs errors if file reading or YAML parsing fails

        Returns:
            None
        """
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    self.players = yaml.safe_load(f) or {}
            except Exception as e:
                logger.error(f"Error loading config: {e}")
                self.players = {}
        else:
            self.players = {}
    
    def save_config(self) -> None:
        """
        Save current player configuration to the YAML configuration file.

        Writes self.players dictionary to CONFIG_FILE in YAML format.
        Uses block style (not flow style) for human readability.

        Side Effects:
            - Writes to CONFIG_FILE (/app/config/players.yaml)
            - Logs errors if file writing fails

        Returns:
            None
        """
        try:
            with open(CONFIG_FILE, 'w') as f:
                yaml.dump(self.players, f, default_flow_style=False)
        except Exception as e:
            logger.error(f"Error saving config: {e}")
    
    def get_audio_devices(self) -> List["SqueezeliteManager.AudioDevice"]:
        """Get list of available audio devices.

        Returns:
            List of audio device dictionaries, each containing:
            - id: ALSA device identifier (e.g., 'hw:0,0', 'null', 'default')
            - name: Human-readable device name
            - card: ALSA card number or identifier
            - device: ALSA device number
        """
        if WINDOWS_MODE:
            logger.info("Windows mode detected - returning simulated audio devices")
            return [
                {'id': 'default', 'name': 'Default Audio Device (Windows)', 'card': '0', 'device': '0'},
                {'id': 'pulse', 'name': 'PulseAudio (Network)', 'card': 'pulse', 'device': '0'},
                {'id': 'tcp:host.docker.internal:4713', 'name': 'Network Audio Stream', 'card': 'net', 'device': '0'}
            ]
        
        # Always provide fallback devices
        fallback_devices = [
            {'id': 'null', 'name': 'Null Audio Device (Silent)', 'card': 'null', 'device': '0'},
            {'id': 'default', 'name': 'Default Audio Device', 'card': '0', 'device': '0'},
            {'id': 'dmix', 'name': 'Software Mixing Device', 'card': 'dmix', 'device': '0'}
        ]
        
        try:
            logger.debug("Attempting to detect hardware audio devices with aplay -l")
            result = subprocess.run(['aplay', '-l'], 
                                  capture_output=True, text=True, check=True)
            devices = []
            
            logger.debug(f"aplay -l output:\n{result.stdout}")
            
            # Parse actual audio devices
            for line in result.stdout.split('\n'):
                if 'card' in line and ':' in line:
                    # Parse line like "card 0: PCH [HDA Intel PCH], device 0: ALC887-VD Analog [ALC887-VD Analog]"
                    parts = line.split(':')
                    if len(parts) >= 2:
                        card_info = parts[0].strip()
                        device_info = parts[1].strip()
                        # Extract card and device numbers
                        try:
                            card_num = card_info.split()[1]
                            if 'device' in line:
                                device_num = line.split('device')[1].split(':')[0].strip()
                                device_id = f"hw:{card_num},{device_num}"
                                device_name = device_info.split('[')[0].strip() if '[' in device_info else device_info
                                devices.append({
                                    'id': device_id,
                                    'name': f"{device_name} ({device_id})",
                                    'card': card_num,
                                    'device': device_num
                                })
                                logger.debug(f"Found hardware device: {device_name} -> {device_id}")
                        except (IndexError, ValueError) as e:
                            logger.warning(f"Error parsing audio device line: {line} - {e}")
                            continue
            
            # If we found real devices, add them to fallback devices
            if devices:
                logger.info(f"Found {len(devices)} hardware audio devices")
                return fallback_devices + devices
            else:
                logger.warning("No hardware audio devices found in aplay output, using fallback devices only")
                return fallback_devices
                
        except subprocess.CalledProcessError as e:
            logger.warning(f"Could not get audio devices list (aplay failed): {e}")
            logger.debug(f"aplay stderr: {e.stderr.decode() if e.stderr else 'No stderr'}")
            return fallback_devices
        except FileNotFoundError:
            logger.warning("aplay command not found, using fallback devices only")
            return fallback_devices
        except Exception as e:
            logger.error(f"Unexpected error getting audio devices: {e}")
            return fallback_devices
    
    def create_player(
        self,
        name: str,
        device: str,
        server_ip: str = '',
        mac_address: str = ''
    ) -> Tuple[bool, str]:
        """Create a new squeezelite player.

        Args:
            name: Unique name for the player (used as identifier).
            device: ALSA device ID (e.g., 'hw:0,0', 'null').
            server_ip: Optional Logitech Media Server IP address.
            mac_address: Optional MAC address. If empty, one is auto-generated.

        Returns:
            Tuple of (success: bool, message: str).
        """
        if name in self.players:
            return False, "Player with this name already exists"
        
        if not mac_address:
            # Generate a MAC address based on the player name
            import hashlib
            hash_obj = hashlib.md5(name.encode())
            mac_hex = hash_obj.hexdigest()[:12]
            mac_address = ':'.join([mac_hex[i:i+2] for i in range(0, 12, 2)])
        
        player_config = {
            'name': name,
            'device': device,
            'server_ip': server_ip,
            'mac_address': mac_address,
            'enabled': True,
            'volume': 75
        }
        
        self.players[name] = player_config
        self.save_config()
        return True, "Player created successfully"

    def update_player(
        self,
        old_name: str,
        new_name: str,
        device: str,
        server_ip: str = '',
        mac_address: str = ''
    ) -> Tuple[bool, str]:
        """Update an existing squeezelite player.

        Args:
            old_name: Current name of the player to update.
            new_name: New name for the player (can be same as old_name).
            device: ALSA device ID (e.g., 'hw:0,0', 'null').
            server_ip: Optional Logitech Media Server IP address.
            mac_address: Optional new MAC address.

        Returns:
            Tuple of (success: bool, message: str).
        """
        if old_name not in self.players:
            return False, "Player not found"
        
        # If name is changing, check if new name already exists
        if old_name != new_name and new_name in self.players:
            return False, "Player with this name already exists"
        
        # Stop the player if it's running (we'll need to restart with new config)
        was_running = self.get_player_status(old_name)
        if was_running:
            self.stop_player(old_name)
        
        # Get current player config
        player_config = self.players[old_name].copy()
        
        # Update the configuration
        player_config['name'] = new_name
        player_config['device'] = device
        player_config['server_ip'] = server_ip
        if mac_address:
            player_config['mac_address'] = mac_address
        
        # If name changed, remove old entry and add new one
        if old_name != new_name:
            del self.players[old_name]
            # Also remove from processes if exists
            if old_name in self.processes:
                del self.processes[old_name]
        
        # Save updated config
        self.players[new_name] = player_config
        self.save_config()
        
        # Restart the player if it was running
        if was_running:
            success, message = self.start_player(new_name)
            if success:
                return True, f"Player updated and restarted successfully"
            else:
                return True, f"Player updated successfully, but failed to restart: {message}"
        
        return True, "Player updated successfully"

    def delete_player(self, name: str) -> Tuple[bool, str]:
        """Delete a player.

        Stops the player process if running and removes from configuration.

        Args:
            name: Name of the player to delete.

        Returns:
            Tuple of (success: bool, message: str).
        """
        if name not in self.players:
            return False, "Player not found"

        # Stop the player if running
        self.stop_player(name)

        # Remove from config
        del self.players[name]
        self.save_config()
        return True, "Player deleted successfully"
    
    def start_player(self, name: str) -> Tuple[bool, str]:
        """Start a squeezelite player process.

        Launches a new squeezelite subprocess with the player's configuration.
        If the configured audio device fails, falls back to null device.

        Args:
            name: Name of the player to start.

        Returns:
            Tuple of (success: bool, message: str).
        """
        if name not in self.players:
            return False, "Player not found"

        if name in self.processes and self.processes[name].poll() is None:
            return False, "Player already running"

        player = self.players[name]
        
        # Build squeezelite command
        cmd = [
            'squeezelite',
            '-n', player['name'],
            '-o', player['device'],
            '-m', player['mac_address']
        ]
        
        if player.get('server_ip'):
            cmd.extend(['-s', player['server_ip']])
        
        # Add logging
        log_file = f"/app/logs/{name}.log"
        cmd.extend(['-f', log_file])
        
        # Add options for better compatibility with virtual/missing devices
        cmd.extend([
            '-a', '80',  # Set buffer size
            '-b', '500:2000',  # Set buffer parameters
            '-C', '5'  # Close output device when idle
        ])
        
        # If using null device, add specific parameters
        if player['device'] == 'null':
            cmd.extend(['-r', '44100'])  # Set sample rate for null device
        
        logger.info(f"Starting player {name} with command: {' '.join(cmd)}")
        
        try:
            # Start the process
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid
            )
            
            self.processes[name] = process
            
            # Give the process a moment to start and check if it fails immediately
            time.sleep(PROCESS_STARTUP_DELAY_SECS)
            
            if process.poll() is not None:
                # Process terminated immediately, check error
                stdout, stderr = process.communicate()
                error_msg = stderr.decode() if stderr else "Unknown error"
                logger.error(f"Player {name} failed to start: {error_msg}")
                
                # Try with null device as fallback if original device failed
                if player['device'] != 'null':
                    logger.info(f"Retrying player {name} with null device as fallback")
                    
                    # Update command to use null device
                    fallback_cmd = cmd.copy()
                    for i, arg in enumerate(fallback_cmd):
                        if arg == '-o':
                            fallback_cmd[i + 1] = 'null'
                            break
                    
                    # Add null device specific parameters
                    if '-r' not in fallback_cmd:
                        fallback_cmd.extend(['-r', '44100'])
                    
                    logger.info(f"Fallback command: {' '.join(fallback_cmd)}")
                    
                    try:
                        process = subprocess.Popen(
                            fallback_cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            preexec_fn=os.setsid
                        )
                        
                        self.processes[name] = process
                        time.sleep(PROCESS_STARTUP_DELAY_SECS)

                        if process.poll() is not None:
                            stdout, stderr = process.communicate()
                            error_msg = stderr.decode() if stderr else "Unknown error"
                            return False, f"Player failed to start even with null device: {error_msg}"
                        else:
                            logger.info(f"Player {name} started successfully with null device fallback")
                            return True, f"Player {name} started with null device (audio device '{player['device']}' not available)"
                    
                    except Exception as e:
                        logger.error(f"Error starting player {name} with fallback: {e}")
                        return False, f"Error starting player with fallback: {e}"
                else:
                    return False, f"Player failed to start: {error_msg}"
            
            logger.info(f"Started player {name} with PID {process.pid}")
            return True, f"Player {name} started successfully"
            
        except FileNotFoundError:
            logger.error("squeezelite binary not found")
            return False, "squeezelite binary not found - container may not be built correctly"
        except Exception as e:
            logger.error(f"Error starting player {name}: {e}")
            return False, f"Error starting player: {e}"
    
    def stop_player(self, name: str) -> Tuple[bool, str]:
        """
        Stop a squeezelite player process.

        Sends SIGTERM to gracefully stop the process. If the process doesn't
        terminate within PROCESS_STOP_TIMEOUT_SECS, sends SIGKILL.

        Args:
            name: Name of the player to stop.

        Returns:
            Tuple of (success: bool, message: str).

        Side Effects:
            - Removes process from self.processes dict
            - Logs stop/error messages
        """
        if name not in self.processes:
            return False, "Player not running"
        
        process = self.processes[name]
        if process.poll() is not None:
            # Process already terminated
            del self.processes[name]
            return False, "Player was not running"
        
        try:
            # Send SIGTERM to the process group
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            
            # Wait for process to terminate
            process.wait(timeout=PROCESS_STOP_TIMEOUT_SECS)
            del self.processes[name]
            logger.info(f"Stopped player {name}")
            return True, f"Player {name} stopped successfully"
            
        except subprocess.TimeoutExpired:
            # Force kill if it doesn't respond to SIGTERM
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                process.wait(timeout=PROCESS_KILL_TIMEOUT_SECS)
            except:
                pass
            del self.processes[name]
            return True, f"Player {name} force stopped"
        except Exception as e:
            logger.error(f"Error stopping player {name}: {e}")
            return False, f"Error stopping player: {e}"
    
    def get_player_status(self, name: str) -> bool:
        """
        Get the running status of a player.

        Checks if the player's subprocess is still running by polling its status.

        Args:
            name: Name of the player to check.

        Returns:
            True if the player process is running, False otherwise.
        """
        if name not in self.processes:
            return False
        
        process = self.processes[name]
        return process.poll() is None
    
    def get_all_statuses(self) -> Dict[str, bool]:
        """
        Get running status of all configured players.

        Returns:
            Dictionary mapping player names to their running status (True/False).
        """
        statuses = {}
        for name in self.players:
            statuses[name] = self.get_player_status(name)
        return statuses
    
    def get_mixer_controls(self, device: str) -> List[str]:
        """
        Get available ALSA mixer controls for a device.

        Queries amixer for the list of simple controls available on the
        specified sound card.

        Args:
            device: ALSA device identifier (e.g., 'hw:0,0').

        Returns:
            List of control names (e.g., ['Master', 'PCM', 'Headphone']).
            Returns DEFAULT_MIXER_CONTROLS for virtual devices.
        """
        if WINDOWS_MODE or device in VIRTUAL_AUDIO_DEVICES:
            # Return virtual controls for non-hardware devices
            return DEFAULT_MIXER_CONTROLS.copy()
        
        try:
            # Extract card number from device ID
            card_match = re.search(r'hw:([0-9]+)', device)
            if not card_match:
                return DEFAULT_MIXER_CONTROLS.copy()
            
            card_num = card_match.group(1)
            result = subprocess.run(['amixer', '-c', card_num, 'scontrols'], 
                                  capture_output=True, text=True, check=True)
            
            controls = []
            for line in result.stdout.split('\n'):
                if "Simple mixer control" in line:
                    # Extract control name from line like "Simple mixer control 'Master',0"
                    match = re.search(r"'([^']+)'", line)
                    if match:
                        controls.append(match.group(1))
            
            return controls if controls else DEFAULT_MIXER_CONTROLS.copy()

        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.warning(f"Could not get mixer controls for device {device}: {e}")
            return DEFAULT_MIXER_CONTROLS.copy()
    
    def get_device_volume(self, device: str, control: str = 'Master') -> int:
        """
        Get the current volume for an audio device.

        Queries the ALSA mixer to read the current volume level. Tries multiple
        control names (Master, PCM, etc.) until one works.

        Args:
            device: ALSA device identifier (e.g., 'hw:0,0').
            control: Preferred control name (default: 'Master').

        Returns:
            Volume level as integer percentage (0-100).
            Returns DEFAULT_VOLUME_PERCENT for virtual devices or on error.
        """
        if WINDOWS_MODE or device in VIRTUAL_AUDIO_DEVICES:
            # Return default volume for virtual devices
            logger.debug(f"Virtual device {device}, returning default volume")
            return DEFAULT_VOLUME_PERCENT

        try:
            # Extract card number from device ID
            card_match = re.search(r'hw:([0-9]+)', device)
            if not card_match:
                logger.debug(f"No card number found in device {device}, returning default volume")
                return DEFAULT_VOLUME_PERCENT

            card_num = card_match.group(1)

            for control_name in VOLUME_READ_CONTROLS:
                try:
                    result = subprocess.run(['amixer', '-c', card_num, 'sget', control_name],
                                          capture_output=True, text=True, check=True)

                    # Parse volume from output like "[75%]"
                    volume_match = re.search(r'\[(\d+)%\]', result.stdout)
                    if volume_match:
                        volume = int(volume_match.group(1))
                        logger.debug(f"Got volume {volume}% for device {device} control {control_name}")
                        return volume
                except subprocess.CalledProcessError:
                    continue  # Try next control name

            # If no controls worked, return default
            logger.warning(f"Could not find working volume control for device {device}")
            return DEFAULT_VOLUME_PERCENT

        except (subprocess.CalledProcessError, FileNotFoundError, ValueError) as e:
            logger.warning(f"Could not get volume for device {device}: {e}")
            return DEFAULT_VOLUME_PERCENT
    
    def set_device_volume(
        self, device: str, volume: int, control: str = 'Master'
    ) -> Tuple[bool, str]:
        """
        Set the volume for an audio device.

        Uses amixer to set the volume level on the ALSA mixer. Tries multiple
        control names (Master, PCM, etc.) until one works.

        Args:
            device: ALSA device identifier (e.g., 'hw:0,0').
            volume: Volume level as integer percentage (0-100).
            control: Preferred control name (default: 'Master').

        Returns:
            Tuple of (success: bool, message: str).

        Side Effects:
            - Changes hardware volume level if device supports it
            - Logs volume changes and errors
        """
        if not 0 <= volume <= 100:
            return False, "Volume must be between 0 and 100"

        if WINDOWS_MODE or device in VIRTUAL_AUDIO_DEVICES:
            # For virtual devices, just store the volume setting
            logger.info(f"Virtual device {device}, volume {volume}% stored (no hardware control)")
            return True, f"Volume set to {volume}% (virtual device)"

        try:
            # Extract card number from device ID
            card_match = re.search(r'hw:([0-9]+)', device)
            if not card_match:
                logger.debug(f"No card number found in device {device}, storing volume only")
                return True, f"Volume set to {volume}% (no hardware control)"

            card_num = card_match.group(1)

            for control_name in VOLUME_WRITE_CONTROLS:
                try:
                    result = subprocess.run(['amixer', '-c', card_num, 'sset', control_name, f'{volume}%'], 
                                          capture_output=True, text=True, check=True)
                    
                    logger.info(f"Set volume to {volume}% for device {device} control {control_name}")
                    return True, f"Volume set to {volume}% ({control_name})"
                except subprocess.CalledProcessError as e:
                    logger.debug(f"Control {control_name} failed for device {device}: {e}")
                    continue  # Try next control name
            
            # If no controls worked
            logger.warning(f"Could not find working volume control for device {device}")
            return False, f"No working volume controls found for device {device}"
            
        except subprocess.CalledProcessError as e:
            # Handle both string and bytes stderr
            if hasattr(e, 'stderr') and e.stderr:
                if isinstance(e.stderr, bytes):
                    error_msg = e.stderr.decode()
                else:
                    error_msg = str(e.stderr)
            else:
                error_msg = str(e)
            logger.warning(f"Could not set volume for device {device}: {error_msg}")
            return False, f"Could not set volume: {error_msg}"
        except FileNotFoundError:
            logger.warning("amixer command not found")
            return False, "Audio mixer control not available"
    
    def get_player_volume(self, name: str) -> Optional[int]:
        """
        Get the current volume for a player.

        Retrieves the actual hardware volume for the player's audio device.
        Updates stored volume in config if not previously set.

        Args:
            name: Name of the player.

        Returns:
            Volume level as integer percentage (0-100), or None if player not found.
        """
        if name not in self.players:
            return None
        
        player = self.players[name]
        device = player['device']
        
        # First try to get actual hardware volume
        actual_volume = self.get_device_volume(device)
        
        # Update stored volume to match actual volume
        if 'volume' not in player:
            player['volume'] = actual_volume
            self.save_config()
        
        return actual_volume
    
    def set_player_volume(self, name: str, volume: int) -> Tuple[bool, str]:
        """
        Set the volume for a player.

        Sets the hardware volume for the player's audio device and stores the
        volume setting in the player configuration.

        Args:
            name: Name of the player.
            volume: Volume level as integer percentage (0-100).

        Returns:
            Tuple of (success: bool, message: str).

        Side Effects:
            - Changes hardware volume if device supports it
            - Updates and saves player volume in config file
        """
        if name not in self.players:
            return False, "Player not found"
        
        if not 0 <= volume <= 100:
            return False, "Volume must be between 0 and 100"
        
        player = self.players[name]
        device = player['device']
        
        # Set the hardware volume
        success, message = self.set_device_volume(device, volume)
        
        # Always update stored volume regardless of hardware control success
        player['volume'] = volume
        self.save_config()
        
        return success, message

# Initialize the manager
try:
    logger.info("Initializing Squeezelite Manager...")
    manager = SqueezeliteManager()
    logger.info("Squeezelite Manager initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Squeezelite Manager: {e}")
    traceback.print_exc()
    sys.exit(1)

@app.route('/')
def index():
    """Main page showing all players"""
    players = manager.players
    statuses = manager.get_all_statuses()
    devices = manager.get_audio_devices()
    return render_template('index.html', players=players, statuses=statuses, devices=devices)

@app.route('/api/swagger.yaml')
def swagger_yaml():
    """Serve the Swagger YAML specification"""
    try:
        return send_from_directory('/app', 'swagger.yaml')
    except Exception as e:
        logger.error(f"Error serving swagger.yaml: {e}")
        return jsonify({'error': 'Swagger specification not found'}), 404

@app.route('/api/players', methods=['GET'])
def get_players():
    """API endpoint to get all players"""
    return jsonify({
        'players': manager.players,
        'statuses': manager.get_all_statuses()
    })

@app.route('/api/devices', methods=['GET'])
def get_devices():
    """API endpoint to get audio devices"""
    return jsonify({'devices': manager.get_audio_devices()})

@app.route('/api/players', methods=['POST'])
def create_player():
    """API endpoint to create a new player"""
    data = request.json
    name = data.get('name')
    device = data.get('device')
    server_ip = data.get('server_ip', '')
    mac_address = data.get('mac_address', '')
    
    if not name or not device:
        return jsonify({'success': False, 'message': 'Name and device are required'}), 400
    
    success, message = manager.create_player(name, device, server_ip, mac_address)
    return jsonify({'success': success, 'message': message})

@app.route('/api/players/<name>', methods=['PUT'])
def update_player(name):
    """API endpoint to update a player"""
    data = request.json
    new_name = data.get('name', name)
    device = data.get('device')
    server_ip = data.get('server_ip', '')
    mac_address = data.get('mac_address', '')
    
    if not device:
        return jsonify({'success': False, 'message': 'Device is required'}), 400
    
    success, message = manager.update_player(name, new_name, device, server_ip, mac_address)
    if success:
        return jsonify({'success': success, 'message': message, 'new_name': new_name})
    else:
        return jsonify({'success': success, 'message': message}), 400

@app.route('/api/players/<name>', methods=['DELETE'])
def delete_player(name):
    """API endpoint to delete a player"""
    success, message = manager.delete_player(name)
    return jsonify({'success': success, 'message': message})

@app.route('/api/players/<name>/start', methods=['POST'])
def start_player(name):
    """API endpoint to start a player"""
    success, message = manager.start_player(name)
    return jsonify({'success': success, 'message': message})

@app.route('/api/players/<name>/stop', methods=['POST'])
def stop_player(name):
    """API endpoint to stop a player"""
    success, message = manager.stop_player(name)
    return jsonify({'success': success, 'message': message})

@app.route('/api/players/<name>/status', methods=['GET'])
def get_player_status(name):
    """API endpoint to get player status"""
    status = manager.get_player_status(name)
    return jsonify({'running': status})

@app.route('/api/players/<n>/volume', methods=['GET'])
def get_player_volume(n):
    """API endpoint to get player volume"""
    try:
        volume = manager.get_player_volume(n)
        if volume is None:
            return jsonify({'success': False, 'message': 'Player not found'}), 404
        return jsonify({'success': True, 'volume': volume})
    except Exception as e:
        logger.error(f"Error in get_player_volume for {n}: {e}")
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'}), 500

@app.route('/api/players/<n>/volume', methods=['POST'])
def set_player_volume(n):
    """API endpoint to set player volume"""
    try:
        data = request.json
        volume = data.get('volume')
        
        if volume is None:
            return jsonify({'success': False, 'message': 'Volume is required'}), 400
        
        try:
            volume = int(volume)
        except (ValueError, TypeError):
            return jsonify({'success': False, 'message': 'Volume must be a number'}), 400
        
        success, message = manager.set_player_volume(n, volume)
        return jsonify({'success': success, 'message': message})
    except Exception as e:
        logger.error(f"Error in set_player_volume for {n}: {e}")
        logger.error(f"Request data: {request.get_data()}")
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'}), 500

@app.route('/api/debug/audio', methods=['GET'])
def debug_audio():
    """Debug endpoint to check audio device detection"""
    try:
        debug_info = {
            'container_mode': WINDOWS_MODE,
            'detected_devices': manager.get_audio_devices(),
            'aplay_available': False,
            'amixer_available': False,
            'aplay_output': '',
            'amixer_cards_output': '',
            'mixer_controls': {}
        }
        
        # Test aplay command
        try:
            result = subprocess.run(['aplay', '-l'], capture_output=True, text=True, check=True)
            debug_info['aplay_available'] = True
            debug_info['aplay_output'] = result.stdout
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            debug_info['aplay_output'] = str(e)
        
        # Test amixer command
        try:
            result = subprocess.run(['amixer'], capture_output=True, text=True, check=True)
            debug_info['amixer_available'] = True
            debug_info['amixer_cards_output'] = result.stdout
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            debug_info['amixer_cards_output'] = str(e)
        
        # Test mixer controls for each detected hardware device
        for device in debug_info['detected_devices']:
            if device['id'].startswith('hw:'):
                device_id = device['id']
                try:
                    controls = manager.get_mixer_controls(device_id)
                    debug_info['mixer_controls'][device_id] = controls
                except Exception as e:
                    debug_info['mixer_controls'][device_id] = f"Error: {e}"
        
        return jsonify(debug_info)
    except Exception as e:
        logger.error(f"Error in debug_audio: {e}")
        return jsonify({'error': str(e)}), 500

@socketio.on('connect')
def handle_connect():
    """Handle WebSocket connection"""
    emit('status_update', manager.get_all_statuses())

def status_monitor():
    """Background thread to monitor player statuses"""
    logger.info("Starting status monitor thread")
    while True:
        try:
            statuses = manager.get_all_statuses()
            socketio.emit('status_update', statuses)
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

if __name__ == '__main__':
    try:
        logger.info("Starting Flask-SocketIO server...")
        logger.info("Server will be available at: http://0.0.0.0:8080")
        
        # Test if port is available
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('localhost', 8080))
        if result == 0:
            logger.warning("Port 8080 appears to be in use, but will try to bind anyway")
        sock.close()
        
        socketio.run(app, host='0.0.0.0', port=8080, debug=False, allow_unsafe_werkzeug=True)
    except Exception as e:
        logger.error(f"Failed to start Flask-SocketIO server: {e}")
        traceback.print_exc()
        sys.exit(1)
