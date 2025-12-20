"""
Pydantic schemas for player configuration validation.

Defines validation schemas for both Squeezelite and Sendspin player
configurations, ensuring type safety and format correctness.
"""

import re
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

# =============================================================================
# CONSTANTS
# =============================================================================

# MAC address regex pattern (XX:XX:XX:XX:XX:XX format)
MAC_ADDRESS_PATTERN = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")

# WebSocket URL pattern for Sendspin server
WEBSOCKET_URL_PATTERN = re.compile(r"^wss?://")

# Invalid characters for player names (filesystem/process safety)
# Includes path traversal (..) and shell metacharacters to prevent injection
INVALID_NAME_CHARS = frozenset("/\\\x00$`;|&")

# Dangerous patterns for player names (path traversal)
INVALID_NAME_PATTERNS = ("..",)

# Maximum player name length
MAX_NAME_LENGTH = 64

# Volume range
MIN_VOLUME = 0
MAX_VOLUME = 100

# Default volume
DEFAULT_VOLUME = 75

# Valid log levels for Sendspin
VALID_LOG_LEVELS = frozenset({"TRACE", "DEBUG", "INFO", "WARN", "ERROR"})


# =============================================================================
# BASE SCHEMA
# =============================================================================


class BasePlayerConfig(BaseModel):
    """
    Base configuration shared by all player providers.

    Contains common fields that apply regardless of the underlying
    audio player implementation.
    """

    model_config = ConfigDict(
        extra="allow",  # Allow provider-specific fields
        str_strip_whitespace=True,
    )

    name: Annotated[
        str,
        Field(
            min_length=1,
            max_length=MAX_NAME_LENGTH,
            description="Player display name (1-64 characters)",
        ),
    ]

    device: Annotated[
        str,
        Field(
            default="default",
            description="Audio output device identifier",
        ),
    ]

    volume: Annotated[
        int,
        Field(
            default=DEFAULT_VOLUME,
            ge=MIN_VOLUME,
            le=MAX_VOLUME,
            description="Volume level (0-100)",
        ),
    ]

    autostart: Annotated[
        bool,
        Field(
            default=False,
            description="Whether to start player automatically on container boot",
        ),
    ]

    enabled: Annotated[
        bool,
        Field(
            default=True,
            description="Whether the player is enabled",
        ),
    ]

    @field_validator("name")
    @classmethod
    def validate_name_chars(cls, v: str) -> str:
        """Validate that name doesn't contain invalid characters or dangerous patterns."""
        # Check for invalid characters (shell metacharacters, path separators)
        invalid_found = set(v) & INVALID_NAME_CHARS
        if invalid_found:
            chars_repr = ", ".join(repr(c) for c in invalid_found)
            raise ValueError(f"Name contains invalid characters: {chars_repr}")

        # Check for dangerous patterns (path traversal)
        for pattern in INVALID_NAME_PATTERNS:
            if pattern in v:
                raise ValueError(f"Name contains invalid pattern: {pattern!r}")

        return v


# =============================================================================
# SQUEEZELITE SCHEMA
# =============================================================================


class SqueezelitePlayerConfig(BasePlayerConfig):
    """
    Configuration schema for Squeezelite players.

    Squeezelite is a lightweight headless Squeezebox emulator that
    connects to Logitech Media Server (LMS).

    Required fields:
        - name: Player display name
        - device: ALSA audio output device

    Optional fields:
        - server_ip: LMS server address (auto-discovered if empty)
        - mac_address: Player MAC address (auto-generated if empty)
        - volume: Volume level 0-100 (default: 75)
        - autostart: Start on boot (default: False)
    """

    provider: Annotated[
        Literal["squeezelite"],
        Field(
            default="squeezelite",
            description="Provider type identifier",
        ),
    ]

    server_ip: Annotated[
        str,
        Field(
            default="",
            description="Logitech Media Server IP address (empty for auto-discovery)",
        ),
    ] = ""

    mac_address: Annotated[
        str,
        Field(
            default="",
            description="MAC address for LMS identification (auto-generated if empty)",
        ),
    ] = ""

    @field_validator("mac_address")
    @classmethod
    def validate_mac_address(cls, v: str) -> str:
        """Validate MAC address format if provided."""
        if v and not MAC_ADDRESS_PATTERN.match(v):
            raise ValueError(f"Invalid MAC address format: {v!r}. Expected format: XX:XX:XX:XX:XX:XX")
        return v.lower() if v else v

    @field_validator("server_ip")
    @classmethod
    def validate_server_ip(cls, v: str) -> str:
        """Validate server IP format if provided."""
        if not v:
            return v

        # Allow hostname or IP address format
        # Basic validation - not exhaustive but catches obvious errors
        if v.startswith(("http://", "https://", "ws://", "wss://")):
            raise ValueError(f"server_ip should be an IP address or hostname, not a URL: {v!r}")
        return v


