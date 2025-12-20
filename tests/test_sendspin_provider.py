"""
Tests for the Sendspin player provider.

Tests cover command building, configuration validation, client ID generation,
and volume control delegation.
"""

from unittest.mock import Mock

import pytest
from providers.sendspin import (
    CLIENT_ID_PREFIX,
    DEFAULT_LOG_LEVEL,
    SendspinProvider,
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
def sendspin_provider(mock_audio_manager):
    """Create a SendspinProvider instance with mocked AudioManager."""
    return SendspinProvider(mock_audio_manager)


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
        "client_id": "bedroom-player",
        "delay_ms": 100,
        "log_level": "INFO",
    }


@pytest.fixture
def minimal_sendspin_config():
    """Minimal valid Sendspin configuration (required fields only)."""
    return {
        "name": "TestPlayer",
        "provider": "sendspin",
    }


# =============================================================================
# TEST CLASS ATTRIBUTES
# =============================================================================


class TestSendspinProviderAttributes:
    """Test provider class attributes."""

    def test_provider_type(self, sendspin_provider):
        """Test that provider_type is correct."""
        assert sendspin_provider.provider_type == "sendspin"

    def test_display_name(self, sendspin_provider):
        """Test that display_name is correct."""
        assert sendspin_provider.display_name == "Sendspin"

    def test_binary_name(self, sendspin_provider):
        """Test that binary_name is correct."""
        assert sendspin_provider.binary_name == "sendspin"


# =============================================================================
# TEST BUILD_COMMAND
# =============================================================================


class TestBuildCommand:
    """Tests for build_command method."""

    def test_build_command_minimal(self, sendspin_provider, minimal_sendspin_config):
        """Test command building with minimal config."""
        cmd = sendspin_provider.build_command(minimal_sendspin_config, "/app/logs/test.log")

        assert cmd[0] == "sendspin"
        assert "--headless" in cmd
        assert "--name" in cmd
        assert "TestPlayer" in cmd
        assert "--id" in cmd
        assert "--log-level" in cmd

    def test_build_command_with_device(self, sendspin_provider, sample_sendspin_config):
        """Test command building with audio device specified."""
        cmd = sendspin_provider.build_command(sample_sendspin_config, "/app/logs/test.log")

        assert "--audio-device" in cmd
        device_idx = cmd.index("--audio-device")
        assert cmd[device_idx + 1] == "0"

    def test_build_command_with_client_id(self, sendspin_provider, sample_sendspin_config):
        """Test command building with client ID specified."""
        cmd = sendspin_provider.build_command(sample_sendspin_config, "/app/logs/test.log")

        assert "--id" in cmd
        id_idx = cmd.index("--id")
        assert cmd[id_idx + 1] == "bedroom-player"

    def test_build_command_with_delay_ms(self, sendspin_provider, sample_sendspin_config):
        """Test command building with delay_ms specified."""
        cmd = sendspin_provider.build_command(sample_sendspin_config, "/app/logs/test.log")

        assert "--static-delay-ms" in cmd
        delay_idx = cmd.index("--static-delay-ms")
        assert cmd[delay_idx + 1] == "100"

    def test_build_command_with_log_level(self, sendspin_provider, sample_sendspin_config):
        """Test command building with log level specified."""
        cmd = sendspin_provider.build_command(sample_sendspin_config, "/app/logs/test.log")

        assert "--log-level" in cmd
        level_idx = cmd.index("--log-level")
        assert cmd[level_idx + 1] == "INFO"

    def test_build_command_default_device_not_included(self, sendspin_provider):
        """Test that default device doesn't add --audio-device option."""
        config = {"name": "Test", "device": "default"}
        cmd = sendspin_provider.build_command(config, "/app/logs/test.log")

        assert "--audio-device" not in cmd

    def test_build_command_null_device_not_included(self, sendspin_provider):
        """Test that null device doesn't add --audio-device option."""
        config = {"name": "Test", "device": "null"}
        cmd = sendspin_provider.build_command(config, "/app/logs/test.log")

        assert "--audio-device" not in cmd

    def test_build_command_zero_delay_not_included(self, sendspin_provider):
        """Test that zero delay doesn't add --static-delay-ms option."""
        config = {"name": "Test", "delay_ms": 0}
        cmd = sendspin_provider.build_command(config, "/app/logs/test.log")

        assert "--static-delay-ms" not in cmd

    def test_build_command_none_delay_not_included(self, sendspin_provider):
        """Test that None delay doesn't add --static-delay-ms option."""
        config = {"name": "Test", "delay_ms": None}
        cmd = sendspin_provider.build_command(config, "/app/logs/test.log")

        assert "--static-delay-ms" not in cmd

    def test_build_command_alsa_device_skipped(self, sendspin_provider):
        """Test that ALSA-style device names are skipped."""
        config = {"name": "Test", "device": "hw:1,0"}
        cmd = sendspin_provider.build_command(config, "/app/logs/test.log")

        assert "--audio-device" not in cmd

    def test_build_command_plughw_device_skipped(self, sendspin_provider):
        """Test that plughw device names are skipped."""
        config = {"name": "Test", "device": "plughw:0,0"}
        cmd = sendspin_provider.build_command(config, "/app/logs/test.log")

        assert "--audio-device" not in cmd

    def test_build_command_generates_client_id_if_missing(self, sendspin_provider):
        """Test that client_id is generated if not provided."""
        config = {"name": "Kitchen"}
        cmd = sendspin_provider.build_command(config, "/app/logs/test.log")

        assert "--id" in cmd
        id_idx = cmd.index("--id")
        client_id = cmd[id_idx + 1]
        assert client_id.startswith(CLIENT_ID_PREFIX)

    def test_build_command_always_headless(self, sendspin_provider, sample_sendspin_config):
        """Test that --headless is always included."""
        cmd = sendspin_provider.build_command(sample_sendspin_config, "/app/logs/test.log")
        assert "--headless" in cmd

    def test_build_command_usb_audio_device(self, sendspin_provider):
        """Test command building with USB Audio device name."""
        config = {"name": "Test", "device": "USB Audio"}
        cmd = sendspin_provider.build_command(config, "/app/logs/test.log")

        assert "--audio-device" in cmd
        device_idx = cmd.index("--audio-device")
        assert cmd[device_idx + 1] == "USB Audio"


