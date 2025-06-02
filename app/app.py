#!/usr/bin/env python3

import os
import sys
import json
import subprocess
import signal
import yaml
import psutil
import traceback
from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_socketio import SocketIO, emit
import threading
import time
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
    app.config['SECRET_KEY'] = 'squeezelite-multiroom-secret'
    socketio = SocketIO(app, cors_allowed_origins="*")
    logger.info("Flask app and SocketIO initialized successfully")
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
    def __init__(self):
        self.players = {}
        self.processes = {}
        self.load_config()
    
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
            result = subprocess.run(['aplay', '-l'], 
                                  capture_output=True, text=True, check=True)
            devices = []
            
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
                        except (IndexError, ValueError) as e:
                            logger.warning(f"Error parsing audio device line: {line} - {e}")
                            continue
            
            # If we found real devices, add them to fallback devices
            if devices:
                logger.info(f"Found {len(devices)} audio devices")
                return fallback_devices + devices
            else:
                logger.warning("No hardware audio devices found, using fallback devices only")
                return fallback_devices
                
        except subprocess.CalledProcessError as e:
            logger.warning(f"Could not get audio devices list (aplay failed): {e}")
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
                return True, f"Player updated and restarted successfully"
            else:
                return True, f"Player updated successfully, but failed to restart: {message}"
        
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
    
    def stop_player(self, name):
        """Stop a squeezelite player process"""
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
            process.wait(timeout=5)
            del self.processes[name]
            logger.info(f"Stopped player {name}")
            return True, f"Player {name} stopped successfully"
            
        except subprocess.TimeoutExpired:
            # Force kill if it doesn't respond to SIGTERM
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                process.wait(timeout=2)
            except:
                pass
            del self.processes[name]
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
