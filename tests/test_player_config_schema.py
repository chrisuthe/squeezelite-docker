"""
Unit tests for Pydantic player configuration schemas.

Tests validation logic for both Squeezelite and Sendspin player
configurations, including field validation, type checking, and
custom validators.
"""

import pytest
from pydantic import ValidationError
from schemas.player_config import (
    DEFAULT_VOLUME,
    MAX_NAME_LENGTH,
    MAX_VOLUME,
    MIN_VOLUME,
    BasePlayerConfig,
    SendspinPlayerConfig,
    SqueezelitePlayerConfig,
    get_default_config,
    get_schema_for_provider,
    validate_player_config,
    validate_players_file,
)

# =============================================================================
# TESTS - BasePlayerConfig
# =============================================================================


class TestBasePlayerConfig:
    """Tests for the base player configuration schema."""

    def test_minimal_config(self):
        """Test minimal valid base config."""
        config = BasePlayerConfig(name="TestPlayer")
        assert config.name == "TestPlayer"
        assert config.device == "default"
        assert config.volume == DEFAULT_VOLUME
        assert config.autostart is False
        assert config.enabled is True

    def test_all_fields(self):
        """Test config with all base fields specified."""
        config = BasePlayerConfig(
            name="Kitchen",
            device="hw:0,0",
            volume=80,
            autostart=True,
            enabled=False,
        )
        assert config.name == "Kitchen"
        assert config.device == "hw:0,0"
        assert config.volume == 80
        assert config.autostart is True
        assert config.enabled is False

    def test_name_required(self):
        """Test that name field is required."""
        with pytest.raises(ValidationError) as exc_info:
            BasePlayerConfig()
        assert "name" in str(exc_info.value)

    def test_name_too_long(self):
        """Test that name cannot exceed maximum length."""
        long_name = "x" * (MAX_NAME_LENGTH + 1)
        with pytest.raises(ValidationError) as exc_info:
            BasePlayerConfig(name=long_name)
        assert "name" in str(exc_info.value)

    def test_name_empty_string(self):
        """Test that empty name is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            BasePlayerConfig(name="")
        assert "name" in str(exc_info.value)

    def test_name_whitespace_stripped(self):
        """Test that whitespace is stripped from name."""
        config = BasePlayerConfig(name="  Kitchen  ")
        assert config.name == "Kitchen"

    def test_name_invalid_characters(self):
        """Test that invalid characters in name are rejected."""
        invalid_names = [
            "player/test",  # Forward slash
            "player\\test",  # Backslash
            "player\x00test",  # Null byte
        ]
        for invalid_name in invalid_names:
            with pytest.raises(ValidationError) as exc_info:
                BasePlayerConfig(name=invalid_name)
            assert "invalid characters" in str(exc_info.value).lower()

    def test_volume_range_min(self):
        """Test volume minimum boundary."""
        config = BasePlayerConfig(name="Test", volume=MIN_VOLUME)
        assert config.volume == MIN_VOLUME

    def test_volume_range_max(self):
        """Test volume maximum boundary."""
        config = BasePlayerConfig(name="Test", volume=MAX_VOLUME)
        assert config.volume == MAX_VOLUME

    def test_volume_below_min(self):
        """Test that volume below minimum is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            BasePlayerConfig(name="Test", volume=MIN_VOLUME - 1)
        assert "volume" in str(exc_info.value).lower()

    def test_volume_above_max(self):
        """Test that volume above maximum is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            BasePlayerConfig(name="Test", volume=MAX_VOLUME + 1)
        assert "volume" in str(exc_info.value).lower()

    def test_volume_default(self):
        """Test default volume value."""
        config = BasePlayerConfig(name="Test")
        assert config.volume == DEFAULT_VOLUME

    def test_autostart_default(self):
        """Test default autostart value."""
        config = BasePlayerConfig(name="Test")
        assert config.autostart is False

    def test_enabled_default(self):
        """Test default enabled value."""
        config = BasePlayerConfig(name="Test")
        assert config.enabled is True

    def test_extra_fields_allowed(self):
        """Test that extra fields are allowed (for provider-specific fields)."""
        config = BasePlayerConfig(
            name="Test",
            custom_field="value",
            another_field=123,
        )
        # Should not raise an error
        assert config.name == "Test"


# =============================================================================
# TESTS - SqueezelitePlayerConfig
# =============================================================================


class TestSqueezelitePlayerConfig:
    """Tests for Squeezelite player configuration schema."""

    def test_minimal_config(self):
        """Test minimal valid Squeezelite config."""
        config = SqueezelitePlayerConfig(name="Kitchen", device="hw:0,0")
        assert config.name == "Kitchen"
        assert config.device == "hw:0,0"
        assert config.provider == "squeezelite"
        assert config.server_ip == ""
        assert config.mac_address == ""

    def test_full_config(self):
        """Test Squeezelite config with all fields."""
        config = SqueezelitePlayerConfig(
            name="Kitchen",
            device="hw:0,0",
            provider="squeezelite",
            volume=75,
            autostart=True,
            enabled=True,
            server_ip="192.168.1.100",
            mac_address="aa:bb:cc:dd:ee:ff",
        )
        assert config.name == "Kitchen"
        assert config.device == "hw:0,0"
        assert config.provider == "squeezelite"
        assert config.volume == 75
        assert config.server_ip == "192.168.1.100"
        assert config.mac_address == "aa:bb:cc:dd:ee:ff"

    def test_mac_address_valid_formats(self):
        """Test various valid MAC address formats."""
        valid_macs = [
            "aa:bb:cc:dd:ee:ff",
            "AA:BB:CC:DD:EE:FF",
            "00:00:00:00:00:00",
            "FF:FF:FF:FF:FF:FF",
            "12:34:56:78:9a:bc",
        ]
        for mac in valid_macs:
            config = SqueezelitePlayerConfig(
                name="Test",
                device="hw:0,0",
                mac_address=mac,
            )
            # MAC should be normalized to lowercase
            assert config.mac_address == mac.lower()

    def test_mac_address_invalid_formats(self):
        """Test that invalid MAC address formats are rejected."""
        invalid_macs = [
            "invalid",
            "aa:bb:cc:dd:ee",  # Too short
            "aa:bb:cc:dd:ee:ff:gg",  # Too long
            "aa-bb-cc-dd-ee-ff",  # Wrong separator
            "aabbccddeeff",  # No separators
            "zz:zz:zz:zz:zz:zz",  # Invalid hex
        ]
        for mac in invalid_macs:
            with pytest.raises(ValidationError) as exc_info:
                SqueezelitePlayerConfig(
                    name="Test",
                    device="hw:0,0",
                    mac_address=mac,
                )
            assert "mac" in str(exc_info.value).lower()

    def test_mac_address_empty_allowed(self):
        """Test that empty MAC address is allowed (auto-generated)."""
        config = SqueezelitePlayerConfig(name="Test", device="hw:0,0", mac_address="")
        assert config.mac_address == ""

    def test_server_ip_valid(self):
        """Test valid server IP formats."""
        valid_ips = [
            "192.168.1.100",
            "10.0.0.1",
            "localhost",
            "media-server.local",
            "",  # Empty for auto-discovery
        ]
        for ip in valid_ips:
            config = SqueezelitePlayerConfig(
                name="Test",
                device="hw:0,0",
                server_ip=ip,
            )
            assert config.server_ip == ip

    def test_server_ip_rejects_urls(self):
        """Test that URL formats are rejected for server_ip."""
        invalid_ips = [
            "http://192.168.1.100",
            "https://server.local",
            "ws://192.168.1.100:9000",
            "wss://server.local",
        ]
        for ip in invalid_ips:
            with pytest.raises(ValidationError) as exc_info:
                SqueezelitePlayerConfig(
                    name="Test",
                    device="hw:0,0",
                    server_ip=ip,
                )
            assert "server_ip" in str(exc_info.value).lower()

    def test_provider_locked_to_squeezelite(self):
        """Test that provider field is locked to 'squeezelite'."""
        config = SqueezelitePlayerConfig(name="Test", device="hw:0,0")
        assert config.provider == "squeezelite"

        # Attempting to set different provider should fail
        with pytest.raises(ValidationError):
            SqueezelitePlayerConfig(
                name="Test",
                device="hw:0,0",
                provider="sendspin",
            )


# =============================================================================
# TESTS - SendspinPlayerConfig
# =============================================================================


class TestSendspinPlayerConfig:
    """Tests for Sendspin player configuration schema."""

    def test_minimal_config(self):
        """Test minimal valid Sendspin config."""
        config = SendspinPlayerConfig(name="Bedroom")
        assert config.name == "Bedroom"
        assert config.provider == "sendspin"
        assert config.server_url == ""
        assert config.client_id == ""
        assert config.delay_ms == 0
        assert config.log_level == "INFO"

    def test_full_config(self):
        """Test Sendspin config with all fields."""
        config = SendspinPlayerConfig(
            name="Bedroom",
            device="0",
            provider="sendspin",
            volume=60,
            autostart=False,
            enabled=True,
            server_url="ws://192.168.1.200:8080",
            client_id="bedroom-player",
            delay_ms=100,
            log_level="DEBUG",
        )
        assert config.name == "Bedroom"
        assert config.device == "0"
        assert config.provider == "sendspin"
        assert config.volume == 60
        assert config.server_url == "ws://192.168.1.200:8080"
        assert config.client_id == "bedroom-player"
        assert config.delay_ms == 100
        assert config.log_level == "DEBUG"

    def test_server_url_valid_formats(self):
        """Test valid WebSocket URL formats."""
        valid_urls = [
            "ws://192.168.1.200:8080",
            "wss://secure-server.local:8080",
            "ws://localhost:9000",
            "",  # Empty for mDNS discovery
        ]
        for url in valid_urls:
            config = SendspinPlayerConfig(name="Test", server_url=url)
            assert config.server_url == url

    def test_server_url_invalid_formats(self):
        """Test that non-WebSocket URLs are rejected."""
        invalid_urls = [
            "http://192.168.1.200:8080",
            "https://server.local",
            "192.168.1.200:8080",  # Missing protocol
            "tcp://192.168.1.200:8080",
        ]
        for url in invalid_urls:
            with pytest.raises(ValidationError) as exc_info:
                SendspinPlayerConfig(name="Test", server_url=url)
            assert "server_url" in str(exc_info.value).lower() or "ws://" in str(exc_info.value).lower()

    def test_log_level_valid(self):
        """Test all valid log levels."""
        valid_levels = ["TRACE", "DEBUG", "INFO", "WARN", "ERROR"]
        for level in valid_levels:
            config = SendspinPlayerConfig(name="Test", log_level=level)
            assert config.log_level == level

    def test_log_level_case_insensitive(self):
        """Test that log level is case-insensitive."""
        config = SendspinPlayerConfig(name="Test", log_level="debug")
        assert config.log_level == "DEBUG"

    def test_log_level_invalid(self):
        """Test that invalid log levels are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            SendspinPlayerConfig(name="Test", log_level="INVALID")
        assert "log level" in str(exc_info.value).lower()

    def test_device_rejects_alsa_format(self):
        """Test that ALSA device formats are rejected for Sendspin."""
        alsa_devices = [
            "hw:0,0",
            "hw:1,0",
            "plughw:0,0",
        ]
        for device in alsa_devices:
            with pytest.raises(ValidationError) as exc_info:
                SendspinPlayerConfig(name="Test", device=device)
            assert "alsa" in str(exc_info.value).lower() or "portaudio" in str(exc_info.value).lower()

    def test_device_accepts_portaudio_format(self):
        """Test that PortAudio device formats are accepted."""
        portaudio_devices = [
            "0",
            "1",
            "default",
            "pulse",
            "MyAudioDevice",
        ]
        for device in portaudio_devices:
            config = SendspinPlayerConfig(name="Test", device=device)
            assert config.device == device

    def test_delay_ms_accepts_integers(self):
        """Test that delay_ms accepts integer values."""
        config = SendspinPlayerConfig(name="Test", delay_ms=150)
        assert config.delay_ms == 150

    def test_provider_locked_to_sendspin(self):
        """Test that provider field is locked to 'sendspin'."""
        config = SendspinPlayerConfig(name="Test")
        assert config.provider == "sendspin"

        # Attempting to set different provider should fail
        with pytest.raises(ValidationError):
            SendspinPlayerConfig(name="Test", provider="squeezelite")


