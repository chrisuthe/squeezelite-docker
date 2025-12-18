"""
Player provider implementations for multi-room audio.

This package contains the provider abstraction layer that allows
different audio player backends (Squeezelite, Sendspin, Snapcast)
to be used interchangeably.
"""

from .base import PlayerProvider
from .registry import ProviderRegistry
from .sendspin import SendspinProvider
from .squeezelite import SqueezeliteProvider

__all__ = [
    "PlayerProvider",
    "ProviderRegistry",
    "SqueezeliteProvider",
    "SendspinProvider",
]
