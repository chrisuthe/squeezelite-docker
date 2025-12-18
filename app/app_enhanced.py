#!/usr/bin/env python3
"""
Squeezelite Multi-Room Controller - Enhanced Version with State Persistence

Extended version of app.py that adds automatic state persistence and restoration.
When the container restarts, previously running players are automatically restarted.

Additional Features (vs app.py):
    - State persistence: Running players saved to /app/config/player_states.yaml
    - Auto-restore: Players automatically restarted on container startup
    - Graceful shutdown: Signal handlers for clean process termination
    - Periodic state saving: Background thread saves state every 30 seconds

State File Format (player_states.yaml):
    timestamp: ISO format datetime of last save
    running_players: List of player names that were running
    total_players: Total number of configured players

Configuration:
    - State freshness timeout: 5 minutes (states older than this are not restored)
    - State save interval: 30 seconds
    - Restore delay: 3 seconds after startup

Note:
    Use this version instead of app.py if you need players to survive container
    restarts. Configure supervisord to run this file instead of app.py.
"""

import os
import sys
import json
import subprocess
import signal
import yaml
import psutil
import traceback
import re
import threading
import time
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, send_from_directory
from flask_socketio import SocketIO, emit
from flask_swagger_ui import get_swaggerui_blueprint
import logging

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
STATE_FILE = '/app/config/player_states.yaml'  # NEW: State persistence file
PLAYERS_DIR = '/app/config/players'

# Ensure directories exist
os.makedirs('/app/config', exist_ok=True)
os.makedirs(PLAYERS_DIR, exist_ok=True)
os.makedirs('/app/logs', exist_ok=True)

