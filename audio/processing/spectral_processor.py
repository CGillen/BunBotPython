"""
Spectral domain audio processing using scipy.signal.

This module provides frequency domain analysis and processing capabilities
including FFT-based operations, spectral subtraction, and windowing functions.
"""

import logging
import time
from typing import Optional, Callable, Tuple
import numpy as np
from scipy import signal
from scipy.fft import fft, ifft, fftfreq

from audio.interfaces.advanced_interfaces import (
    ISpectralProcessor, SpectrumAnalysis, AudioBuffer
)

logger = logging.getLogger('audio.processing.spectral_processor')

class SpectralProcessor:
    """
    Spectral domain audio processing implementation.
    
    Provides FFT-based analysis and processing with configurable
    window functions and overlap settings.
    """
    
    def __init__(self, window_size: int = 2048, overlap: float = 0.5, window_type: str = "hann"):
        """
        Initialize spectral processor.
        
        Args:
            window_size: FFT window size (power of 2 recommended)
            overlap: Overlap ratio between windows (0.0 to 0.95)
            window_type: Window function type ('hann', 'hamming', 'blackman', etc.)
        """
        self.window_size = window_size
        self.overlap = max(0.0, min(0.95, overlap))
        self.window_type = window_type
        self.hop_size = int(window_size * (1 - overlap))
        
        # Pre-compute window function
        self._window = self._create_window(window_type, window_size)
        
        # Performance tracking
        self._processing_count = 0
        self._total_processing_time = 0.0
        
        logger.debug(f"SpectralProcessor initialized: window_size={window_size}, "
                    f"overlap={overlap}, window_type={window_type}")
    
    def analyze_spectrum(self, audio_data: np.ndarray, sample_rate: float) -> SpectrumAnalysis:
        """
        Analyze frequency content of audio using FFT.
        
        Args:
            audio_data: Time domain audio samples (1D array)
            sample_rate: Audio sample rate in Hz
            
        Returns:
            Spectral analysis results
        """
        try:
            start_time = time.perf_counter()
            
            if audio_data.ndim != 1:
                raise ValueError("Audio data must be 1D for spectral analysis")
            
            if len(audio_data) < self.window_size:
                # Zero-pad if audio is shorter than window
                padded_audio = np.zeros(self.window_size)
                padded_audio[:len(audio_data)] = audio_data
                audio_data = padded_audio
            
            # Apply window function
            windowed_audio = audio_data[:self.window_size] * self._window
            
            # Compute FFT
            spectrum = fft(windowed_audio)
            frequencies = fftfreq(self.window_size, 1/sample_rate)[:self.window_size//2]
            
            # Extract magnitude and phase (positive frequencies only)
            magnitudes = np.abs(spectrum[:self.window_size//2])
            phases = np.angle(spectrum[:self.window_size//2])
            
            # Update performance metrics
            processing_time = time.perf_counter() - start_time
            self._update_performance_metrics(processing_time)
            
            return SpectrumAnalysis(
                frequencies=frequencies,
                magnitudes=magnitudes,
                phases=phases,
                sample_rate=sample_rate,
                window_size=self.window_size,
                window_type=self.window_type
            )
            
        except Exception as e:
            logger.error(f"Spectral analysis failed: {e}")
            raise
    
    def process_spectrum(self, spectrum: np.ndarray, 
                        processing_func: Callable[[np.ndarray], np.ndarray]) -> np.ndarray:
        """
        Apply processing function in frequency domain.
        
        Args:
            spectrum: Complex frequency domain data
            processing_func: Function to apply to spectrum
            
        Returns:
            Processed spectrum
        """
        try:
            start_time = time.perf_counter()
            
            # Apply processing function
            processed_spectrum = processing_func(spectrum)
            
            # Update performance metrics
            processing_time = time.perf_counter() - start_time
            self._update_performance_metrics(processing_time)
            
            return processed_spectrum
            
        except Exception as e:
            logger.error(f"Spectrum processing failed: {e}")
            raise
    
    def spectral_subtraction(self, audio_data: np.ndarray, noise_profile: np.ndarray, 
                           alpha: float = 2.0) -> np.ndarray:
        """
        Perform noise reduction using spectral subtraction.
        
        Args:
            audio_data: Input audio samples
            noise_profile: Noise magnitude spectrum
            alpha: Subtraction factor (higher = more aggressive)
            
        Returns:
            Denoised audio samples
        """
        try:
            start_time = time.perf_counter()
            
            if len(audio_data) < self.window_size:
                # Process short audio directly
                return self._spectral_subtract_frame(audio_data, noise_profile, alpha)
            
            # Process audio in overlapping frames
            output_audio = np.zeros_like(audio_data)
            
            for i in range(0, len(audio_data) - self.window_size + 1, self.hop_size):
                frame = audio_data[i:i + self.window_size]
                processed_frame = self._spectral_subtract_frame(frame, noise_profile, alpha)
                
                # Overlap-add
                output_audio[i:i + self.window_size] += processed_frame * self._window
            
            # Update performance metrics
            processing_time = time.perf_counter() - start_time
            self._update_performance_metrics(processing_time)
            
            return output_audio
            
        except Exception as e:
            logger.error(f"Spectral subtraction failed: {e}")
            raise
    
    def stft(self, audio_data: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Compute Short-Time Fourier Transform.
        
        Args:
            audio_data: Input audio samples
            
        Returns:
            Tuple of (frequencies, times, STFT matrix)
        """
        try:
            frequencies, times, stft_matrix = signal.stft(
                audio_data,
                nperseg=self.window_size,
                noverlap=int(self.window_size * self.overlap),
                window=self.window_type
            )
            
            return frequencies, times, stft_matrix
            
        except Exception as e:
            logger.error(f"STFT computation failed: {e}")
            raise
    
    def istft(self, stft_matrix: np.ndarray, frequencies: np.ndarray, 
              times: np.ndarray) -> np.ndarray:
        """
        Compute Inverse Short-Time Fourier Transform.
        
        Args:
            stft_matrix: STFT matrix
            frequencies: Frequency array
            times: Time array
            
        Returns:
            Reconstructed audio samples
        """
        try:
            _, reconstructed_audio = signal.istft(
                stft_matrix,
                nperseg=self.window_size,
                noverlap=int(self.window_size * self.overlap),
                window=self.window_type
            )
            
            return reconstructed_audio
            
        except Exception as e:
            logger.error(f"ISTFT computation failed: {e}")
            raise
    
    def get_performance_stats(self) -> dict:
        """Get spectral processing performance statistics"""
        avg_processing_time = (
            self._total_processing_time / self._processing_count 
            if self._processing_count > 0 else 0.0
        )
        
        return {
            'processing_count': self._processing_count,
            'average_processing_time_ms': avg_processing_time * 1000,
            'total_processing_time_ms': self._total_processing_time * 1000,
            'window_size': self.window_size,
            'overlap': self.overlap,
            'hop_size': self.hop_size,
            'window_type': self.window_type
        }
    
    def _create_window(self, window_type: str, size: int) -> np.ndarray:
        """Create window function"""
        try:
            if window_type == "hann":
                return signal.windows.hann(size)
            elif window_type == "hamming":
                return signal.windows.hamming(size)
            elif window_type == "blackman":
                return signal.windows.blackman(size)
            elif window_type == "bartlett":
                return signal.windows.bartlett(size)
            elif window_type == "kaiser":
                return signal.windows.kaiser(size, beta=8.6)
            else:
                logger.warning(f"Unknown window type '{window_type}', using Hann")
                return signal.windows.hann(size)
                
        except Exception as e:
            logger.error(f"Failed to create window: {e}")
            # Fallback to rectangular window
            return np.ones(size)
    
    def _spectral_subtract_frame(self, frame: np.ndarray, noise_profile: np.ndarray, 
                                alpha: float) -> np.ndarray:
        """Apply spectral subtraction to a single frame"""
        # Apply window
        windowed_frame = frame * self._window[:len(frame)]
        
        # FFT
        spectrum = fft(windowed_frame, n=self.window_size)
        magnitude = np.abs(spectrum)
        phase = np.angle(spectrum)
        
        # Ensure noise profile matches spectrum size
        if len(noise_profile) != len(magnitude):
            # Interpolate noise profile to match spectrum size
            noise_profile = np.interp(
                np.linspace(0, 1, len(magnitude)),
                np.linspace(0, 1, len(noise_profile)),
                noise_profile
            )
        
        # Spectral subtraction
        subtracted_magnitude = magnitude - alpha * noise_profile
        
        # Prevent over-subtraction (keep minimum 10% of original)
        subtracted_magnitude = np.maximum(subtracted_magnitude, 0.1 * magnitude)
        
        # Reconstruct spectrum
        processed_spectrum = subtracted_magnitude * np.exp(1j * phase)
        
        # IFFT
        processed_frame = np.real(ifft(processed_spectrum))[:len(frame)]
        
        return processed_frame
    
    def _update_performance_metrics(self, processing_time: float) -> None:
        """Update performance tracking metrics"""
        self._processing_count += 1
        self._total_processing_time += processing_time


class SpectralAnalyzer:
    """
    Utility class for spectral analysis and visualization.
    
    Provides methods for computing various spectral features
    and analysis metrics.
    """
    
    @staticmethod
    def compute_spectral_centroid(spectrum: SpectrumAnalysis) -> float:
        """
        Compute spectral centroid (brightness measure).
        
        Args:
            spectrum: Spectral analysis results
            
        Returns:
            Spectral centroid in Hz
        """
        try:
            # Weighted average of frequencies
            total_magnitude = np.sum(spectrum.magnitudes)
            if total_magnitude == 0:
                return 0.0
            
            centroid = np.sum(spectrum.frequencies * spectrum.magnitudes) / total_magnitude
            return float(centroid)
            
        except Exception as e:
            logger.error(f"Spectral centroid computation failed: {e}")
            return 0.0
    
    @staticmethod
    def compute_spectral_rolloff(spectrum: SpectrumAnalysis, rolloff_percent: float = 0.85) -> float:
        """
        Compute spectral rolloff frequency.
        
        Args:
            spectrum: Spectral analysis results
            rolloff_percent: Percentage of total energy (0.0 to 1.0)
            
        Returns:
            Rolloff frequency in Hz
        """
        try:
            # Cumulative energy
            energy = spectrum.magnitudes ** 2
            cumulative_energy = np.cumsum(energy)
            total_energy = cumulative_energy[-1]
            
            if total_energy == 0:
                return 0.0
            
            # Find frequency where cumulative energy reaches rolloff percentage
            rolloff_energy = rolloff_percent * total_energy
            rolloff_index = np.argmax(cumulative_energy >= rolloff_energy)
            
            return float(spectrum.frequencies[rolloff_index])
            
        except Exception as e:
            logger.error(f"Spectral rolloff computation failed: {e}")
            return 0.0
    
    @staticmethod
    def compute_spectral_bandwidth(spectrum: SpectrumAnalysis) -> float:
        """
        Compute spectral bandwidth.
        
        Args:
            spectrum: Spectral analysis results
            
        Returns:
            Spectral bandwidth in Hz
        """
        try:
            centroid = SpectralAnalyzer.compute_spectral_centroid(spectrum)
            
            # Weighted variance around centroid
            total_magnitude = np.sum(spectrum.magnitudes)
            if total_magnitude == 0:
                return 0.0
            
            variance = np.sum(
                ((spectrum.frequencies - centroid) ** 2) * spectrum.magnitudes
            ) / total_magnitude
            
            return float(np.sqrt(variance))
            
        except Exception as e:
            logger.error(f"Spectral bandwidth computation failed: {e}")
            return 0.0
    
    @staticmethod
    def find_peaks(spectrum: SpectrumAnalysis, height_threshold: float = 0.1, 
                   distance: int = 10) -> Tuple[np.ndarray, np.ndarray]:
        """
        Find spectral peaks.
        
        Args:
            spectrum: Spectral analysis results
            height_threshold: Minimum peak height (relative to max)
            distance: Minimum distance between peaks
            
        Returns:
            Tuple of (peak_frequencies, peak_magnitudes)
        """
        try:
            # Normalize magnitudes
            max_magnitude = np.max(spectrum.magnitudes)
            if max_magnitude == 0:
                return np.array([]), np.array([])
            
            normalized_magnitudes = spectrum.magnitudes / max_magnitude
            
            # Find peaks
            peaks, _ = signal.find_peaks(
                normalized_magnitudes,
                height=height_threshold,
                distance=distance
            )
            
            peak_frequencies = spectrum.frequencies[peaks]
            peak_magnitudes = spectrum.magnitudes[peaks]
            
            return peak_frequencies, peak_magnitudes
            
        except Exception as e:
            logger.error(f"Peak finding failed: {e}")
            return np.array([]), np.array([])
