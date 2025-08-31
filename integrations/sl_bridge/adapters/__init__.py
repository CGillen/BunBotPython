"""
Adapter Layer for SL Bridge

Bridges SL API requests to Discord service calls
"""

from .stream_adapter import StreamAdapter
from .audio_adapter import AudioAdapter

__all__ = [
    "StreamAdapter",
    "AudioAdapter"
]
