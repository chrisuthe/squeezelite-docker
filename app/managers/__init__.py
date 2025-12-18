"""
Manager classes for the multi-room audio player system.

This package contains focused manager classes that handle specific
responsibilities, extracted from the original monolithic SqueezeliteManager.
"""

from .audio_manager import AudioManager
from .config_manager import ConfigManager
from .process_manager import ProcessManager

__all__ = ["ConfigManager", "AudioManager", "ProcessManager"]
