"""
Unit tests for ConfigManager class.

Tests configuration loading, saving, validation, and player
management operations with mocked file I/O.
"""

from unittest.mock import patch

import pytest
import yaml
from managers.config_manager import ConfigManager, ConfigValidationError

# =============================================================================
# TESTS - Initialization
# =============================================================================


class TestConfigManagerInit:
    """Tests for ConfigManager initialization."""

    def test_init_creates_directory(self, tmp_path):
        """Test that ConfigManager creates config directory if missing."""
        config_path = tmp_path / "config" / "players.yaml"
        with patch("os.makedirs") as mock_makedirs, patch("os.path.exists", return_value=False):
            ConfigManager(str(config_path), validate_on_load=False)
            # Should create parent directory
            mock_makedirs.assert_called_once()

    def test_init_loads_existing_file(self, mock_yaml_file):
        """Test that ConfigManager loads existing config file."""
        manager = ConfigManager(mock_yaml_file)
        assert len(manager.players) == 2
        assert "Kitchen" in manager.players
        assert "Bedroom" in manager.players

    def test_init_empty_file(self, tmp_path):
        """Test initialization with non-existent file."""
        config_path = tmp_path / "players.yaml"
        manager = ConfigManager(str(config_path), validate_on_load=False)
        assert len(manager.players) == 0

    def test_init_validation_enabled_by_default(self, tmp_path):
        """Test that validation is enabled by default."""
        config_path = tmp_path / "players.yaml"
        manager = ConfigManager(str(config_path))
        assert manager.validate_on_load is True
        assert manager.validate_on_save is True

    def test_init_validation_can_be_disabled(self, tmp_path):
        """Test that validation can be disabled."""
        config_path = tmp_path / "players.yaml"
        manager = ConfigManager(str(config_path), validate_on_load=False, validate_on_save=False)
        assert manager.validate_on_load is False
        assert manager.validate_on_save is False


# =============================================================================
# TESTS - Load
# =============================================================================


class TestConfigManagerLoad:
    """Tests for ConfigManager.load() method."""

    def test_load_valid_yaml(self, mock_yaml_file):
        """Test loading valid YAML configuration."""
        manager = ConfigManager(mock_yaml_file, validate_on_load=False)
        players = manager.load()
        assert len(players) == 2
        assert "Kitchen" in players
        assert "Bedroom" in players

    def test_load_empty_file(self, empty_yaml_file):
        """Test loading empty YAML file."""
        manager = ConfigManager(empty_yaml_file, validate_on_load=False)
        players = manager.load()
        assert len(players) == 0

    def test_load_nonexistent_file(self, tmp_path):
        """Test loading non-existent file returns empty dict."""
        config_path = tmp_path / "nonexistent.yaml"
        manager = ConfigManager(str(config_path), validate_on_load=False)
        players = manager.load()
        assert len(players) == 0

    def test_load_corrupt_yaml(self, corrupt_yaml_file):
        """Test loading corrupt YAML returns empty dict and logs error."""
        manager = ConfigManager(corrupt_yaml_file, validate_on_load=False)
        players = manager.load()
        assert len(players) == 0

    def test_load_with_validation_valid_configs(self, mock_yaml_file):
        """Test load with validation enabled for valid configs."""
        manager = ConfigManager(mock_yaml_file, validate_on_load=True)
        assert len(manager.players) == 2

    def test_load_with_validation_skips_invalid(self, tmp_path):
        """Test load with validation skips invalid configs."""
        # Create file with one valid and one invalid player
        config_file = tmp_path / "mixed.yaml"
        data = {
            "Valid": {"name": "Valid", "device": "hw:0,0", "provider": "squeezelite"},
            "Invalid": {"name": "Invalid", "volume": 150},  # Invalid volume
        }
        with open(config_file, "w") as f:
            yaml.dump(data, f)

        manager = ConfigManager(str(config_file), validate_on_load=True)
        assert len(manager.players) == 1
        assert "Valid" in manager.players
        assert "Invalid" not in manager.players

    def test_load_without_validation_loads_all(self, tmp_path):
        """Test load without validation loads all configs."""
        # Create file with one valid and one invalid player
        config_file = tmp_path / "mixed.yaml"
        data = {
            "Valid": {"name": "Valid", "device": "hw:0,0", "provider": "squeezelite"},
            "Invalid": {"name": "Invalid", "volume": 150},  # Invalid volume
        }
        with open(config_file, "w") as f:
            yaml.dump(data, f)

        manager = ConfigManager(str(config_file), validate_on_load=False)
        assert len(manager.players) == 2
        assert "Valid" in manager.players
        assert "Invalid" in manager.players