class SqueezeliteManager:
    def __init__(self):
        self.players = {}
        self.processes = {}
        self.state_lock = threading.Lock()  # Thread safety for state operations
        self.load_config()
        self.load_state()  # NEW: Load previous running states
    
    def load_config(self):
        """Load player configuration from YAML file"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    self.players = yaml.safe_load(f) or {}
            except Exception as e:
                logger.error(f"Error loading config: {e}")
                self.players = {}
        else:
            self.players = {}
    
    def save_config(self):
        """Save player configuration to YAML file"""
        try:
            with open(CONFIG_FILE, 'w') as f:
                yaml.dump(self.players, f, default_flow_style=False)
        except Exception as e:
            logger.error(f"Error saving config: {e}")
    
    def load_state(self):
        """NEW: Load player running states from state file"""
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, 'r') as f:
                    state_data = yaml.safe_load(f) or {}
                    
                # Only restore if the state file is recent (less than 5 minutes old)
                # This prevents restoring stale state from old shutdowns
                state_timestamp = state_data.get('timestamp')
                if state_timestamp:
                    try:
                        last_update = datetime.fromisoformat(state_timestamp)
                        time_diff = datetime.now() - last_update
                        if time_diff.total_seconds() > 300:  # 5 minutes
                            logger.info("State file is older than 5 minutes, not restoring player states")
                            return
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Invalid timestamp in state file: {e}")
                        return
                
                running_players = state_data.get('running_players', [])
                if running_players:
                    logger.info(f"Found {len(running_players)} players to restore: {running_players}")
                    # Start restoration in a separate thread to avoid blocking startup
                    threading.Thread(target=self._restore_player_states, 
                                   args=(running_players,), daemon=True).start()
                else:
                    logger.info("No players were running when service last stopped")
                    
            except Exception as e:
                logger.error(f"Error loading state: {e}")
        else:
            logger.info("No previous state file found")
    
    def save_state(self):
        """NEW: Save current player running states to state file"""
        try:
            with self.state_lock:
                running_players = []
                for name in self.players:
                    if self.get_player_status(name):
                        running_players.append(name)
                
                state_data = {
                    'timestamp': datetime.now().isoformat(),
                    'running_players': running_players,
                    'total_players': len(self.players)
                }
                
                with open(STATE_FILE, 'w') as f:
                    yaml.dump(state_data, f, default_flow_style=False)
                
                logger.debug(f"Saved state: {len(running_players)} running players")
                
        except Exception as e:
            logger.error(f"Error saving state: {e}")
    
    def _restore_player_states(self, running_players):
        """NEW: Restore player states in background thread"""
        # Wait a moment for the system to fully initialize
        time.sleep(3)
        
        restored_count = 0
        failed_count = 0
        
        for player_name in running_players:
            if player_name not in self.players:
                logger.warning(f"Cannot restore player '{player_name}' - no longer exists in configuration")
                failed_count += 1
                continue
            
            try:
                logger.info(f"Restoring player: {player_name}")
                success, message = self.start_player(player_name)
                if success:
                    restored_count += 1
                    logger.info(f"Successfully restored player: {player_name}")
                else:
                    failed_count += 1
                    logger.warning(f"Failed to restore player {player_name}: {message}")
                
                # Brief pause between starting players to avoid overwhelming the system
                time.sleep(1)
                
            except Exception as e:
                failed_count += 1
                logger.error(f"Error restoring player {player_name}: {e}")
        
        logger.info(f"State restoration complete: {restored_count} restored, {failed_count} failed")
        
        # Update state file to reflect current status
        self.save_state()
    
    def auto_save_state_periodically(self):
        """NEW: Periodically save state (called by background thread)"""
        while True:
            try:
                time.sleep(30)  # Save state every 30 seconds
                self.save_state()
            except Exception as e:
                logger.error(f"Error in periodic state save: {e}")
                time.sleep(60)  # Wait longer on error
    
    def get_audio_devices(self):
        """Get list of available audio devices"""
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
    
    def create_player(self, name, device, server_ip='', mac_address=''):
        """Create a new squeezelite player"""
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
        self.save_state()  # NEW: Save state when configuration changes
        return True, "Player created successfully"
    
    def update_player(self, old_name, new_name, device, server_ip='', mac_address=''):
        """Update an existing squeezelite player"""
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
                self.save_state()  # NEW: Save state after restart
                return True, f"Player updated and restarted successfully"
            else:
                self.save_state()  # NEW: Save state even if restart failed
                return True, f"Player updated successfully, but failed to restart: {message}"
        
        self.save_state()  # NEW: Save state after update
        return True, "Player updated successfully"
    
    def delete_player(self, name):
        """Delete a player"""
        if name not in self.players:
            return False, "Player not found"
        
        # Stop the player if running
        self.stop_player(name)
        
        # Remove from config
        del self.players[name]
        self.save_config()
        self.save_state()  # NEW: Save state when configuration changes
        return True, "Player deleted successfully"
    
    def start_player(self, name):
        """Start a squeezelite player process"""
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
            import time
            time.sleep(0.5)
            
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
                        time.sleep(0.5)
                        
                        if process.poll() is not None:
                            stdout, stderr = process.communicate()
                            error_msg = stderr.decode() if stderr else "Unknown error"
                            return False, f"Player failed to start even with null device: {error_msg}"
                        else:
                            logger.info(f"Player {name} started successfully with null device fallback")
                            self.save_state()  # NEW: Save state when player starts
                            return True, f"Player {name} started with null device (audio device '{player['device']}' not available)"
                    
                    except Exception as e:
                        logger.error(f"Error starting player {name} with fallback: {e}")
                        return False, f"Error starting player with fallback: {e}"
                else:
                    return False, f"Player failed to start: {error_msg}"
            
            logger.info(f"Started player {name} with PID {process.pid}")
            self.save_state()  # NEW: Save state when player starts
            return True, f"Player {name} started successfully"
            
        except FileNotFoundError:
            logger.error("squeezelite binary not found")
            return False, "squeezelite binary not found - container may not be built correctly"
        except Exception as e:
            logger.error(f"Error starting player {name}: {e}")
            return False, f"Error starting player: {e}"
    
    def stop_player(self, name):
        """Stop a squeezelite player process"""
        if name not in self.processes:
            return False, "Player not running"
        
        process = self.processes[name]
        if process.poll() is not None:
            # Process already terminated
            del self.processes[name]
            self.save_state()  # NEW: Save state when player stops
            return False, "Player was not running"
        
        try:
            # Send SIGTERM to the process group
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            
            # Wait for process to terminate
            process.wait(timeout=5)
            del self.processes[name]
            logger.info(f"Stopped player {name}")
            self.save_state()  # NEW: Save state when player stops
            return True, f"Player {name} stopped successfully"
            
        except subprocess.TimeoutExpired:
            # Force kill if it doesn't respond to SIGTERM
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                process.wait(timeout=2)
            except:
                pass
            del self.processes[name]
            self.save_state()  # NEW: Save state when player stops
            return True, f"Player {name} force stopped"
        except Exception as e:
            logger.error(f"Error stopping player {name}: {e}")
            return False, f"Error stopping player: {e}"
    
    def get_player_status(self, name):
        """Get the running status of a player"""
        if name not in self.processes:
            return False
        
        process = self.processes[name]
        return process.poll() is None
    
    def get_all_statuses(self):
        """Get status of all players"""
        statuses = {}
        for name in self.players:
            statuses[name] = self.get_player_status(name)
        return statuses
    
    def stop_all_players(self):
        """NEW: Stop all running players (useful for graceful shutdown)"""
        stopped_count = 0
        for name in list(self.processes.keys()):
            if self.get_player_status(name):
                success, message = self.stop_player(name)
                if success:
                    stopped_count += 1
                    logger.info(f"Stopped player {name} for shutdown")
        logger.info(f"Stopped {stopped_count} players for shutdown")
        self.save_state()  # Save final state
        return stopped_count
    
    def get_state_info(self):
        """NEW: Get information about current state and state file"""
        state_info = {
            'total_players': len(self.players),
            'running_players': len([name for name in self.players if self.get_player_status(name)]),
            'state_file_exists': os.path.exists(STATE_FILE),
            'last_state_save': None
        }
        
        if os.path.exists(STATE_FILE):
            try:
                stat = os.stat(STATE_FILE)
                state_info['last_state_save'] = datetime.fromtimestamp(stat.st_mtime).isoformat()
            except Exception as e:
                logger.warning(f"Could not get state file timestamp: {e}")
        
        return state_info

    def get_mixer_controls(self, device):
        """Get available mixer controls for a device"""
        if WINDOWS_MODE or device in ['null', 'pulse', 'dmix', 'default']:
            # Return virtual controls for non-hardware devices
            return ['Master', 'PCM']
        
        try:
            # Extract card number from device ID
            card_match = re.search(r'hw:([0-9]+)', device)
            if not card_match:
                return ['Master', 'PCM']
            
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
            
            return controls if controls else ['Master', 'PCM']
            
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.warning(f"Could not get mixer controls for device {device}: {e}")
            return ['Master', 'PCM']
    
    def get_device_volume(self, device, control='Master'):
        """Get the current volume for a device"""
        if WINDOWS_MODE or device in ['null', 'pulse', 'dmix', 'default']:
            # Return default volume for virtual devices
            logger.debug(f"Virtual device {device}, returning default volume")
            return 75
        
        try:
            # Extract card number from device ID
            card_match = re.search(r'hw:([0-9]+)', device)
            if not card_match:
                logger.debug(f"No card number found in device {device}, returning default volume")
                return 75
            
            card_num = card_match.group(1)
            
            # Try multiple common control names
            control_names = ['Master', 'PCM', 'Speaker', 'Headphone', 'Digital', 'Capture']
            
            for control_name in control_names:
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
            return 75
                
        except (subprocess.CalledProcessError, FileNotFoundError, ValueError) as e:
            logger.warning(f"Could not get volume for device {device}: {e}")
            return 75
    
    def set_device_volume(self, device, volume, control='Master'):
        """Set the volume for a device"""
        if not 0 <= volume <= 100:
            return False, "Volume must be between 0 and 100"
        
        if WINDOWS_MODE or device in ['null', 'pulse', 'dmix', 'default']:
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
            
            # Try multiple common control names
            control_names = ['Master', 'PCM', 'Speaker', 'Headphone', 'Digital']
            
            for control_name in control_names:
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
    
    def get_player_volume(self, name):
        """Get the current volume for a player"""
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
    
    def set_player_volume(self, name, volume):
        """Set the volume for a player"""
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

# Set up graceful shutdown handler
def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    logger.info(f"Received signal {signum}, shutting down gracefully...")
    
    # Stop all players
    try:
        stopped_count = manager.stop_all_players()
        logger.info(f"Graceful shutdown: stopped {stopped_count} players")
    except Exception as e:
        logger.error(f"Error during graceful shutdown: {e}")
    
    # Save final state
    try:
        manager.save_state()
        logger.info("Final state saved successfully")
    except Exception as e:
        logger.error(f"Error saving final state: {e}")
    
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

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

# NEW: State management endpoints
@app.route('/api/state', methods=['GET'])
def get_state():
    """API endpoint to get state information"""
    return jsonify(manager.get_state_info())

@app.route('/api/state/save', methods=['POST'])
def save_state():
    """API endpoint to manually save current state"""
    try:
        manager.save_state()
        return jsonify({'success': True, 'message': 'State saved successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error saving state: {e}'}), 500

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

@app.route('/api/players/<n>', methods=['PUT'])
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

@app.route('/api/players/<n>', methods=['DELETE'])
def delete_player(name):
    """API endpoint to delete a player"""
    success, message = manager.delete_player(name)
    return jsonify({'success': success, 'message': message})

@app.route('/api/players/<n>/start', methods=['POST'])
def start_player(name):
    """API endpoint to start a player"""
    success, message = manager.start_player(name)
    return jsonify({'success': success, 'message': message})

@app.route('/api/players/<n>/stop', methods=['POST'])
def stop_player(name):
    """API endpoint to stop a player"""
    success, message = manager.stop_player(name)
    return jsonify({'success': success, 'message': message})

@app.route('/api/players/<n>/status', methods=['GET'])
def get_player_status(name):
    """API endpoint to get player status"""
    status = manager.get_player_status(name)
    return jsonify({'running': status})

@app.route('/api/players/<n>/volume', methods=['GET'])
def get_player_volume(name):
    """API endpoint to get player volume"""
    try:
        volume = manager.get_player_volume(name)
        if volume is None:
            return jsonify({'success': False, 'message': 'Player not found'}), 404
        return jsonify({'success': True, 'volume': volume})
    except Exception as e:
        logger.error(f"Error in get_player_volume for {name}: {e}")
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'}), 500

@app.route('/api/players/<n>/volume', methods=['POST'])
def set_player_volume(name):
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
        
        success, message = manager.set_player_volume(name, volume)
        return jsonify({'success': success, 'message': message})
    except Exception as e:
        logger.error(f"Error in set_player_volume for {name}: {e}")
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
            time.sleep(2)
        except Exception as e:
            logger.error(f"Error in status monitor: {e}")
            time.sleep(5)

# Start status monitoring thread
try:
    logger.info("Starting status monitoring thread...")
    status_thread = threading.Thread(target=status_monitor, daemon=True)
    status_thread.start()
    logger.info("Status monitoring thread started successfully")
except Exception as e:
    logger.error(f"Failed to start status monitoring thread: {e}")
    # Continue without status monitoring

# NEW: Start periodic state saving thread
try:
    logger.info("Starting periodic state saving thread...")
    state_thread = threading.Thread(target=manager.auto_save_state_periodically, daemon=True)
    state_thread.start()
    logger.info("Periodic state saving thread started successfully")
except Exception as e:
    logger.error(f"Failed to start periodic state saving thread: {e}")
    # Continue without periodic state saving

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
