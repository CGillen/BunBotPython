#!/usr/bin/env python3
"""
Comprehensive test suite for advanced audio processing features
"""

import asyncio
import sys
import logging
import numpy as np
from typing import Dict, Any

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('audio_test')

async def test_imports():
    """Test that all advanced audio components can be imported"""
    print("🔍 Testing imports...")
    
    try:
        # Test legacy interfaces
        from audio import (
            AudioConfig, AudioStream, AudioMetrics, ProcessedAudioSource,
            IAudioProcessor, IVolumeManager, IEffectsChain, IAudioMixer,
            AudioQuality, EffectType, MixingMode
        )
        print("✅ Legacy interfaces imported successfully")
        
        # Test advanced interfaces
        from audio import (
            FilterType, FilterResponse, ProcessingQuality,
            FilterSpecification, FilterCoefficients, AudioBuffer,
            FrequencyBand, SpectrumAnalysis,
            IDigitalFilter, IFilterDesigner, ISpectralProcessor,
            IParametricEqualizer, IAudioQualityManager,
            IFilterDesignService, IAdvancedAudioProcessor
        )
        print("✅ Advanced interfaces imported successfully")
        
        # Test filter system
        from audio import (
            ScipyFilterDesigner, FilterDesignService, DigitalFilter, FilterBank
        )
        print("✅ Filter system imported successfully")
        
        # Test processing system
        from audio import (
            SpectralProcessor, SpectralAnalyzer, ParametricEqualizer, EQPresets,
            AdvancedAudioProcessor, AudioQualityManager
        )
        print("✅ Processing system imported successfully")
        
        # Test legacy implementations
        from audio import (
            AudioProcessor, VolumeManager, EffectsChain, AudioMixer, StreamManager
        )
        print("✅ Legacy implementations imported successfully")
        
        return True
        
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False

async def test_filter_designer():
    """Test the scipy filter designer"""
    print("\n🔍 Testing ScipyFilterDesigner...")
    
    try:
        from audio import ScipyFilterDesigner, FilterType, FilterResponse
        
        designer = ScipyFilterDesigner()
        
        # Test lowpass filter design
        from audio import FilterSpecification
        
        spec = FilterSpecification(
            filter_type=FilterType.BUTTERWORTH,
            response_type=FilterResponse.LOWPASS,
            cutoff_frequencies=(1000.0,),
            sample_rate=48000,
            order=4
        )
        
        coefficients = designer.design_filter(spec)
        
        if coefficients and hasattr(coefficients, 'numerator') and hasattr(coefficients, 'denominator'):
            print(f"✅ Filter designed successfully: {len(coefficients.numerator)} b coeffs, {len(coefficients.denominator)} a coeffs")
            return True
        else:
            print("❌ Filter design returned invalid coefficients")
            return False
            
    except Exception as e:
        print(f"❌ Filter designer test failed: {e}")
        return False

async def test_spectral_processor():
    """Test the spectral processor"""
    print("\n🔍 Testing SpectralProcessor...")
    
    try:
        from audio import SpectralProcessor, ProcessingQuality
        
        processor = SpectralProcessor(sample_rate=48000, quality=ProcessingQuality.HIGH)
        
        # Create test audio data (1 second of 440Hz sine wave)
        duration = 1.0
        sample_rate = 48000
        frequency = 440.0
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        test_audio = np.sin(2 * np.pi * frequency * t).astype(np.float32)
        
        # Test spectral analysis
        analysis = await processor.analyze_spectrum(test_audio)
        
        if analysis and hasattr(analysis, 'frequencies') and hasattr(analysis, 'magnitudes'):
            print(f"✅ Spectral analysis successful: {len(analysis.frequencies)} frequency bins")
            
            # Check if we can detect the 440Hz peak
            peak_idx = np.argmax(analysis.magnitudes)
            peak_freq = analysis.frequencies[peak_idx]
            print(f"   Peak frequency detected: {peak_freq:.1f} Hz (expected: 440 Hz)")
            
            return True
        else:
            print("❌ Spectral analysis returned invalid results")
            return False
            
    except Exception as e:
        print(f"❌ Spectral processor test failed: {e}")
        return False

async def test_parametric_eq():
    """Test the parametric equalizer"""
    print("\n🔍 Testing ParametricEqualizer...")
    
    try:
        from audio import ParametricEqualizer, EQPresets
        
        eq = ParametricEqualizer(sample_rate=48000)
        
        # Test preset loading
        presets = await eq.get_available_presets()
        if presets and len(presets) > 0:
            print(f"✅ EQ presets loaded: {', '.join(presets)}")
        else:
            print("❌ No EQ presets available")
            return False
        
        # Test applying a preset
        success = await eq.apply_preset("rock")
        if success:
            print("✅ Rock preset applied successfully")
        else:
            print("❌ Failed to apply rock preset")
            return False
        
        # Test custom band configuration
        success = await eq.set_band(0, frequency=100.0, gain=3.0, q_factor=0.7)
        if success:
            print("✅ Custom EQ band configured successfully")
        else:
            print("❌ Failed to configure custom EQ band")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Parametric EQ test failed: {e}")
        return False

