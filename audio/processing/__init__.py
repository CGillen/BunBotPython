"""
Advanced Audio Processing Components

This package provides high-performance audio processing implementations
including spectral analysis, parametric EQ, and quality management.
"""

from .spectral_processor import SpectralProcessor, SpectralAnalyzer
from .parametric_eq import ParametricEqualizer, EQPresets
from .advanced_processor import AdvancedAudioProcessor, AudioQualityManager

__all__ = [
    'SpectralProcessor',
    'SpectralAnalyzer', 
    'ParametricEqualizer',
    'EQPresets',
    'AdvancedAudioProcessor',
    'AudioQualityManager'
]
