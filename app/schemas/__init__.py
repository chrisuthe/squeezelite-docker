"""
Schema definitions for configuration validation.

This package contains Pydantic models for validating player
configurations and other structured data.
"""

from .player_config import (
    BasePlayerConfig,
    SendspinPlayerConfig,
    SqueezelitePlayerConfig,
    ValidationError,
    get_default_config,
    get_schema_for_provider,
    validate_player_config,
    validate_players_file,
)

__all__ = [
    "BasePlayerConfig",
    "SendspinPlayerConfig",
    "SqueezelitePlayerConfig",
    "ValidationError",
    "get_default_config",
    "get_schema_for_provider",
    "validate_player_config",
    "validate_players_file",
]