# =============================================================================
# TESTS - Validation Functions
# =============================================================================


class TestValidatePlayerConfig:
    """Tests for the validate_player_config function."""

    def test_valid_squeezelite_config(self, sample_squeezelite_config):
        """Test validation of valid Squeezelite config."""
        is_valid, error, validated = validate_player_config(sample_squeezelite_config)
        assert is_valid is True
        assert error == ""
        assert validated is not None
        assert validated["provider"] == "squeezelite"

    def test_valid_sendspin_config(self, sample_sendspin_config):
        """Test validation of valid Sendspin config."""
        is_valid, error, validated = validate_player_config(sample_sendspin_config)
        assert is_valid is True
        assert error == ""
        assert validated is not None
        assert validated["provider"] == "sendspin"

    def test_invalid_config_missing_name(self, invalid_config_missing_name):
        """Test validation fails for config missing name."""
        is_valid, error, validated = validate_player_config(invalid_config_missing_name)
        assert is_valid is False
        assert error != ""
        assert validated is None

    def test_invalid_config_bad_volume(self, invalid_config_invalid_volume):
        """Test validation fails for invalid volume."""
        is_valid, error, validated = validate_player_config(invalid_config_invalid_volume)
        assert is_valid is False
        assert "volume" in error.lower()
        assert validated is None

    def test_invalid_config_bad_mac(self, invalid_config_bad_mac):
        """Test validation fails for invalid MAC address."""
        is_valid, error, validated = validate_player_config(invalid_config_bad_mac)
        assert is_valid is False
        assert "mac" in error.lower()
        assert validated is None

    def test_invalid_provider(self, invalid_config_bad_provider):
        """Test validation fails for unknown provider."""
        is_valid, error, validated = validate_player_config(invalid_config_bad_provider)
        assert is_valid is False
        assert "provider" in error.lower()
        assert validated is None

    def test_name_parameter_used_if_missing(self):
        """Test that name parameter is used if not in config."""
        config = {"device": "hw:0,0", "provider": "squeezelite"}
        is_valid, error, validated = validate_player_config(config, name="TestPlayer")
        assert is_valid is True
        assert validated["name"] == "TestPlayer"

    def test_defaults_applied(self):
        """Test that default values are applied to minimal config."""
        config = {"name": "Test", "device": "hw:0,0", "provider": "squeezelite"}
        is_valid, error, validated = validate_player_config(config)
        assert is_valid is True
        assert validated["volume"] == DEFAULT_VOLUME
        assert validated["autostart"] is False
        assert validated["enabled"] is True


