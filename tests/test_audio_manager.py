"""
Unit tests for AudioManager class.

Tests audio device detection, mixer control enumeration, and volume
control operations with mocked subprocess calls.
"""

import subprocess
from unittest.mock import Mock, patch

from managers.audio_manager import (
    DEFAULT_MIXER_CONTROLS,
    DEFAULT_VOLUME_PERCENT,
    VIRTUAL_AUDIO_DEVICES,
    VOLUME_READ_CONTROLS,
    VOLUME_WRITE_CONTROLS,
    AudioManager,
)

# =============================================================================
# TESTS - Initialization
# =============================================================================


class TestAudioManagerInit:
    """Tests for AudioManager initialization."""

    def test_init_normal_mode(self):
        """Test initialization in normal mode."""
        manager = AudioManager(windows_mode=False)
        assert manager.windows_mode is False

    def test_init_windows_mode(self):
        """Test initialization in Windows compatibility mode."""
        manager = AudioManager(windows_mode=True)
        assert manager.windows_mode is True


# =============================================================================
# TESTS - Get Devices
# =============================================================================


class TestAudioManagerGetDevices:
    """Tests for AudioManager.get_devices() method."""

    def test_get_devices_windows_mode(self):
        """Test get_devices in Windows mode returns simulated devices."""
        manager = AudioManager(windows_mode=True)
        devices = manager.get_devices()

        assert len(devices) > 0
        assert any(d["id"] == "default" for d in devices)
        assert any("Windows" in d["name"] for d in devices)

    @patch("subprocess.run")
    def test_get_devices_with_hardware(self, mock_run, mock_aplay_output):
        """Test get_devices detects hardware devices."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=mock_aplay_output,
            stderr="",
        )

        manager = AudioManager(windows_mode=False)
        devices = manager.get_devices()

        # Should have fallback devices plus hardware devices
        assert len(devices) > 3  # At least 3 fallback + 2 hardware
        assert any(d["id"] == "null" for d in devices)
        assert any(d["id"] == "default" for d in devices)
        assert any(d["id"] == "hw:0,0" for d in devices)
        assert any(d["id"] == "hw:1,3" for d in devices)

    @patch("subprocess.run")
    def test_get_devices_no_hardware(self, mock_run):
        """Test get_devices with no hardware detected."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="**** List of PLAYBACK Hardware Devices ****\n",
            stderr="",
        )

        manager = AudioManager(windows_mode=False)
        devices = manager.get_devices()

        # Should only have fallback devices
        assert len(devices) == 3
        assert any(d["id"] == "null" for d in devices)
        assert any(d["id"] == "default" for d in devices)
        assert any(d["id"] == "dmix" for d in devices)

    @patch("subprocess.run")
    def test_get_devices_aplay_fails(self, mock_run):
        """Test get_devices handles aplay command failure."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "aplay")

        manager = AudioManager(windows_mode=False)
        devices = manager.get_devices()

        # Should return fallback devices only
        assert len(devices) == 3
        assert any(d["id"] == "null" for d in devices)

    @patch("subprocess.run")
    def test_get_devices_aplay_not_found(self, mock_run):
        """Test get_devices handles missing aplay command."""
        mock_run.side_effect = FileNotFoundError()

        manager = AudioManager(windows_mode=False)
        devices = manager.get_devices()

        # Should return fallback devices only
        assert len(devices) == 3

    @patch("subprocess.run")
    def test_get_devices_parsing_error(self, mock_run):
        """Test get_devices handles malformed aplay output."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="card malformed line without proper format",
            stderr="",
        )

        manager = AudioManager(windows_mode=False)
        devices = manager.get_devices()

        # Should return fallback devices only due to parsing failure
        assert len(devices) == 3

    @patch("subprocess.run")
    def test_get_devices_extracts_device_info(self, mock_run, mock_aplay_output):
        """Test get_devices correctly extracts device information."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=mock_aplay_output,
            stderr="",
        )

        manager = AudioManager(windows_mode=False)
        devices = manager.get_devices()

        # Find the hw:0,0 device
        hw00 = next(d for d in devices if d["id"] == "hw:0,0")
        assert hw00["card"] == "0"
        assert hw00["device"] == "0"
        assert "ALC887-VD Analog" in hw00["name"]


# =============================================================================
# TESTS - Get Mixer Controls
# =============================================================================


class TestAudioManagerGetMixerControls:
    """Tests for AudioManager.get_mixer_controls() method."""

    def test_get_mixer_controls_windows_mode(self):
        """Test get_mixer_controls in Windows mode returns defaults."""
        manager = AudioManager(windows_mode=True)
        controls = manager.get_mixer_controls("hw:0,0")

        assert controls == DEFAULT_MIXER_CONTROLS

    def test_get_mixer_controls_virtual_device(self):
        """Test get_mixer_controls for virtual devices returns defaults."""
        manager = AudioManager(windows_mode=False)
        for device in VIRTUAL_AUDIO_DEVICES:
            controls = manager.get_mixer_controls(device)
            assert controls == DEFAULT_MIXER_CONTROLS

    @patch("subprocess.run")
    def test_get_mixer_controls_hardware_device(self, mock_run, mock_amixer_scontrols_output):
        """Test get_mixer_controls detects real controls."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=mock_amixer_scontrols_output,
            stderr="",
        )

        manager = AudioManager(windows_mode=False)
        controls = manager.get_mixer_controls("hw:0,0")

        assert "Master" in controls
        assert "PCM" in controls
        assert "Headphone" in controls

    @patch("subprocess.run")
    def test_get_mixer_controls_no_card_number(self, mock_run):
        """Test get_mixer_controls handles device without card number."""
        manager = AudioManager(windows_mode=False)
        controls = manager.get_mixer_controls("invalid_device")

        assert controls == DEFAULT_MIXER_CONTROLS
        # Should not call subprocess
        mock_run.assert_not_called()

    @patch("subprocess.run")
    def test_get_mixer_controls_amixer_fails(self, mock_run):
        """Test get_mixer_controls handles amixer failure."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "amixer")

        manager = AudioManager(windows_mode=False)
        controls = manager.get_mixer_controls("hw:0,0")

        assert controls == DEFAULT_MIXER_CONTROLS

    @patch("subprocess.run")
    def test_get_mixer_controls_amixer_not_found(self, mock_run):
        """Test get_mixer_controls handles missing amixer."""
        mock_run.side_effect = FileNotFoundError()

        manager = AudioManager(windows_mode=False)
        controls = manager.get_mixer_controls("hw:0,0")

        assert controls == DEFAULT_MIXER_CONTROLS

    @patch("subprocess.run")
    def test_get_mixer_controls_empty_output(self, mock_run):
        """Test get_mixer_controls handles empty amixer output."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="",
            stderr="",
        )

        manager = AudioManager(windows_mode=False)
        controls = manager.get_mixer_controls("hw:0,0")

        assert controls == DEFAULT_MIXER_CONTROLS


