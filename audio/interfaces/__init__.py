"""
Audio Processing Interfaces

This module exports both legacy and advanced interfaces to resolve import conflicts.
Legacy interfaces are imported from the parent interfaces.py file.
Advanced interfaces are imported from advanced_interfaces.py.
"""

# Import legacy interfaces from the parent interfaces.py file
import sys
import os
import importlib.util

# Load the legacy interfaces.py file directly to avoid circular imports
interfaces_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'interfaces.py')
spec = importlib.util.spec_from_file_location("legacy_interfaces", interfaces_path)
if spec is not None and spec.loader is not None:
    legacy_interfaces = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(legacy_interfaces)
    
    # Import legacy interfaces
    IAudioProcessor = legacy_interfaces.IAudioProcessor
    IVolumeManager = legacy_interfaces.IVolumeManager
    IEffectsChain = legacy_interfaces.IEffectsChain
    IAudioMixer = legacy_interfaces.IAudioMixer
    IStreamManager = legacy_interfaces.IStreamManager
    AudioConfig = legacy_interfaces.AudioConfig
    AudioStream = legacy_interfaces.AudioStream
    AudioMetrics = legacy_interfaces.AudioMetrics
    ProcessedAudioSource = legacy_interfaces.ProcessedAudioSource
    AudioQuality = legacy_interfaces.AudioQuality
    EffectType = legacy_interfaces.EffectType
    MixingMode = legacy_interfaces.MixingMode
    AudioFormat = legacy_interfaces.AudioFormat
    AUDIO_EVENTS = legacy_interfaces.AUDIO_EVENTS
else:
    # Fallback - create placeholder classes if import fails
    import logging
    logger = logging.getLogger(__name__)
    logger.warning("Failed to import legacy audio interfaces")
    
    class IAudioProcessor: pass
    class IVolumeManager: pass
    class IEffectsChain: pass
    class IAudioMixer: pass
    class IStreamManager: pass
    class AudioConfig: pass
    class AudioStream: pass
    class AudioMetrics: pass
    class ProcessedAudioSource: pass
    class AudioQuality: pass
    class EffectType: pass
    class MixingMode: pass
    class AudioFormat: pass
    AUDIO_EVENTS = {}

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
