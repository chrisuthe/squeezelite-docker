"""
Tests for the Snapcast player provider.

Tests cover command building, configuration validation, host ID generation,
and volume control delegation.
"""

from unittest.mock import Mock

import pytest
from providers.snapcast import SnapcastProvider

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
def snapcast_provider(mock_audio_manager):
    """Create a SnapcastProvider instance with mocked AudioManager."""
    return SnapcastProvider(mock_audio_manager)


@pytest.fixture
def sample_snapcast_config():
    """Sample valid Snapcast player configuration."""
    return {
        "name": "Living Room",
        "device": "hw:1,0",
        "provider": "snapcast",
        "server_ip": "192.168.1.50",
        "host_id": "snapcast-living-room-abc123",
        "latency": 100,
        "volume": 75,
        "autostart": True,
        "enabled": True,
    }


@pytest.fixture
def minimal_snapcast_config():
    """Minimal valid Snapcast configuration (required fields only)."""
    return {
        "name": "TestPlayer",
        "provider": "snapcast",
    }


# =============================================================================
# TEST CLASS ATTRIBUTES
# =============================================================================


class TestSnapcastProviderAttributes:
    """Test provider class attributes."""

    def test_provider_type(self, snapcast_provider):
        """Test that provider_type is correct."""
        assert snapcast_provider.provider_type == "snapcast"

    def test_display_name(self, snapcast_provider):
        """Test that display_name is correct."""
        assert snapcast_provider.display_name == "Snapcast"

    def test_binary_name(self, snapcast_provider):
        """Test that binary_name is correct."""
        assert snapcast_provider.binary_name == "snapclient"


# =============================================================================
# TEST BUILD_COMMAND
# =============================================================================


class TestBuildCommand:
    """Tests for build_command method."""

    def test_build_command_minimal(self, snapcast_provider, minimal_snapcast_config):
        """Test command building with minimal config."""
        cmd = snapcast_provider.build_command(minimal_snapcast_config, "/app/logs/test.log")

        assert cmd[0] == "snapclient"
        assert "--player" in cmd
        assert "alsa" in cmd
        assert "--logsink" in cmd
        assert "file:/app/logs/test.log" in cmd

    def test_build_command_with_server(self, snapcast_provider, sample_snapcast_config):
        """Test command building with server IP specified."""
        cmd = snapcast_provider.build_command(sample_snapcast_config, "/app/logs/test.log")

        assert "--host" in cmd
        host_idx = cmd.index("--host")
        assert cmd[host_idx + 1] == "192.168.1.50"

    def test_build_command_with_device(self, snapcast_provider, sample_snapcast_config):
        """Test command building with audio device specified."""
        cmd = snapcast_provider.build_command(sample_snapcast_config, "/app/logs/test.log")

        assert "--soundcard" in cmd
        soundcard_idx = cmd.index("--soundcard")
        assert cmd[soundcard_idx + 1] == "hw:1,0"

    def test_build_command_with_host_id(self, snapcast_provider, sample_snapcast_config):
        """Test command building with host ID specified."""
        cmd = snapcast_provider.build_command(sample_snapcast_config, "/app/logs/test.log")

        assert "--hostID" in cmd
        hostid_idx = cmd.index("--hostID")
        assert cmd[hostid_idx + 1] == "snapcast-living-room-abc123"

    def test_build_command_with_latency(self, snapcast_provider, sample_snapcast_config):
        """Test command building with latency specified."""
        cmd = snapcast_provider.build_command(sample_snapcast_config, "/app/logs/test.log")

        assert "--latency" in cmd
        latency_idx = cmd.index("--latency")
        assert cmd[latency_idx + 1] == "100"

    def test_build_command_default_device_not_included(self, snapcast_provider):
        """Test that default device doesn't add --soundcard option."""
        config = {"name": "Test", "device": "default"}
        cmd = snapcast_provider.build_command(config, "/app/logs/test.log")

        assert "--soundcard" not in cmd

    def test_build_command_zero_latency_not_included(self, snapcast_provider):
        """Test that zero latency doesn't add --latency option."""
        config = {"name": "Test", "latency": 0}
        cmd = snapcast_provider.build_command(config, "/app/logs/test.log")

        assert "--latency" not in cmd

    def test_build_command_no_server_ip_means_no_host_flag(self, snapcast_provider):
        """Test that missing server_ip doesn't add --host option (auto-discover)."""
        config = {"name": "Test"}
        cmd = snapcast_provider.build_command(config, "/app/logs/test.log")

        assert "--host" not in cmd


# =============================================================================
# TEST BUILD_FALLBACK_COMMAND
# =============================================================================