# =============================================================================
# TESTS - Save
# =============================================================================


class TestConfigManagerSave:
    """Tests for ConfigManager.save() method."""

    def test_save_creates_file(self, tmp_path, sample_squeezelite_config):
        """Test save creates new config file."""
        config_path = tmp_path / "players.yaml"
        manager = ConfigManager(str(config_path), validate_on_save=False)
        manager.players["Kitchen"] = sample_squeezelite_config
        result = manager.save()

        assert result is True
        assert config_path.exists()

    def test_save_writes_yaml(self, tmp_path, sample_squeezelite_config):
        """Test save writes valid YAML."""
        config_path = tmp_path / "players.yaml"
        manager = ConfigManager(str(config_path), validate_on_save=False)
        manager.players["Kitchen"] = sample_squeezelite_config
        manager.save()

        with open(config_path) as f:
            loaded = yaml.safe_load(f)
        assert "Kitchen" in loaded
        assert loaded["Kitchen"]["name"] == "Kitchen"

    def test_save_empty_config(self, tmp_path):
        """Test save with empty config."""
        config_path = tmp_path / "players.yaml"
        manager = ConfigManager(str(config_path), validate_on_save=False)
        result = manager.save()

        assert result is True
        assert config_path.exists()

    def test_save_with_validation_valid_configs(self, tmp_path, sample_squeezelite_config):
        """Test save with validation for valid configs."""
        config_path = tmp_path / "players.yaml"
        manager = ConfigManager(str(config_path), validate_on_save=True)
        manager.players["Kitchen"] = sample_squeezelite_config
        result = manager.save()

        assert result is True

    def test_save_with_validation_invalid_configs(self, tmp_path):
        """Test save with validation raises error for invalid configs."""
        config_path = tmp_path / "players.yaml"
        manager = ConfigManager(str(config_path), validate_on_save=True)
        manager.players["Invalid"] = {"name": "Invalid", "volume": 150}  # Invalid volume

        with pytest.raises(ConfigValidationError) as exc_info:
            manager.save()
        assert "invalid configuration" in str(exc_info.value).lower()

    def test_save_without_validation_allows_invalid(self, tmp_path):
        """Test save without validation allows invalid configs."""
        config_path = tmp_path / "players.yaml"
        manager = ConfigManager(str(config_path), validate_on_save=False)
        manager.players["Invalid"] = {"name": "Invalid", "volume": 150}
        result = manager.save()

        assert result is True

    def test_save_returns_false_on_error(self, tmp_path):
        """Test save returns False on file I/O error."""
        config_path = tmp_path / "players.yaml"
        manager = ConfigManager(str(config_path), validate_on_save=False)

        # Mock open to raise an exception
        with patch("builtins.open", side_effect=OSError("Disk full")):
            result = manager.save()
            assert result is False


# =============================================================================
# TESTS - Player Operations
# =============================================================================


class TestConfigManagerGetPlayer:
    """Tests for ConfigManager.get_player() method."""

    def test_get_existing_player(self, mock_yaml_file):
        """Test getting an existing player."""
        manager = ConfigManager(mock_yaml_file)
        player = manager.get_player("Kitchen")
        assert player is not None
        assert player["name"] == "Kitchen"

    def test_get_nonexistent_player(self, mock_yaml_file):
        """Test getting a non-existent player returns None."""
        manager = ConfigManager(mock_yaml_file)
        player = manager.get_player("NonExistent")
        assert player is None


