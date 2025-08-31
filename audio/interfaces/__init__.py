"""
Audio Processing Interfaces

This module exports both legacy and advanced interfaces to resolve import conflicts.
Legacy interfaces are imported from the parent audio module to ensure single source of truth.
Advanced interfaces are imported from advanced_interfaces.py.
"""

# Import legacy interfaces from parent audio module to ensure same objects
# This eliminates the duplicate module creation issue
from .. import (
    IAudioProcessor, IVolumeManager, IEffectsChain, IAudioMixer,
    AudioConfig, AudioStream, AudioMetrics, ProcessedAudioSource,
    AudioQuality, EffectType, MixingMode
)

# Import AUDIO_EVENTS separately to avoid circular imports
import importlib.util
import os
interfaces_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'interfaces.py')
spec = importlib.util.spec_from_file_location("audio_interfaces", interfaces_path)
if spec is not None and spec.loader is not None:
    audio_interfaces = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audio_interfaces)
    AUDIO_EVENTS = audio_interfaces.AUDIO_EVENTS
    # Import additional items that might not be in parent __init__.py
    try:
        IStreamManager = audio_interfaces.IStreamManager
        AudioFormat = audio_interfaces.AudioFormat
    except AttributeError:
        # Create fallbacks if not available
        class IStreamManager: pass
        class AudioFormat: pass
else:
    AUDIO_EVENTS = {}
    class IStreamManager: pass
    class AudioFormat: pass

# Import advanced interfaces
from .advanced_interfaces import (
    # Enums
    FilterType, FilterResponse, ProcessingQuality,
    
    # Value Objects
    FilterSpecification, FilterCoefficients, AudioBuffer, 
    FrequencyBand, SpectrumAnalysis,
    
    # Advanced Interfaces (prefixed to avoid conflicts)
    IDigitalFilter, IFilterDesigner, ISpectralProcessor,
    IParametricEqualizer, IAudioQualityManager,
    IFilterDesignService, IAdvancedAudioProcessor,
    
    # Events
    AudioProcessingEvent, FilterAppliedEvent, 
    EQBandUpdatedEvent, ProcessingQualityChangedEvent
)

__all__ = [
    # Legacy Interfaces
    'IAudioProcessor', 'IVolumeManager', 'IEffectsChain', 'IAudioMixer', 'IStreamManager',
    
    # Legacy Data Classes
    'AudioConfig', 'AudioStream', 'AudioMetrics', 'ProcessedAudioSource',
    
    # Legacy Enums
    'AudioQuality', 'EffectType', 'MixingMode', 'AudioFormat',
    
    # Legacy Constants
    'AUDIO_EVENTS',
    
    # Advanced Enums
    'FilterType', 'FilterResponse', 'ProcessingQuality',
    
    # Advanced Value Objects
    'FilterSpecification', 'FilterCoefficients', 'AudioBuffer', 
    'FrequencyBand', 'SpectrumAnalysis',
    
    # Advanced Interfaces
    'IDigitalFilter', 'IFilterDesigner', 'ISpectralProcessor',
    'IParametricEqualizer', 'IAudioQualityManager',
    'IFilterDesignService', 'IAdvancedAudioProcessor',
    
    # Advanced Events
    'AudioProcessingEvent', 'FilterAppliedEvent', 
    'EQBandUpdatedEvent', 'ProcessingQualityChangedEvent'
]