class TestBuildFallbackCommand:
    """Tests for build_fallback_command method."""

    def test_fallback_returns_none(self, snapcast_provider, sample_snapcast_config):
        """Test that fallback command is not supported."""
        result = snapcast_provider.build_fallback_command(sample_snapcast_config, "/app/logs/test.log")
        assert result is None

    def test_supports_fallback_returns_false(self, snapcast_provider):
        """Test that supports_fallback returns False."""
        assert snapcast_provider.supports_fallback() is False


# =============================================================================
# TEST VALIDATE_CONFIG
# =============================================================================


class TestValidateConfig:
    """Tests for validate_config method."""

    def test_validate_valid_config(self, snapcast_provider, sample_snapcast_config):
        """Test validation of a valid configuration."""
        is_valid, error = snapcast_provider.validate_config(sample_snapcast_config)
        assert is_valid is True
        assert error == ""

    def test_validate_minimal_config(self, snapcast_provider, minimal_snapcast_config):
        """Test validation of minimal configuration."""
        is_valid, error = snapcast_provider.validate_config(minimal_snapcast_config)
        assert is_valid is True
        assert error == ""

    def test_validate_missing_name(self, snapcast_provider):
        """Test validation fails when name is missing."""
        config = {"device": "hw:0,0"}
        is_valid, error = snapcast_provider.validate_config(config)
        assert is_valid is False
        assert "name is required" in error.lower()

    def test_validate_empty_name(self, snapcast_provider):
        """Test validation fails when name is empty."""
        config = {"name": "", "device": "hw:0,0"}
        is_valid, error = snapcast_provider.validate_config(config)
        assert is_valid is False
        assert "name is required" in error.lower()

    def test_validate_name_too_long(self, snapcast_provider):
        """Test validation fails when name exceeds 64 characters."""
        config = {"name": "x" * 65}
        is_valid, error = snapcast_provider.validate_config(config)
        assert is_valid is False
        assert "too long" in error.lower()

    def test_validate_name_with_invalid_chars(self, snapcast_provider):
        """Test validation fails when name contains invalid characters."""
        for invalid_char in ["/", "\\", "\x00"]:
            config = {"name": f"test{invalid_char}name"}
            is_valid, error = snapcast_provider.validate_config(config)
            assert is_valid is False
            assert "invalid characters" in error.lower()

    def test_validate_invalid_latency_type(self, snapcast_provider):
        """Test validation fails when latency is not an integer."""
        config = {"name": "Test", "latency": "not_a_number"}
        is_valid, error = snapcast_provider.validate_config(config)
        assert is_valid is False
        assert "latency" in error.lower()

    def test_validate_latency_as_string_number(self, snapcast_provider):
        """Test validation accepts latency as string number."""
        config = {"name": "Test", "latency": "100"}
        is_valid, error = snapcast_provider.validate_config(config)
        assert is_valid is True


# =============================================================================
# TEST GET_DEFAULT_CONFIG
# =============================================================================


class TestGetDefaultConfig:
    """Tests for get_default_config method."""

    def test_default_config_has_required_fields(self, snapcast_provider):
        """Test that default config contains all expected fields."""
        defaults = snapcast_provider.get_default_config()

        assert "provider" in defaults
        assert defaults["provider"] == "snapcast"
        assert "device" in defaults
        assert "server_ip" in defaults
        assert "host_id" in defaults
        assert "latency" in defaults
        assert "volume" in defaults
        assert "autostart" in defaults

    def test_default_config_values(self, snapcast_provider):
        """Test that default config has correct default values."""
        defaults = snapcast_provider.get_default_config()

        assert defaults["device"] == "default"
        assert defaults["server_ip"] == ""
        assert defaults["host_id"] == ""
        assert defaults["latency"] == 0
        assert defaults["volume"] == 75
        assert defaults["autostart"] is False


# =============================================================================
# TEST GET_REQUIRED_FIELDS
# =============================================================================


class TestGetRequiredFields:
    """Tests for get_required_fields method."""

    def test_required_fields(self, snapcast_provider):
        """Test that only name is required."""
        required = snapcast_provider.get_required_fields()
        assert required == ["name"]


# =============================================================================
# TEST GENERATE_HOST_ID
# =============================================================================


class TestGenerateHostId:
    """Tests for generate_host_id static method."""

    def test_generate_host_id_format(self):
        """Test that generated host ID has correct format."""
        host_id = SnapcastProvider.generate_host_id("Kitchen")

        assert host_id.startswith("snapcast-")
        assert "kitchen" in host_id  # Name should be lowercased
        assert len(host_id) > len("snapcast-kitchen-")  # Should have hash suffix

    def test_generate_host_id_deterministic(self):
        """Test that same name always generates same host ID."""
        id1 = SnapcastProvider.generate_host_id("Living Room")
        id2 = SnapcastProvider.generate_host_id("Living Room")

        assert id1 == id2

    def test_generate_host_id_unique_for_different_names(self):
        """Test that different names generate different host IDs."""
        id1 = SnapcastProvider.generate_host_id("Kitchen")
        id2 = SnapcastProvider.generate_host_id("Bedroom")

        assert id1 != id2

    def test_generate_host_id_handles_spaces(self):
        """Test that spaces in name are replaced with dashes."""
        host_id = SnapcastProvider.generate_host_id("Living Room")

        assert " " not in host_id
        assert "living-room" in host_id

    def test_generate_host_id_truncates_long_names(self):
        """Test that long names are truncated."""
        long_name = "A" * 100
        host_id = SnapcastProvider.generate_host_id(long_name)

        # Name part should be truncated to 20 chars
        assert len(host_id) < 100


