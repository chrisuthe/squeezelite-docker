"""
Environment variable validation for application startup.

Validates environment variables to provide better error messages when users
misconfigure their environment. Uses defaults and logs warnings instead of
crashing, ensuring the application remains robust.
"""

import logging
import os
import re
from typing import Any

logger = logging.getLogger(__name__)

# =============================================================================
# VALIDATION HELPERS
# =============================================================================


def validate_integer(
    env_var: str, default: str, min_value: int | None = None, max_value: int | None = None
) -> tuple[bool, int, str]:
    """
    Validate that an environment variable is a valid integer.

    Args:
        env_var: Name of the environment variable.
        default: Default value as string.
        min_value: Optional minimum allowed value.
        max_value: Optional maximum allowed value.

    Returns:
        Tuple of (is_valid, parsed_value, warning_message).
        is_valid is False if parsing failed, True if valid or using default.
        parsed_value is the integer value (either parsed or default).
        warning_message is empty string if valid, or contains warning details.
    """
    value_str = os.environ.get(env_var, default)
    default_int = int(default)

    # If using default, no validation needed
    if value_str == default:
        return True, default_int, ""

    # Try to parse as integer
    try:
        value = int(value_str)
    except ValueError:
        warning = f"Invalid value for {env_var}='{value_str}': must be an integer. Using default value: {default}"
        return False, default_int, warning

    # Check range if specified
    if min_value is not None and value < min_value:
        warning = f"Value for {env_var}={value} is below minimum {min_value}. Using default value: {default}"
        return False, default_int, warning

    if max_value is not None and value > max_value:
        warning = f"Value for {env_var}={value} exceeds maximum {max_value}. Using default value: {default}"
        return False, default_int, warning

    return True, value, ""


def validate_buffer_params(env_var: str, default: str) -> tuple[bool, str, str]:
    """
    Validate buffer parameters in format "stream:output".

    Args:
        env_var: Name of the environment variable.
        default: Default value as string.

    Returns:
        Tuple of (is_valid, value, warning_message).
    """
    value = os.environ.get(env_var, default)

    # If using default, no validation needed
    if value == default:
        return True, value, ""

    # Validate format: should be "number:number"
    pattern = r"^\d+:\d+$"
    if not re.match(pattern, value):
        warning = (
            f"Invalid value for {env_var}='{value}': must be in format 'stream:output' "
            f"(e.g., '500:2000'). Using default value: {default}"
        )
        return False, default, warning

    # Validate individual numbers are reasonable (1-100000 KB)
    try:
        stream, output = value.split(":")
        stream_kb = int(stream)
        output_kb = int(output)

        if stream_kb < 1 or stream_kb > 100000:
            warning = (
                f"Stream buffer size in {env_var}={stream_kb} KB is out of range (1-100000). "
                f"Using default value: {default}"
            )
            return False, default, warning

        if output_kb < 1 or output_kb > 100000:
            warning = (
                f"Output buffer size in {env_var}={output_kb} KB is out of range (1-100000). "
                f"Using default value: {default}"
            )
            return False, default, warning

    except ValueError:
        warning = f"Invalid numeric values in {env_var}='{value}'. Using default value: {default}"
        return False, default, warning

    return True, value, ""


def validate_boolean(env_var: str, default: str = "0") -> tuple[bool, bool, str]:
    """
    Validate boolean environment variable (expects "0" or "1").

    Args:
        env_var: Name of the environment variable.
        default: Default value as string ("0" or "1").

    Returns:
        Tuple of (is_valid, parsed_value, warning_message).
    """
    value_str = os.environ.get(env_var, default)
    default_bool = default == "1"

    # If using default, no validation needed
    if value_str == default:
        return True, default_bool, ""

    # Accept 0/1, true/false, yes/no
    value_lower = value_str.lower().strip()
    if value_lower in ("1", "true", "yes", "on"):
        return True, True, ""
    elif value_lower in ("0", "false", "no", "off"):
        return True, False, ""
    else:
        warning = (
            f"Invalid boolean value for {env_var}='{value_str}': "
            f"expected 0/1, true/false, yes/no. Using default value: {default}"
        )
        return False, default_bool, warning


def validate_enum(
    env_var: str, default: str, allowed_values: list[str], case_sensitive: bool = False
) -> tuple[bool, str, str]:
    """
    Validate that environment variable is one of allowed values.

    Args:
        env_var: Name of the environment variable.
        default: Default value.
        allowed_values: List of allowed values.
        case_sensitive: Whether comparison should be case-sensitive.

    Returns:
        Tuple of (is_valid, value, warning_message).
    """
    value = os.environ.get(env_var, default)

    # If using default, no validation needed
    if value == default:
        return True, value, ""

    # Prepare comparison values
    if case_sensitive:
        compare_value = value
        compare_allowed = allowed_values
    else:
        compare_value = value.lower()
        compare_allowed = [v.lower() for v in allowed_values]

    if compare_value not in compare_allowed:
        warning = (
            f"Invalid value for {env_var}='{value}': "
            f"must be one of {', '.join(allowed_values)}. Using default value: {default}"
        )
        return False, default, warning

    return True, value, ""


# =============================================================================
# VALIDATION FUNCTION
# =============================================================================


