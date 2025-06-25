"""
Abstract Interfaces and Data Structures for BunBot Audio Processing
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union, AsyncGenerator, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone
import asyncio

logger = logging.getLogger('discord.audio.interfaces')

class AudioQuality(Enum):
    """Audio quality levels for processing"""
    LOW = "low"           # 22kHz, 8-bit, minimal processing
    MEDIUM = "medium"     # 44kHz, 16-bit, standard processing
    HIGH = "high"         # 48kHz, 16-bit, full processing
    ULTRA = "ultra"       # 48kHz, 24-bit, maximum quality

class EffectType(Enum):
    """Types of audio effects"""
    EQUALIZER = "equalizer"
    COMPRESSOR = "compressor"
    LIMITER = "limiter"
    REVERB = "reverb"
    CHORUS = "chorus"
    DISTORTION = "distortion"
    NOISE_GATE = "noise_gate"
    DUCKING = "ducking"
    CROSSFADE = "crossfade"

class MixingMode(Enum):
    """Audio mixing modes"""
    REPLACE = "replace"       # New stream replaces current
    OVERLAY = "overlay"       # New stream mixes with current
    PRIORITY = "priority"     # Priority-based mixing
    CROSSFADE = "crossfade"   # Smooth transition between streams

class AudioFormat(Enum):
    """Supported audio formats"""
    PCM_16 = "pcm_s16le"
    PCM_24 = "pcm_s24le"
    PCM_32 = "pcm_s32le"
    FLOAT_32 = "pcm_f32le"

@dataclass
class AudioConfig:
    """Audio configuration for a guild"""
    # Volume settings
    master_volume: float = 0.8              # 0.0 to 1.0
    normalization_enabled: bool = True
    normalization_target_lufs: float = -23.0  # EBU R128 standard
    auto_gain_control: bool = True
    dynamic_range_compression: float = 0.0   # 0.0 to 1.0
    
    # EQ settings
    eq_enabled: bool = False
    eq_bass: float = 0.0      # -12 to +12 dB
    eq_mid: float = 0.0       # -12 to +12 dB
    eq_treble: float = 0.0    # -12 to +12 dB
    eq_preset: Optional[str] = None
    
    # Effects settings
    effects_enabled: bool = True
    crossfade_duration: float = 3.0          # seconds
    ducking_enabled: bool = False
    ducking_level: float = 0.3               # 0.0 to 1.0
    ducking_sensitivity: float = 0.5         # 0.0 to 1.0
    
    # Quality settings
    quality: AudioQuality = AudioQuality.HIGH
    sample_rate: int = 48000
    channels: int = 2
    bit_depth: int = 16
    buffer_size: int = 2048
    
    # Processing settings
    real_time_processing: bool = True
    low_latency_mode: bool = False
    cpu_limit_percent: float = 50.0          # Max CPU usage for audio processing
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'master_volume': self.master_volume,
            'normalization_enabled': self.normalization_enabled,
            'normalization_target_lufs': self.normalization_target_lufs,
            'auto_gain_control': self.auto_gain_control,
            'dynamic_range_compression': self.dynamic_range_compression,
            'eq_enabled': self.eq_enabled,
            'eq_bass': self.eq_bass,
            'eq_mid': self.eq_mid,
            'eq_treble': self.eq_treble,
            'eq_preset': self.eq_preset,
            'effects_enabled': self.effects_enabled,
            'crossfade_duration': self.crossfade_duration,
            'ducking_enabled': self.ducking_enabled,
            'ducking_level': self.ducking_level,
            'ducking_sensitivity': self.ducking_sensitivity,
            'quality': self.quality.value,
            'sample_rate': self.sample_rate,
            'channels': self.channels,
            'bit_depth': self.bit_depth,
            'buffer_size': self.buffer_size,
            'real_time_processing': self.real_time_processing,
            'low_latency_mode': self.low_latency_mode,
            'cpu_limit_percent': self.cpu_limit_percent
        }

@dataclass
class AudioStream:
    """Represents an audio stream with metadata"""
    stream_id: str
    guild_id: int
    url: str
    priority: int = 1                        # 1-10, higher = more important
    volume: float = 1.0                      # Stream-specific volume multiplier
    fade_in_duration: float = 0.0            # Fade in time in seconds
    fade_out_duration: float = 0.0           # Fade out time in seconds
    loop: bool = False                       # Whether to loop the stream
    start_time: Optional[datetime] = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: Optional[datetime] = None      # When to stop the stream
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_active(self) -> bool:
        """Check if stream is currently active"""
        now = datetime.now(timezone.utc)
        if self.end_time and now > self.end_time:
            return False
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'stream_id': self.stream_id,
            'guild_id': self.guild_id,
            'url': self.url,
            'priority': self.priority,
            'volume': self.volume,
            'fade_in_duration': self.fade_in_duration,
            'fade_out_duration': self.fade_out_duration,
            'loop': self.loop,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'metadata': self.metadata
        }

@dataclass
class AudioMetrics:
    """Audio processing performance metrics"""
    guild_id: int
    processing_latency_ms: float
    cpu_usage_percent: float
    memory_usage_mb: float
    buffer_underruns: int
    audio_dropouts: int
    sample_rate: int
    bit_depth: int
    channels: int
    quality_score: float                     # 0.0 to 1.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for monitoring"""
        return {
            'guild_id': self.guild_id,
            'processing_latency_ms': self.processing_latency_ms,
            'cpu_usage_percent': self.cpu_usage_percent,
            'memory_usage_mb': self.memory_usage_mb,
            'buffer_underruns': self.buffer_underruns,
            'audio_dropouts': self.audio_dropouts,
            'sample_rate': self.sample_rate,
            'bit_depth': self.bit_depth,
            'channels': self.channels,
            'quality_score': self.quality_score,
            'timestamp': self.timestamp.isoformat()
        }