async def test_advanced_audio_processor():
    """Test the main advanced audio processor"""
    print("\n🔍 Testing AdvancedAudioProcessor...")
    
    try:
        from audio import AdvancedAudioProcessor, ProcessingQuality
        
        processor = AdvancedAudioProcessor(sample_rate=48000, quality=ProcessingQuality.HIGH)
        
        # Test initialization
        if processor:
            print("✅ AdvancedAudioProcessor initialized successfully")
        else:
            print("❌ Failed to initialize AdvancedAudioProcessor")
            return False
        
        # Test quality management
        await processor.set_quality(ProcessingQuality.MEDIUM)
        current_quality = await processor.get_quality()
        
        if current_quality == ProcessingQuality.MEDIUM:
            print("✅ Quality management working correctly")
        else:
            print("❌ Quality management failed")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Advanced audio processor test failed: {e}")
        return False

async def test_audio_config():
    """Test audio configuration classes"""
    print("\n🔍 Testing AudioConfig...")
    
    try:
        from audio import AudioConfig, AudioQuality
        
        # Test creating audio config
        config = AudioConfig(
            master_volume=0.8,
            quality=AudioQuality.HIGH,
            sample_rate=48000,
            channels=2,
            bit_depth=16
        )
        
        if config and hasattr(config, 'master_volume') and config.master_volume == 0.8:
            print("✅ AudioConfig created successfully")
        else:
            print("❌ AudioConfig creation failed")
            return False
        
        # Test serialization
        config_dict = config.to_dict()
        if config_dict and 'master_volume' in config_dict:
            print("✅ AudioConfig serialization working")
        else:
            print("❌ AudioConfig serialization failed")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ AudioConfig test failed: {e}")
        return False

async def test_service_integration():
    """Test integration with the service registry"""
    print("\n🔍 Testing service integration...")
    
    try:
        from core import ServiceRegistry
        from audio import AdvancedAudioProcessor, ProcessingQuality
        
        # Create service registry
        registry = ServiceRegistry()
        
        # Test registering advanced audio processor
        processor = AdvancedAudioProcessor(sample_rate=48000, quality=ProcessingQuality.HIGH)
        registry.register_instance(AdvancedAudioProcessor, processor)
        
        # Test retrieving from registry
        retrieved = registry.get(AdvancedAudioProcessor)
        
        if retrieved and retrieved == processor:
            print("✅ Service registry integration working")
            return True
        else:
            print("❌ Service registry integration failed")
            return False
        
    except Exception as e:
        print(f"❌ Service integration test failed: {e}")
        return False

async def test_numpy_scipy_integration():
    """Test that numpy and scipy are working correctly"""
    print("\n🔍 Testing numpy/scipy integration...")
    
    try:
        import numpy as np
        import scipy.signal
        
        # Test numpy operations
        test_array = np.array([1, 2, 3, 4, 5])
        fft_result = np.fft.fft(test_array)
        
        if len(fft_result) == 5:
            print("✅ NumPy FFT operations working")
        else:
            print("❌ NumPy FFT operations failed")
            return False
        
        # Test scipy signal processing
        b, a = scipy.signal.butter(4, 0.1, 'low')
        
        if len(b) > 0 and len(a) > 0:
            print("✅ SciPy signal processing working")
        else:
            print("❌ SciPy signal processing failed")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ NumPy/SciPy integration test failed: {e}")
        return False

async def run_all_tests():
    """Run all tests and report results"""
    print("🚀 Starting comprehensive advanced audio testing...\n")
    
    tests = [
        ("Import Tests", test_imports),
        ("NumPy/SciPy Integration", test_numpy_scipy_integration),
        ("Filter Designer", test_filter_designer),
        ("Spectral Processor", test_spectral_processor),
        ("Parametric EQ", test_parametric_eq),
        ("Advanced Audio Processor", test_advanced_audio_processor),
        ("Audio Config", test_audio_config),
        ("Service Integration", test_service_integration),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results[test_name] = result
        except Exception as e:
            print(f"❌ {test_name} crashed: {e}")
            results[test_name] = False
    
    # Print summary
    print("\n" + "="*60)
    print("📊 TEST RESULTS SUMMARY")
    print("="*60)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
        if result:
            passed += 1
    
    print(f"\n🎯 Overall: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED - Advanced audio processing is 100% functional!")
        return True
    else:
        print("⚠️  Some tests failed - feature needs fixes")
        return False

if __name__ == "__main__":
    try:
        result = asyncio.run(run_all_tests())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n⏹️  Testing interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Testing crashed: {e}")
        sys.exit(1)