# =============================================================================
# TEST BUILD_FALLBACK_COMMAND
# =============================================================================


class TestBuildFallbackCommand:
    """Tests for build_fallback_command method."""

    def test_fallback_returns_none(self, sendspin_provider, sample_sendspin_config):
        """Test that fallback command is not supported."""
        result = sendspin_provider.build_fallback_command(sample_sendspin_config, "/app/logs/test.log")
        assert result is None

    def test_supports_fallback_returns_false(self, sendspin_provider):
        """Test that supports_fallback returns False."""
        assert sendspin_provider.supports_fallback() is False


# =============================================================================
# TEST VALIDATE_CONFIG
# =============================================================================


class TestValidateConfig:
    """Tests for validate_config method."""

    def test_validate_valid_config(self, sendspin_provider, sample_sendspin_config):
        """Test validation of a valid configuration."""
        is_valid, error = sendspin_provider.validate_config(sample_sendspin_config)
        assert is_valid is True
        assert error == ""

    def test_validate_minimal_config(self, sendspin_provider, minimal_sendspin_config):
        """Test validation of minimal configuration."""
        is_valid, error = sendspin_provider.validate_config(minimal_sendspin_config)
        assert is_valid is True
        assert error == ""

    def test_validate_missing_name(self, sendspin_provider):
        """Test validation fails when name is missing."""
        config = {"device": "0"}
        is_valid, error = sendspin_provider.validate_config(config)
        assert is_valid is False
        assert "name is required" in error.lower()

    def test_validate_empty_name(self, sendspin_provider):
        """Test validation fails when name is empty."""
        config = {"name": "", "device": "0"}
        is_valid, error = sendspin_provider.validate_config(config)
        assert is_valid is False
        assert "name is required" in error.lower()

    def test_validate_name_too_long(self, sendspin_provider):
        """Test validation fails when name exceeds 64 characters."""
        config = {"name": "x" * 65}
        is_valid, error = sendspin_provider.validate_config(config)
        assert is_valid is False
        assert "too long" in error.lower()

    def test_validate_name_at_max_length(self, sendspin_provider):
        """Test validation passes when name is exactly 64 characters."""
        config = {"name": "x" * 64}
        is_valid, error = sendspin_provider.validate_config(config)
        assert is_valid is True

    def test_validate_name_with_invalid_chars(self, sendspin_provider):
        """Test validation fails when name contains invalid characters."""
        for invalid_char in ["/", "\\", "\x00"]:
            config = {"name": f"test{invalid_char}name"}
            is_valid, error = sendspin_provider.validate_config(config)
            assert is_valid is False
            assert "invalid characters" in error.lower()

    def test_validate_invalid_delay_type(self, sendspin_provider):
        """Test validation fails when delay_ms is not an integer."""
        config = {"name": "Test", "delay_ms": "not_a_number"}
        is_valid, error = sendspin_provider.validate_config(config)
        assert is_valid is False
        assert "delay" in error.lower()

    def test_validate_delay_as_string_number(self, sendspin_provider):
        """Test validation accepts delay_ms as string number."""
        config = {"name": "Test", "delay_ms": "100"}
        is_valid, error = sendspin_provider.validate_config(config)
        assert is_valid is True

    def test_validate_delay_as_integer(self, sendspin_provider):
        """Test validation accepts delay_ms as integer."""
        config = {"name": "Test", "delay_ms": 100}
        is_valid, error = sendspin_provider.validate_config(config)
        assert is_valid is True

    def test_validate_negative_delay(self, sendspin_provider):
        """Test validation accepts negative delay_ms (for sync adjustment)."""
        config = {"name": "Test", "delay_ms": -50}
        is_valid, error = sendspin_provider.validate_config(config)
        assert is_valid is True

    def test_validate_no_device_required(self, sendspin_provider):
        """Test that device is not required for Sendspin."""
        config = {"name": "Test"}
        is_valid, error = sendspin_provider.validate_config(config)
        assert is_valid is True


