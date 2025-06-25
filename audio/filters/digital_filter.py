"""
High-performance digital filter implementation using scipy.signal.

This module provides professional-grade digital filter processing
with stateful operation and comprehensive error handling.
"""

import logging
import time
from typing import Optional, Tuple
import numpy as np
from scipy import signal

from audio.interfaces.advanced_interfaces import (
    IDigitalFilter, FilterCoefficients, AudioBuffer
)
from .exceptions import FilterProcessingError

logger = logging.getLogger('audio.filters.digital_filter')

class DigitalFilter:
    """
    High-performance digital filter implementation.
    
    Provides stateful digital filtering with support for both IIR and FIR filters.
    Optimized for real-time audio processing with minimal latency.
    """
    
    def __init__(self, coefficients: FilterCoefficients):
        """
        Initialize digital filter with coefficients.
        
        Args:
            coefficients: Filter coefficients (numerator and denominator)
        """
        self._coefficients = coefficients
        self._state = None
        self._is_fir = len(coefficients.denominator) == 1 and coefficients.denominator[0] == 1.0
        self._reset_state()
        
        # Performance tracking
        self._processing_count = 0
        self._total_processing_time = 0.0
        
        logger.debug(f"Initialized {'FIR' if self._is_fir else 'IIR'} filter "
                    f"(order: {len(coefficients.numerator)-1})")
    
    def process(self, audio_data: np.ndarray) -> np.ndarray:
        """
        Process audio data through the filter.
        
        Args:
            audio_data: Input audio samples (1D or 2D array)
            
        Returns:
            Filtered audio samples
            
        Raises:
            FilterProcessingError: If processing fails
        """
        try:
            start_time = time.perf_counter()
            
            if audio_data.size == 0:
                return audio_data
            
            # Handle different input shapes
            if audio_data.ndim == 1:
                result = self._process_mono(audio_data)
            elif audio_data.ndim == 2:
                result = self._process_multichannel(audio_data)
            else:
                raise FilterProcessingError(f"Unsupported audio data shape: {audio_data.shape}")
            
            # Update performance metrics
            processing_time = time.perf_counter() - start_time
            self._update_performance_metrics(processing_time)
            
            return result
            
        except FilterProcessingError:
            raise
        except Exception as e:
            logger.error(f"Filter processing failed: {e}")
            raise FilterProcessingError(f"Filter processing error: {e}") from e
    
    def process_buffer(self, buffer: AudioBuffer) -> AudioBuffer:
        """
        Process an audio buffer through the filter.
        
        Args:
            buffer: Input audio buffer
            
        Returns:
            Filtered audio buffer with same metadata
        """
        try:
            filtered_data = self.process(buffer.data)
            
            return AudioBuffer(
                data=filtered_data,
                sample_rate=buffer.sample_rate,
                channels=buffer.channels,
                bit_depth=buffer.bit_depth,
                timestamp=buffer.timestamp,
                buffer_id=buffer.buffer_id
            )
            
        except Exception as e:
            logger.error(f"Buffer processing failed: {e}")
            raise FilterProcessingError(f"Buffer processing error: {e}") from e
    
    def get_frequency_response(self, frequencies: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Get magnitude and phase response at specified frequencies.
        
        Args:
            frequencies: Frequency points in Hz (requires sample rate context)
            
        Returns:
            Tuple of (magnitude, phase) responses
        """
        try:
            # Calculate frequency response at specified number of points
            w, h = signal.freqz(
                self._coefficients.numerator,
                self._coefficients.denominator,
                worN=len(frequencies),
                whole=False
            )
            
            magnitude = np.abs(h) * self._coefficients.gain
            phase = np.angle(h)
            
            return magnitude, phase
            
        except Exception as e:
            logger.error(f"Frequency response calculation failed: {e}")
            # Return flat response as fallback
            return np.ones_like(frequencies), np.zeros_like(frequencies)
    
    def reset_state(self) -> None:
        """Reset internal filter state for stateful filters"""
        self._reset_state()
        logger.debug("Filter state reset")
    
    @property
    def coefficients(self) -> FilterCoefficients:
        """Get filter coefficients"""
        return self._coefficients
    
    def get_performance_stats(self) -> dict:
        """Get filter performance statistics"""
        avg_processing_time = (
            self._total_processing_time / self._processing_count 
            if self._processing_count > 0 else 0.0
        )
        
        return {
            'processing_count': self._processing_count,
            'average_processing_time_ms': avg_processing_time * 1000,
            'total_processing_time_ms': self._total_processing_time * 1000,
            'is_fir': self._is_fir,
            'filter_order': len(self._coefficients.numerator) - 1
        }
    
    def _process_mono(self, audio_data: np.ndarray) -> np.ndarray:
        """Process mono audio data"""
        if self._is_fir:
            # FIR filter - no state needed for scipy.lfilter
            filtered_data = signal.lfilter(
                self._coefficients.numerator,
                self._coefficients.denominator,
                audio_data
            )
        else:
            # IIR filter - use state for continuous processing
            filtered_data, self._state = signal.lfilter(
                self._coefficients.numerator,
                self._coefficients.denominator,
                audio_data,
                zi=self._state
            )
        
        return filtered_data * self._coefficients.gain
    
    def _process_multichannel(self, audio_data: np.ndarray) -> np.ndarray:
        """Process multi-channel audio data"""
        num_channels = audio_data.shape[1]
        filtered_channels = []
        
        for channel in range(num_channels):
            channel_data = audio_data[:, channel]
            filtered_channel = self._process_mono(channel_data)
            filtered_channels.append(filtered_channel)
        
        return np.column_stack(filtered_channels)
    
    def _reset_state(self) -> None:
        """Initialize filter state for IIR filters"""
        if not self._is_fir and len(self._coefficients.denominator) > 1:
            # Initialize state for IIR filter
            self._state = signal.lfiltic(
                self._coefficients.numerator,
                self._coefficients.denominator,
                y=[0.0] * (len(self._coefficients.denominator) - 1)
            )
        else:
            self._state = None
    
    def _update_performance_metrics(self, processing_time: float) -> None:
        """Update performance tracking metrics"""
        self._processing_count += 1
        self._total_processing_time += processing_time


class FilterBank:
    """
    Collection of digital filters for parallel processing.
    
    Useful for implementing parametric EQ with multiple bands
    or other multi-filter applications.
    """
    
    def __init__(self):
        """Initialize empty filter bank"""
        self._filters: dict[str, DigitalFilter] = {}
        self._processing_order: list[str] = []
        
        logger.debug("FilterBank initialized")
    
    def add_filter(self, filter_id: str, filter_instance: DigitalFilter) -> None:
        """
        Add filter to the bank.
        
        Args:
            filter_id: Unique identifier for the filter
            filter_instance: Digital filter instance
        """
        self._filters[filter_id] = filter_instance
        if filter_id not in self._processing_order:
            self._processing_order.append(filter_id)
        
        logger.debug(f"Added filter '{filter_id}' to bank")
    
    def remove_filter(self, filter_id: str) -> bool:
        """
        Remove filter from the bank.
        
        Args:
            filter_id: Filter identifier to remove
            
        Returns:
            True if filter was removed, False if not found
        """
        if filter_id in self._filters:
            del self._filters[filter_id]
            if filter_id in self._processing_order:
                self._processing_order.remove(filter_id)
            logger.debug(f"Removed filter '{filter_id}' from bank")
            return True
        return False
    
    def process(self, audio_data: np.ndarray, parallel: bool = False) -> np.ndarray:
        """
        Process audio through all filters in the bank.
        
        Args:
            audio_data: Input audio samples
            parallel: If True, process filters in parallel and sum results.
                     If False, process filters in series.
            
        Returns:
            Processed audio samples
        """
        try:
            if not self._filters:
                return audio_data
            
            if parallel:
                return self._process_parallel(audio_data)
            else:
                return self._process_series(audio_data)
                
        except Exception as e:
            logger.error(f"FilterBank processing failed: {e}")
            raise FilterProcessingError(f"FilterBank processing error: {e}") from e
    
    def reset_all_states(self) -> None:
        """Reset state for all filters in the bank"""
        for filter_instance in self._filters.values():
            filter_instance.reset_state()
        logger.debug("Reset all filter states in bank")
    
    def get_filter_count(self) -> int:
        """Get number of filters in the bank"""
        return len(self._filters)
    
    def get_filter_ids(self) -> list[str]:
        """Get list of filter IDs in processing order"""
        return self._processing_order.copy()
    
    def _process_series(self, audio_data: np.ndarray) -> np.ndarray:
        """Process filters in series (cascaded)"""
        processed_data = audio_data.copy()
        
        for filter_id in self._processing_order:
            if filter_id in self._filters:
                processed_data = self._filters[filter_id].process(processed_data)
        
        return processed_data
    
    def _process_parallel(self, audio_data: np.ndarray) -> np.ndarray:
        """Process filters in parallel and sum results"""
        if not self._filters:
            return audio_data
        
        # Process each filter and accumulate results
        accumulated_result = np.zeros_like(audio_data, dtype=np.float64)
        
        for filter_id in self._processing_order:
            if filter_id in self._filters:
                filter_result = self._filters[filter_id].process(audio_data)
                accumulated_result += filter_result.astype(np.float64)
        
        # Average the results to prevent clipping
        final_result = accumulated_result / len(self._filters)
        
        # Convert back to original dtype
        return final_result.astype(audio_data.dtype)
