"""
Audio Processing System for BunBot

Provides advanced audio processing capabilities including volume normalization,
real-time effects, multi-stream mixing, and enhanced audio quality management.
Built on the core infrastructure for seamless integration.

Key Components:
- Audio processing pipeline with real-time controls
- Volume normalization and dynamic range management
- Audio effects chain (EQ, crossfading, ducking)
- Multi-stream mixing with priority management
- Performance monitoring and quality adaptation
- Advanced digital filter system with scipy integration
- Professional-grade spectral processing

Architecture:
- Built on core ServiceRegistry, StateManager, EventBus, and ConfigurationManager
- Real-time audio processing with minimal latency
- Per-guild audio configuration and state management
- Integration with Discord.py voice capabilities
- Event-driven audio control and monitoring
- Modular and scalable filter design system
"""

# Legacy interfaces (maintain backward compatibility)
# Import from the interfaces.py file using importlib to avoid directory conflict
try:
    import importlib.util
    import os
    
    # Load the interfaces.py file directly
    interfaces_path = os.path.join(os.path.dirname(__file__), 'interfaces.py')
    spec = importlib.util.spec_from_file_location("legacy_interfaces", interfaces_path)
    if spec is None or spec.loader is None:
        raise ImportError("Could not load interfaces.py")
    legacy_interfaces = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(legacy_interfaces)
    
    # Import the classes
    AudioConfig = legacy_interfaces.AudioConfig
    AudioStream = legacy_interfaces.AudioStream
    AudioMetrics = legacy_interfaces.AudioMetrics
    ProcessedAudioSource = legacy_interfaces.ProcessedAudioSource
    IAudioProcessor = legacy_interfaces.IAudioProcessor
    IVolumeManager = legacy_interfaces.IVolumeManager
    IEffectsChain = legacy_interfaces.IEffectsChain
    IAudioMixer = legacy_interfaces.IAudioMixer
    AudioQuality = legacy_interfaces.AudioQuality
    EffectType = legacy_interfaces.EffectType
    MixingMode = legacy_interfaces.MixingMode
    
except Exception as e:
    # Fallback - create placeholder interfaces if import fails
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"Failed to import legacy audio interfaces: {e}")
    
    # Create minimal placeholder classes
    class AudioConfig: pass
    class AudioStream: pass  
    class ProcessedAudioSource: pass
    class IAudioProcessor: pass
    class IVolumeManager: pass
    class IEffectsChain: pass
    class IAudioMixer: pass
    class AudioQuality: pass
    class EffectType: pass
    class MixingMode: pass

# Advanced interfaces (new scipy-based system)
from .interfaces.advanced_interfaces import (
    FilterType, FilterResponse, ProcessingQuality,
    FilterSpecification, FilterCoefficients, AudioBuffer, 
    FrequencyBand, SpectrumAnalysis,
    IDigitalFilter, IFilterDesigner, ISpectralProcessor,
    IParametricEqualizer, IAudioQualityManager,
    IFilterDesignService, IAdvancedAudioProcessor
)

# Filter system
from .filters import ScipyFilterDesigner, FilterDesignService, DigitalFilter, FilterBank

# Processing system
from .processing import (
    SpectralProcessor, SpectralAnalyzer, ParametricEqualizer, EQPresets,
    AdvancedAudioProcessor, AudioQualityManager
)

# Legacy implementations
from .audio_processor import AudioProcessor
from .volume_manager import VolumeManager
from .effects_chain import EffectsChain
from .mixer import AudioMixer
from .stream_manager import StreamManager

__all__ = [
    # Legacy Configuration and Data Classes
    'AudioConfig',
    'AudioStream',
    'AudioMetrics',
    'ProcessedAudioSource',
    'AudioQuality',
    'EffectType',
    'MixingMode',
    
    # Legacy Interfaces
    'IAudioProcessor',
    'IVolumeManager', 
    'IEffectsChain',
    'IAudioMixer',
    
    # Advanced Enums
    'FilterType', 
    'FilterResponse', 
    'ProcessingQuality',
    
    # Advanced Value Objects
    'FilterSpecification', 
    'FilterCoefficients', 
    'AudioBuffer', 
    'FrequencyBand', 
    'SpectrumAnalysis',
    
    # Advanced Interfaces
    'IDigitalFilter', 
    'IFilterDesigner', 
    'ISpectralProcessor',
    'IParametricEqualizer', 
    'IAudioQualityManager',
    'IFilterDesignService', 
    'IAdvancedAudioProcessor',
    
    # Filter System
    'ScipyFilterDesigner',
    'FilterDesignService',
    'DigitalFilter',
    'FilterBank',
    
    # Processing System
    'SpectralProcessor',
    'SpectralAnalyzer',
    'ParametricEqualizer',
    'EQPresets',
    'AdvancedAudioProcessor',
    'AudioQualityManager',
    
    # Legacy Implementations
    'AudioProcessor',
    'VolumeManager',
    'EffectsChain',
    'AudioMixer',
    'StreamManager'
]