# =============================================================================
# TESTS - Get Volume
# =============================================================================


class TestAudioManagerGetVolume:
    """Tests for AudioManager.get_volume() method."""

    def test_get_volume_windows_mode(self):
        """Test get_volume in Windows mode returns default."""
        manager = AudioManager(windows_mode=True)
        volume = manager.get_volume("hw:0,0")

        assert volume == DEFAULT_VOLUME_PERCENT

    def test_get_volume_virtual_device(self):
        """Test get_volume for virtual devices returns default."""
        manager = AudioManager(windows_mode=False)
        for device in VIRTUAL_AUDIO_DEVICES:
            volume = manager.get_volume(device)
            assert volume == DEFAULT_VOLUME_PERCENT

    @patch("subprocess.run")
    def test_get_volume_hardware_device(self, mock_run, mock_amixer_get_volume_output):
        """Test get_volume reads volume from hardware device."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=mock_amixer_get_volume_output,
            stderr="",
        )

        manager = AudioManager(windows_mode=False)
        volume = manager.get_volume("hw:0,0")

        assert volume == 75

    @patch("subprocess.run")
    def test_get_volume_tries_multiple_controls(self, mock_run, mock_amixer_get_volume_output):
        """Test get_volume tries multiple control names."""
        # First call fails, second succeeds
        mock_run.side_effect = [
            subprocess.CalledProcessError(1, "amixer"),  # Master fails
            Mock(returncode=0, stdout=mock_amixer_get_volume_output, stderr=""),  # PCM succeeds
        ]

        manager = AudioManager(windows_mode=False)
        volume = manager.get_volume("hw:0,0")

        assert volume == 75
        assert mock_run.call_count >= 2

    @patch("subprocess.run")
    def test_get_volume_all_controls_fail(self, mock_run):
        """Test get_volume returns default when all controls fail."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "amixer")

        manager = AudioManager(windows_mode=False)
        volume = manager.get_volume("hw:0,0")

        assert volume == DEFAULT_VOLUME_PERCENT
        # Should have tried all read controls
        assert mock_run.call_count == len(VOLUME_READ_CONTROLS)

    @patch("subprocess.run")
    def test_get_volume_no_card_number(self, mock_run):
        """Test get_volume handles device without card number."""
        manager = AudioManager(windows_mode=False)
        volume = manager.get_volume("invalid_device")

        assert volume == DEFAULT_VOLUME_PERCENT
        # Should not call subprocess
        mock_run.assert_not_called()

    @patch("subprocess.run")
    def test_get_volume_parsing_error(self, mock_run):
        """Test get_volume handles malformed amixer output."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="No volume percentage found in this output",
            stderr="",
        )

        manager = AudioManager(windows_mode=False)
        volume = manager.get_volume("hw:0,0")

        assert volume == DEFAULT_VOLUME_PERCENT

    @patch("subprocess.run")
    def test_get_volume_amixer_not_found(self, mock_run):
        """Test get_volume handles missing amixer."""
        mock_run.side_effect = FileNotFoundError()

        manager = AudioManager(windows_mode=False)
        volume = manager.get_volume("hw:0,0")

        assert volume == DEFAULT_VOLUME_PERCENT


# =============================================================================
# TESTS - Set Volume
# =============================================================================


class TestAudioManagerSetVolume:
    """Tests for AudioManager.set_volume() method."""

    def test_set_volume_windows_mode(self):
        """Test set_volume in Windows mode returns success."""
        manager = AudioManager(windows_mode=True)
        success, message = manager.set_volume("hw:0,0", 75)

        assert success is True
        assert "virtual device" in message.lower()

    def test_set_volume_virtual_device(self):
        """Test set_volume for virtual devices returns success."""
        manager = AudioManager(windows_mode=False)
        for device in VIRTUAL_AUDIO_DEVICES:
            success, message = manager.set_volume(device, 75)
            assert success is True
            assert "virtual" in message.lower()

    def test_set_volume_invalid_range_low(self):
        """Test set_volume rejects volume below 0."""
        manager = AudioManager(windows_mode=False)
        success, message = manager.set_volume("hw:0,0", -1)

        assert success is False
        assert "between 0 and 100" in message

    def test_set_volume_invalid_range_high(self):
        """Test set_volume rejects volume above 100."""
        manager = AudioManager(windows_mode=False)
        success, message = manager.set_volume("hw:0,0", 101)

        assert success is False
        assert "between 0 and 100" in message

    def test_set_volume_valid_range_boundaries(self):
        """Test set_volume accepts boundary values."""
        manager = AudioManager(windows_mode=True)

        success, _ = manager.set_volume("default", 0)
        assert success is True

        success, _ = manager.set_volume("default", 100)
        assert success is True

    @patch("subprocess.run")
    def test_set_volume_hardware_device(self, mock_run):
        """Test set_volume sets volume on hardware device."""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        manager = AudioManager(windows_mode=False)
        success, message = manager.set_volume("hw:0,0", 75)

        assert success is True
        assert "75%" in message
        mock_run.assert_called_once()

        # Check command arguments
        args = mock_run.call_args[0][0]
        assert "amixer" in args
        assert "75%" in args

    @patch("subprocess.run")
    def test_set_volume_tries_multiple_controls(self, mock_run):
        """Test set_volume tries multiple control names."""
        # First call fails, second succeeds
        mock_run.side_effect = [
            subprocess.CalledProcessError(1, "amixer"),  # Master fails
            Mock(returncode=0, stdout="", stderr=""),  # PCM succeeds
        ]

        manager = AudioManager(windows_mode=False)
        success, message = manager.set_volume("hw:0,0", 75)

        assert success is True
        assert mock_run.call_count == 2

    @patch("subprocess.run")
    def test_set_volume_all_controls_fail(self, mock_run):
        """Test set_volume returns failure when all controls fail."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "amixer")

        manager = AudioManager(windows_mode=False)
        success, message = manager.set_volume("hw:0,0", 75)

        assert success is False
        assert "no working volume controls" in message.lower()
        # Should have tried all write controls
        assert mock_run.call_count == len(VOLUME_WRITE_CONTROLS)

    @patch("subprocess.run")
    def test_set_volume_no_card_number(self, mock_run):
        """Test set_volume handles device without card number."""
        manager = AudioManager(windows_mode=False)
        success, message = manager.set_volume("invalid_device", 75)

        assert success is True
        assert "no hardware control" in message.lower()
        # Should not call subprocess
        mock_run.assert_not_called()

    @patch("subprocess.run")
    def test_set_volume_amixer_not_found(self, mock_run):
        """Test set_volume handles missing amixer."""
        mock_run.side_effect = FileNotFoundError()

        manager = AudioManager(windows_mode=False)
        success, message = manager.set_volume("hw:0,0", 75)

        assert success is False
        assert "not available" in message.lower()

    @patch("subprocess.run")
    def test_set_volume_error_message_bytes(self, mock_run):
        """Test set_volume handles bytes stderr."""
        error = subprocess.CalledProcessError(1, "amixer")
        error.stderr = b"Error message in bytes"
        mock_run.side_effect = error

        manager = AudioManager(windows_mode=False)
        success, message = manager.set_volume("hw:0,0", 75)

        assert success is False
        # Should decode bytes error message

    @patch("subprocess.run")
    def test_set_volume_error_message_string(self, mock_run):
        """Test set_volume handles string stderr."""
        error = subprocess.CalledProcessError(1, "amixer")
        error.stderr = "Error message as string"
        mock_run.side_effect = error

        manager = AudioManager(windows_mode=False)
        success, message = manager.set_volume("hw:0,0", 75)

        assert success is False


