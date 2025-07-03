"""
Main advanced audio processor that orchestrates all audio processing components.

This module provides the primary interface for advanced audio processing,
integrating filters, EQ, spectral processing, and quality management.
"""

import logging
import time
from typing import Dict, Any, Optional, List
import numpy as np

from audio.interfaces.advanced_interfaces import (
    IAdvancedAudioProcessor, IParametricEqualizer, AudioBuffer,
    ProcessingQuality, FrequencyBand
)
from .spectral_processor import SpectralProcessor
from .parametric_eq import ParametricEqualizer, EQPresets
from audio.filters import ScipyFilterDesigner, FilterDesignService, DigitalFilter

logger = logging.getLogger('audio.processing.advanced_processor')

class AdvancedAudioProcessor:
    """
    Main advanced audio processor implementation.
    
    Orchestrates all audio processing components including filters,
    EQ, spectral processing, and adaptive quality management.
    """
    
    def __init__(self, sample_rate: float = 48000):
        """
        Initialize advanced audio processor.
        
        Args:
            sample_rate: Audio sample rate in Hz
        """
        self.sample_rate = sample_rate
        
        # Initialize processing components
        self._spectral_processor = SpectralProcessor()
        self._filter_designer = ScipyFilterDesigner()
        self._filter_service = FilterDesignService(self._filter_designer)
        
        # Per-guild processing state
        self._guild_equalizers: Dict[int, ParametricEqualizer] = {}
        self._guild_noise_profiles: Dict[int, np.ndarray] = {}
        self._guild_quality_settings: Dict[int, ProcessingQuality] = {}
        self._guild_processing_stats: Dict[int, Dict[str, Any]] = {}
        
        # Performance tracking
        self._processing_count = 0
        self._total_processing_time = 0.0
        
        logger.info(f"AdvancedAudioProcessor initialized at {sample_rate} Hz")
    
    def process_audio_buffer(self, buffer: AudioBuffer, guild_id: int) -> AudioBuffer:
        """
        Process audio buffer through complete processing pipeline.
        
        Args:
            buffer: Input audio buffer
            guild_id: Discord guild ID for settings
            
        Returns:
            Processed audio buffer
        """
        try:
            start_time = time.perf_counter()
            
            # Get or create guild-specific components
            equalizer = self._get_or_create_equalizer(guild_id)
            quality = self._guild_quality_settings.get(guild_id, ProcessingQuality.HIGH)
            
            # Start with original buffer
            processed_buffer = buffer
            
            # Apply noise reduction if profile exists
            if guild_id in self._guild_noise_profiles:
                processed_buffer = self._apply_noise_reduction(
                    processed_buffer, guild_id, quality
                )
            
            # Apply parametric EQ
            if equalizer.get_band_count() > 0:
                processed_buffer = equalizer.process_buffer(processed_buffer)
            
            # Update processing statistics
            processing_time = time.perf_counter() - start_time
            self._update_guild_stats(guild_id, processing_time, buffer)
            self._update_performance_metrics(processing_time)
            
            return processed_buffer
            
        except Exception as e:
            logger.error(f"Audio processing failed for guild {guild_id}: {e}")
            # Return original buffer on error
            return buffer
    
    def get_equalizer(self, guild_id: int) -> IParametricEqualizer:
        """
        Get parametric equalizer for guild.
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            Parametric equalizer instance
        """
        return self._get_or_create_equalizer(guild_id)
    
    def set_noise_profile(self, guild_id: int, noise_profile: np.ndarray) -> None:
        """
        Set noise profile for noise reduction.
        
        Args:
            guild_id: Discord guild ID
            noise_profile: Noise magnitude spectrum
        """
        try:
            self._guild_noise_profiles[guild_id] = noise_profile.copy()
            logger.debug(f"Set noise profile for guild {guild_id}")
            
        except Exception as e:
            logger.error(f"Failed to set noise profile for guild {guild_id}: {e}")
    
    def get_processing_stats(self, guild_id: int) -> Dict[str, Any]:
        """
        Get processing statistics for guild.
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            Dictionary of processing statistics
        """
        try:
            guild_stats = self._guild_processing_stats.get(guild_id, {})
            
            # Add component-specific stats
            equalizer = self._guild_equalizers.get(guild_id)
            eq_stats = equalizer.get_performance_stats() if equalizer else {}
            
            spectral_stats = self._spectral_processor.get_performance_stats()
            filter_stats = self._filter_service.get_cache_stats()
            
            return {
                'guild_id': guild_id,
                'sample_rate': self.sample_rate,
                'quality_setting': self._guild_quality_settings.get(
                    guild_id, ProcessingQuality.HIGH
                ).value,
                'has_noise_profile': guild_id in self._guild_noise_profiles,
                'eq_band_count': equalizer.get_band_count() if equalizer else 0,
                'guild_stats': guild_stats,
                'equalizer_stats': eq_stats,
                'spectral_stats': spectral_stats,
                'filter_cache_stats': filter_stats,
                'processor_stats': {
                    'total_processing_count': self._processing_count,
                    'average_processing_time_ms': (
                        self._total_processing_time / self._processing_count * 1000
                        if self._processing_count > 0 else 0.0
                    )
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get processing stats for guild {guild_id}: {e}")
            return {'guild_id': guild_id, 'error': str(e)}
    
    def set_quality(self, guild_id: int, quality: ProcessingQuality) -> None:
        """
        Set processing quality for guild.
        
        Args:
            guild_id: Discord guild ID
            quality: Processing quality level
        """
        try:
            self._guild_quality_settings[guild_id] = quality
            logger.debug(f"Set processing quality for guild {guild_id}: {quality.value}")
            
        except Exception as e:
            logger.error(f"Failed to set quality for guild {guild_id}: {e}")
    
    def apply_eq_preset(self, guild_id: int, preset_name: str) -> bool:
        """
        Apply EQ preset to guild.
        
        Args:
            guild_id: Discord guild ID
            preset_name: Name of EQ preset
            
        Returns:
            True if preset was applied successfully
        """
        try:
            equalizer = self._get_or_create_equalizer(guild_id)
            
            # Reset current EQ
            equalizer.reset()
            
            # Get preset bands
            preset_bands = EQPresets.get_preset(preset_name)
            
            # Add preset bands
            for band in preset_bands:
                equalizer.add_band(band)
            
            logger.info(f"Applied EQ preset '{preset_name}' to guild {guild_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to apply EQ preset '{preset_name}' to guild {guild_id}: {e}")
            return False
    
    def analyze_audio_spectrum(self, audio_data: np.ndarray) -> Dict[str, Any]:
        """
        Analyze audio spectrum and return analysis results.
        
        Args:
            audio_data: Audio samples to analyze
            
        Returns:
            Dictionary containing spectral analysis results
        """
        try:
            # Ensure mono audio for analysis
            if audio_data.ndim == 2:
                audio_data = np.mean(audio_data, axis=1)
            
            # Perform spectral analysis
            spectrum = self._spectral_processor.analyze_spectrum(audio_data, self.sample_rate)
            
            # Compute spectral features
            from .spectral_processor import SpectralAnalyzer
            centroid = SpectralAnalyzer.compute_spectral_centroid(spectrum)
            rolloff = SpectralAnalyzer.compute_spectral_rolloff(spectrum)
            bandwidth = SpectralAnalyzer.compute_spectral_bandwidth(spectrum)
            peaks_freq, peaks_mag = SpectralAnalyzer.find_peaks(spectrum)
            
            return {
                'sample_rate': spectrum.sample_rate,
                'window_size': spectrum.window_size,
                'frequency_resolution': spectrum.frequency_resolution,
                'spectral_centroid_hz': centroid,
                'spectral_rolloff_hz': rolloff,
                'spectral_bandwidth_hz': bandwidth,
                'peak_frequencies': peaks_freq.tolist(),
                'peak_magnitudes': peaks_mag.tolist(),
                'magnitude_db_range': {
                    'min': float(np.min(spectrum.magnitude_db)),
                    'max': float(np.max(spectrum.magnitude_db)),
                    'mean': float(np.mean(spectrum.magnitude_db))
                }
            }
            
        except Exception as e:
            logger.error(f"Spectral analysis failed: {e}")
            return {'error': str(e)}
    
    def clear_guild_data(self, guild_id: int) -> None:
        """
        Clear all processing data for a guild.
        
        Args:
            guild_id: Discord guild ID
        """
        try:
            # Remove guild-specific data
            self._guild_equalizers.pop(guild_id, None)
            self._guild_noise_profiles.pop(guild_id, None)
            self._guild_quality_settings.pop(guild_id, None)
            self._guild_processing_stats.pop(guild_id, None)
            
            logger.debug(f"Cleared processing data for guild {guild_id}")
            
        except Exception as e:
            logger.error(f"Failed to clear data for guild {guild_id}: {e}")
    
    def get_available_eq_presets(self) -> List[str]:
        """Get list of available EQ presets"""
        return EQPresets.get_preset_names()
    
    def _get_or_create_equalizer(self, guild_id: int) -> ParametricEqualizer:
        """Get or create equalizer for guild"""
        if guild_id not in self._guild_equalizers:
            self._guild_equalizers[guild_id] = ParametricEqualizer(self.sample_rate)
        return self._guild_equalizers[guild_id]
    
    def _apply_noise_reduction(self, buffer: AudioBuffer, guild_id: int, 
                              quality: ProcessingQuality) -> AudioBuffer:
        """Apply noise reduction to audio buffer"""
        try:
            noise_profile = self._guild_noise_profiles[guild_id]
            
            # Adjust noise reduction aggressiveness based on quality
            alpha_map = {
                ProcessingQuality.LOW: 1.5,
                ProcessingQuality.MEDIUM: 2.0,
                ProcessingQuality.HIGH: 2.5,
                ProcessingQuality.ULTRA: 3.0
            }
            alpha = alpha_map.get(quality, 2.0)
            
            # Apply noise reduction
            if buffer.data.ndim == 1:
                # Mono audio
                processed_data = self._spectral_processor.spectral_subtraction(
                    buffer.data, noise_profile, alpha
                )
            else:
                # Multi-channel audio - process each channel
                processed_channels = []
                for channel in range(buffer.data.shape[1]):
                    channel_data = buffer.data[:, channel]
                    processed_channel = self._spectral_processor.spectral_subtraction(
                        channel_data, noise_profile, alpha
                    )
                    processed_channels.append(processed_channel)
                processed_data = np.column_stack(processed_channels)
            
            return AudioBuffer(
                data=processed_data,
                sample_rate=buffer.sample_rate,
                channels=buffer.channels,
                bit_depth=buffer.bit_depth,
                timestamp=buffer.timestamp,
                buffer_id=buffer.buffer_id
            )
            
        except Exception as e:
            logger.error(f"Noise reduction failed: {e}")
            return buffer
    
    def _update_guild_stats(self, guild_id: int, processing_time: float, 
                           buffer: AudioBuffer) -> None:
        """Update processing statistics for guild"""
        try:
            if guild_id not in self._guild_processing_stats:
                self._guild_processing_stats[guild_id] = {
                    'processing_count': 0,
                    'total_processing_time': 0.0,
                    'total_samples_processed': 0,
                    'last_buffer_size': 0,
                    'last_processing_time_ms': 0.0
                }
            
            stats = self._guild_processing_stats[guild_id]
            stats['processing_count'] += 1
            stats['total_processing_time'] += processing_time
            stats['total_samples_processed'] += buffer.data.size
            stats['last_buffer_size'] = buffer.data.size
            stats['last_processing_time_ms'] = processing_time * 1000
            
        except Exception as e:
            logger.error(f"Failed to update guild stats: {e}")
    
    def _update_performance_metrics(self, processing_time: float) -> None:
        """Update overall performance metrics"""
        self._processing_count += 1
        self._total_processing_time += processing_time


class AudioQualityManager:
    """
    Manages adaptive audio quality based on system performance.
    
    Monitors system resources and adjusts processing quality accordingly.
    """
    
    def __init__(self):
        """Initialize quality manager"""
        self._quality_thresholds = {
            'cpu_high': 80.0,      # CPU usage above this = reduce quality
            'cpu_medium': 60.0,    # CPU usage above this = medium quality
            'memory_high': 85.0,   # Memory usage above this = reduce quality
            'memory_medium': 70.0  # Memory usage above this = medium quality
        }
        
        logger.debug("AudioQualityManager initialized")
    
    def get_optimal_quality(self, cpu_usage: float, memory_usage: float) -> ProcessingQuality:
        """
        Determine optimal processing quality based on system resources.
        
        Args:
            cpu_usage: Current CPU usage percentage (0-100)
            memory_usage: Current memory usage percentage (0-100)
            
        Returns:
            Recommended processing quality level
        """
        try:
            # Check for high resource usage
            if (cpu_usage >= self._quality_thresholds['cpu_high'] or 
                memory_usage >= self._quality_thresholds['memory_high']):
                return ProcessingQuality.LOW
            
            # Check for medium resource usage
            if (cpu_usage >= self._quality_thresholds['cpu_medium'] or 
                memory_usage >= self._quality_thresholds['memory_medium']):
                return ProcessingQuality.MEDIUM
            
            # Low resource usage - can use high quality
            return ProcessingQuality.HIGH
            
        except Exception as e:
            logger.error(f"Quality determination failed: {e}")
            return ProcessingQuality.MEDIUM
    
    def adapt_processing_parameters(self, quality: ProcessingQuality) -> Dict[str, Any]:
        """
        Get processing parameters for given quality level.
        
        Args:
            quality: Target quality level
            
        Returns:
            Dictionary of processing parameters
        """
        try:
            parameter_map = {
                ProcessingQuality.LOW: {
                    'window_size': 1024,
                    'overlap': 0.25,
                    'filter_order_max': 8,
                    'eq_bands_max': 3,
                    'noise_reduction_alpha': 1.5
                },
                ProcessingQuality.MEDIUM: {
                    'window_size': 2048,
                    'overlap': 0.5,
                    'filter_order_max': 12,
                    'eq_bands_max': 6,
                    'noise_reduction_alpha': 2.0
                },
                ProcessingQuality.HIGH: {
                    'window_size': 4096,
                    'overlap': 0.75,
                    'filter_order_max': 16,
                    'eq_bands_max': 10,
                    'noise_reduction_alpha': 2.5
                },
                ProcessingQuality.ULTRA: {
                    'window_size': 8192,
                    'overlap': 0.875,
                    'filter_order_max': 20,
                    'eq_bands_max': 15,
                    'noise_reduction_alpha': 3.0
                }
            }
            
            return parameter_map.get(quality, parameter_map[ProcessingQuality.MEDIUM])
            
        except Exception as e:
            logger.error(f"Parameter adaptation failed: {e}")
            return parameter_map[ProcessingQuality.MEDIUM]