# =============================================================================
# TEST PREPARE_CONFIG
# =============================================================================


class TestPrepareConfig:
    """Tests for prepare_config method."""

    def test_prepare_config_merges_with_defaults(self, snapcast_provider):
        """Test that prepare_config merges user config with defaults."""
        user_config = {"name": "Kitchen", "device": "hw:1,0"}
        prepared = snapcast_provider.prepare_config(user_config)

        # User values preserved
        assert prepared["name"] == "Kitchen"
        assert prepared["device"] == "hw:1,0"

        # Defaults added
        assert prepared["provider"] == "snapcast"
        assert prepared["volume"] == 75
        assert prepared["autostart"] is False

    def test_prepare_config_generates_host_id(self, snapcast_provider):
        """Test that prepare_config generates host_id if not provided."""
        user_config = {"name": "Kitchen"}
        prepared = snapcast_provider.prepare_config(user_config)

        assert prepared["host_id"] != ""
        assert "snapcast-" in prepared["host_id"]

    def test_prepare_config_preserves_provided_host_id(self, snapcast_provider):
        """Test that prepare_config preserves user-provided host_id."""
        user_config = {"name": "Kitchen", "host_id": "my-custom-id"}
        prepared = snapcast_provider.prepare_config(user_config)

        assert prepared["host_id"] == "my-custom-id"

    def test_prepare_config_user_overrides_defaults(self, snapcast_provider):
        """Test that user config overrides defaults."""
        user_config = {"name": "Kitchen", "volume": 50, "autostart": True}
        prepared = snapcast_provider.prepare_config(user_config)

        assert prepared["volume"] == 50
        assert prepared["autostart"] is True


# =============================================================================
# TEST GET_PLAYER_IDENTIFIER
# =============================================================================


class TestGetPlayerIdentifier:
    """Tests for get_player_identifier method."""

    def test_get_identifier_uses_host_id(self, snapcast_provider, sample_snapcast_config):
        """Test that host_id is used as identifier when present."""
        identifier = snapcast_provider.get_player_identifier(sample_snapcast_config)
        assert identifier == "snapcast-living-room-abc123"

    def test_get_identifier_falls_back_to_name(self, snapcast_provider):
        """Test that name is used when host_id is not present."""
        config = {"name": "Kitchen"}
        identifier = snapcast_provider.get_player_identifier(config)
        assert identifier == "Kitchen"

    def test_get_identifier_unknown_fallback(self, snapcast_provider):
        """Test that 'unknown' is returned when neither host_id nor name present."""
        config = {}
        identifier = snapcast_provider.get_player_identifier(config)
        assert identifier == "unknown"


# =============================================================================
# TEST VOLUME CONTROL
# =============================================================================


class TestVolumeControl:
    """Tests for volume control methods."""

    def test_get_volume_delegates_to_audio_manager(self, snapcast_provider, mock_audio_manager, sample_snapcast_config):
        """Test that get_volume delegates to AudioManager."""
        volume = snapcast_provider.get_volume(sample_snapcast_config)

        mock_audio_manager.get_volume.assert_called_once_with("hw:1,0")
        assert volume == 75

    def test_get_volume_uses_default_device(self, snapcast_provider, mock_audio_manager):
        """Test that get_volume uses 'default' when no device specified."""
        config = {"name": "Test"}
        snapcast_provider.get_volume(config)

        mock_audio_manager.get_volume.assert_called_once_with("default")

    def test_set_volume_delegates_to_audio_manager(self, snapcast_provider, mock_audio_manager, sample_snapcast_config):
        """Test that set_volume delegates to AudioManager."""
        success, message = snapcast_provider.set_volume(sample_snapcast_config, 50)

        mock_audio_manager.set_volume.assert_called_once_with("hw:1,0", 50)
        assert success is True
        assert "50%" in message

    def test_set_volume_uses_default_device(self, snapcast_provider, mock_audio_manager):
        """Test that set_volume uses 'default' when no device specified."""
        config = {"name": "Test"}
        snapcast_provider.set_volume(config, 50)

        mock_audio_manager.set_volume.assert_called_once_with("default", 50)
