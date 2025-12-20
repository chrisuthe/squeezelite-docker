"""
Tests for the Squeezelite player provider.

Tests cover command building, configuration validation, MAC address generation,
environment variable handling, and volume control delegation.
"""

from unittest.mock import Mock, patch

import pytest
from providers.squeezelite import (
    DEFAULT_BUFFER_PARAMS,
    DEFAULT_BUFFER_SIZE,
    DEFAULT_CLOSE_TIMEOUT,
    DEFAULT_SAMPLE_RATE,
    NULL_DEVICE,
    SqueezeliteProvider,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_audio_manager():
    """Mock AudioManager for testing volume control."""
    manager = Mock()
    manager.get_volume.return_value = 75
    manager.set_volume.return_value = (True, "Volume set to 50%")
    return manager


@pytest.fixture
def squeezelite_provider(mock_audio_manager):
    """Create a SqueezeliteProvider instance with mocked AudioManager."""
    return SqueezeliteProvider(mock_audio_manager)


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
def minimal_squeezelite_config():
    """Minimal valid Squeezelite configuration (required fields only)."""
    return {
        "name": "TestPlayer",
        "device": "default",
        "provider": "squeezelite",
        "mac_address": "00:11:22:33:44:55",
    }


# =============================================================================
# TEST CLASS ATTRIBUTES
# =============================================================================


class TestSqueezeliteProviderAttributes:
    """Test provider class attributes."""

    def test_provider_type(self, squeezelite_provider):
        """Test that provider_type is correct."""
        assert squeezelite_provider.provider_type == "squeezelite"

    def test_display_name(self, squeezelite_provider):
        """Test that display_name is correct."""
        assert squeezelite_provider.display_name == "Squeezelite"

    def test_binary_name(self, squeezelite_provider):
        """Test that binary_name is correct."""
        assert squeezelite_provider.binary_name == "squeezelite"


# =============================================================================
# TEST BUILD_COMMAND
# =============================================================================


class TestBuildCommand:
    """Tests for build_command method."""

    def test_build_command_minimal(self, squeezelite_provider, minimal_squeezelite_config):
        """Test command building with minimal config."""
        with patch("providers.squeezelite.get_squeezelite_output_device", return_value="default"):
            cmd = squeezelite_provider.build_command(minimal_squeezelite_config, "/app/logs/test.log")

        assert cmd[0] == "squeezelite"
        assert "-n" in cmd
        assert "TestPlayer" in cmd
        assert "-o" in cmd
        assert "-m" in cmd
        assert "-f" in cmd
        assert "/app/logs/test.log" in cmd

    def test_build_command_with_server(self, squeezelite_provider, sample_squeezelite_config):
        """Test command building with server IP specified."""
        with patch("providers.squeezelite.get_squeezelite_output_device", return_value="hw:0,0"):
            cmd = squeezelite_provider.build_command(sample_squeezelite_config, "/app/logs/test.log")

        assert "-s" in cmd
        server_idx = cmd.index("-s")
        assert cmd[server_idx + 1] == "192.168.1.100"

    def test_build_command_with_device(self, squeezelite_provider, sample_squeezelite_config):
        """Test command building with audio device specified."""
        with patch("providers.squeezelite.get_squeezelite_output_device", return_value="hw:0,0"):
            cmd = squeezelite_provider.build_command(sample_squeezelite_config, "/app/logs/test.log")

        assert "-o" in cmd
        device_idx = cmd.index("-o")
        assert cmd[device_idx + 1] == "hw:0,0"

    def test_build_command_with_mac_address(self, squeezelite_provider, sample_squeezelite_config):
        """Test command building with MAC address specified."""
        with patch("providers.squeezelite.get_squeezelite_output_device", return_value="hw:0,0"):
            cmd = squeezelite_provider.build_command(sample_squeezelite_config, "/app/logs/test.log")

        assert "-m" in cmd
        mac_idx = cmd.index("-m")
        assert cmd[mac_idx + 1] == "aa:bb:cc:dd:ee:ff"

    def test_build_command_includes_buffer_settings(self, squeezelite_provider, minimal_squeezelite_config):
        """Test that buffer settings are included in command."""
        with patch("providers.squeezelite.get_squeezelite_output_device", return_value="default"):
            cmd = squeezelite_provider.build_command(minimal_squeezelite_config, "/app/logs/test.log")

        assert "-a" in cmd
        assert "-b" in cmd
        assert "-C" in cmd

    def test_build_command_null_device_includes_sample_rate(self, squeezelite_provider):
        """Test that null device includes explicit sample rate."""
        config = {
            "name": "Test",
            "device": "null",
            "mac_address": "00:11:22:33:44:55",
        }
        with patch("providers.squeezelite.get_squeezelite_output_device", return_value="null"):
            cmd = squeezelite_provider.build_command(config, "/app/logs/test.log")

        assert "-r" in cmd
        rate_idx = cmd.index("-r")
        assert cmd[rate_idx + 1] == DEFAULT_SAMPLE_RATE

    def test_build_command_non_null_device_no_sample_rate(self, squeezelite_provider, minimal_squeezelite_config):
        """Test that non-null device does not include sample rate."""
        with patch("providers.squeezelite.get_squeezelite_output_device", return_value="default"):
            cmd = squeezelite_provider.build_command(minimal_squeezelite_config, "/app/logs/test.log")

        assert "-r" not in cmd

    def test_build_command_no_server_means_no_s_flag(self, squeezelite_provider):
        """Test that missing server_ip doesn't add -s option."""
        config = {
            "name": "Test",
            "device": "default",
            "mac_address": "00:11:22:33:44:55",
        }
        with patch("providers.squeezelite.get_squeezelite_output_device", return_value="default"):
            cmd = squeezelite_provider.build_command(config, "/app/logs/test.log")

        assert "-s" not in cmd

    def test_build_command_player_name(self, squeezelite_provider, sample_squeezelite_config):
        """Test that player name is correctly set."""
        with patch("providers.squeezelite.get_squeezelite_output_device", return_value="hw:0,0"):
            cmd = squeezelite_provider.build_command(sample_squeezelite_config, "/app/logs/test.log")

        name_idx = cmd.index("-n")
        assert cmd[name_idx + 1] == "Kitchen"


# =============================================================================
# TEST BUILD_FALLBACK_COMMAND
# =============================================================================


class TestBuildFallbackCommand:
    """Tests for build_fallback_command method."""

    def test_fallback_command_uses_null_device(self, squeezelite_provider, sample_squeezelite_config):
        """Test that fallback command uses null device."""
        cmd = squeezelite_provider.build_fallback_command(sample_squeezelite_config, "/app/logs/test.log")

        assert "-o" in cmd
        device_idx = cmd.index("-o")
        assert cmd[device_idx + 1] == NULL_DEVICE

    def test_fallback_command_includes_sample_rate(self, squeezelite_provider, sample_squeezelite_config):
        """Test that fallback command includes sample rate for null device."""
        cmd = squeezelite_provider.build_fallback_command(sample_squeezelite_config, "/app/logs/test.log")

        assert "-r" in cmd
        rate_idx = cmd.index("-r")
        assert cmd[rate_idx + 1] == DEFAULT_SAMPLE_RATE

    def test_fallback_command_preserves_player_name(self, squeezelite_provider, sample_squeezelite_config):
        """Test that fallback command preserves player name."""
        cmd = squeezelite_provider.build_fallback_command(sample_squeezelite_config, "/app/logs/test.log")

        name_idx = cmd.index("-n")
        assert cmd[name_idx + 1] == "Kitchen"

    def test_fallback_command_preserves_mac_address(self, squeezelite_provider, sample_squeezelite_config):
        """Test that fallback command preserves MAC address."""
        cmd = squeezelite_provider.build_fallback_command(sample_squeezelite_config, "/app/logs/test.log")

        mac_idx = cmd.index("-m")
        assert cmd[mac_idx + 1] == "aa:bb:cc:dd:ee:ff"

    def test_fallback_command_includes_server_if_specified(self, squeezelite_provider, sample_squeezelite_config):
        """Test that fallback command includes server IP if specified."""
        cmd = squeezelite_provider.build_fallback_command(sample_squeezelite_config, "/app/logs/test.log")

        assert "-s" in cmd
        server_idx = cmd.index("-s")
        assert cmd[server_idx + 1] == "192.168.1.100"

    def test_supports_fallback_returns_true(self, squeezelite_provider):
        """Test that supports_fallback returns True."""
        assert squeezelite_provider.supports_fallback() is True


# =============================================================================
# TEST VALIDATE_CONFIG
# =============================================================================


class TestValidateConfig:
    """Tests for validate_config method."""

    def test_validate_valid_config(self, squeezelite_provider, sample_squeezelite_config):
        """Test validation of a valid configuration."""
        is_valid, error = squeezelite_provider.validate_config(sample_squeezelite_config)
        assert is_valid is True
        assert error == ""

    def test_validate_minimal_config(self, squeezelite_provider, minimal_squeezelite_config):
        """Test validation of minimal configuration."""
        is_valid, error = squeezelite_provider.validate_config(minimal_squeezelite_config)
        assert is_valid is True
        assert error == ""

    def test_validate_missing_name(self, squeezelite_provider):
        """Test validation fails when name is missing."""
        config = {"device": "hw:0,0"}
        is_valid, error = squeezelite_provider.validate_config(config)
        assert is_valid is False
        assert "name is required" in error.lower()

    def test_validate_empty_name(self, squeezelite_provider):
        """Test validation fails when name is empty."""
        config = {"name": "", "device": "hw:0,0"}
        is_valid, error = squeezelite_provider.validate_config(config)
        assert is_valid is False
        assert "name is required" in error.lower()

    def test_validate_missing_device(self, squeezelite_provider):
        """Test validation fails when device is missing."""
        config = {"name": "TestPlayer"}
        is_valid, error = squeezelite_provider.validate_config(config)
        assert is_valid is False
        assert "device is required" in error.lower()

    def test_validate_empty_device(self, squeezelite_provider):
        """Test validation fails when device is empty."""
        config = {"name": "TestPlayer", "device": ""}
        is_valid, error = squeezelite_provider.validate_config(config)
        assert is_valid is False
        assert "device is required" in error.lower()

    def test_validate_name_too_long(self, squeezelite_provider):
        """Test validation fails when name exceeds 64 characters."""
        config = {"name": "x" * 65, "device": "hw:0,0"}
        is_valid, error = squeezelite_provider.validate_config(config)
        assert is_valid is False
        assert "too long" in error.lower()

    def test_validate_name_at_max_length(self, squeezelite_provider):
        """Test validation passes when name is exactly 64 characters."""
        config = {"name": "x" * 64, "device": "hw:0,0"}
        is_valid, error = squeezelite_provider.validate_config(config)
        assert is_valid is True

    def test_validate_name_with_invalid_chars(self, squeezelite_provider):
        """Test validation fails when name contains invalid characters."""
        for invalid_char in ["/", "\\", "\x00"]:
            config = {"name": f"test{invalid_char}name", "device": "hw:0,0"}
            is_valid, error = squeezelite_provider.validate_config(config)
            assert is_valid is False
            assert "invalid characters" in error.lower()

    def test_validate_name_with_valid_special_chars(self, squeezelite_provider):
        """Test validation passes with valid special characters."""
        config = {"name": "Kitchen-Speaker_1", "device": "hw:0,0"}
        is_valid, error = squeezelite_provider.validate_config(config)
        assert is_valid is True


# =============================================================================
# TEST GET_DEFAULT_CONFIG
# =============================================================================


class TestGetDefaultConfig:
    """Tests for get_default_config method."""

    def test_default_config_has_required_fields(self, squeezelite_provider):
        """Test that default config contains all expected fields."""
        defaults = squeezelite_provider.get_default_config()

        assert "provider" in defaults
        assert defaults["provider"] == "squeezelite"
        assert "device" in defaults
        assert "server_ip" in defaults
        assert "mac_address" in defaults
        assert "volume" in defaults
        assert "autostart" in defaults

    def test_default_config_values(self, squeezelite_provider):
        """Test that default config has correct default values."""
        defaults = squeezelite_provider.get_default_config()

        assert defaults["device"] == "default"
        assert defaults["server_ip"] == ""
        assert defaults["mac_address"] == ""
        assert defaults["volume"] == 75
        assert defaults["autostart"] is False


# =============================================================================
# TEST GET_REQUIRED_FIELDS
# =============================================================================


class TestGetRequiredFields:
    """Tests for get_required_fields method."""

    def test_required_fields(self, squeezelite_provider):
        """Test that name and device are required."""
        required = squeezelite_provider.get_required_fields()
        assert "name" in required
        assert "device" in required


# =============================================================================
# TEST GENERATE_MAC_ADDRESS
# =============================================================================


class TestGenerateMacAddress:
    """Tests for generate_mac_address static method."""

    def test_generate_mac_address_format(self):
        """Test that generated MAC address has correct format."""
        mac = SqueezeliteProvider.generate_mac_address("Kitchen")

        # Should be 6 octets separated by colons
        parts = mac.split(":")
        assert len(parts) == 6

        # Each part should be 2 hex digits
        for part in parts:
            assert len(part) == 2
            int(part, 16)  # Should not raise ValueError

    def test_generate_mac_address_deterministic(self):
        """Test that same name always generates same MAC address."""
        mac1 = SqueezeliteProvider.generate_mac_address("Living Room")
        mac2 = SqueezeliteProvider.generate_mac_address("Living Room")

        assert mac1 == mac2

    def test_generate_mac_address_unique_for_different_names(self):
        """Test that different names generate different MAC addresses."""
        mac1 = SqueezeliteProvider.generate_mac_address("Kitchen")
        mac2 = SqueezeliteProvider.generate_mac_address("Bedroom")

        assert mac1 != mac2

    def test_generate_mac_address_locally_administered_bit(self):
        """Test that locally-administered bit (0x02) is set."""
        mac = SqueezeliteProvider.generate_mac_address("Test")
        first_octet = int(mac.split(":")[0], 16)

        # Locally-administered bit should be set
        assert (first_octet & 0x02) == 0x02

    def test_generate_mac_address_unicast_bit(self):
        """Test that unicast bit (0x01) is cleared."""
        mac = SqueezeliteProvider.generate_mac_address("Test")
        first_octet = int(mac.split(":")[0], 16)

        # Multicast bit should be cleared (unicast)
        assert (first_octet & 0x01) == 0x00

    def test_generate_mac_address_lowercase(self):
        """Test that MAC address is lowercase."""
        mac = SqueezeliteProvider.generate_mac_address("UPPERCASE")
        assert mac == mac.lower()

    def test_generate_mac_address_empty_name(self):
        """Test that empty name still generates valid MAC."""
        mac = SqueezeliteProvider.generate_mac_address("")
        parts = mac.split(":")
        assert len(parts) == 6

    def test_generate_mac_address_special_characters(self):
        """Test MAC generation with special characters in name."""
        mac = SqueezeliteProvider.generate_mac_address("Kitchen Speaker #1")
        parts = mac.split(":")
        assert len(parts) == 6


# =============================================================================
# TEST PREPARE_CONFIG
# =============================================================================


class TestPrepareConfig:
    """Tests for prepare_config method."""

    def test_prepare_config_merges_with_defaults(self, squeezelite_provider):
        """Test that prepare_config merges user config with defaults."""
        user_config = {"name": "Kitchen", "device": "hw:1,0"}
        prepared = squeezelite_provider.prepare_config(user_config)

        # User values preserved
        assert prepared["name"] == "Kitchen"
        assert prepared["device"] == "hw:1,0"

        # Defaults added
        assert prepared["provider"] == "squeezelite"
        assert prepared["volume"] == 75
        assert prepared["autostart"] is False

    def test_prepare_config_generates_mac_address(self, squeezelite_provider):
        """Test that prepare_config generates mac_address if not provided."""
        user_config = {"name": "Kitchen", "device": "hw:0,0"}
        prepared = squeezelite_provider.prepare_config(user_config)

        assert prepared["mac_address"] != ""
        assert ":" in prepared["mac_address"]

    def test_prepare_config_preserves_provided_mac_address(self, squeezelite_provider):
        """Test that prepare_config preserves user-provided mac_address."""
        user_config = {"name": "Kitchen", "device": "hw:0,0", "mac_address": "aa:bb:cc:dd:ee:ff"}
        prepared = squeezelite_provider.prepare_config(user_config)

        assert prepared["mac_address"] == "aa:bb:cc:dd:ee:ff"

    def test_prepare_config_user_overrides_defaults(self, squeezelite_provider):
        """Test that user config overrides defaults."""
        user_config = {"name": "Kitchen", "device": "hw:0,0", "volume": 50, "autostart": True}
        prepared = squeezelite_provider.prepare_config(user_config)

        assert prepared["volume"] == 50
        assert prepared["autostart"] is True


# =============================================================================
# TEST VOLUME CONTROL
# =============================================================================


class TestVolumeControl:
    """Tests for volume control methods."""

    def test_get_volume_delegates_to_audio_manager(
        self, squeezelite_provider, mock_audio_manager, sample_squeezelite_config
    ):
        """Test that get_volume delegates to AudioManager."""
        volume = squeezelite_provider.get_volume(sample_squeezelite_config)

        mock_audio_manager.get_volume.assert_called_once_with("hw:0,0")
        assert volume == 75

    def test_get_volume_uses_default_device(self, squeezelite_provider, mock_audio_manager):
        """Test that get_volume uses 'default' when no device specified."""
        config = {"name": "Test"}
        squeezelite_provider.get_volume(config)

        mock_audio_manager.get_volume.assert_called_once_with("default")

    def test_set_volume_delegates_to_audio_manager(
        self, squeezelite_provider, mock_audio_manager, sample_squeezelite_config
    ):
        """Test that set_volume delegates to AudioManager."""
        success, message = squeezelite_provider.set_volume(sample_squeezelite_config, 50)

        mock_audio_manager.set_volume.assert_called_once_with("hw:0,0", 50)
        assert success is True
        assert "50%" in message

    def test_set_volume_uses_default_device(self, squeezelite_provider, mock_audio_manager):
        """Test that set_volume uses 'default' when no device specified."""
        config = {"name": "Test"}
        squeezelite_provider.set_volume(config, 50)

        mock_audio_manager.set_volume.assert_called_once_with("default", 50)


# =============================================================================
# TEST ENVIRONMENT VARIABLE HANDLING
# =============================================================================


class TestEnvironmentVariables:
    """Tests for environment variable handling."""

    def test_default_buffer_size_from_env(self):
        """Test that SQUEEZELITE_BUFFER_TIME env var is used."""
        # The default values are set at module import time, so we check they exist
        assert DEFAULT_BUFFER_SIZE is not None
        assert isinstance(DEFAULT_BUFFER_SIZE, str)

    def test_default_buffer_params_from_env(self):
        """Test that SQUEEZELITE_BUFFER_PARAMS env var is used."""
        assert DEFAULT_BUFFER_PARAMS is not None
        assert isinstance(DEFAULT_BUFFER_PARAMS, str)
        assert ":" in DEFAULT_BUFFER_PARAMS  # Format should be "stream:output"

    def test_default_close_timeout_from_env(self):
        """Test that SQUEEZELITE_CLOSE_TIMEOUT env var is used."""
        assert DEFAULT_CLOSE_TIMEOUT is not None
        assert isinstance(DEFAULT_CLOSE_TIMEOUT, str)

    def test_default_sample_rate_from_env(self):
        """Test that SQUEEZELITE_SAMPLE_RATE env var is used."""
        assert DEFAULT_SAMPLE_RATE is not None
        assert isinstance(DEFAULT_SAMPLE_RATE, str)

    def test_null_device_constant(self):
        """Test that NULL_DEVICE constant is defined."""
        assert NULL_DEVICE == "null"

    def test_build_command_uses_buffer_settings(self, squeezelite_provider, minimal_squeezelite_config):
        """Test that build_command uses the buffer settings from environment."""
        with patch("providers.squeezelite.get_squeezelite_output_device", return_value="default"):
            cmd = squeezelite_provider.build_command(minimal_squeezelite_config, "/app/logs/test.log")

        # Check buffer size (-a)
        a_idx = cmd.index("-a")
        assert cmd[a_idx + 1] == DEFAULT_BUFFER_SIZE

        # Check buffer params (-b)
        b_idx = cmd.index("-b")
        assert cmd[b_idx + 1] == DEFAULT_BUFFER_PARAMS

        # Check close timeout (-C)
        c_idx = cmd.index("-C")
        assert cmd[c_idx + 1] == DEFAULT_CLOSE_TIMEOUT
