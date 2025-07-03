"""
Advanced Audio Processing Interfaces

This module defines the core interfaces and protocols for the advanced audio processing system.
Follows hexagonal architecture principles with clear separation between domain logic and infrastructure.
"""

from abc import ABC, abstractmethod
from typing import Protocol, TypeVar, Generic, Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum
import numpy as np
from datetime import datetime

# Type variables for generic interfaces
T = TypeVar('T')
AudioDataType = TypeVar('AudioDataType', bound=np.ndarray)

class FilterType(Enum):
    """Supported digital filter types"""
    BUTTERWORTH = "butterworth"
    CHEBYSHEV_I = "chebyshev1"
    CHEBYSHEV_II = "chebyshev2"
    ELLIPTIC = "elliptic"
    BESSEL = "bessel"
    FIR = "fir"

class FilterResponse(Enum):
    """Filter frequency response types"""
    LOWPASS = "lowpass"
    HIGHPASS = "highpass"
    BANDPASS = "bandpass"
    BANDSTOP = "bandstop"
    PEAK = "peak"
    NOTCH = "notch"

class ProcessingQuality(Enum):
    """Audio processing quality levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    ULTRA = "ultra"

@dataclass(frozen=True)
class FilterSpecification:
    """
    Immutable value object for filter specifications.
    
    Encapsulates all parameters needed to design a digital filter.
    """
    filter_type: FilterType
    response_type: FilterResponse
    cutoff_frequencies: tuple[float, ...]
    sample_rate: float
    order: int
    ripple_db: float = 0.5
    attenuation_db: float = 60.0
    
    def __post_init__(self):
        """Validate filter specification parameters"""
        if self.sample_rate <= 0:
            raise ValueError("Sample rate must be positive")
        if self.order <= 0:
            raise ValueError("Filter order must be positive")
        if not self.cutoff_frequencies:
            raise ValueError("At least one cutoff frequency required")
        
        # Validate cutoff frequencies are within Nyquist limit
        nyquist = self.sample_rate / 2
        for freq in self.cutoff_frequencies:
            if freq <= 0 or freq >= nyquist:
                raise ValueError(f"Cutoff frequency {freq} must be between 0 and {nyquist} Hz")

@dataclass(frozen=True)
class FilterCoefficients:
    """
    Immutable value object for digital filter coefficients.
    
    Represents the numerator and denominator coefficients of a digital filter
    in the z-domain transfer function.
    """
    numerator: np.ndarray
    denominator: np.ndarray
    gain: float = 1.0
    
    def __post_init__(self):
        """Ensure immutability and validate coefficients"""
        if len(self.numerator) == 0 or len(self.denominator) == 0:
            raise ValueError("Filter coefficients cannot be empty")
        
        # Create immutable copies
        object.__setattr__(self, 'numerator', self.numerator.copy())
        object.__setattr__(self, 'denominator', self.denominator.copy())
        
        # Ensure denominator is normalized (first coefficient = 1)
        if self.denominator[0] != 1.0:
            norm_factor = self.denominator[0]
            object.__setattr__(self, 'numerator', self.numerator / norm_factor)
            object.__setattr__(self, 'denominator', self.denominator / norm_factor)

@dataclass(frozen=True)
class AudioBuffer:
    """
    Immutable audio buffer with comprehensive metadata.
    
    Represents a chunk of audio data with all necessary information
    for processing and routing.
    """
    data: np.ndarray
    sample_rate: float
    channels: int
    bit_depth: int
    timestamp: float
    buffer_id: Optional[str] = None
    
    def __post_init__(self):
        """Validate audio buffer parameters"""
        if self.data.ndim not in (1, 2):
            raise ValueError("Audio data must be 1D (mono) or 2D (multi-channel)")
        
        if self.data.ndim == 2 and self.data.shape[1] != self.channels:
            raise ValueError(f"Data shape {self.data.shape} doesn't match {self.channels} channels")
        
        if self.sample_rate <= 0:
            raise ValueError("Sample rate must be positive")
        
        if self.channels <= 0:
            raise ValueError("Channel count must be positive")
        
        if self.bit_depth not in (8, 16, 24, 32):
            raise ValueError("Bit depth must be 8, 16, 24, or 32")
        
        # Create immutable copy of audio data
        object.__setattr__(self, 'data', self.data.copy())
    
    @property
    def duration_seconds(self) -> float:
        """Calculate buffer duration in seconds"""
        return len(self.data) / self.sample_rate
    
    @property
    def is_mono(self) -> bool:
        """Check if audio is mono"""
        return self.channels == 1 or self.data.ndim == 1
    
    @property
    def is_stereo(self) -> bool:
        """Check if audio is stereo"""
        return self.channels == 2

@dataclass(frozen=True)
class FrequencyBand:
    """
    Represents a frequency band for parametric EQ processing.
    
    Encapsulates all parameters needed to define an EQ band.
    """
    center_frequency: float
    gain_db: float
    q_factor: float
    bandwidth: Optional[float] = None
    
    def __post_init__(self):
        """Validate frequency band parameters"""
        if self.center_frequency <= 0:
            raise ValueError("Center frequency must be positive")
        if self.q_factor <= 0:
            raise ValueError("Q factor must be positive")
        if abs(self.gain_db) > 24:
            raise ValueError("Gain must be between -24 and +24 dB")
    
    @property
    def low_frequency(self) -> float:
        """Calculate lower frequency bound"""
        if self.bandwidth:
            return self.center_frequency - (self.bandwidth / 2)
        else:
            # Calculate from Q factor
            return self.center_frequency / (1 + 1/(2*self.q_factor))
    
    @property
    def high_frequency(self) -> float:
        """Calculate upper frequency bound"""
        if self.bandwidth:
            return self.center_frequency + (self.bandwidth / 2)
        else:
            # Calculate from Q factor
            return self.center_frequency * (1 + 1/(2*self.q_factor))

@dataclass(frozen=True)
class SpectrumAnalysis:
    """
    Results of spectral analysis.
    
    Contains frequency domain representation and analysis metadata.
    """
    frequencies: np.ndarray
    magnitudes: np.ndarray
    phases: np.ndarray
    sample_rate: float
    window_size: int
    window_type: str = "hann"
    
    def __post_init__(self):
        """Validate spectrum analysis data"""
        if len(self.frequencies) != len(self.magnitudes) or len(self.frequencies) != len(self.phases):
            raise ValueError("Frequencies, magnitudes, and phases must have same length")
        
        # Create immutable copies
        object.__setattr__(self, 'frequencies', self.frequencies.copy())
        object.__setattr__(self, 'magnitudes', self.magnitudes.copy())
        object.__setattr__(self, 'phases', self.phases.copy())
    
    @property
    def frequency_resolution(self) -> float:
        """Calculate frequency resolution in Hz"""
        return self.sample_rate / self.window_size
    
    @property
    def magnitude_db(self) -> np.ndarray:
        """Get magnitude in dB scale"""
        return 20 * np.log10(np.maximum(self.magnitudes, 1e-10))

# Core Processing Interfaces

class IDigitalFilter(Protocol):
    """
    Interface for digital filter implementations.
    
    Defines the contract for all digital filter types including
    IIR and FIR filters.
    """
    
    def process(self, audio_data: np.ndarray) -> np.ndarray:
        """
        Process audio data through the filter.
        
        Args:
            audio_data: Input audio samples
            
        Returns:
            Filtered audio samples
        """
        ...
    
    def process_buffer(self, buffer: AudioBuffer) -> AudioBuffer:
        """
        Process an audio buffer through the filter.
        
        Args:
            buffer: Input audio buffer
            
        Returns:
            Filtered audio buffer
        """
        ...
    
    def get_frequency_response(self, frequencies: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """
        Get magnitude and phase response at specified frequencies.
        
        Args:
            frequencies: Frequency points in Hz
            
        Returns:
            Tuple of (magnitude, phase) responses
        """
        ...
    
    def reset_state(self) -> None:
        """Reset internal filter state for stateful filters"""
        ...
    
    @property
    def coefficients(self) -> FilterCoefficients:
        """Get filter coefficients"""
        ...

class IFilterDesigner(Protocol):
    """
    Interface for filter design strategies.
    
    Abstracts the filter design process to allow different
    implementation strategies (scipy, custom, etc.).
    """
    
    def design_filter(self, spec: FilterSpecification) -> FilterCoefficients:
        """
        Design filter coefficients from specification.
        
        Args:
            spec: Filter specification parameters
            
        Returns:
            Designed filter coefficients
        """
        ...
    
    def validate_specification(self, spec: FilterSpecification) -> bool:
        """
        Validate filter specification parameters.
        
        Args:
            spec: Filter specification to validate
            
        Returns:
            True if specification is valid
        """
        ...
    
    def estimate_filter_order(self, spec: FilterSpecification) -> int:
        """
        Estimate minimum filter order for given specifications.
        
        Args:
            spec: Filter specification
            
        Returns:
            Estimated minimum filter order
        """
        ...

class ISpectralProcessor(Protocol):
    """
    Interface for spectral domain processing.
    
    Defines operations for frequency domain analysis and processing.
    """
    
    def analyze_spectrum(self, audio_data: np.ndarray, sample_rate: float) -> SpectrumAnalysis:
        """
        Analyze frequency content of audio.
        
        Args:
            audio_data: Time domain audio samples
            sample_rate: Audio sample rate in Hz
            
        Returns:
            Spectral analysis results
        """
        ...
    
    def process_spectrum(self, spectrum: np.ndarray, processing_func: Callable[[np.ndarray], np.ndarray]) -> np.ndarray:
        """
        Apply processing function in frequency domain.
        
        Args:
            spectrum: Complex frequency domain data
            processing_func: Function to apply to spectrum
            
        Returns:
            Processed spectrum
        """
        ...
    
    def spectral_subtraction(self, audio_data: np.ndarray, noise_profile: np.ndarray, alpha: float = 2.0) -> np.ndarray:
        """
        Perform noise reduction using spectral subtraction.
        
        Args:
            audio_data: Input audio samples
            noise_profile: Noise magnitude spectrum
            alpha: Subtraction factor
            
        Returns:
            Denoised audio samples
        """
        ...

class IParametricEqualizer(Protocol):
    """
    Interface for parametric equalizer implementations.
    
    Defines operations for multi-band parametric EQ processing.
    """
    
    def add_band(self, band: FrequencyBand) -> int:
        """
        Add EQ band and return band ID.
        
        Args:
            band: Frequency band specification
            
        Returns:
            Band ID for future reference
        """
        ...
    
    def update_band(self, band_id: int, band: FrequencyBand) -> None:
        """
        Update existing EQ band parameters.
        
        Args:
            band_id: ID of band to update
            band: New band parameters
        """
        ...
    
    def remove_band(self, band_id: int) -> None:
        """
        Remove EQ band.
        
        Args:
            band_id: ID of band to remove
        """
        ...
    
    def process(self, audio_data: np.ndarray) -> np.ndarray:
        """
        Process audio through all EQ bands.
        
        Args:
            audio_data: Input audio samples
            
        Returns:
            EQ processed audio samples
        """
        ...
    
    def get_frequency_response(self, frequencies: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """
        Get combined frequency response of all bands.
        
        Args:
            frequencies: Frequency points in Hz
            
        Returns:
            Tuple of (magnitude, phase) responses
        """
        ...
    
    def reset(self) -> None:
        """Reset all EQ bands to flat response"""
        ...

class IAudioQualityManager(Protocol):
    """
    Interface for adaptive audio quality management.
    
    Manages dynamic quality adjustment based on system performance.
    """
    
    def get_optimal_quality(self, cpu_usage: float, memory_usage: float) -> ProcessingQuality:
        """
        Determine optimal processing quality based on system resources.
        
        Args:
            cpu_usage: Current CPU usage percentage (0-100)
            memory_usage: Current memory usage percentage (0-100)
            
        Returns:
            Recommended processing quality level
        """
        ...
    
    def adapt_processing_parameters(self, quality: ProcessingQuality) -> dict[str, Any]:
        """
        Get processing parameters for given quality level.
        
        Args:
            quality: Target quality level
            
        Returns:
            Dictionary of processing parameters
        """
        ...

# Domain Service Interfaces

class IFilterDesignService(Protocol):
    """
    Domain service for filter design operations.
    
    Provides high-level filter design operations with caching and optimization.
    """
    
    def get_or_create_filter(self, spec: FilterSpecification) -> IDigitalFilter:
        """
        Get cached filter or create new one.
        
        Args:
            spec: Filter specification
            
        Returns:
            Digital filter instance
        """
        ...
    
    def create_eq_filter_bank(self, bands: list[FrequencyBand], sample_rate: float) -> list[IDigitalFilter]:
        """
        Create filter bank for parametric EQ.
        
        Args:
            bands: List of frequency bands
            sample_rate: Audio sample rate
            
        Returns:
            List of filters for each band
        """
        ...
    
    def clear_cache(self) -> None:
        """Clear filter coefficient cache"""
        ...

class IAdvancedAudioProcessor(Protocol):
    """
    Main interface for advanced audio processing operations.
    
    Orchestrates all audio processing components.
    """
    
    def process_audio_buffer(self, buffer: AudioBuffer, guild_id: int) -> AudioBuffer:
        """
        Process audio buffer through complete processing pipeline.
        
        Args:
            buffer: Input audio buffer
            guild_id: Discord guild ID for settings
            
        Returns:
            Processed audio buffer
        """
        ...
    
    def get_equalizer(self, guild_id: int) -> IParametricEqualizer:
        """
        Get parametric equalizer for guild.
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            Parametric equalizer instance
        """
        ...
    
    def set_noise_profile(self, guild_id: int, noise_profile: np.ndarray) -> None:
        """
        Set noise profile for noise reduction.
        
        Args:
            guild_id: Discord guild ID
            noise_profile: Noise magnitude spectrum
        """
        ...
    
    def get_processing_stats(self, guild_id: int) -> dict[str, Any]:
        """
        Get processing statistics for guild.
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            Dictionary of processing statistics
        """
        ...

# Event interfaces for integration with existing event system

class AudioProcessingEvent:
    """Base class for audio processing events"""
    
    def __init__(self, guild_id: int, timestamp: Optional[float] = None):
        self.guild_id = guild_id
        self.timestamp = timestamp or datetime.now().timestamp()

class FilterAppliedEvent(AudioProcessingEvent):
    """Event fired when a filter is applied"""
    
    def __init__(self, guild_id: int, filter_type: str, parameters: dict[str, Any]):
        super().__init__(guild_id)
        self.filter_type = filter_type
        self.parameters = parameters

class EQBandUpdatedEvent(AudioProcessingEvent):
    """Event fired when an EQ band is updated"""
    
    def __init__(self, guild_id: int, band_id: int, band: FrequencyBand):
        super().__init__(guild_id)
        self.band_id = band_id
        self.band = band

class ProcessingQualityChangedEvent(AudioProcessingEvent):
    """Event fired when processing quality changes"""
    
    def __init__(self, guild_id: int, old_quality: ProcessingQuality, new_quality: ProcessingQuality, reason: str):
        super().__init__(guild_id)
        self.old_quality = old_quality
        self.new_quality = new_quality
        self.reason = reason
