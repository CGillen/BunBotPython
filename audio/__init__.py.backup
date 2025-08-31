"""
Audio Processing System for BunBot

Provides advanced audio processing capabilities including volume normalization,
real-time effects, multi-stream mixing, and enhanced audio quality management.
Built on the core infrastructure for seamless integration.

Key Components:
- Audio processing pipeline with real-time controls
- Volume normalization and dynamic range management
- Audio effects chain (EQ, crossfading, ducking)
- Multi-stream mixing with priority management
- Performance monitoring and quality adaptation

Architecture:
- Built on core ServiceRegistry, StateManager, EventBus, and ConfigurationManager
- Real-time audio processing with minimal latency
- Per-guild audio configuration and state management
- Integration with Discord.py voice capabilities
- Event-driven audio control and monitoring
"""

from .interfaces import (
    AudioConfig, AudioStream, ProcessedAudioSource,
    IAudioProcessor, IVolumeManager, IEffectsChain, IAudioMixer,
    AudioQuality, EffectType, MixingMode
)
from .audio_processor import AudioProcessor
from .volume_manager import VolumeManager
from .effects_chain import EffectsChain
from .mixer import AudioMixer
from .stream_manager import StreamManager

__all__ = [
    # Configuration and Data Classes
    'AudioConfig',
    'AudioStream', 
    'ProcessedAudioSource',
    'AudioQuality',
    'EffectType',
    'MixingMode',
    
    # Interfaces
    'IAudioProcessor',
    'IVolumeManager', 
    'IEffectsChain',
    'IAudioMixer',
    
    # Implementations
    'AudioProcessor',
    'VolumeManager',
    'EffectsChain',
    'AudioMixer',
    'StreamManager'
]
