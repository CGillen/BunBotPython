"""
Multi-Stream Audio Mixer for BunBot Audio Processing
"""

import logging
import asyncio
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

import numpy as np

from core import StateManager, EventBus, ConfigurationManager
from .interfaces import (
    IAudioMixer, AudioStream, MixingMode, AudioConfig, AUDIO_EVENTS
)

logger = logging.getLogger('discord.audio.mixer')

class AudioMixer(IAudioMixer):
    """
    Multi-stream audio mixer for BunBot.
    
    Handles mixing of multiple audio streams with priority-based routing,
    crossfading capabilities, and dynamic stream management for enhanced
    audio experiences.
    """
    
    def __init__(self, state_manager: StateManager, event_bus: EventBus, 
                 config_manager: ConfigurationManager):
        self.state_manager = state_manager
        self.event_bus = event_bus
        self.config_manager = config_manager
        
        # Stream management
        self._active_streams: Dict[int, List[AudioStream]] = {}  # guild_id -> streams
        self._stream_buffers: Dict[str, bytearray] = {}          # stream_id -> buffer
        self._stream_volumes: Dict[str, float] = {}              # stream_id -> volume
        
        # Mixing state
        self._mixing_modes: Dict[int, MixingMode] = {}           # guild_id -> mode
        self._crossfade_state: Dict[int, Dict[str, Any]] = {}    # guild_id -> crossfade_info
        self._mix_weights: Dict[int, Dict[str, float]] = {}      # guild_id -> stream_weights
        
        # Performance tracking
        self._mix_metrics: Dict[int, Dict[str, Any]] = {}        # guild_id -> metrics
        self._last_mix_time: Dict[int, float] = {}               # guild_id -> timestamp
        
        logger.info("AudioMixer initialized")
    
    async def add_stream(self, guild_id: int, stream: AudioStream, 
                        mixing_mode: MixingMode = MixingMode.REPLACE) -> str:
        """
        Add a new audio stream to the mix.
        
        Args:
            guild_id: Discord guild ID
            stream: Audio stream to add
            mixing_mode: How to mix the new stream
            
        Returns:
            Stream identifier for tracking
        """
        try:
            # Initialize guild streams if needed
            if guild_id not in self._active_streams:
                self._active_streams[guild_id] = []
                self._mixing_modes[guild_id] = mixing_mode
                self._mix_weights[guild_id] = {}
            
            # Handle different mixing modes
            if mixing_mode == MixingMode.REPLACE:
                # Remove all existing streams
                await self._clear_all_streams(guild_id)
            
            # Add the new stream
            self._active_streams[guild_id].append(stream)
            self._stream_volumes[stream.stream_id] = stream.volume
            
            # Initialize mixing weight based on priority and mode
            await self._calculate_mix_weights(guild_id, mixing_mode)
            
            # Initialize stream buffer
            self._stream_buffers[stream.stream_id] = bytearray()
            
            # Emit stream added event
            await self.event_bus.emit_async(AUDIO_EVENTS['audio_stream_added'],
                                          guild_id=guild_id,
                                          stream_id=stream.stream_id,
                                          mixing_mode=mixing_mode.value,
                                          priority=stream.priority)
            
            logger.info(f"[{guild_id}]: Added stream {stream.stream_id} "
                       f"(mode: {mixing_mode.value}, priority: {stream.priority})")
            
            return stream.stream_id
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to add stream: {e}")
            return ""
    
    async def remove_stream(self, guild_id: int, stream_id: str, 
                           fade_out: bool = True) -> bool:
        """
        Remove a stream from the mix.
        
        Args:
            guild_id: Discord guild ID
            stream_id: Stream ID to remove
            fade_out: Whether to fade out the stream
            
        Returns:
            True if stream was removed successfully
        """
        try:
            if guild_id not in self._active_streams:
                return False
            
            # Find and remove the stream
            streams = self._active_streams[guild_id]
            for i, stream in enumerate(streams):
                if stream.stream_id == stream_id:
                    removed_stream = streams.pop(i)
                    
                    # Handle fade out if requested
                    if fade_out and removed_stream.fade_out_duration > 0:
                        await self._start_fade_out(guild_id, stream_id, removed_stream.fade_out_duration)
                    
                    # Clean up stream resources
                    await self._cleanup_stream_resources(stream_id)
                    
                    # Recalculate mix weights
                    current_mode = self._mixing_modes.get(guild_id, MixingMode.REPLACE)
                    await self._calculate_mix_weights(guild_id, current_mode)
                    
                    # Emit stream removed event
                    await self.event_bus.emit_async(AUDIO_EVENTS['audio_stream_removed'],
                                                  guild_id=guild_id,
                                                  stream_id=stream_id,
                                                  fade_out=fade_out)
                    
                    logger.info(f"[{guild_id}]: Removed stream {stream_id}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to remove stream {stream_id}: {e}")
            return False
    
    async def set_stream_volume(self, guild_id: int, stream_id: str, volume: float) -> bool:
        """
        Set volume for a specific stream.
        
        Args:
            guild_id: Discord guild ID
            stream_id: Stream ID to adjust
            volume: Volume level (0.0 to 1.0)
            
        Returns:
            True if volume was set successfully
        """
        try:
            volume = max(0.0, min(1.0, volume))
            
            # Update stream volume in the stream object
            if guild_id in self._active_streams:
                for stream in self._active_streams[guild_id]:
                    if stream.stream_id == stream_id:
                        stream.volume = volume
                        self._stream_volumes[stream_id] = volume
                        
                        # Recalculate mix weights to account for volume change
                        current_mode = self._mixing_modes.get(guild_id, MixingMode.REPLACE)
                        await self._calculate_mix_weights(guild_id, current_mode)
                        
                        logger.info(f"[{guild_id}]: Set stream {stream_id} volume to {volume:.2f}")
                        return True
            
            return False
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to set stream volume: {e}")
            return False
    
    async def crossfade_to_stream(self, guild_id: int, target_stream_id: str, 
                                 duration: float) -> bool:
        """
        Crossfade from current mix to target stream.
        
        Args:
            guild_id: Discord guild ID
            target_stream_id: Stream to crossfade to
            duration: Crossfade duration in seconds
            
        Returns:
            True if crossfade was started successfully
        """
        try:
            if guild_id not in self._active_streams:
                return False
            
            # Find target stream
            target_stream = None
            for stream in self._active_streams[guild_id]:
                if stream.stream_id == target_stream_id:
                    target_stream = stream
                    break
            
            if not target_stream:
                logger.warning(f"[{guild_id}]: Target stream {target_stream_id} not found for crossfade")
                return False
            
            # Start crossfade
            await self._start_crossfade(guild_id, target_stream_id, duration)
            
            logger.info(f"[{guild_id}]: Started crossfade to {target_stream_id} ({duration}s)")
            return True
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to start crossfade: {e}")
            return False
    
    async def get_active_streams(self, guild_id: int) -> List[AudioStream]:
        """Get list of currently active streams"""
        return self._active_streams.get(guild_id, []).copy()
    
    async def set_mixing_mode(self, guild_id: int, mode: MixingMode) -> bool:
        """
        Set the mixing mode for new streams.
        
        Args:
            guild_id: Discord guild ID
            mode: New mixing mode
            
        Returns:
            True if mode was set successfully
        """
        try:
            self._mixing_modes[guild_id] = mode
            
            # Recalculate weights for current streams
            await self._calculate_mix_weights(guild_id, mode)
            
            logger.info(f"[{guild_id}]: Set mixing mode to {mode.value}")
            return True
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to set mixing mode: {e}")
            return False
    
    async def get_mix_metrics(self, guild_id: int) -> Dict[str, Any]:
        """Get mixing performance metrics"""
        try:
            metrics = self._mix_metrics.get(guild_id, {})
            streams = self._active_streams.get(guild_id, [])
            
            # Add current stream information
            metrics.update({
                'active_stream_count': len(streams),
                'mixing_mode': self._mixing_modes.get(guild_id, MixingMode.REPLACE).value,
                'total_streams': len(streams),
                'stream_info': [
                    {
                        'stream_id': stream.stream_id,
                        'priority': stream.priority,
                        'volume': stream.volume,
                        'weight': self._mix_weights.get(guild_id, {}).get(stream.stream_id, 0.0)
                    }
                    for stream in streams
                ],
                'has_crossfade': guild_id in self._crossfade_state,
                'last_mix_time': self._last_mix_time.get(guild_id, 0)
            })
            
            return metrics
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to get mix metrics: {e}")
            return {}
    
    def mix_audio_streams(self, guild_id: int, audio_chunks: Dict[str, bytes], 
                         config: AudioConfig) -> bytes:
        """
        Mix multiple audio streams into a single output.
        
        Args:
            guild_id: Discord guild ID
            audio_chunks: Dictionary of stream_id -> audio_data
            config: Audio configuration
            
        Returns:
            Mixed audio data
        """
        try:
            start_time = time.time()
            
            if not audio_chunks:
                return b''
            
            # Convert all audio chunks to numpy arrays
            audio_arrays = {}
            max_length = 0
            
            for stream_id, chunk in audio_chunks.items():
                if chunk:
                    array = np.frombuffer(chunk, dtype=np.int16).astype(np.float32)
                    audio_arrays[stream_id] = array
                    max_length = max(max_length, len(array))
            
            if not audio_arrays or max_length == 0:
                return b''
            
            # Pad arrays to same length
            for stream_id in audio_arrays:
                array = audio_arrays[stream_id]
                if len(array) < max_length:
                    padded = np.zeros(max_length, dtype=np.float32)
                    padded[:len(array)] = array
                    audio_arrays[stream_id] = padded
            
            # Apply mixing based on current mode and weights
            mixed_audio = self._mix_audio_arrays(guild_id, audio_arrays)
            
            # Apply crossfade if active
            if guild_id in self._crossfade_state:
                mixed_audio = self._apply_crossfade(guild_id, mixed_audio)
            
            # Convert back to int16 and clip to prevent distortion
            mixed_audio = np.clip(mixed_audio, -32768, 32767)
            mixed_bytes = mixed_audio.astype(np.int16).tobytes()
            
            # Update performance metrics
            processing_time = time.time() - start_time
            self._update_mix_metrics(guild_id, len(audio_chunks), processing_time, len(mixed_bytes))
            
            return mixed_bytes
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to mix audio streams: {e}")
            # Return first available chunk as fallback
            for chunk in audio_chunks.values():
                if chunk:
                    return chunk
            return b''
    
    def _mix_audio_arrays(self, guild_id: int, audio_arrays: Dict[str, np.ndarray]) -> np.ndarray:
        """Mix audio arrays based on current mixing mode and weights"""
        try:
            mode = self._mixing_modes.get(guild_id, MixingMode.REPLACE)
            weights = self._mix_weights.get(guild_id, {})
            
            if mode == MixingMode.REPLACE or len(audio_arrays) == 1:
                # Use the highest priority stream
                highest_priority_stream = None
                highest_priority = -1
                
                streams = self._active_streams.get(guild_id, [])
                for stream in streams:
                    if stream.stream_id in audio_arrays and stream.priority > highest_priority:
                        highest_priority = stream.priority
                        highest_priority_stream = stream.stream_id
                
                if highest_priority_stream:
                    return audio_arrays[highest_priority_stream]
                else:
                    return list(audio_arrays.values())[0]
            
            elif mode == MixingMode.OVERLAY:
                # Simple additive mixing
                mixed = np.zeros_like(list(audio_arrays.values())[0])
                for stream_id, array in audio_arrays.items():
                    weight = weights.get(stream_id, 1.0 / len(audio_arrays))
                    mixed += array * weight
                return mixed
            
            elif mode == MixingMode.PRIORITY:
                # Weighted mixing based on priority
                mixed = np.zeros_like(list(audio_arrays.values())[0])
                for stream_id, array in audio_arrays.items():
                    weight = weights.get(stream_id, 0.0)
                    mixed += array * weight
                return mixed
            
            elif mode == MixingMode.CROSSFADE:
                # Crossfade mixing (handled separately)
                return self._crossfade_mix(guild_id, audio_arrays)
            
            else:
                # Default to simple overlay
                mixed = np.zeros_like(list(audio_arrays.values())[0])
                for array in audio_arrays.values():
                    mixed += array * (1.0 / len(audio_arrays))
                return mixed
                
        except Exception as e:
            logger.error(f"[{guild_id}]: Error in mix audio arrays: {e}")
            return list(audio_arrays.values())[0] if audio_arrays else np.array([])
    
    async def _calculate_mix_weights(self, guild_id: int, mode: MixingMode) -> None:
        """Calculate mixing weights for all active streams"""
        try:
            streams = self._active_streams.get(guild_id, [])
            if not streams:
                return
            
            weights = {}
            
            if mode == MixingMode.REPLACE:
                # Only highest priority stream gets weight 1.0
                highest_priority = max(stream.priority for stream in streams)
                for stream in streams:
                    weights[stream.stream_id] = 1.0 if stream.priority == highest_priority else 0.0
            
            elif mode == MixingMode.OVERLAY:
                # Equal weights adjusted by stream volume
                base_weight = 1.0 / len(streams)
                for stream in streams:
                    weights[stream.stream_id] = base_weight * stream.volume
            
            elif mode == MixingMode.PRIORITY:
                # Weights based on priority and volume
                total_priority = sum(stream.priority for stream in streams)
                for stream in streams:
                    priority_weight = stream.priority / total_priority if total_priority > 0 else 1.0 / len(streams)
                    weights[stream.stream_id] = priority_weight * stream.volume
            
            elif mode == MixingMode.CROSSFADE:
                # Crossfade weights (managed separately)
                for stream in streams:
                    weights[stream.stream_id] = stream.volume
            
            self._mix_weights[guild_id] = weights
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to calculate mix weights: {e}")
    
    async def _start_crossfade(self, guild_id: int, target_stream_id: str, duration: float) -> None:
        """Start a crossfade to target stream"""
        try:
            self._crossfade_state[guild_id] = {
                'target_stream_id': target_stream_id,
                'duration': duration,
                'start_time': time.time(),
                'fade_curve': 'linear'  # Could be 'linear', 'exponential', etc.
            }
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to start crossfade: {e}")
    
    def _apply_crossfade(self, guild_id: int, mixed_audio: np.ndarray) -> np.ndarray:
        """Apply crossfade effect to mixed audio"""
        try:
            crossfade_info = self._crossfade_state.get(guild_id)
            if not crossfade_info:
                return mixed_audio
            
            elapsed = time.time() - crossfade_info['start_time']
            duration = crossfade_info['duration']
            
            if elapsed >= duration:
                # Crossfade complete
                del self._crossfade_state[guild_id]
                return mixed_audio
            
            # Calculate crossfade progress (0.0 to 1.0)
            progress = elapsed / duration
            
            # Apply fade curve (linear for now)
            fade_factor = progress
            
            # Apply crossfade (simplified - would need more complex logic for real crossfading)
            return mixed_audio * fade_factor
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Error applying crossfade: {e}")
            return mixed_audio
    
    def _crossfade_mix(self, guild_id: int, audio_arrays: Dict[str, np.ndarray]) -> np.ndarray:
        """Handle crossfade mixing mode"""
        # Placeholder for crossfade mixing logic
        # Would implement sophisticated crossfading between streams
        mixed = np.zeros_like(list(audio_arrays.values())[0])
        for array in audio_arrays.values():
            mixed += array * (1.0 / len(audio_arrays))
        return mixed
    
    async def _start_fade_out(self, guild_id: int, stream_id: str, duration: float) -> None:
        """Start fade out for a stream being removed"""
        # Placeholder for fade out implementation
        logger.debug(f"[{guild_id}]: Starting fade out for {stream_id} ({duration}s)")
    
    async def _clear_all_streams(self, guild_id: int) -> None:
        """Clear all streams for a guild"""
        if guild_id in self._active_streams:
            streams_to_remove = [stream.stream_id for stream in self._active_streams[guild_id]]
            for stream_id in streams_to_remove:
                await self._cleanup_stream_resources(stream_id)
            self._active_streams[guild_id].clear()
            self._mix_weights[guild_id] = {}
    
    async def _cleanup_stream_resources(self, stream_id: str) -> None:
        """Clean up resources for a stream"""
        if stream_id in self._stream_buffers:
            del self._stream_buffers[stream_id]
        if stream_id in self._stream_volumes:
            del self._stream_volumes[stream_id]
    
    def _update_mix_metrics(self, guild_id: int, stream_count: int, 
                           processing_time: float, output_size: int) -> None:
        """Update mixing performance metrics"""
        try:
            self._mix_metrics[guild_id] = {
                'stream_count': stream_count,
                'processing_time_ms': processing_time * 1000,
                'output_size_bytes': output_size,
                'throughput_bps': output_size / processing_time if processing_time > 0 else 0,
                'last_update': time.time()
            }
            self._last_mix_time[guild_id] = time.time()
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to update mix metrics: {e}")
    
    def get_mixer_stats(self) -> Dict[str, Any]:
        """Get overall mixer statistics"""
        try:
            total_guilds = len(self._active_streams)
            total_streams = sum(len(streams) for streams in self._active_streams.values())
            
            mode_counts = {}
            for mode in self._mixing_modes.values():
                mode_counts[mode.value] = mode_counts.get(mode.value, 0) + 1
            
            return {
                'total_guilds': total_guilds,
                'total_active_streams': total_streams,
                'mixing_mode_distribution': mode_counts,
                'active_crossfades': len(self._crossfade_state),
                'average_streams_per_guild': total_streams / total_guilds if total_guilds > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Failed to get mixer stats: {e}")
            return {}