# =============================================================================
# TESTS - Is Virtual Device
# =============================================================================


class TestAudioManagerIsVirtualDevice:
    """Tests for AudioManager.is_virtual_device() method."""

    def test_is_virtual_device_true(self):
        """Test is_virtual_device returns True for virtual devices."""
        manager = AudioManager()
        for device in VIRTUAL_AUDIO_DEVICES:
            assert manager.is_virtual_device(device) is True

    def test_is_virtual_device_false(self):
        """Test is_virtual_device returns False for hardware devices."""
        manager = AudioManager()
        hardware_devices = ["hw:0,0", "hw:1,0", "plughw:0,0"]
        for device in hardware_devices:
            assert manager.is_virtual_device(device) is False


# =============================================================================
# TESTS - Constants
# =============================================================================


class TestAudioManagerConstants:
    """Tests for AudioManager constants."""

    def test_default_mixer_controls_not_empty(self):
        """Test DEFAULT_MIXER_CONTROLS is not empty."""
        assert len(DEFAULT_MIXER_CONTROLS) > 0

    def test_volume_read_controls_not_empty(self):
        """Test VOLUME_READ_CONTROLS is not empty."""
        assert len(VOLUME_READ_CONTROLS) > 0

    def test_volume_write_controls_not_empty(self):
        """Test VOLUME_WRITE_CONTROLS is not empty."""
        assert len(VOLUME_WRITE_CONTROLS) > 0

    def test_virtual_audio_devices_not_empty(self):
        """Test VIRTUAL_AUDIO_DEVICES is not empty."""
        assert len(VIRTUAL_AUDIO_DEVICES) > 0

    def test_default_volume_in_range(self):
        """Test DEFAULT_VOLUME_PERCENT is in valid range."""
        assert 0 <= DEFAULT_VOLUME_PERCENT <= 100

    def test_write_controls_subset_of_read(self):
        """Test that write controls don't include input-only controls."""
        # Capture should be in read but not write
        assert "Capture" in VOLUME_READ_CONTROLS
        assert "Capture" not in VOLUME_WRITE_CONTROLS
