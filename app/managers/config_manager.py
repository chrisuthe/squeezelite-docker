"""
Configuration Manager for player persistence.

Handles loading, saving, and validating player configurations
stored in YAML format.
"""

import logging
import os
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# Type alias for player configuration
PlayerConfig = dict[str, Any]


class ConfigManager:
    """
    Manages player configuration persistence.

    Handles loading and saving player configurations to/from YAML files.
    Provides a clean interface for configuration operations without
    coupling to specific player implementations.

    Attributes:
        config_path: Path to the YAML configuration file.
        players: Dictionary mapping player names to their configurations.
    """

    def __init__(self, config_path: str) -> None:
        """
        Initialize the ConfigManager.

        Args:
            config_path: Path to the YAML configuration file.
        """
        self.config_path = config_path
        self.players: dict[str, PlayerConfig] = {}

        # Ensure config directory exists
        config_dir = os.path.dirname(config_path)
        if config_dir:
            os.makedirs(config_dir, exist_ok=True)

        self.load()

    def load(self) -> dict[str, PlayerConfig]:
        """
        Load player configuration from the YAML configuration file.

        Reads the config file and populates self.players with stored
        player configurations. If the file doesn't exist or contains
        invalid YAML, initializes with an empty dictionary.

        Returns:
            Dictionary of player configurations.

        Side Effects:
            - Modifies self.players dictionary
            - Logs errors if file reading or YAML parsing fails
        """
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path) as f:
                    self.players = yaml.safe_load(f) or {}
                logger.debug(f"Loaded {len(self.players)} players from {self.config_path}")
            except Exception as e:
                logger.error(f"Error loading config from {self.config_path}: {e}")
                self.players = {}
        else:
            logger.info(f"Config file {self.config_path} does not exist, starting fresh")
            self.players = {}

        return self.players

    def save(self) -> bool:
        """
        Save current player configuration to the YAML configuration file.

        Writes self.players dictionary to the config file in YAML format.
        Uses block style (not flow style) for human readability.

        Returns:
            True if save was successful, False otherwise.

        Side Effects:
            - Writes to config_path
            - Logs errors if file writing fails
        """
        try:
            with open(self.config_path, "w") as f:
                yaml.dump(self.players, f, default_flow_style=False)
            logger.debug(f"Saved {len(self.players)} players to {self.config_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving config to {self.config_path}: {e}")
            return False

    def get_player(self, name: str) -> PlayerConfig | None:
        """
        Get a player configuration by name.

        Args:
            name: Name of the player.

        Returns:
            Player configuration dictionary, or None if not found.
        """
        return self.players.get(name)

    def set_player(self, name: str, config: PlayerConfig) -> None:
        """
        Set a player configuration.

        Args:
            name: Name of the player.
            config: Player configuration dictionary.

        Side Effects:
            - Modifies self.players dictionary
            - Does NOT automatically save (call save() explicitly)
        """
        self.players[name] = config

    def delete_player(self, name: str) -> bool:
        """
        Delete a player configuration.

        Args:
            name: Name of the player to delete.

        Returns:
            True if player was deleted, False if not found.

        Side Effects:
            - Modifies self.players dictionary
            - Does NOT automatically save (call save() explicitly)
        """
        if name in self.players:
            del self.players[name]
            return True
        return False

    def rename_player(self, old_name: str, new_name: str) -> bool:
        """
        Rename a player (change its key in the config).

        Args:
            old_name: Current name of the player.
            new_name: New name for the player.

        Returns:
            True if rename was successful, False if old_name not found
            or new_name already exists.

        Side Effects:
            - Modifies self.players dictionary
            - Does NOT automatically save (call save() explicitly)
        """
        if old_name not in self.players:
            return False
        if new_name in self.players and old_name != new_name:
            return False

        config = self.players[old_name]
        config["name"] = new_name
        del self.players[old_name]
        self.players[new_name] = config
        return True

    def player_exists(self, name: str) -> bool:
        """
        Check if a player exists.

        Args:
            name: Name of the player.

        Returns:
            True if player exists, False otherwise.
        """
        return name in self.players

    def list_players(self) -> list[str]:
        """
        Get list of all player names.

        Returns:
            List of player names.
        """
        return list(self.players.keys())
