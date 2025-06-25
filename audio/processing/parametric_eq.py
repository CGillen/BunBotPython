"""
Parametric equalizer implementation using digital filters.

This module provides multi-band parametric EQ with configurable
frequency bands, gain, and Q factor controls.
"""

import logging
import time
from typing import Dict, List, Optional, Tuple
import numpy as np
from scipy import signal

from audio.interfaces.advanced_interfaces import (
    IParametricEqualizer, FrequencyBand, AudioBuffer
)
from audio.filters.digital_filter import DigitalFilter, FilterBank
from audio.filters.design.filter_designer import ScipyFilterDesigner
from audio.interfaces.advanced_interfaces import (
    FilterSpecification, FilterType, FilterResponse
)

logger = logging.getLogger('audio.processing.parametric_eq')

class ParametricEqualizer:
    """
    Multi-band parametric equalizer implementation.
    
    Provides real-time EQ processing with configurable frequency bands.
    Each band can be independently controlled for frequency, gain, and Q factor.
    """
    
    def __init__(self, sample_rate: float = 48000):
        """
        Initialize parametric equalizer.
        
        Args:
            sample_rate: Audio sample rate in Hz
        """
        self.sample_rate = sample_rate
        self._bands: Dict[int, FrequencyBand] = {}
        self._filters: Dict[int, DigitalFilter] = {}
        self._filter_bank = FilterBank()
        self._filter_designer = ScipyFilterDesigner()
        
        # Band ID counter
        self._next_band_id = 1
        
        # Performance tracking
        self._processing_count = 0
        self._total_processing_time = 0.0
        
        logger.debug(f"ParametricEqualizer initialized at {sample_rate} Hz")
    
    def add_band(self, band: FrequencyBand) -> int:
        """
        Add EQ band and return band ID.
        
        Args:
            band: Frequency band specification
            
        Returns:
            Band ID for future reference
        """
        try:
            band_id = self._next_band_id
            self._next_band_id += 1
            
            # Store band configuration
            self._bands[band_id] = band
            
            # Create filter for this band
            filter_instance = self._create_band_filter(band)
            self._filters[band_id] = filter_instance
            self._filter_bank.add_filter(f"band_{band_id}", filter_instance)
            
            logger.debug(f"Added EQ band {band_id}: {band.center_frequency} Hz, "
                        f"{band.gain_db} dB, Q={band.q_factor}")
            
            return band_id
            
        except Exception as e:
            logger.error(f"Failed to add EQ band: {e}")
            raise
    
    def update_band(self, band_id: int, band: FrequencyBand) -> None:
        """
        Update existing EQ band parameters.
        
        Args:
            band_id: ID of band to update
            band: New band parameters
        """
        try:
            if band_id not in self._bands:
                raise ValueError(f"Band ID {band_id} not found")
            
            # Update band configuration
            self._bands[band_id] = band
            
            # Recreate filter with new parameters
            filter_instance = self._create_band_filter(band)
            self._filters[band_id] = filter_instance
            
            # Update filter bank
            self._filter_bank.remove_filter(f"band_{band_id}")
            self._filter_bank.add_filter(f"band_{band_id}", filter_instance)
            
            logger.debug(f"Updated EQ band {band_id}: {band.center_frequency} Hz, "
                        f"{band.gain_db} dB, Q={band.q_factor}")
            
        except Exception as e:
            logger.error(f"Failed to update EQ band {band_id}: {e}")
            raise
    
    def remove_band(self, band_id: int) -> None:
        """
        Remove EQ band.
        
        Args:
            band_id: ID of band to remove
        """
        try:
            if band_id not in self._bands:
                raise ValueError(f"Band ID {band_id} not found")
            
            # Remove from all collections
            del self._bands[band_id]
            del self._filters[band_id]
            self._filter_bank.remove_filter(f"band_{band_id}")
            
            logger.debug(f"Removed EQ band {band_id}")
            
        except Exception as e:
            logger.error(f"Failed to remove EQ band {band_id}: {e}")
            raise
    
    def process(self, audio_data: np.ndarray) -> np.ndarray:
        """
        Process audio through all EQ bands.
        
        Args:
            audio_data: Input audio samples
            
        Returns:
            EQ processed audio samples
        """
        try:
            start_time = time.perf_counter()
            
            if len(self._bands) == 0:
                return audio_data
            
            # Process through filter bank (series processing)
            processed_audio = self._filter_bank.process(audio_data, parallel=False)
            
            # Update performance metrics
            processing_time = time.perf_counter() - start_time
            self._update_performance_metrics(processing_time)
            
            return processed_audio
            
        except Exception as e:
            logger.error(f"EQ processing failed: {e}")
            raise
    
    def process_buffer(self, buffer: AudioBuffer) -> AudioBuffer:
        """
        Process audio buffer through EQ.
        
        Args:
            buffer: Input audio buffer
            
        Returns:
            EQ processed audio buffer
        """
        try:
            processed_data = self.process(buffer.data)
            
            return AudioBuffer(
                data=processed_data,
                sample_rate=buffer.sample_rate,
                channels=buffer.channels,
                bit_depth=buffer.bit_depth,
                timestamp=buffer.timestamp,
                buffer_id=buffer.buffer_id
            )
            
        except Exception as e:
            logger.error(f"EQ buffer processing failed: {e}")
            raise
    
    def get_frequency_response(self, frequencies: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Get combined frequency response of all bands.
        
        Args:
            frequencies: Frequency points in Hz
            
        Returns:
            Tuple of (magnitude, phase) responses
        """
        try:
            if len(self._bands) == 0:
                return np.ones_like(frequencies), np.zeros_like(frequencies)
            
            # Combine responses from all bands
            combined_magnitude = np.ones_like(frequencies, dtype=np.complex128)
            combined_phase = np.zeros_like(frequencies)
            
            for filter_instance in self._filters.values():
                mag, phase = filter_instance.get_frequency_response(frequencies)
                combined_magnitude *= mag * np.exp(1j * phase)
            
            final_magnitude = np.abs(combined_magnitude)
            final_phase = np.angle(combined_magnitude)
            
            return final_magnitude, final_phase
            
        except Exception as e:
            logger.error(f"Frequency response calculation failed: {e}")
            return np.ones_like(frequencies), np.zeros_like(frequencies)
    
    def reset(self) -> None:
        """Reset all EQ bands to flat response"""
        try:
            self._bands.clear()
            self._filters.clear()
            self._filter_bank = FilterBank()
            self._next_band_id = 1
            
            logger.debug("EQ reset to flat response")
            
        except Exception as e:
            logger.error(f"EQ reset failed: {e}")
            raise
    
    def get_band_count(self) -> int:
        """Get number of active EQ bands"""
        return len(self._bands)
    
    def get_band_ids(self) -> List[int]:
        """Get list of active band IDs"""
        return list(self._bands.keys())
    
    def get_band(self, band_id: int) -> Optional[FrequencyBand]:
        """Get band configuration by ID"""
        return self._bands.get(band_id)
    
    def get_performance_stats(self) -> dict:
        """Get EQ performance statistics"""
        avg_processing_time = (
            self._total_processing_time / self._processing_count 
            if self._processing_count > 0 else 0.0
        )
        
        return {
            'processing_count': self._processing_count,
            'average_processing_time_ms': avg_processing_time * 1000,
            'total_processing_time_ms': self._total_processing_time * 1000,
            'band_count': len(self._bands),
            'sample_rate': self.sample_rate
        }
    
    def _create_band_filter(self, band: FrequencyBand) -> DigitalFilter:
        """Create digital filter for EQ band"""
        try:
            # Determine filter type based on gain
            if abs(band.gain_db) < 0.1:
                # No gain change - create all-pass filter
                return self._create_allpass_filter()
            
            # Create peaking filter specification
            filter_spec = FilterSpecification(
                filter_type=FilterType.BUTTERWORTH,  # Use Butterworth for smooth response
                response_type=FilterResponse.PEAK,
                cutoff_frequencies=(band.center_frequency,),
                sample_rate=self.sample_rate,
                order=2,  # Second-order for peaking filters
                ripple_db=0.5,
                attenuation_db=60.0
            )
            
            # Design the filter
            coefficients = self._filter_designer.design_filter(filter_spec)
            
            # Apply gain adjustment to coefficients
            gain_linear = 10 ** (band.gain_db / 20)
            adjusted_coefficients = self._apply_peaking_gain(
                coefficients, band.center_frequency, band.q_factor, gain_linear
            )
            
            return DigitalFilter(adjusted_coefficients)
            
        except Exception as e:
            logger.error(f"Failed to create band filter: {e}")
            # Return all-pass filter as fallback
            return self._create_allpass_filter()
    
    def _create_allpass_filter(self) -> DigitalFilter:
        """Create all-pass filter (no effect)"""
        from audio.interfaces.advanced_interfaces import FilterCoefficients
        
        # All-pass filter: y[n] = x[n]
        coefficients = FilterCoefficients(
            numerator=np.array([1.0]),
            denominator=np.array([1.0]),
            gain=1.0
        )
        
        return DigitalFilter(coefficients)
    
    def _apply_peaking_gain(self, coefficients, center_freq: float, 
                           q_factor: float, gain_linear: float):
        """Apply peaking gain to filter coefficients"""
        try:
            # Design peaking filter using scipy
            # Convert to normalized frequency
            nyquist = self.sample_rate / 2
            normalized_freq = center_freq / nyquist
            
            # Ensure frequency is within valid range
            normalized_freq = max(0.001, min(0.999, normalized_freq))
            
            # Design peaking filter
            if gain_linear != 1.0:
                # Use scipy's iirpeak for peaking filters
                b, a = signal.iirpeak(normalized_freq, Q=q_factor)
                
                # Apply gain
                if gain_linear > 1.0:
                    # Boost
                    b = b * gain_linear
                else:
                    # Cut - invert the filter response
                    b = b / gain_linear
            else:
                # Unity gain - all-pass
                b, a = np.array([1.0]), np.array([1.0])
            
            from audio.interfaces.advanced_interfaces import FilterCoefficients
            return FilterCoefficients(numerator=b, denominator=a, gain=1.0)
            
        except Exception as e:
            logger.warning(f"Failed to apply peaking gain: {e}")
            return coefficients
    
    def _update_performance_metrics(self, processing_time: float) -> None:
        """Update performance tracking metrics"""
        self._processing_count += 1
        self._total_processing_time += processing_time


class EQPresets:
    """
    Predefined EQ presets for common audio scenarios.
    
    Provides factory methods for creating common EQ configurations.
    """
    
    @staticmethod
    def create_flat() -> List[FrequencyBand]:
        """Create flat EQ (no processing)"""
        return []
    
    @staticmethod
    def create_bass_boost() -> List[FrequencyBand]:
        """Create bass boost preset"""
        return [
            FrequencyBand(center_frequency=60.0, gain_db=6.0, q_factor=0.7),
            FrequencyBand(center_frequency=120.0, gain_db=4.0, q_factor=0.7),
            FrequencyBand(center_frequency=250.0, gain_db=2.0, q_factor=0.7)
        ]
    
    @staticmethod
    def create_vocal_enhance() -> List[FrequencyBand]:
        """Create vocal enhancement preset"""
        return [
            FrequencyBand(center_frequency=200.0, gain_db=-2.0, q_factor=0.5),  # Reduce muddiness
            FrequencyBand(center_frequency=1000.0, gain_db=3.0, q_factor=1.0),  # Presence
            FrequencyBand(center_frequency=3000.0, gain_db=4.0, q_factor=1.2),  # Clarity
            FrequencyBand(center_frequency=8000.0, gain_db=2.0, q_factor=0.8)   # Air
        ]
    
    @staticmethod
    def create_classical() -> List[FrequencyBand]:
        """Create classical music preset"""
        return [
            FrequencyBand(center_frequency=50.0, gain_db=2.0, q_factor=0.6),
            FrequencyBand(center_frequency=400.0, gain_db=-1.0, q_factor=0.8),
            FrequencyBand(center_frequency=2000.0, gain_db=1.0, q_factor=0.7),
            FrequencyBand(center_frequency=6000.0, gain_db=2.0, q_factor=0.9),
            FrequencyBand(center_frequency=12000.0, gain_db=3.0, q_factor=0.8)
        ]
    
    @staticmethod
    def create_rock() -> List[FrequencyBand]:
        """Create rock music preset"""
        return [
            FrequencyBand(center_frequency=80.0, gain_db=4.0, q_factor=0.8),
            FrequencyBand(center_frequency=250.0, gain_db=-2.0, q_factor=1.0),
            FrequencyBand(center_frequency=1500.0, gain_db=2.0, q_factor=0.9),
            FrequencyBand(center_frequency=4000.0, gain_db=3.0, q_factor=1.1),
            FrequencyBand(center_frequency=10000.0, gain_db=4.0, q_factor=0.7)
        ]
    
    @staticmethod
    def create_electronic() -> List[FrequencyBand]:
        """Create electronic music preset"""
        return [
            FrequencyBand(center_frequency=40.0, gain_db=5.0, q_factor=0.9),
            FrequencyBand(center_frequency=100.0, gain_db=3.0, q_factor=0.8),
            FrequencyBand(center_frequency=500.0, gain_db=-1.0, q_factor=0.6),
            FrequencyBand(center_frequency=2000.0, gain_db=1.0, q_factor=0.8),
            FrequencyBand(center_frequency=8000.0, gain_db=3.0, q_factor=1.0),
            FrequencyBand(center_frequency=16000.0, gain_db=2.0, q_factor=0.7)
        ]
    
    @staticmethod
    def get_preset_names() -> List[str]:
        """Get list of available preset names"""
        return [
            "flat",
            "bass_boost", 
            "vocal_enhance",
            "classical",
            "rock",
            "electronic"
        ]
    
    @staticmethod
    def get_preset(name: str) -> List[FrequencyBand]:
        """Get preset by name"""
        presets = {
            "flat": EQPresets.create_flat,
            "bass_boost": EQPresets.create_bass_boost,
            "vocal_enhance": EQPresets.create_vocal_enhance,
            "classical": EQPresets.create_classical,
            "rock": EQPresets.create_rock,
            "electronic": EQPresets.create_electronic
        }
        
        preset_func = presets.get(name.lower())
        if preset_func:
            return preset_func()
        else:
            logger.warning(f"Unknown EQ preset: {name}")
            return EQPresets.create_flat()
    
    @staticmethod
    def get_all_presets() -> Dict[str, List[FrequencyBand]]:
        """Get all available presets as a dictionary"""
        return {
            "flat": EQPresets.create_flat(),
            "bass_boost": EQPresets.create_bass_boost(),
            "vocal_enhance": EQPresets.create_vocal_enhance(),
            "classical": EQPresets.create_classical(),
            "rock": EQPresets.create_rock(),
            "electronic": EQPresets.create_electronic()
        }