class TestValidatePlayersFile:
    """Tests for the validate_players_file function."""

    def test_valid_players_file(self, sample_players_dict):
        """Test validation of valid players dictionary."""
        is_valid, errors, validated = validate_players_file(sample_players_dict)
        assert is_valid is True
        assert len(errors) == 0
        assert len(validated) == 2
        assert "Kitchen" in validated
        assert "Bedroom" in validated

    def test_empty_players_file(self):
        """Test validation of empty players dictionary."""
        is_valid, errors, validated = validate_players_file({})
        assert is_valid is True
        assert len(errors) == 0
        assert len(validated) == 0

    def test_mixed_valid_invalid_players(self):
        """Test validation with mix of valid and invalid players."""
        players = {
            "Valid": {"name": "Valid", "device": "hw:0,0", "provider": "squeezelite"},
            "Invalid": {"name": "Invalid", "device": "hw:0,0", "volume": 150},  # Invalid volume
        }
        is_valid, errors, validated = validate_players_file(players)
        assert is_valid is False
        assert len(errors) == 1
        assert "Invalid" in errors[0]
        assert len(validated) == 1
        assert "Valid" in validated

    def test_all_invalid_players(self):
        """Test validation with all invalid players."""
        players = {
            "Bad1": {"device": "hw:0,0"},  # Missing name
            "Bad2": {"name": "Bad2", "volume": 150},  # Invalid volume
        }
        is_valid, errors, validated = validate_players_file(players)
        assert is_valid is False
        assert len(errors) == 2
        assert len(validated) == 0

    def test_non_dict_config(self):
        """Test validation fails for non-dictionary player config."""
        players = {
            "Player1": "not a dict",
        }
        is_valid, errors, validated = validate_players_file(players)
        assert is_valid is False
        assert len(errors) == 1
        assert "Player1" in errors[0]

    def test_non_dict_input(self):
        """Test validation fails for non-dictionary input."""
        is_valid, errors, validated = validate_players_file("not a dict")
        assert is_valid is False
        assert len(errors) == 1
        assert "dictionary" in errors[0].lower()


