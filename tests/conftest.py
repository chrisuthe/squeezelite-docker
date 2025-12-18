"""
Pytest configuration and shared fixtures for tests.

This module provides reusable fixtures for mocking and testing
the Multi Output Player application components.
"""

import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

# Add the app directory to sys.path so we can import modules
app_dir = Path(__file__).parent.parent / "app"
sys.path.insert(0, str(app_dir))


# =============================================================================
# FIXTURES - Configuration Files
# =============================================================================


@pytest.fixture
def temp_config_file(tmp_path):
    """Create a temporary config file path for testing."""
    config_path = tmp_path / "players.yaml"
    return str(config_path)


@pytest.fixture
def temp_log_dir(tmp_path):
    """Create a temporary log directory for testing."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir(exist_ok=True)
    return str(log_dir)


# =============================================================================
# FIXTURES - Sample Player Configurations
# =============================================================================


@pytest.fixture
def sample_squeezelite_config():
    """Sample valid Squeezelite player configuration."""
    return {
        "name": "Kitchen",
        "device": "hw:0,0",
        "provider": "squeezelite",
        "volume": 75,
        "autostart": True,
        "enabled": True,
        "server_ip": "192.168.1.100",
        "mac_address": "aa:bb:cc:dd:ee:ff",
    }


@pytest.fixture
def sample_sendspin_config():
    """Sample valid Sendspin player configuration."""
    return {
        "name": "Bedroom",
        "device": "0",
        "provider": "sendspin",
        "volume": 50,
        "autostart": False,
        "enabled": True,
        "server_url": "ws://192.168.1.200:8080",
        "client_id": "bedroom-player",
        "delay_ms": 100,
        "log_level": "INFO",
    }


@pytest.fixture
def sample_players_dict(sample_squeezelite_config, sample_sendspin_config):
    """Sample dictionary of multiple player configurations."""
    return {
        "Kitchen": sample_squeezelite_config,
        "Bedroom": sample_sendspin_config,
    }


@pytest.fixture
def minimal_squeezelite_config():
    """Minimal valid Squeezelite configuration (required fields only)."""
    return {
        "name": "TestPlayer",
        "device": "default",
        "provider": "squeezelite",
    }


@pytest.fixture
def minimal_sendspin_config():
    """Minimal valid Sendspin configuration (required fields only)."""
    return {
        "name": "TestPlayer",
        "provider": "sendspin",
    }


# =============================================================================
# FIXTURES - Invalid Configurations
# =============================================================================


@pytest.fixture
def invalid_config_missing_name():
    """Invalid config - missing required name field."""
    return {
        "device": "hw:0,0",
        "provider": "squeezelite",
    }


@pytest.fixture
def invalid_config_invalid_volume():
    """Invalid config - volume out of range."""
    return {
        "name": "TestPlayer",
        "device": "hw:0,0",
        "provider": "squeezelite",
        "volume": 150,  # Invalid - must be 0-100
    }


@pytest.fixture
def invalid_config_bad_mac():
    """Invalid config - malformed MAC address."""
    return {
        "name": "TestPlayer",
        "device": "hw:0,0",
        "provider": "squeezelite",
        "mac_address": "invalid-mac",
    }


@pytest.fixture
def invalid_config_bad_provider():
    """Invalid config - unknown provider type."""
    return {
        "name": "TestPlayer",
        "device": "hw:0,0",
        "provider": "unknown_provider",
    }


@pytest.fixture
def invalid_config_sendspin_alsa_device():
    """Invalid config - Sendspin with ALSA device format."""
    return {
        "name": "TestPlayer",
        "device": "hw:0,0",  # Invalid for Sendspin - should be PortAudio format
        "provider": "sendspin",
    }


@pytest.fixture
def invalid_config_bad_log_level():
    """Invalid config - invalid Sendspin log level."""
    return {
        "name": "TestPlayer",
        "provider": "sendspin",
        "log_level": "INVALID",
    }


# =============================================================================
# FIXTURES - Mock Subprocess Results
# =============================================================================


@pytest.fixture
def mock_aplay_output():
    """Mock output from 'aplay -l' command."""
    return """**** List of PLAYBACK Hardware Devices ****
card 0: PCH [HDA Intel PCH], device 0: ALC887-VD Analog [ALC887-VD Analog]
  Subdevices: 1/1
  Subdevice #0: subdevice #0
card 1: HDMI [HDA Intel HDMI], device 3: HDMI 0 [HDMI 0]
  Subdevices: 1/1
  Subdevice #0: subdevice #0
"""


@pytest.fixture
def mock_amixer_scontrols_output():
    """Mock output from 'amixer scontrols' command."""
    return """Simple mixer control 'Master',0
Simple mixer control 'PCM',0
Simple mixer control 'Headphone',0
"""


@pytest.fixture
def mock_amixer_get_volume_output():
    """Mock output from 'amixer sget Master' command."""
    return """Simple mixer control 'Master',0
  Capabilities: pvolume pswitch pswitch-joined
  Playback channels: Front Left - Front Right
  Limits: Playback 0 - 87
  Mono:
  Front Left: Playback 65 [75%] [-16.50dB] [on]
  Front Right: Playback 65 [75%] [-16.50dB] [on]
"""


# =============================================================================
# FIXTURES - Mock Process Objects
# =============================================================================


@pytest.fixture
def mock_process():
    """Mock subprocess.Popen object."""
    process = Mock()
    process.pid = 12345
    process.poll.return_value = None  # Process is running
    process.communicate.return_value = (b"stdout", b"stderr")
    process.wait.return_value = 0
    return process


@pytest.fixture
def mock_failed_process():
    """Mock subprocess.Popen object that failed to start."""
    process = Mock()
    process.pid = 12346
    process.poll.return_value = 1  # Process terminated immediately
    process.communicate.return_value = (b"", b"Error: Device not found")
    return process


# =============================================================================
# FIXTURES - Mock File System
# =============================================================================


@pytest.fixture
def mock_yaml_file(tmp_path, sample_players_dict):
    """Create a temporary YAML file with sample player configurations."""
    import yaml

    config_file = tmp_path / "players.yaml"
    with open(config_file, "w") as f:
        yaml.dump(sample_players_dict, f)
    return str(config_file)


@pytest.fixture
def empty_yaml_file(tmp_path):
    """Create an empty YAML file."""
    config_file = tmp_path / "empty.yaml"
    config_file.touch()
    return str(config_file)


@pytest.fixture
def corrupt_yaml_file(tmp_path):
    """Create a YAML file with invalid syntax."""
    config_file = tmp_path / "corrupt.yaml"
    with open(config_file, "w") as f:
        f.write("invalid: yaml: syntax: [[[")
    return str(config_file)


# =============================================================================
# FIXTURES - Mocked Managers
# =============================================================================


@pytest.fixture
def mock_subprocess_run():
    """Mock subprocess.run for testing without actual system calls."""
    with pytest.mock.patch("subprocess.run") as mock:
        mock.return_value = Mock(
            returncode=0,
            stdout="",
            stderr="",
        )
        yield mock


@pytest.fixture
def mock_subprocess_popen():
    """Mock subprocess.Popen for testing without actual system calls."""
    with pytest.mock.patch("subprocess.Popen") as mock:
        yield mock


@pytest.fixture
def mock_os_makedirs():
    """Mock os.makedirs to avoid filesystem operations."""
    with pytest.mock.patch("os.makedirs") as mock:
        yield mock


@pytest.fixture
def mock_os_path_exists():
    """Mock os.path.exists for testing file existence checks."""
    with pytest.mock.patch("os.path.exists") as mock:
        yield mock