class TestConfigManagerSetPlayer:
    """Tests for ConfigManager.set_player() method."""

    def test_set_new_player(self, tmp_path, sample_squeezelite_config):
        """Test setting a new player."""
        config_path = tmp_path / "players.yaml"
        manager = ConfigManager(str(config_path), validate_on_save=False)
        manager.set_player("Kitchen", sample_squeezelite_config, validate=False)

        assert "Kitchen" in manager.players
        assert manager.players["Kitchen"]["name"] == "Kitchen"

    def test_set_update_existing_player(self, mock_yaml_file):
        """Test updating an existing player."""
        manager = ConfigManager(mock_yaml_file, validate_on_save=False)
        manager.set_player("Kitchen", {"name": "Kitchen", "volume": 50}, validate=False)

        assert manager.players["Kitchen"]["volume"] == 50

    def test_set_with_validation_valid(self, tmp_path, sample_squeezelite_config):
        """Test set_player with validation for valid config."""
        config_path = tmp_path / "players.yaml"
        manager = ConfigManager(str(config_path))
        manager.set_player("Kitchen", sample_squeezelite_config, validate=True)

        assert "Kitchen" in manager.players

    def test_set_with_validation_invalid(self, tmp_path):
        """Test set_player with validation raises error for invalid config."""
        config_path = tmp_path / "players.yaml"
        manager = ConfigManager(str(config_path))

        with pytest.raises(ConfigValidationError) as exc_info:
            manager.set_player("Invalid", {"name": "Invalid", "volume": 150}, validate=True)
        assert "invalid" in str(exc_info.value).lower()

    def test_set_uses_manager_validation_setting(self, tmp_path, sample_squeezelite_config):
        """Test set_player uses manager's validate_on_save setting by default."""
        config_path = tmp_path / "players.yaml"

        # With validation enabled
        manager = ConfigManager(str(config_path), validate_on_save=True)
        manager.set_player("Kitchen", sample_squeezelite_config)  # Should validate
        assert "Kitchen" in manager.players

        # With validation disabled
        manager2 = ConfigManager(str(config_path), validate_on_save=False)
        manager2.set_player("Invalid", {"name": "Invalid", "volume": 150})  # Should not validate
        assert "Invalid" in manager2.players

    def test_set_does_not_auto_save(self, tmp_path, sample_squeezelite_config):
        """Test that set_player does not automatically save."""
        config_path = tmp_path / "players.yaml"
        manager = ConfigManager(str(config_path), validate_on_save=False)
        manager.set_player("Kitchen", sample_squeezelite_config, validate=False)

        # File should not exist yet
        assert not config_path.exists()

        # Explicitly save
        manager.save()
        assert config_path.exists()


class TestConfigManagerDeletePlayer:
    """Tests for ConfigManager.delete_player() method."""

    def test_delete_existing_player(self, mock_yaml_file):
        """Test deleting an existing player."""
        manager = ConfigManager(mock_yaml_file)
        result = manager.delete_player("Kitchen")

        assert result is True
        assert "Kitchen" not in manager.players

    def test_delete_nonexistent_player(self, mock_yaml_file):
        """Test deleting a non-existent player returns False."""
        manager = ConfigManager(mock_yaml_file)
        result = manager.delete_player("NonExistent")

        assert result is False

    def test_delete_does_not_auto_save(self, mock_yaml_file):
        """Test that delete_player does not automatically save."""
        manager = ConfigManager(mock_yaml_file)
        manager.delete_player("Kitchen")

        # Reload to verify file unchanged
        manager.load()
        assert "Kitchen" in manager.players  # Still in file


class TestConfigManagerRenamePlayer:
    """Tests for ConfigManager.rename_player() method."""

    def test_rename_existing_player(self, mock_yaml_file):
        """Test renaming an existing player."""
        manager = ConfigManager(mock_yaml_file)
        result = manager.rename_player("Kitchen", "LivingRoom")

        assert result is True
        assert "Kitchen" not in manager.players
        assert "LivingRoom" in manager.players
        assert manager.players["LivingRoom"]["name"] == "LivingRoom"

    def test_rename_nonexistent_player(self, mock_yaml_file):
        """Test renaming a non-existent player returns False."""
        manager = ConfigManager(mock_yaml_file)
        result = manager.rename_player("NonExistent", "NewName")

        assert result is False

    def test_rename_to_existing_name(self, mock_yaml_file):
        """Test renaming to an existing name returns False."""
        manager = ConfigManager(mock_yaml_file)
        result = manager.rename_player("Kitchen", "Bedroom")  # Bedroom already exists

        assert result is False
        assert "Kitchen" in manager.players  # Original still exists

    def test_rename_to_same_name(self, mock_yaml_file):
        """Test renaming to same name is allowed."""
        manager = ConfigManager(mock_yaml_file)
        result = manager.rename_player("Kitchen", "Kitchen")

        assert result is True
        assert "Kitchen" in manager.players

    def test_rename_updates_config_name(self, mock_yaml_file):
        """Test rename updates the name field in config."""
        manager = ConfigManager(mock_yaml_file)
        manager.rename_player("Kitchen", "LivingRoom")

        assert manager.players["LivingRoom"]["name"] == "LivingRoom"