# =============================================================================
# SENDSPIN SCHEMA
# =============================================================================


class SendspinPlayerConfig(BasePlayerConfig):
    """
    Configuration schema for Sendspin players.

    Sendspin is an open protocol for synchronized multi-room audio,
    developed by the Music Assistant team.

    Required fields:
        - name: Player display name

    Optional fields:
        - device: PortAudio device (NOT ALSA format like hw:X,Y)
        - server_url: WebSocket URL (ws:// or wss://) - empty for mDNS discovery
        - client_id: Unique client identifier (auto-generated if empty)
        - delay_ms: Latency compensation in milliseconds
        - log_level: Logging verbosity (TRACE, DEBUG, INFO, WARN, ERROR)
    """

    provider: Annotated[
        Literal["sendspin"],
        Field(
            default="sendspin",
            description="Provider type identifier",
        ),
    ]

    server_url: Annotated[
        str,
        Field(
            default="",
            description="Sendspin server WebSocket URL (ws:// or wss://)",
        ),
    ] = ""

    client_id: Annotated[
        str,
        Field(
            default="",
            description="Unique client identifier (auto-generated if empty)",
        ),
    ] = ""

    delay_ms: Annotated[
        int,
        Field(
            default=0,
            description="Latency compensation in milliseconds",
        ),
    ] = 0

    log_level: Annotated[
        str,
        Field(
            default="INFO",
            description="Log level (TRACE, DEBUG, INFO, WARN, ERROR)",
        ),
    ] = "INFO"

    @field_validator("server_url")
    @classmethod
    def validate_server_url(cls, v: str) -> str:
        """Validate WebSocket URL format if provided."""
        if v and not WEBSOCKET_URL_PATTERN.match(v):
            raise ValueError(f"Server URL must start with ws:// or wss://, got: {v!r}")
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is one of the accepted values."""
        v_upper = v.upper()
        if v_upper not in VALID_LOG_LEVELS:
            valid = ", ".join(sorted(VALID_LOG_LEVELS))
            raise ValueError(f"Invalid log level: {v!r}. Must be one of: {valid}")
        return v_upper

    @field_validator("device")
    @classmethod
    def validate_device_not_alsa(cls, v: str) -> str:
        """Warn if ALSA-style device is used (not compatible with PortAudio)."""
        if v.startswith(("hw:", "plughw:")):
            raise ValueError(
                f"ALSA device format {v!r} is not compatible with Sendspin. "
                "Use PortAudio device index (e.g., '0', '1') or device name prefix. "
                "Run 'sendspin --list-audio-devices' to see available devices."
            )
        return v


# =============================================================================
# DISCRIMINATED UNION
# =============================================================================

# Union type for any valid player configuration
PlayerConfigSchema = SqueezelitePlayerConfig | SendspinPlayerConfig


# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================


class ValidationError(Exception):
    """
    Custom exception for player configuration validation errors.

    Provides detailed error messages including field paths and
    multiple errors when applicable.
    """

    def __init__(self, message: str, errors: list[dict[str, Any]] | None = None):
        """
        Initialize validation error.

        Args:
            message: Human-readable error summary.
            errors: List of detailed error dictionaries from Pydantic.
        """
        super().__init__(message)
        self.message = message
        self.errors = errors or []

    def __str__(self) -> str:
        """Return formatted error message."""
        if not self.errors:
            return self.message

        lines = [self.message]
        for err in self.errors:
            loc = " -> ".join(str(x) for x in err.get("loc", []))
            msg = err.get("msg", "Unknown error")
            lines.append(f"  - {loc}: {msg}")
        return "\n".join(lines)


def validate_player_config(
    config: dict[str, Any],
    name: str | None = None,
) -> tuple[bool, str, dict[str, Any] | None]:
    """
    Validate a single player configuration.

    Automatically detects provider type and applies appropriate schema.

    Args:
        config: Player configuration dictionary to validate.
        name: Optional player name (used if not in config).

    Returns:
        Tuple of (is_valid, error_message, validated_config).
        If valid, error_message is empty and validated_config contains
        the normalized configuration with defaults applied.
        If invalid, validated_config is None.

    Example:
        >>> valid, error, config = validate_player_config({
        ...     "name": "Kitchen",
        ...     "device": "hw:1,0",
        ...     "provider": "squeezelite"
        ... })
        >>> if not valid:
        ...     print(f"Validation failed: {error}")
    """
    # Ensure name is in config
    if name and "name" not in config:
        config = {**config, "name": name}

    # Determine provider type
    provider = config.get("provider", "squeezelite")

    try:
        validated: BasePlayerConfig
        if provider == "sendspin":
            validated = SendspinPlayerConfig.model_validate(config)
        elif provider == "squeezelite":
            validated = SqueezelitePlayerConfig.model_validate(config)
        else:
            return (
                False,
                f"Unknown provider type: {provider!r}. Supported providers: squeezelite, sendspin",
                None,
            )

        return True, "", validated.model_dump()

    except Exception as e:
        # Extract error details from Pydantic ValidationError
        if hasattr(e, "errors"):
            errors = e.errors()
            if errors:
                # Format the first error for the simple message
                first_error = errors[0]
                loc = " -> ".join(str(x) for x in first_error.get("loc", []))
                msg = first_error.get("msg", str(e))
                error_msg = f"{loc}: {msg}" if loc else msg

                # Include additional errors if present
                if len(errors) > 1:
                    error_msg += f" (and {len(errors) - 1} more error(s))"

                return False, error_msg, None

        return False, str(e), None


def validate_players_file(
    players: dict[str, dict[str, Any]],
) -> tuple[bool, list[str], dict[str, dict[str, Any]]]:
    """
    Validate an entire players configuration dictionary.

    Validates each player individually and collects all errors.

    Args:
        players: Dictionary mapping player names to configurations.

    Returns:
        Tuple of (all_valid, error_messages, validated_players).
        If all valid, error_messages is empty and validated_players
        contains normalized configurations.
        If any invalid, validated_players contains only the valid ones.

    Example:
        >>> players = {
        ...     "Kitchen": {"device": "hw:1,0", "provider": "squeezelite"},
        ...     "Bedroom": {"device": "0", "provider": "sendspin"},
        ... }
        >>> valid, errors, validated = validate_players_file(players)
    """
    errors: list[str] = []
    validated: dict[str, dict[str, Any]] = {}

    if not isinstance(players, dict):
        return False, [f"Expected dictionary, got {type(players).__name__}"], {}

    for name, config in players.items():
        if not isinstance(config, dict):
            errors.append(f"Player '{name}': Expected dictionary, got {type(config).__name__}")
            continue

        is_valid, error_msg, validated_config = validate_player_config(config, name)

        if is_valid and validated_config:
            validated[name] = validated_config
        else:
            errors.append(f"Player '{name}': {error_msg}")

    return len(errors) == 0, errors, validated


def get_schema_for_provider(provider: str) -> type[BasePlayerConfig]:
    """
    Get the appropriate schema class for a provider type.

    Args:
        provider: Provider type string ('squeezelite' or 'sendspin').

    Returns:
        The corresponding Pydantic model class.

    Raises:
        ValueError: If provider type is unknown.
    """
    schemas = {
        "squeezelite": SqueezelitePlayerConfig,
        "sendspin": SendspinPlayerConfig,
    }

    if provider not in schemas:
        valid = ", ".join(sorted(schemas.keys()))
        raise ValueError(f"Unknown provider: {provider!r}. Valid providers: {valid}")

    return schemas[provider]  # type: ignore[return-value]


def get_default_config(provider: str) -> dict[str, Any]:
    """
    Get default configuration for a provider type.

    Args:
        provider: Provider type string ('squeezelite' or 'sendspin').

    Returns:
        Dictionary of default configuration values.

    Raises:
        ValueError: If provider type is unknown.
    """
    schema_class = get_schema_for_provider(provider)

    # Create instance with only required fields to get defaults
    # We use a placeholder name that will be replaced
    if provider == "squeezelite":
        instance = schema_class(name="__default__", device="default")  # type: ignore[call-arg]
    else:
        instance = schema_class(name="__default__")  # type: ignore[call-arg]

    config = instance.model_dump()
    del config["name"]  # Remove placeholder name
    return config