# =============================================================================
# TEST GET_DEFAULT_CONFIG
# =============================================================================


class TestGetDefaultConfig:
    """Tests for get_default_config method."""

    def test_default_config_has_required_fields(self, sendspin_provider):
        """Test that default config contains all expected fields."""
        defaults = sendspin_provider.get_default_config()

        assert "provider" in defaults
        assert defaults["provider"] == "sendspin"
        assert "device" in defaults
        assert "client_id" in defaults
        assert "delay_ms" in defaults
        assert "log_level" in defaults
        assert "volume" in defaults
        assert "autostart" in defaults

    def test_default_config_values(self, sendspin_provider):
        """Test that default config has correct default values."""
        defaults = sendspin_provider.get_default_config()

        assert defaults["device"] == "default"
        assert defaults["client_id"] == ""
        assert defaults["delay_ms"] == 0
        assert defaults["log_level"] == DEFAULT_LOG_LEVEL
        assert defaults["volume"] == 75
        assert defaults["autostart"] is False


# =============================================================================
# TEST GET_REQUIRED_FIELDS
# =============================================================================


class TestGetRequiredFields:
    """Tests for get_required_fields method."""

    def test_required_fields(self, sendspin_provider):
        """Test that only name is required."""
        required = sendspin_provider.get_required_fields()
        assert required == ["name"]


# =============================================================================
# TEST GENERATE_CLIENT_ID
# =============================================================================


class TestGenerateClientId:
    """Tests for _generate_client_id method."""

    def test_generate_client_id_format(self, sendspin_provider):
        """Test that generated client ID has correct format."""
        client_id = sendspin_provider._generate_client_id("Kitchen")

        assert client_id.startswith(f"{CLIENT_ID_PREFIX}-")
        assert "kitchen" in client_id  # Name should be lowercased
        assert len(client_id) > len(f"{CLIENT_ID_PREFIX}-kitchen-")  # Should have hash suffix

    def test_generate_client_id_deterministic(self, sendspin_provider):
        """Test that same name always generates same client ID."""
        id1 = sendspin_provider._generate_client_id("Living Room")
        id2 = sendspin_provider._generate_client_id("Living Room")

        assert id1 == id2

    def test_generate_client_id_unique_for_different_names(self, sendspin_provider):
        """Test that different names generate different client IDs."""
        id1 = sendspin_provider._generate_client_id("Kitchen")
        id2 = sendspin_provider._generate_client_id("Bedroom")

        assert id1 != id2

    def test_generate_client_id_handles_spaces(self, sendspin_provider):
        """Test that spaces in name are replaced with dashes."""
        client_id = sendspin_provider._generate_client_id("Living Room")

        assert " " not in client_id
        assert "living-room" in client_id

    def test_generate_client_id_truncates_long_names(self, sendspin_provider):
        """Test that long names are truncated."""
        long_name = "A" * 100
        client_id = sendspin_provider._generate_client_id(long_name)

        # Name part should be truncated to 20 chars
        assert len(client_id) < 100

    def test_generate_client_id_has_hash_suffix(self, sendspin_provider):
        """Test that client ID has hash suffix for uniqueness."""
        client_id = sendspin_provider._generate_client_id("Test")

        parts = client_id.split("-")
        # Should have: prefix, name, hash
        assert len(parts) >= 3
        # Last part should be 8-char hex hash
        assert len(parts[-1]) == 8


# =============================================================================
# TEST PREPARE_CONFIG
# =============================================================================