class ProcessedAudioSource:
    """
    Wrapper for processed audio that can be used with Discord.py
    
    This class bridges the gap between our audio processing pipeline
    and Discord.py's FFmpegPCMAudio requirements.
    """
    
    def __init__(self, audio_data: bytes, sample_rate: int, channels: int, 
                 bit_depth: int, metadata: Optional[Dict[str, Any]] = None):
        self.audio_data = audio_data
        self.sample_rate = sample_rate
        self.channels = channels
        self.bit_depth = bit_depth
        self.metadata = metadata or {}
        self.position = 0
    
    def read(self, frame_size: int = 4096) -> bytes:
        """Read audio data in chunks"""
        if self.position >= len(self.audio_data):
            return b''
        
        chunk = self.audio_data[self.position:self.position + frame_size]
        self.position += len(chunk)
        return chunk
    
    def seek(self, position: int) -> None:
        """Seek to specific position in audio data"""
        self.position = max(0, min(position, len(self.audio_data)))
    
    def remaining_bytes(self) -> int:
        """Get remaining bytes in the stream"""
        return max(0, len(self.audio_data) - self.position)

class IAudioProcessor(ABC):
    """Abstract interface for audio processing"""
    
    @abstractmethod
    async def process_stream(self, guild_id: int, stream: AudioStream, 
                           config: AudioConfig) -> ProcessedAudioSource:
        """Process an audio stream with the given configuration"""
        pass
    
    @abstractmethod
    async def set_config(self, guild_id: int, config: AudioConfig) -> bool:
        """Update audio configuration for a guild"""
        pass
    
    @abstractmethod
    async def get_config(self, guild_id: int) -> Optional[AudioConfig]:
        """Get current audio configuration for a guild"""
        pass
    
    @abstractmethod
    async def get_metrics(self, guild_id: int) -> Optional[AudioMetrics]:
        """Get current audio processing metrics"""
        pass
    
    @abstractmethod
    async def start_processing(self, guild_id: int) -> bool:
        """Start audio processing for a guild"""
        pass
    
    @abstractmethod
    async def stop_processing(self, guild_id: int) -> bool:
        """Stop audio processing for a guild"""
        pass

class IVolumeManager(ABC):
    """Abstract interface for volume management"""
    
    @abstractmethod
    async def set_master_volume(self, guild_id: int, volume: float) -> bool:
        """Set master volume (0.0 to 1.0)"""
        pass
    
    @abstractmethod
    async def get_master_volume(self, guild_id: int) -> float:
        """Get current master volume"""
        pass
    
    @abstractmethod
    async def set_normalization_target(self, guild_id: int, lufs_target: float) -> bool:
        """Set audio normalization target in LUFS"""
        pass
    
    @abstractmethod
    async def enable_auto_gain_control(self, guild_id: int, enabled: bool) -> bool:
        """Enable or disable automatic gain control"""
        pass
    
    @abstractmethod
    async def set_dynamic_range_compression(self, guild_id: int, ratio: float) -> bool:
        """Set dynamic range compression ratio (0.0 to 1.0)"""
        pass
    
    @abstractmethod
    async def get_volume_metrics(self, guild_id: int) -> Dict[str, float]:
        """Get volume-related metrics (RMS, peak, LUFS, etc.)"""
        pass

