"""
Core Audio Processing Engine for BunBot
"""

import logging
import asyncio
import time
import threading
from typing import Dict, Any, Optional, Callable
from datetime import datetime, timezone
import numpy as np

from core import StateManager, EventBus, ConfigurationManager
from audio.interfaces import (
    IAudioProcessor, AudioConfig, AudioStream, AudioMetrics, ProcessedAudioSource,
    AudioQuality, AUDIO_EVENTS
)

logger = logging.getLogger('discord.audio.audio_processor')

class AudioProcessor(IAudioProcessor):
    """
    Core audio processing engine for BunBot.
    
    Handles real-time audio processing including volume control, normalization,
    effects processing, and quality management. Integrates with the existing
    bot infrastructure while providing enhanced audio capabilities.
    """
    
    def __init__(self, state_manager: StateManager, event_bus: EventBus, 
                 config_manager: ConfigurationManager):
        self.state_manager = state_manager
        self.event_bus = event_bus
        self.config_manager = config_manager
        
        # Processing state tracking
        self._processing_active: Dict[int, bool] = {}  # guild_id -> active status
        self._processing_threads: Dict[int, threading.Thread] = {}
        self._audio_configs: Dict[int, AudioConfig] = {}
        self._processing_metrics: Dict[int, AudioMetrics] = {}
        
        # Performance monitoring
        self._performance_monitor_task: Optional[asyncio.Task] = None
        self._cpu_usage_history: Dict[int, list] = {}
        self._quality_adjustment_cooldown: Dict[int, float] = {}
        
        # Audio processing buffers and state
        self._audio_buffers: Dict[int, bytearray] = {}
        self._buffer_locks: Dict[int, threading.Lock] = {}
        
        logger.info("AudioProcessor initialized")
    
    async def process_stream(self, guild_id: int, stream: AudioStream, 
                           config: AudioConfig) -> ProcessedAudioSource:
        """
        Process an audio stream with real-time enhancements.
        
        Args:
            guild_id: Discord guild ID
            stream: Audio stream to process
            config: Audio configuration settings
            
        Returns:
            ProcessedAudioSource compatible with Discord.py
        """
        try:
            start_time = time.time()
            
            # Update configuration
            await self.set_config(guild_id, config)
            
            # Get raw audio data from stream
            audio_data = await self._get_stream_data(stream.url)
            if not audio_data:
                raise ValueError(f"Failed to get audio data from {stream.url}")
            
            # Process audio through the enhancement pipeline
            processed_data = await self._process_audio_data(guild_id, audio_data, config)
            
            # Create processed audio source
            processed_source = ProcessedAudioSource(
                audio_data=processed_data,
                sample_rate=config.sample_rate,
                channels=config.channels,
                bit_depth=config.bit_depth,
                metadata={
                    'stream_id': stream.stream_id,
                    'processing_time_ms': (time.time() - start_time) * 1000,
                    'quality': config.quality.value,
                    'enhanced': True
                }
            )
            
            # Update metrics
            await self._update_processing_metrics(guild_id, start_time, len(processed_data))
            
            # Emit processing event
            await self.event_bus.emit_async(AUDIO_EVENTS['audio_processing_started'],
                                          guild_id=guild_id,
                                          stream_id=stream.stream_id,
                                          quality=config.quality.value)
            
            logger.info(f"[{guild_id}]: Processed audio stream {stream.stream_id} "
                       f"({len(processed_data)} bytes, {config.quality.value} quality)")
            
            return processed_source
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to process audio stream: {e}")
            # Fallback to basic processing
            return await self._fallback_processing(guild_id, stream, config)
    
    async def set_config(self, guild_id: int, config: AudioConfig) -> bool:
        """
        Update audio configuration for a guild.
        
        Args:
            guild_id: Discord guild ID
            config: New audio configuration
            
        Returns:
            True if configuration was updated successfully
        """
        try:
            # Validate configuration
            if not self._validate_config(config):
                logger.warning(f"[{guild_id}]: Invalid audio configuration provided")
                return False
            
            # Store previous config for comparison
            previous_config = self._audio_configs.get(guild_id)
            
            # Update configuration
            self._audio_configs[guild_id] = config
            
            # Update guild state
            guild_state = self.state_manager.get_guild_state(guild_id, create_if_missing=True)
            if guild_state and hasattr(guild_state, 'audio_config'):
                guild_state.audio_config = config
            
            # Check if processing needs to be restarted
            if previous_config and self._needs_processing_restart(previous_config, config):
                if self._processing_active.get(guild_id, False):
                    await self.stop_processing(guild_id)
                    await self.start_processing(guild_id)
            
            # Emit configuration change event
            await self.event_bus.emit_async(AUDIO_EVENTS['audio_config_changed'],
                                          guild_id=guild_id,
                                          config=config.to_dict())
            
            logger.info(f"[{guild_id}]: Updated audio configuration "
                       f"(quality: {config.quality.value}, volume: {config.master_volume})")
            
            return True
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to set audio configuration: {e}")
            return False
    
    async def get_config(self, guild_id: int) -> Optional[AudioConfig]:
        """Get current audio configuration for a guild"""
        # Create default configuration if none exists
        if guild_id not in self._audio_configs:
            default_config = AudioConfig()
            self._audio_configs[guild_id] = default_config
            
            # Also update guild state
            guild_state = self.state_manager.get_guild_state(guild_id, create_if_missing=True)
            if guild_state and hasattr(guild_state, 'audio_config'):
                guild_state.audio_config = default_config
            
            logger.info(f"[{guild_id}]: Created default audio configuration")
        
        return self._audio_configs.get(guild_id)
    
    async def get_metrics(self, guild_id: int) -> Optional[AudioMetrics]:
        """Get current audio processing metrics"""
        return self._processing_metrics.get(guild_id)
    
    async def start_processing(self, guild_id: int) -> bool:
        """
        Start audio processing for a guild.
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            True if processing was started successfully
        """
        try:
            if self._processing_active.get(guild_id, False):
                logger.warning(f"[{guild_id}]: Audio processing already active")
                return True
            
            # Initialize processing state
            self._processing_active[guild_id] = True
            self._audio_buffers[guild_id] = bytearray()
            self._buffer_locks[guild_id] = threading.Lock()
            self._cpu_usage_history[guild_id] = []
            
            # Get or create default configuration
            if guild_id not in self._audio_configs:
                self._audio_configs[guild_id] = AudioConfig()
            
            # Start performance monitoring if not already running
            if not self._performance_monitor_task or self._performance_monitor_task.done():
                self._performance_monitor_task = asyncio.create_task(self._monitor_performance())
            
            # Emit processing started event
            await self.event_bus.emit_async(AUDIO_EVENTS['audio_processing_started'],
                                          guild_id=guild_id)
            
            logger.info(f"[{guild_id}]: Started audio processing")
            return True
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to start audio processing: {e}")
            self._processing_active[guild_id] = False
            return False
    
    async def stop_processing(self, guild_id: int) -> bool:
        """
        Stop audio processing for a guild.
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            True if processing was stopped successfully
        """
        try:
            if not self._processing_active.get(guild_id, False):
                logger.debug(f"[{guild_id}]: Audio processing not active")
                return True
            
            # Stop processing
            self._processing_active[guild_id] = False
            
            # Clean up processing thread if exists
            if guild_id in self._processing_threads:
                thread = self._processing_threads[guild_id]
                if thread.is_alive():
                    # Thread should check _processing_active and exit
                    thread.join(timeout=2.0)
                del self._processing_threads[guild_id]
            
            # Clean up buffers and locks
            if guild_id in self._audio_buffers:
                del self._audio_buffers[guild_id]
            if guild_id in self._buffer_locks:
                del self._buffer_locks[guild_id]
            if guild_id in self._cpu_usage_history:
                del self._cpu_usage_history[guild_id]
            
            # Emit processing stopped event
            await self.event_bus.emit_async(AUDIO_EVENTS['audio_processing_stopped'],
                                          guild_id=guild_id)
            
            logger.info(f"[{guild_id}]: Stopped audio processing")
            return True
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to stop audio processing: {e}")
            return False
    
    async def _get_stream_data(self, url: str, max_duration: float = 30.0) -> Optional[bytes]:
        """
        Get audio data from stream URL using existing bot infrastructure.
        
        This integrates with the existing stream handling in bot.py to avoid
        breaking the current audio pipeline.
        """
        try:
            logger.debug(f"Getting audio data from stream: {url}")
            
            # Use existing urllib_hack for ICY stream compatibility
            try:
                import urllib_hack
                import urllib.request
                import io
                
                # Create request with existing stream compatibility
                request = urllib.request.Request(url)
                
                # Read initial audio data for processing
                with urllib.request.urlopen(request, timeout=10) as response:
                    # Read a reasonable chunk for processing (not the entire stream)
                    audio_data = response.read(65536)  # 64KB chunk
                    return audio_data if audio_data else b''
                    
            except ImportError:
                # Fallback if urllib_hack isn't available
                import urllib.request
                
                with urllib.request.urlopen(url, timeout=10) as response:
                    audio_data = response.read(65536)  # 64KB chunk
                    return audio_data if audio_data else b''
            
        except Exception as e:
            logger.error(f"Failed to get stream data from {url}: {e}")
            return None
    
    async def _process_audio_data(self, guild_id: int, audio_data: bytes, 
                                config: AudioConfig) -> bytes:
        """
        Process raw audio data through the enhancement pipeline.
        
        Args:
            guild_id: Discord guild ID
            audio_data: Raw audio data to process
            config: Audio configuration
            
        Returns:
            Processed audio data
        """
        try:
            if not audio_data:
                return audio_data
            
            # Convert to numpy array for processing
            audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
            
            # Normalize to [-1, 1] range for processing
            if np.max(np.abs(audio_array)) > 0:
                audio_array = audio_array / 32768.0
            
            # 1. Volume normalization
            if config.normalization_enabled:
                audio_array = self._apply_normalization(audio_array, config)
            
            # 2. Auto gain control
            if config.auto_gain_control:
                audio_array = self._apply_auto_gain_control(audio_array, config)
            
            # 3. Dynamic range compression
            if config.dynamic_range_compression > 0.0:
                audio_array = self._apply_compression(audio_array, config)
            
            # 4. Apply master volume
            audio_array = audio_array * config.master_volume
            
            # 5. EQ processing (if enabled through effects chain)
            if config.eq_enabled:
                audio_array = self._apply_simple_eq(audio_array, config)
            
            # Convert back to int16 and clip to prevent distortion
            audio_array = np.clip(audio_array * 32767.0, -32768, 32767)
            processed_data = audio_array.astype(np.int16).tobytes()
            
            return processed_data
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to process audio data: {e}")
            return audio_data
    
    def _apply_volume(self, audio_data: bytes, volume: float) -> bytes:
        """Apply volume adjustment to audio data"""
        try:
            if not audio_data or volume == 1.0:
                return audio_data
            
            # Convert bytes to numpy array for processing
            # This is a simplified implementation
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            
            # Apply volume scaling with clipping protection
            scaled_audio = np.clip(audio_array * volume, -32768, 32767)
            
            # Convert back to bytes
            return scaled_audio.astype(np.int16).tobytes()
            
        except Exception as e:
            logger.error(f"Failed to apply volume adjustment: {e}")
            return audio_data
    
    async def _fallback_processing(self, guild_id: int, stream: AudioStream, 
                                 config: AudioConfig) -> ProcessedAudioSource:
        """Fallback to basic processing when enhanced processing fails"""
        try:
            logger.warning(f"[{guild_id}]: Using fallback audio processing")
            
            # Create a minimal processed audio source
            fallback_data = b''  # Empty data for fallback
            
            return ProcessedAudioSource(
                audio_data=fallback_data,
                sample_rate=config.sample_rate,
                channels=config.channels,
                bit_depth=config.bit_depth,
                metadata={
                    'stream_id': stream.stream_id,
                    'enhanced': False,
                    'fallback': True
                }
            )
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Fallback processing failed: {e}")
            raise
    
    async def _update_processing_metrics(self, guild_id: int, start_time: float, 
                                       data_size: int) -> None:
        """Update processing performance metrics"""
        try:
            processing_time = (time.time() - start_time) * 1000  # Convert to ms
            config = self._audio_configs.get(guild_id, AudioConfig())
            
            # Create metrics object
            metrics = AudioMetrics(
                guild_id=guild_id,
                processing_latency_ms=processing_time,
                cpu_usage_percent=0.0,  # Would be calculated from actual CPU monitoring
                memory_usage_mb=0.0,    # Would be calculated from actual memory monitoring
                buffer_underruns=0,
                audio_dropouts=0,
                sample_rate=config.sample_rate,
                bit_depth=config.bit_depth,
                channels=config.channels,
                quality_score=self._calculate_quality_score(guild_id, processing_time)
            )
            
            self._processing_metrics[guild_id] = metrics
            
            # Track CPU usage history for quality adaptation
            cpu_history = self._cpu_usage_history.get(guild_id, [])
            cpu_history.append(metrics.cpu_usage_percent)
            if len(cpu_history) > 10:  # Keep last 10 measurements
                cpu_history.pop(0)
            self._cpu_usage_history[guild_id] = cpu_history
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to update processing metrics: {e}")
    
    def _calculate_quality_score(self, guild_id: int, processing_latency_ms: float) -> float:
        """Calculate audio quality score based on performance metrics"""
        try:
            # Base quality score
            quality_score = 1.0
            
            # Reduce score based on processing latency
            if processing_latency_ms > 50:  # 50ms threshold
                quality_score *= max(0.1, 1.0 - (processing_latency_ms - 50) / 100)
            
            # Additional factors would include:
            # - Buffer underruns
            # - Audio dropouts
            # - CPU usage
            # - Memory usage
            
            return max(0.0, min(1.0, quality_score))
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to calculate quality score: {e}")
            return 0.5  # Default middle quality
    
    async def _monitor_performance(self) -> None:
        """Monitor audio processing performance and adapt quality as needed"""
        try:
            while True:
                # Check all active processing guilds
                for guild_id in list(self._processing_active.keys()):
                    if not self._processing_active.get(guild_id, False):
                        continue
                    
                    try:
                        await self._check_guild_performance(guild_id)
                    except Exception as e:
                        logger.error(f"[{guild_id}]: Performance monitoring error: {e}")
                
                # Wait before next check
                await asyncio.sleep(5.0)
                
        except asyncio.CancelledError:
            logger.info("Performance monitoring cancelled")
        except Exception as e:
            logger.error(f"Performance monitoring error: {e}")
    
    async def _check_guild_performance(self, guild_id: int) -> None:
        """Check performance for a specific guild and adapt quality if needed"""
        try:
            config = self._audio_configs.get(guild_id)
            if not config:
                return
            
            cpu_history = self._cpu_usage_history.get(guild_id, [])
            if len(cpu_history) < 3:  # Need some history for decisions
                return
            
            avg_cpu = sum(cpu_history) / len(cpu_history)
            
            # Check if we need to reduce quality
            if avg_cpu > config.cpu_limit_percent:
                await self._reduce_quality(guild_id, config)
            
            # Check if we can increase quality
            elif avg_cpu < config.cpu_limit_percent * 0.5 and config.quality != AudioQuality.ULTRA:
                await self._increase_quality(guild_id, config)
                
        except Exception as e:
            logger.error(f"[{guild_id}]: Performance check failed: {e}")
    
    async def _reduce_quality(self, guild_id: int, config: AudioConfig) -> None:
        """Reduce audio quality to improve performance"""
        try:
            # Check cooldown to prevent rapid changes
            last_adjustment = self._quality_adjustment_cooldown.get(guild_id, 0)
            if time.time() - last_adjustment < 10.0:  # 10 second cooldown
                return
            
            # Reduce quality level
            if config.quality == AudioQuality.ULTRA:
                config.quality = AudioQuality.HIGH
            elif config.quality == AudioQuality.HIGH:
                config.quality = AudioQuality.MEDIUM
            elif config.quality == AudioQuality.MEDIUM:
                config.quality = AudioQuality.LOW
            else:
                return  # Already at lowest quality
            
            self._quality_adjustment_cooldown[guild_id] = time.time()
            
            # Update configuration
            await self.set_config(guild_id, config)
            
            # Emit quality change event
            await self.event_bus.emit_async(AUDIO_EVENTS['audio_quality_changed'],
                                          guild_id=guild_id,
                                          new_quality=config.quality.value,
                                          reason='cpu_overload')
            
            logger.info(f"[{guild_id}]: Reduced audio quality to {config.quality.value} due to high CPU usage")
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to reduce quality: {e}")
    
    async def _increase_quality(self, guild_id: int, config: AudioConfig) -> None:
        """Increase audio quality when performance allows"""
        try:
            # Check cooldown
            last_adjustment = self._quality_adjustment_cooldown.get(guild_id, 0)
            if time.time() - last_adjustment < 30.0:  # 30 second cooldown for increases
                return
            
            # Increase quality level
            if config.quality == AudioQuality.LOW:
                config.quality = AudioQuality.MEDIUM
            elif config.quality == AudioQuality.MEDIUM:
                config.quality = AudioQuality.HIGH
            elif config.quality == AudioQuality.HIGH:
                config.quality = AudioQuality.ULTRA
            else:
                return  # Already at highest quality
            
            self._quality_adjustment_cooldown[guild_id] = time.time()
            
            # Update configuration
            await self.set_config(guild_id, config)
            
            # Emit quality change event
            await self.event_bus.emit_async(AUDIO_EVENTS['audio_quality_changed'],
                                          guild_id=guild_id,
                                          new_quality=config.quality.value,
                                          reason='performance_improved')
            
            logger.info(f"[{guild_id}]: Increased audio quality to {config.quality.value}")
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to increase quality: {e}")
    
    def _validate_config(self, config: AudioConfig) -> bool:
        """Validate audio configuration parameters"""
        try:
            # Volume validation
            if not (0.0 <= config.master_volume <= 1.0):
                return False
            
            # EQ validation
            if not (-12.0 <= config.eq_bass <= 12.0):
                return False
            if not (-12.0 <= config.eq_mid <= 12.0):
                return False
            if not (-12.0 <= config.eq_treble <= 12.0):
                return False
            
            # Sample rate validation
            if config.sample_rate not in [22050, 44100, 48000]:
                return False
            
            # Channel validation
            if config.channels not in [1, 2]:
                return False
            
            # Bit depth validation
            if config.bit_depth not in [8, 16, 24]:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Config validation failed: {e}")
            return False
    
    def _needs_processing_restart(self, old_config: AudioConfig, new_config: AudioConfig) -> bool:
        """Check if processing needs to be restarted due to configuration changes"""
        # Restart if core audio parameters changed
        return (old_config.sample_rate != new_config.sample_rate or
                old_config.channels != new_config.channels or
                old_config.bit_depth != new_config.bit_depth or
                old_config.quality != new_config.quality)
    
    def _apply_normalization(self, audio_array: np.ndarray, config: AudioConfig) -> np.ndarray:
        """Apply audio normalization to target LUFS"""
        try:
            # Calculate RMS for loudness estimation
            rms = np.sqrt(np.mean(audio_array ** 2))
            
            if rms < 1e-10:  # Silence
                return audio_array
            
            # Convert RMS to approximate LUFS (simplified)
            current_lufs = 20 * np.log10(rms) - 0.691  # Rough conversion
            target_lufs = config.normalization_target_lufs
            
            # Calculate gain adjustment
            gain_db = target_lufs - current_lufs
            gain_linear = 10 ** (gain_db / 20.0)
            
            # Limit gain to prevent excessive amplification
            gain_linear = np.clip(gain_linear, 0.1, 3.0)
            
            return audio_array * gain_linear
            
        except Exception as e:
            logger.error(f"Error in normalization: {e}")
            return audio_array
    
    def _apply_auto_gain_control(self, audio_array: np.ndarray, config: AudioConfig) -> np.ndarray:
        """Apply automatic gain control"""
        try:
            # Calculate current RMS
            rms = np.sqrt(np.mean(audio_array ** 2))
            
            if rms < 1e-10:  # Silence
                return audio_array
            
            # Target RMS level (roughly -20 dB)
            target_rms = 0.1
            
            # Calculate gain factor
            gain = target_rms / rms
            
            # Smooth gain adjustment to prevent sudden changes
            gain = np.clip(gain, 0.5, 2.0)  # Limit AGC range
            
            return audio_array * gain
            
        except Exception as e:
            logger.error(f"Error in auto gain control: {e}")
            return audio_array
    
    def _apply_compression(self, audio_array: np.ndarray, config: AudioConfig) -> np.ndarray:
        """Apply dynamic range compression"""
        try:
            compression_ratio = config.dynamic_range_compression
            threshold = 0.7  # Compression threshold
            
            # Calculate gain reduction for each sample
            abs_audio = np.abs(audio_array)
            gain_reduction = np.ones_like(abs_audio)
            
            # Apply compression above threshold
            over_threshold = abs_audio > threshold
            if np.any(over_threshold):
                excess = abs_audio[over_threshold] - threshold
                compressed_excess = excess * (1.0 - compression_ratio)
                gain_reduction[over_threshold] = (threshold + compressed_excess) / abs_audio[over_threshold]
            
            # Apply gain reduction while preserving sign
            return audio_array * gain_reduction
            
        except Exception as e:
            logger.error(f"Error in compression: {e}")
            return audio_array
    
    def _apply_simple_eq(self, audio_array: np.ndarray, config: AudioConfig) -> np.ndarray:
        """Apply simple 3-band EQ (basic implementation)"""
        try:
            # Get EQ settings
            bass_gain = 10 ** (config.eq_bass / 20.0)
            mid_gain = 10 ** (config.eq_mid / 20.0)
            treble_gain = 10 ** (config.eq_treble / 20.0)
            
            # This is a very simplified EQ implementation
            # In a full implementation, this would use proper digital filters
            # For now, just apply mid-range gain to the entire signal
            # Real EQ would require frequency domain processing or IIR filters
            
            processed_audio = audio_array * mid_gain
            
            # Simple bass boost/cut (affects lower portion of signal)
            if bass_gain != 1.0:
                # Apply bass adjustment to first third of samples (simplified)
                third = len(processed_audio) // 3
                if third > 0:
                    processed_audio[:third] *= bass_gain
            
            # Simple treble boost/cut (affects higher portion of signal)
            if treble_gain != 1.0:
                # Apply treble adjustment to last third of samples (simplified)
                third = len(processed_audio) // 3
                if third > 0:
                    processed_audio[-third:] *= treble_gain
            
            return processed_audio
            
        except Exception as e:
            logger.error(f"Error in EQ processing: {e}")
            return audio_array
