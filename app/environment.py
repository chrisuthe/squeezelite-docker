"""
Environment detection for multi-platform support.

Detects whether the application is running in:
- Standalone Docker container (default)
- Home Assistant OS add-on (HAOS)

Provides appropriate paths and audio backend configuration for each environment.
"""

import logging
import os

logger = logging.getLogger(__name__)

# Environment constants
ENV_STANDALONE = "standalone"
ENV_HASSIO = "hassio"

# HAOS detection markers
HASSIO_OPTIONS_FILE = "/data/options.json"
HASSIO_SUPERVISOR_TOKEN_ENV = "SUPERVISOR_TOKEN"


def detect_environment() -> str:
    """
    Detect the current runtime environment.

    Returns:
        str: Either 'hassio' or 'standalone'
    """
    # Check for HAOS-specific markers
    if os.path.exists(HASSIO_OPTIONS_FILE):
        logger.info("Detected Home Assistant OS environment (options.json present)")
        return ENV_HASSIO

    if os.environ.get(HASSIO_SUPERVISOR_TOKEN_ENV):
        logger.info("Detected Home Assistant OS environment (SUPERVISOR_TOKEN present)")
        return ENV_HASSIO

    logger.info("Detected standalone Docker environment")
    return ENV_STANDALONE


def is_hassio() -> bool:
    """
    Check if running inside Home Assistant OS.

    Returns:
        bool: True if running in HAOS, False otherwise
    """
    return detect_environment() == ENV_HASSIO


def get_config_path() -> str:
    """
    Get the appropriate configuration directory path.

    Returns:
        str: Path to configuration directory
            - HAOS: /data
            - Standalone: /app/config (or CONFIG_PATH env var)
    """
    if is_hassio():
        return "/data"
    return os.environ.get("CONFIG_PATH", "/app/config")


def get_log_path() -> str:
    """
    Get the appropriate log directory path.

    Returns:
        str: Path to log directory
            - HAOS: /data/logs (persisted in add-on data)
            - Standalone: /app/logs (or LOG_PATH env var)
    """
    if is_hassio():
        return "/data/logs"
    return os.environ.get("LOG_PATH", "/app/logs")


def get_audio_backend() -> str:
    """
    Get the appropriate audio backend for the environment.

    Returns:
        str: Audio backend identifier
            - HAOS: 'pulse' (PulseAudio via hassio_audio)
            - Standalone: 'alsa' (direct ALSA, or AUDIO_BACKEND env var)
    """
    # Allow explicit override via environment variable
    override = os.environ.get("AUDIO_BACKEND")
    if override:
        logger.info(f"Audio backend override: {override}")
        return override.lower()

    if is_hassio():
        logger.info("Using PulseAudio backend for HAOS")
        return "pulse"

    logger.info("Using ALSA backend for standalone Docker")
    return "alsa"


def get_player_backend_for_snapcast() -> str:
    """
    Get the appropriate --player argument for snapclient.

    Snapcast supports: alsa, pulse, pipewire, file

    Returns:
        str: Player backend for snapclient --player argument
    """
    backend = get_audio_backend()
    if backend == "pulse":
        return "pulse"
    return "alsa"


def get_squeezelite_output_device(device: str) -> str:
    """
    Transform device identifier for Squeezelite based on environment.

    In HAOS, we need to use PulseAudio device names instead of ALSA hw:X,Y.

    Args:
        device: Original device identifier (e.g., 'hw:0,0' or 'pulse')

    Returns:
        str: Appropriate device identifier for the environment
    """
    # In HAOS, if device looks like ALSA format, use 'pulse' instead
    # The actual device routing is handled by PulseAudio
    if is_hassio() and (device.startswith("hw:") or device.startswith("plughw:")):
        logger.info(f"Converting ALSA device {device} to 'pulse' for HAOS")
        return "pulse"
    return device


def get_volume_control_method() -> str:
    """
    Get the appropriate volume control method.

    Returns:
        str: Volume control method
            - HAOS: 'pactl' (PulseAudio control)
            - Standalone: 'amixer' (ALSA mixer)
    """
    if is_hassio():
        return "pactl"
    return "amixer"


# Cache the environment detection result
_cached_environment: str | None = None


def get_environment() -> str:
    """
    Get the cached environment detection result.

    Returns:
        str: Current environment ('hassio' or 'standalone')
    """
    global _cached_environment
    if _cached_environment is None:
        _cached_environment = detect_environment()
    return _cached_environment


# Log environment on module import
if __name__ != "__main__":
    # Only log when imported, not when run directly
    pass