class TestPrepareConfig:
    """Tests for prepare_config method."""

    def test_prepare_config_merges_with_defaults(self, sendspin_provider):
        """Test that prepare_config merges user config with defaults."""
        user_config = {"name": "Kitchen", "device": "1"}
        prepared = sendspin_provider.prepare_config(user_config)

        # User values preserved
        assert prepared["name"] == "Kitchen"
        assert prepared["device"] == "1"

        # Defaults added
        assert prepared["provider"] == "sendspin"
        assert prepared["volume"] == 75
        assert prepared["autostart"] is False
        assert prepared["delay_ms"] == 0

    def test_prepare_config_generates_client_id(self, sendspin_provider):
        """Test that prepare_config generates client_id if not provided."""
        user_config = {"name": "Kitchen"}
        prepared = sendspin_provider.prepare_config(user_config)

        assert prepared["client_id"] != ""
        assert f"{CLIENT_ID_PREFIX}-" in prepared["client_id"]

    def test_prepare_config_preserves_provided_client_id(self, sendspin_provider):
        """Test that prepare_config preserves user-provided client_id."""
        user_config = {"name": "Kitchen", "client_id": "my-custom-id"}
        prepared = sendspin_provider.prepare_config(user_config)

        assert prepared["client_id"] == "my-custom-id"

    def test_prepare_config_user_overrides_defaults(self, sendspin_provider):
        """Test that user config overrides defaults."""
        user_config = {"name": "Kitchen", "volume": 50, "autostart": True, "delay_ms": 150}
        prepared = sendspin_provider.prepare_config(user_config)

        assert prepared["volume"] == 50
        assert prepared["autostart"] is True
        assert prepared["delay_ms"] == 150


# =============================================================================
# TEST GET_PLAYER_IDENTIFIER
# =============================================================================


class TestGetPlayerIdentifier:
    """Tests for get_player_identifier method."""

    def test_get_identifier_uses_client_id(self, sendspin_provider, sample_sendspin_config):
        """Test that client_id is used as identifier when present."""
        identifier = sendspin_provider.get_player_identifier(sample_sendspin_config)
        assert identifier == "bedroom-player"

    def test_get_identifier_falls_back_to_name(self, sendspin_provider):
        """Test that name is used when client_id is not present."""
        config = {"name": "Kitchen"}
        identifier = sendspin_provider.get_player_identifier(config)
        assert identifier == "Kitchen"

    def test_get_identifier_unknown_fallback(self, sendspin_provider):
        """Test that 'unknown' is returned when neither client_id nor name present."""
        config = {}
        identifier = sendspin_provider.get_player_identifier(config)
        assert identifier == "unknown"


# =============================================================================
# TEST VOLUME CONTROL
# =============================================================================


class TestVolumeControl:
    """Tests for volume control methods."""

    def test_get_volume_delegates_to_audio_manager(self, sendspin_provider, mock_audio_manager, sample_sendspin_config):
        """Test that get_volume delegates to AudioManager."""
        volume = sendspin_provider.get_volume(sample_sendspin_config)

        mock_audio_manager.get_volume.assert_called_once_with("0")
        assert volume == 75

    def test_get_volume_uses_default_device(self, sendspin_provider, mock_audio_manager):
        """Test that get_volume uses 'default' when no device specified."""
        config = {"name": "Test"}
        sendspin_provider.get_volume(config)

        mock_audio_manager.get_volume.assert_called_once_with("default")

    def test_set_volume_delegates_to_audio_manager(self, sendspin_provider, mock_audio_manager, sample_sendspin_config):
        """Test that set_volume delegates to AudioManager."""
        success, message = sendspin_provider.set_volume(sample_sendspin_config, 50)

        mock_audio_manager.set_volume.assert_called_once_with("0", 50)
        assert success is True
        assert "50%" in message

    def test_set_volume_uses_default_device(self, sendspin_provider, mock_audio_manager):
        """Test that set_volume uses 'default' when no device specified."""
        config = {"name": "Test"}
        sendspin_provider.set_volume(config, 50)

        mock_audio_manager.set_volume.assert_called_once_with("default", 50)


# =============================================================================
# TEST CONSTANTS
# =============================================================================


class TestConstants:
    """Tests for module constants."""

    def test_default_log_level(self):
        """Test that DEFAULT_LOG_LEVEL is INFO."""
        assert DEFAULT_LOG_LEVEL == "INFO"

    def test_client_id_prefix(self):
        """Test that CLIENT_ID_PREFIX is sendspin."""
        assert CLIENT_ID_PREFIX == "sendspin"