class TestConfigManagerPlayerExists:
    """Tests for ConfigManager.player_exists() method."""

    def test_exists_returns_true(self, mock_yaml_file):
        """Test player_exists returns True for existing player."""
        manager = ConfigManager(mock_yaml_file)
        assert manager.player_exists("Kitchen") is True

    def test_exists_returns_false(self, mock_yaml_file):
        """Test player_exists returns False for non-existent player."""
        manager = ConfigManager(mock_yaml_file)
        assert manager.player_exists("NonExistent") is False


class TestConfigManagerListPlayers:
    """Tests for ConfigManager.list_players() method."""

    def test_list_players(self, mock_yaml_file):
        """Test list_players returns all player names."""
        manager = ConfigManager(mock_yaml_file)
        players = manager.list_players()

        assert len(players) == 2
        assert "Kitchen" in players
        assert "Bedroom" in players

    def test_list_players_empty(self, tmp_path):
        """Test list_players returns empty list for no players."""
        config_path = tmp_path / "players.yaml"
        manager = ConfigManager(str(config_path))
        players = manager.list_players()

        assert len(players) == 0


# =============================================================================
# TESTS - Validation Methods
# =============================================================================


class TestConfigManagerValidateConfig:
    """Tests for ConfigManager.validate_config() method."""

    def test_validate_valid_config(self, sample_squeezelite_config, tmp_path):
        """Test validating a valid configuration."""
        config_path = tmp_path / "players.yaml"
        manager = ConfigManager(str(config_path))
        is_valid, error, validated = manager.validate_config(sample_squeezelite_config)

        assert is_valid is True
        assert error == ""
        assert validated is not None

    def test_validate_invalid_config(self, tmp_path):
        """Test validating an invalid configuration."""
        config_path = tmp_path / "players.yaml"
        manager = ConfigManager(str(config_path))
        is_valid, error, validated = manager.validate_config({"name": "Test", "volume": 150})

        assert is_valid is False
        assert error != ""
        assert validated is None

    def test_validate_with_name_parameter(self, tmp_path):
        """Test validate_config uses name parameter."""
        config_path = tmp_path / "players.yaml"
        manager = ConfigManager(str(config_path))
        is_valid, error, validated = manager.validate_config(
            {"device": "hw:0,0", "provider": "squeezelite"},
            name="TestPlayer",
        )

        assert is_valid is True
        assert validated["name"] == "TestPlayer"


class TestConfigManagerValidateAll:
    """Tests for ConfigManager.validate_all() method."""

    def test_validate_all_valid(self, mock_yaml_file):
        """Test validate_all with all valid configs."""
        manager = ConfigManager(mock_yaml_file)
        is_valid, errors = manager.validate_all()

        assert is_valid is True
        assert len(errors) == 0

    def test_validate_all_with_invalid(self, tmp_path):
        """Test validate_all with some invalid configs."""
        config_path = tmp_path / "players.yaml"
        manager = ConfigManager(str(config_path), validate_on_save=False)
        manager.players["Valid"] = {"name": "Valid", "device": "hw:0,0", "provider": "squeezelite"}
        manager.players["Invalid"] = {"name": "Invalid", "volume": 150}

        is_valid, errors = manager.validate_all()

        assert is_valid is False
        assert len(errors) > 0
        assert any("Invalid" in error for error in errors)

    def test_validate_all_empty(self, tmp_path):
        """Test validate_all with no players."""
        config_path = tmp_path / "players.yaml"
        manager = ConfigManager(str(config_path))
        is_valid, errors = manager.validate_all()

        assert is_valid is True
        assert len(errors) == 0


# =============================================================================
# TESTS - ConfigValidationError
# =============================================================================


class TestConfigValidationError:
    """Tests for ConfigValidationError exception class."""

    def test_error_basic(self):
        """Test basic error message."""
        error = ConfigValidationError("Test error")
        assert str(error) == "Test error"

    def test_error_with_errors_list(self):
        """Test error with detailed errors list."""
        error = ConfigValidationError("Validation failed", errors=["Error 1", "Error 2"])
        error_str = str(error)
        assert "Validation failed" in error_str
        assert "Error 1" in error_str
        assert "Error 2" in error_str

    def test_error_with_player_name(self):
        """Test error with player name."""
        error = ConfigValidationError("Invalid config", player_name="Kitchen")
        assert error.player_name == "Kitchen"

    def test_error_attributes(self):
        """Test error attributes are accessible."""
        error = ConfigValidationError(
            "Test error",
            errors=["Error 1"],
            player_name="TestPlayer",
        )
        assert error.message == "Test error"
        assert error.errors == ["Error 1"]
        assert error.player_name == "TestPlayer"