class IEffectsChain(ABC):
    """Abstract interface for audio effects processing"""
    
    @abstractmethod
    async def add_effect(self, guild_id: int, effect_type: EffectType, 
                        parameters: Dict[str, Any]) -> str:
        """Add an effect to the processing chain"""
        pass
    
    @abstractmethod
    async def remove_effect(self, guild_id: int, effect_id: str) -> bool:
        """Remove an effect from the processing chain"""
        pass
    
    @abstractmethod
    async def update_effect(self, guild_id: int, effect_id: str, 
                           parameters: Dict[str, Any]) -> bool:
        """Update effect parameters"""
        pass
    
    @abstractmethod
    async def set_eq(self, guild_id: int, bass: float, mid: float, treble: float) -> bool:
        """Set 3-band equalizer values (-12 to +12 dB)"""
        pass
    
    @abstractmethod
    async def apply_eq_preset(self, guild_id: int, preset_name: str) -> bool:
        """Apply a predefined EQ preset"""
        pass
    
    @abstractmethod
    async def enable_crossfade(self, guild_id: int, duration: float) -> bool:
        """Enable crossfading with specified duration"""
        pass
    
    @abstractmethod
    async def enable_ducking(self, guild_id: int, level: float, sensitivity: float) -> bool:
        """Enable audio ducking for voice chat"""
        pass
    
    @abstractmethod
    async def get_available_presets(self) -> List[str]:
        """Get list of available EQ presets"""
        pass

class IAudioMixer(ABC):
    """Abstract interface for multi-stream audio mixing"""
    
    @abstractmethod
    async def add_stream(self, guild_id: int, stream: AudioStream, 
                        mixing_mode: MixingMode = MixingMode.REPLACE) -> str:
        """Add a new audio stream to the mix"""
        pass
    
    @abstractmethod
    async def remove_stream(self, guild_id: int, stream_id: str, 
                           fade_out: bool = True) -> bool:
        """Remove a stream from the mix"""
        pass
    
    @abstractmethod
    async def set_stream_volume(self, guild_id: int, stream_id: str, volume: float) -> bool:
        """Set volume for a specific stream"""
        pass
    
    @abstractmethod
    async def crossfade_to_stream(self, guild_id: int, target_stream_id: str, 
                                 duration: float) -> bool:
        """Crossfade from current mix to target stream"""
        pass
    
    @abstractmethod
    async def get_active_streams(self, guild_id: int) -> List[AudioStream]:
        """Get list of currently active streams"""
        pass
    
    @abstractmethod
    async def set_mixing_mode(self, guild_id: int, mode: MixingMode) -> bool:
        """Set the mixing mode for new streams"""
        pass
    
    @abstractmethod
    async def get_mix_metrics(self, guild_id: int) -> Dict[str, Any]:
        """Get mixing performance metrics"""
        pass

class IStreamManager(ABC):
    """Abstract interface for stream connection and buffering"""
    
    @abstractmethod
    def open_stream(self, url: str, buffer_size: int = 8192) -> AsyncGenerator[bytes, None]:
        """Open and buffer an audio stream"""
        pass
    
    @abstractmethod
    async def test_stream(self, url: str, timeout: float = 10.0) -> Dict[str, Any]:
        """Test stream connectivity and get metadata"""
        pass
    
    @abstractmethod
    async def get_stream_info(self, url: str) -> Dict[str, Any]:
        """Get detailed stream information"""
        pass
    
    @abstractmethod
    async def close_stream(self, stream_id: str) -> bool:
        """Close and cleanup a stream"""
        pass

# Audio Processing Callback Types
AudioProcessingCallback = Callable[[bytes, AudioConfig], bytes]
VolumeAnalysisCallback = Callable[[AudioMetrics], None]
EffectProcessingCallback = Callable[[bytes, Dict[str, Any]], bytes]

# Audio Event Types for EventBus integration
AUDIO_EVENTS = {
    'audio_config_changed': 'audio_config_changed',
    'audio_volume_changed': 'audio_volume_changed', 
    'audio_effect_applied': 'audio_effect_applied',
    'audio_effect_removed': 'audio_effect_removed',
    'audio_stream_added': 'audio_stream_added',
    'audio_stream_removed': 'audio_stream_removed',
    'audio_processing_started': 'audio_processing_started',
    'audio_processing_stopped': 'audio_processing_stopped',
    'audio_quality_changed': 'audio_quality_changed',
    'audio_dropout_detected': 'audio_dropout_detected',
    'audio_cpu_overload': 'audio_cpu_overload',
    'audio_normalization_adjusted': 'audio_normalization_adjusted'
}