class TestGetSchemaForProvider:
    """Tests for the get_schema_for_provider function."""

    def test_get_squeezelite_schema(self):
        """Test getting Squeezelite schema."""
        schema = get_schema_for_provider("squeezelite")
        assert schema == SqueezelitePlayerConfig

    def test_get_sendspin_schema(self):
        """Test getting Sendspin schema."""
        schema = get_schema_for_provider("sendspin")
        assert schema == SendspinPlayerConfig

    def test_unknown_provider(self):
        """Test that unknown provider raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            get_schema_for_provider("unknown")
        assert "unknown" in str(exc_info.value).lower()


class TestGetDefaultConfig:
    """Tests for the get_default_config function."""

    def test_get_squeezelite_defaults(self):
        """Test getting default Squeezelite config."""
        defaults = get_default_config("squeezelite")
        assert defaults["provider"] == "squeezelite"
        assert defaults["volume"] == DEFAULT_VOLUME
        assert defaults["autostart"] is False
        assert defaults["enabled"] is True
        assert defaults["server_ip"] == ""
        assert defaults["mac_address"] == ""

    def test_get_sendspin_defaults(self):
        """Test getting default Sendspin config."""
        defaults = get_default_config("sendspin")
        assert defaults["provider"] == "sendspin"
        assert defaults["volume"] == DEFAULT_VOLUME
        assert defaults["autostart"] is False
        assert defaults["enabled"] is True
        assert defaults["server_url"] == ""
        assert defaults["client_id"] == ""
        assert defaults["delay_ms"] == 0
        assert defaults["log_level"] == "INFO"

    def test_unknown_provider(self):
        """Test that unknown provider raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            get_default_config("unknown")
        assert "unknown" in str(exc_info.value).lower()
