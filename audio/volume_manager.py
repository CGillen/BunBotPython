"""
Volume Management System for BunBot Audio Processing
"""

import logging
import asyncio
import time
import math
import os
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timezone

import numpy as np

from core import StateManager, EventBus, ConfigurationManager
from .interfaces import (
    IVolumeManager, AudioConfig, AUDIO_EVENTS
)

logger = logging.getLogger('discord.audio.volume_manager')

class VolumeManager(IVolumeManager):
    """
    Advanced volume management for BunBot audio processing.
    
    Handles real-time volume control, normalization, automatic gain control,
    and dynamic range compression. Provides smooth volume transitions and
    comprehensive volume analytics.
    """
    
    def __init__(self, state_manager: StateManager, event_bus: EventBus, 
                 config_manager: ConfigurationManager, service_registry=None):
        self.state_manager = state_manager
        self.event_bus = event_bus
        self.config_manager = config_manager
        self.service_registry = service_registry
        
        # Volume state tracking
        self._volume_settings: Dict[int, Dict[str, float]] = {}  # guild_id -> settings
        self._volume_metrics: Dict[int, Dict[str, float]] = {}   # guild_id -> metrics
        self._volume_history: Dict[int, list] = {}               # guild_id -> history
        
        # Normalization state
        self._normalization_targets: Dict[int, float] = {}       # guild_id -> LUFS target
        self._agc_enabled: Dict[int, bool] = {}                  # guild_id -> AGC status
        self._compression_ratios: Dict[int, float] = {}          # guild_id -> compression ratio
        
        # Real-time processing state
        self._volume_smoothing: Dict[int, float] = {}            # guild_id -> current smooth volume
        self._target_volumes: Dict[int, float] = {}              # guild_id -> target volume
        self._volume_ramps: Dict[int, Dict[str, Any]] = {}       # guild_id -> ramp state
        
        # Performance monitoring
        self._last_analysis_time: Dict[int, float] = {}
        self._analysis_interval = 0.1  # 100ms analysis interval
        
        # Resource monitoring for Render free tier
        self._discord_update_failures: Dict[int, int] = {}  # guild_id -> failure_count
        self._max_failures = 3  # Circuit breaker threshold
        
        logger.info("VolumeManager initialized")
    
    def _is_render_free_tier(self) -> bool:
        """Check if running on Render free tier"""
        return bool(os.getenv('RENDER')) and os.getenv('RENDER_SERVICE_TYPE') == 'web'
    
    def _check_memory_usage(self) -> float:
        """Check current memory usage percentage"""
        try:
            import psutil
            return psutil.virtual_memory().percent
        except ImportError:
            # psutil not available, assume safe
            return 50.0
        except Exception:
            # Error checking memory, assume safe
            return 50.0
    
    def _should_use_enhanced_processing(self, guild_id: int) -> bool:
        """Determine if enhanced audio processing should be used"""
        # Check if on Render free tier
        if self._is_render_free_tier():
            # Limit enhanced processing on free tier
            memory_usage = self._check_memory_usage()
            if memory_usage > 80:  # 80% memory usage threshold
                logger.debug(f"[{guild_id}]: Skipping enhanced processing due to high memory usage ({memory_usage:.1f}%)")
                return False
        
        return True
    
    async def set_master_volume(self, guild_id: int, volume: float) -> bool:
        """
        Set master volume with smooth transition and real-time Discord audio update.
        
        Args:
            guild_id: Discord guild ID
            volume: Volume level (0.0 to 1.0)
            
        Returns:
            True if volume was set successfully
        """
        try:
            # Validate volume range
            volume = max(0.0, min(1.0, volume))
            
            # Get current settings or create defaults
            settings = self._volume_settings.get(guild_id, {})
            old_volume = settings.get('master_volume', 0.8)
            
            # Update settings
            settings['master_volume'] = volume
            self._volume_settings[guild_id] = settings
            
            # Start smooth transition
            await self._start_volume_ramp(guild_id, old_volume, volume, duration=0.5)
            
            # Update guild state
            guild_state = self.state_manager.get_guild_state(guild_id, create_if_missing=True)
            if guild_state and hasattr(guild_state, 'volume_level'):
                guild_state.volume_level = volume
            
            # REAL-TIME DISCORD AUDIO UPDATE - This is the key fix!
            await self._update_discord_audio_volume(guild_id, volume)
            
            # Emit volume change event
            await self.event_bus.emit_async(AUDIO_EVENTS['audio_volume_changed'],
                                          guild_id=guild_id,
                                          old_volume=old_volume,
                                          new_volume=volume)
            
            logger.info(f"[{guild_id}]: Set master volume to {volume:.2f}")
            return True
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to set master volume: {e}")
            return False
    
    async def get_master_volume(self, guild_id: int) -> float:
        """Get current master volume level"""
        settings = self._volume_settings.get(guild_id, {})
        return settings.get('master_volume', 0.8)
    
    async def set_normalization_target(self, guild_id: int, lufs_target: float) -> bool:
        """
        Set audio normalization target in LUFS.
        
        Args:
            guild_id: Discord guild ID
            lufs_target: Target loudness in LUFS (-30.0 to -16.0)
            
        Returns:
            True if target was set successfully
        """
        try:
            # Validate LUFS range
            lufs_target = max(-30.0, min(-16.0, lufs_target))
            
            # Store normalization target
            old_target = self._normalization_targets.get(guild_id, -23.0)
            self._normalization_targets[guild_id] = lufs_target
            
            # Update audio config if available
            await self._update_audio_config(guild_id, 'normalization_target_lufs', lufs_target)
            
            # Emit normalization change event
            await self.event_bus.emit_async(AUDIO_EVENTS['audio_normalization_adjusted'],
                                          guild_id=guild_id,
                                          old_target=old_target,
                                          new_target=lufs_target)
            
            logger.info(f"[{guild_id}]: Set normalization target to {lufs_target} LUFS")
            return True
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to set normalization target: {e}")
            return False
    
    async def enable_auto_gain_control(self, guild_id: int, enabled: bool) -> bool:
        """
        Enable or disable automatic gain control.
        
        Args:
            guild_id: Discord guild ID
            enabled: Whether to enable AGC
            
        Returns:
            True if AGC setting was updated successfully
        """
        try:
            old_enabled = self._agc_enabled.get(guild_id, True)
            self._agc_enabled[guild_id] = enabled
            
            # Update audio config
            await self._update_audio_config(guild_id, 'auto_gain_control', enabled)
            
            logger.info(f"[{guild_id}]: {'Enabled' if enabled else 'Disabled'} automatic gain control")
            return True
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to set AGC: {e}")
            return False
    
    async def set_dynamic_range_compression(self, guild_id: int, ratio: float) -> bool:
        """
        Set dynamic range compression ratio.
        
        Args:
            guild_id: Discord guild ID
            ratio: Compression ratio (0.0 = no compression, 1.0 = maximum compression)
            
        Returns:
            True if compression was set successfully
        """
        try:
            # Validate ratio range
            ratio = max(0.0, min(1.0, ratio))
            
            old_ratio = self._compression_ratios.get(guild_id, 0.0)
            self._compression_ratios[guild_id] = ratio
            
            # Update audio config
            await self._update_audio_config(guild_id, 'dynamic_range_compression', ratio)
            
            logger.info(f"[{guild_id}]: Set dynamic range compression to {ratio:.2f}")
            return True
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to set compression: {e}")
            return False
    
    async def get_volume_metrics(self, guild_id: int) -> Dict[str, float]:
        """
        Get volume-related metrics for analysis.
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            Dictionary with volume metrics (RMS, peak, LUFS, etc.)
        """
        try:
            metrics = self._volume_metrics.get(guild_id, {})
            
            # Calculate additional metrics if we have recent data
            volume_history = self._volume_history.get(guild_id, [])
            if volume_history:
                recent_volumes = volume_history[-10:]  # Last 10 measurements
                metrics.update({
                    'average_volume': sum(recent_volumes) / len(recent_volumes),
                    'volume_variance': self._calculate_variance(recent_volumes),
                    'dynamic_range': max(recent_volumes) - min(recent_volumes)
                })
            
            return metrics
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to get volume metrics: {e}")
            return {}
    
    def process_audio_volume(self, guild_id: int, audio_data: bytes, 
                           config: AudioConfig) -> Tuple[bytes, Dict[str, float]]:
        """
        Process audio data for volume control and normalization.
        
        Args:
            guild_id: Discord guild ID
            audio_data: Raw audio data
            config: Audio configuration
            
        Returns:
            Tuple of (processed_audio_data, volume_metrics)
        """
        try:
            if not audio_data:
                return audio_data, {}
            
            # Convert audio data to numpy array for processing
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            
            # Calculate current audio metrics
            metrics = self._analyze_audio_data(audio_array)
            
            # Apply volume processing pipeline
            processed_audio = self._apply_volume_pipeline(guild_id, audio_array, config, metrics)
            
            # Convert back to bytes
            processed_data = processed_audio.astype(np.int16).tobytes()
            
            # Update metrics and history
            self._update_volume_metrics(guild_id, metrics)
            
            return processed_data, metrics
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to process audio volume: {e}")
            return audio_data, {}
    
    def _apply_volume_pipeline(self, guild_id: int, audio_array: np.ndarray, 
                             config: AudioConfig, metrics: Dict[str, float]) -> np.ndarray:
        """Apply the complete volume processing pipeline"""
        try:
            processed_audio = audio_array.copy().astype(np.float32)
            
            # Step 1: Normalize to prevent clipping during processing
            if np.max(np.abs(processed_audio)) > 0:
                processed_audio = processed_audio / 32768.0  # Convert to [-1, 1] range
            
            # Step 2: Apply automatic gain control if enabled
            if self._agc_enabled.get(guild_id, True):
                processed_audio = self._apply_auto_gain_control(processed_audio, config)
            
            # Step 3: Apply dynamic range compression
            compression_ratio = self._compression_ratios.get(guild_id, 0.0)
            if compression_ratio > 0.0:
                processed_audio = self._apply_compression(processed_audio, compression_ratio)
            
            # Step 4: Apply master volume with smooth ramping
            current_volume = self._get_current_smooth_volume(guild_id)
            processed_audio = processed_audio * current_volume
            
            # Step 5: Apply normalization to target LUFS
            if config.normalization_enabled:
                target_lufs = self._normalization_targets.get(guild_id, -23.0)
                processed_audio = self._apply_normalization(processed_audio, target_lufs, metrics)
            
            # Step 6: Final limiting to prevent clipping
            processed_audio = np.clip(processed_audio, -1.0, 1.0)
            
            # Convert back to int16 range
            processed_audio = processed_audio * 32767.0
            
            return processed_audio
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Error in volume pipeline: {e}")
            return audio_array
    
    def _analyze_audio_data(self, audio_array: np.ndarray) -> Dict[str, float]:
        """Analyze audio data and extract volume metrics"""
        try:
            if len(audio_array) == 0:
                return {}
            
            # Convert to float for analysis
            audio_float = audio_array.astype(np.float32) / 32768.0
            
            # Calculate RMS (Root Mean Square) - perceived loudness
            rms = np.sqrt(np.mean(audio_float ** 2))
            rms_db = 20 * np.log10(max(rms, 1e-10))  # Avoid log(0)
            
            # Calculate peak level
            peak = np.max(np.abs(audio_float))
            peak_db = 20 * np.log10(max(peak, 1e-10))
            
            # Estimate LUFS (simplified calculation)
            # This is a rough approximation - proper LUFS requires more complex filtering
            lufs = rms_db - 0.691  # Rough conversion from RMS to LUFS
            
            # Calculate crest factor (peak to RMS ratio)
            crest_factor = peak / max(rms, 1e-10)
            crest_factor_db = 20 * np.log10(crest_factor)
            
            return {
                'rms': rms,
                'rms_db': rms_db,
                'peak': peak,
                'peak_db': peak_db,
                'lufs_estimate': lufs,
                'crest_factor': crest_factor,
                'crest_factor_db': crest_factor_db,
                'sample_count': len(audio_array)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing audio data: {e}")
            return {}
    
    def _apply_auto_gain_control(self, audio: np.ndarray, config: AudioConfig) -> np.ndarray:
        """Apply automatic gain control to maintain consistent levels"""
        try:
            # Calculate current RMS
            rms = np.sqrt(np.mean(audio ** 2))
            
            if rms < 1e-10:  # Silence
                return audio
            
            # Target RMS (roughly equivalent to -20 dB)
            target_rms = 0.1
            
            # Calculate gain adjustment
            gain = target_rms / rms
            
            # Limit gain adjustment to prevent excessive amplification
            gain = np.clip(gain, 0.1, 10.0)
            
            # Apply gain smoothly
            return audio * gain
            
        except Exception as e:
            logger.error(f"Error in auto gain control: {e}")
            return audio
    
    def _apply_compression(self, audio: np.ndarray, ratio: float) -> np.ndarray:
        """Apply dynamic range compression"""
        try:
            # Simple soft knee compressor
            threshold = 0.7  # Compression threshold
            
            # Calculate gain reduction for each sample
            abs_audio = np.abs(audio)
            gain_reduction = np.ones_like(abs_audio)
            
            # Apply compression above threshold
            over_threshold = abs_audio > threshold
            if np.any(over_threshold):
                excess = abs_audio[over_threshold] - threshold
                compressed_excess = excess * (1.0 - ratio)
                gain_reduction[over_threshold] = (threshold + compressed_excess) / abs_audio[over_threshold]
            
            # Apply gain reduction
            return audio * gain_reduction
            
        except Exception as e:
            logger.error(f"Error in compression: {e}")
            return audio
    
    def _apply_normalization(self, audio: np.ndarray, target_lufs: float, 
                           metrics: Dict[str, float]) -> np.ndarray:
        """Apply normalization to target LUFS"""
        try:
            current_lufs = metrics.get('lufs_estimate', -20.0)
            
            # Calculate gain adjustment needed
            gain_db = target_lufs - current_lufs
            gain_linear = 10 ** (gain_db / 20.0)
            
            # Limit gain to prevent excessive amplification
            gain_linear = np.clip(gain_linear, 0.1, 3.0)
            
            return audio * gain_linear
            
        except Exception as e:
            logger.error(f"Error in normalization: {e}")
            return audio
    
    def _get_current_smooth_volume(self, guild_id: int) -> float:
        """Get current smoothly interpolated volume level"""
        # Check if we have an active volume ramp
        ramp_state = self._volume_ramps.get(guild_id)
        if ramp_state:
            current_time = time.time()
            elapsed = current_time - ramp_state['start_time']
            
            if elapsed >= ramp_state['duration']:
                # Ramp completed
                final_volume = ramp_state['target_volume']
                del self._volume_ramps[guild_id]
                self._volume_smoothing[guild_id] = final_volume
                return final_volume
            else:
                # Interpolate current volume
                progress = elapsed / ramp_state['duration']
                # Use smooth cubic interpolation
                smooth_progress = progress * progress * (3.0 - 2.0 * progress)
                current_volume = (ramp_state['start_volume'] + 
                                (ramp_state['target_volume'] - ramp_state['start_volume']) * smooth_progress)
                self._volume_smoothing[guild_id] = current_volume
                return current_volume
        
        # No active ramp, return current volume
        return self._volume_smoothing.get(guild_id, 0.8)
    
    async def _start_volume_ramp(self, guild_id: int, start_volume: float, 
                               target_volume: float, duration: float) -> None:
        """Start a smooth volume transition"""
        self._volume_ramps[guild_id] = {
            'start_volume': start_volume,
            'target_volume': target_volume,
            'duration': duration,
            'start_time': time.time()
        }
        self._target_volumes[guild_id] = target_volume
    
    def _update_volume_metrics(self, guild_id: int, metrics: Dict[str, float]) -> None:
        """Update volume metrics and history"""
        try:
            # Store current metrics
            self._volume_metrics[guild_id] = metrics
            
            # Update volume history
            if 'rms' in metrics:
                history = self._volume_history.get(guild_id, [])
                history.append(metrics['rms'])
                
                # Limit history size
                if len(history) > 100:
                    history = history[-100:]
                
                self._volume_history[guild_id] = history
            
            # Update last analysis time
            self._last_analysis_time[guild_id] = time.time()
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to update volume metrics: {e}")
    
    async def _update_audio_config(self, guild_id: int, field: str, value: Any) -> None:
        """Update audio configuration for a guild"""
        try:
            guild_state = self.state_manager.get_guild_state(guild_id, create_if_missing=True)
            if guild_state and hasattr(guild_state, 'audio_config') and guild_state.audio_config:
                setattr(guild_state.audio_config, field, value)
                logger.debug(f"[{guild_id}]: Updated audio config {field} = {value}")
                
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to update audio config: {e}")
    
    async def _update_discord_audio_volume(self, guild_id: int, volume: float) -> bool:
        """
        Update the Discord audio source volume in real-time with timeout protection.
        
        This method uses the injected service registry to avoid blocking the event loop.
        
        Args:
            guild_id: Discord guild ID
            volume: New volume level (0.0 to 1.0)
            
        Returns:
            True if Discord audio volume was updated successfully
        """
        try:
            # Add timeout protection to prevent blocking
            return await asyncio.wait_for(
                self._update_discord_audio_volume_impl(guild_id, volume),
                timeout=1.0
            )
        except asyncio.TimeoutError:
            logger.warning(f"[{guild_id}]: Discord audio update timed out")
            return False
        except Exception as e:
            logger.error(f"[{guild_id}]: Discord audio update failed: {e}")
            return False
    
    async def _update_discord_audio_volume_impl(self, guild_id: int, volume: float) -> bool:
        """
        Implementation of Discord audio volume update using injected service registry.
        
        Args:
            guild_id: Discord guild ID
            volume: New volume level (0.0 to 1.0)
            
        Returns:
            True if Discord audio volume was updated successfully
        """
        try:
            # Use injected service registry (NON-BLOCKING)
            if not self.service_registry:
                logger.debug(f"[{guild_id}]: Service registry not available for volume update")
                return False
            
            # Get bot instance from injected service registry
            bot = self.service_registry.get_optional('bot')
            if not bot:
                logger.debug(f"[{guild_id}]: Bot instance not available for real-time volume update")
                return False
            
            # Import discord here to avoid import-time dependencies
            import discord
            
            # Find the guild
            guild = discord.utils.get(bot.guilds, id=guild_id)
            if not guild or not guild.voice_client:
                logger.debug(f"[{guild_id}]: No voice client available for real-time volume update")
                return False
            
            # Get the current audio source
            voice_client = guild.voice_client
            audio_source = getattr(voice_client, 'source', None)
            
            if not audio_source:
                logger.debug(f"[{guild_id}]: No active audio source for real-time volume update")
                return False
            
            # Check if the audio source supports volume control
            if hasattr(audio_source, 'volume'):
                # Update the Discord PCMVolumeTransformer volume property
                old_volume = audio_source.volume
                audio_source.volume = volume
                logger.debug(f"[{guild_id}]: Updated Discord audio source volume from {old_volume:.2f} to {volume:.2f}")
                return True
            else:
                logger.debug(f"[{guild_id}]: Audio source does not support real-time volume control")
                return False
                
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to update Discord audio volume implementation: {e}")
            return False
    
    def _calculate_variance(self, values: list) -> float:
        """Calculate variance of a list of values"""
        if len(values) < 2:
            return 0.0
        
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance
    
    def get_volume_stats(self, guild_id: int) -> Dict[str, Any]:
        """Get volume management statistics for a guild"""
        try:
            settings = self._volume_settings.get(guild_id, {})
            metrics = self._volume_metrics.get(guild_id, {})
            history = self._volume_history.get(guild_id, [])
            
            return {
                'current_volume': settings.get('master_volume', 0.8),
                'normalization_target': self._normalization_targets.get(guild_id, -23.0),
                'agc_enabled': self._agc_enabled.get(guild_id, True),
                'compression_ratio': self._compression_ratios.get(guild_id, 0.0),
                'current_metrics': metrics,
                'history_length': len(history),
                'average_volume': sum(history) / len(history) if history else 0.0,
                'smooth_volume': self._volume_smoothing.get(guild_id, 0.8),
                'has_active_ramp': guild_id in self._volume_ramps
            }
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to get volume stats: {e}")
            return {}