def validate_environment_variables() -> dict[str, Any]:
    """
    Validate all environment variables used by the application.

    Checks numeric values, formats, and logs warnings for invalid configurations.
    Always returns valid values (using defaults when necessary) to prevent crashes.

    Returns:
        Dictionary with validation results:
        - 'valid': bool - True if all validations passed
        - 'warnings': list[str] - List of warning messages for invalid values
        - 'variables': dict - Dictionary of validated variable values
    """
    warnings: list[str] = []
    validated_vars: dict[str, Any] = {}

    logger.info("Validating environment variables...")

    # -------------------------------------------------------------------------
    # Squeezelite Configuration Variables
    # -------------------------------------------------------------------------

    # SQUEEZELITE_BUFFER_TIME: ALSA buffer time in milliseconds (20-200ms typical)
    is_valid, int_val, warning = validate_integer("SQUEEZELITE_BUFFER_TIME", "80", min_value=1, max_value=1000)
    if warning:
        warnings.append(warning)
        logger.warning(warning)
    validated_vars["SQUEEZELITE_BUFFER_TIME"] = int_val

    # SQUEEZELITE_BUFFER_PARAMS: Stream and output buffer sizes "stream:output" in KB
    is_valid, str_val, warning = validate_buffer_params("SQUEEZELITE_BUFFER_PARAMS", "500:2000")
    if warning:
        warnings.append(warning)
        logger.warning(warning)
    validated_vars["SQUEEZELITE_BUFFER_PARAMS"] = str_val

    # SQUEEZELITE_CLOSE_TIMEOUT: Output device close timeout in seconds (0+)
    is_valid, int_val, warning = validate_integer("SQUEEZELITE_CLOSE_TIMEOUT", "5", min_value=0, max_value=3600)
    if warning:
        warnings.append(warning)
        logger.warning(warning)
    validated_vars["SQUEEZELITE_CLOSE_TIMEOUT"] = int_val

    # SQUEEZELITE_SAMPLE_RATE: Sample rate for null device (8000-192000 typical)
    is_valid, int_val, warning = validate_integer("SQUEEZELITE_SAMPLE_RATE", "44100", min_value=8000, max_value=384000)
    if warning:
        warnings.append(warning)
        logger.warning(warning)
    validated_vars["SQUEEZELITE_SAMPLE_RATE"] = int_val

    # SQUEEZELITE_WINDOWS_MODE: Windows compatibility mode (0 or 1)
    is_valid, bool_val, warning = validate_boolean("SQUEEZELITE_WINDOWS_MODE", "0")
    if warning:
        warnings.append(warning)
        logger.warning(warning)
    validated_vars["SQUEEZELITE_WINDOWS_MODE"] = bool_val

    # -------------------------------------------------------------------------
    # Application Configuration Variables
    # -------------------------------------------------------------------------

    # SECRET_KEY: Flask secret key (optional, generated if not set)
    secret_key = os.environ.get("SECRET_KEY", "")
    if not secret_key:
        logger.info(
            "SECRET_KEY not set - application will generate a random key. "
            "Set SECRET_KEY environment variable for production use."
        )
    else:
        # Warn if secret key is too short (less than 32 characters)
        if len(secret_key) < 32:
            warning = (
                "SECRET_KEY is set but appears short (less than 32 characters). "
                "Consider using a longer key for better security."
            )
            warnings.append(warning)
            logger.warning(warning)
    validated_vars["SECRET_KEY"] = secret_key

    # AUDIO_BACKEND: Audio backend selection (alsa, pulse, pipewire)
    is_valid, str_val, warning = validate_enum(
        "AUDIO_BACKEND",
        "alsa",
        ["alsa", "pulse", "pulseaudio", "pipewire"],
        case_sensitive=False,
    )
    if warning:
        warnings.append(warning)
        logger.warning(warning)
    validated_vars["AUDIO_BACKEND"] = str_val

    # CONFIG_PATH: Configuration directory path (informational only)
    config_path = os.environ.get("CONFIG_PATH", "/app/config")
    validated_vars["CONFIG_PATH"] = config_path

    # LOG_PATH: Log directory path (informational only)
    log_path = os.environ.get("LOG_PATH", "/app/logs")
    validated_vars["LOG_PATH"] = log_path

    # SUPERVISOR_TOKEN: Home Assistant supervisor token (informational only)
    supervisor_token = os.environ.get("SUPERVISOR_TOKEN", "")
    if supervisor_token:
        logger.info("SUPERVISOR_TOKEN detected - running in Home Assistant OS mode")
    validated_vars["SUPERVISOR_TOKEN"] = supervisor_token

    # SENDSPIN_CONTAINER: Sendspin container mode flag (0 or 1)
    is_valid, bool_val, warning = validate_boolean("SENDSPIN_CONTAINER", "0")
    if warning:
        warnings.append(warning)
        logger.warning(warning)
    validated_vars["SENDSPIN_CONTAINER"] = bool_val

    # -------------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------------

    all_valid = len(warnings) == 0

    if all_valid:
        logger.info("Environment variable validation: PASSED (all variables valid)")
    else:
        logger.warning(
            f"Environment variable validation: COMPLETED with {len(warnings)} warning(s). "
            "Application will use default values where needed."
        )

    return {"valid": all_valid, "warnings": warnings, "variables": validated_vars}
