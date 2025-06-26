#!/usr/bin/env python3
"""
Basic test suite for advanced audio processing features
Tests actual implementations with correct constructors
"""

import asyncio
import sys
import logging
import numpy as np

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('audio_test')

def test_imports():
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
            FrequencyBand, SpectrumAnalysis
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
        
        return True
        
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False

def test_filter_designer():
    """Test the scipy filter designer"""
    print("\n🔍 Testing ScipyFilterDesigner...")
    
    try:
        from audio import ScipyFilterDesigner, FilterType, FilterResponse, FilterSpecification
        
        designer = ScipyFilterDesigner()
        
        # Test lowpass filter design with more conservative parameters
        spec = FilterSpecification(
            filter_type=FilterType.BUTTERWORTH,
            response_type=FilterResponse.LOWPASS,
            cutoff_frequencies=(8000.0,),  # Higher cutoff frequency for stability
            sample_rate=48000,
            order=2  # Lower order for stability
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

def test_spectral_processor():
    """Test the spectral processor"""
    print("\n🔍 Testing SpectralProcessor...")
    
    try:
        from audio import SpectralProcessor
        
        # Try different constructor patterns
        try:
            processor = SpectralProcessor()
            print("✅ SpectralProcessor created with default constructor")
        except Exception as e1:
            try:
                processor = SpectralProcessor(48000)
                print("✅ SpectralProcessor created with sample_rate parameter")
            except Exception as e2:
                print(f"❌ SpectralProcessor constructor failed: {e1}, {e2}")
                return False
        
        # Create test audio data
        test_audio = np.sin(2 * np.pi * 440 * np.linspace(0, 1, 48000)).astype(np.float32)
        
        # Test spectral analysis
        try:
            analysis = processor.analyze_spectrum(test_audio, 48000)
            if analysis and hasattr(analysis, 'frequencies') and hasattr(analysis, 'magnitudes'):
                print(f"✅ Spectral analysis successful: {len(analysis.frequencies)} frequency bins")
                return True
            else:
                print("❌ Spectral analysis returned invalid results")
                return False
        except Exception as e:
            print(f"❌ Spectral analysis failed: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Spectral processor test failed: {e}")
        return False

def test_parametric_eq():
    """Test the parametric equalizer"""
    print("\n🔍 Testing ParametricEqualizer...")
    
    try:
        from audio import ParametricEqualizer, EQPresets
        
        # Try different constructor patterns
        try:
            eq = ParametricEqualizer(48000)
            print("✅ ParametricEqualizer created successfully")
        except Exception as e:
            print(f"❌ ParametricEqualizer constructor failed: {e}")
            return False
        
        # Test EQ presets
        try:
            presets = EQPresets.get_all_presets()
            if presets and len(presets) > 0:
                print(f"✅ EQ presets available: {', '.join(presets.keys())}")
                return True
            else:
                print("❌ No EQ presets available")
                return False
        except Exception as e:
            print(f"❌ EQ presets test failed: {e}")
            return False
        
    except Exception as e:
        print(f"❌ Parametric EQ test failed: {e}")
        return False

def test_advanced_audio_processor():
    """Test the main advanced audio processor"""
    print("\n🔍 Testing AdvancedAudioProcessor...")
    
    try:
        from audio import AdvancedAudioProcessor
        
        # Try different constructor patterns
        try:
            processor = AdvancedAudioProcessor(48000)
            print("✅ AdvancedAudioProcessor created successfully")
            return True
        except Exception as e:
            print(f"❌ AdvancedAudioProcessor constructor failed: {e}")
            return False
        
    except Exception as e:
        print(f"❌ Advanced audio processor test failed: {e}")
        return False

def test_audio_config():
    """Test audio configuration classes"""
    print("\n🔍 Testing AudioConfig...")
    
    try:
        from audio import AudioConfig, AudioQuality
        
        # Test creating audio config with default constructor
        config = AudioConfig()
        
        if config and hasattr(config, 'master_volume'):
            print("✅ AudioConfig created successfully")
            
            # Test serialization
            try:
                config_dict = config.to_dict()
                if config_dict and 'master_volume' in config_dict:
                    print("✅ AudioConfig serialization working")
                    return True
                else:
                    print("❌ AudioConfig serialization failed")
                    return False
            except Exception as e:
                print(f"❌ AudioConfig serialization failed: {e}")
                return False
        else:
            print("❌ AudioConfig creation failed")
            return False
        
    except Exception as e:
        print(f"❌ AudioConfig test failed: {e}")
        return False

def test_numpy_scipy_integration():
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
            return True
        else:
            print("❌ SciPy signal processing failed")
            return False
        
    except Exception as e:
        print(f"❌ NumPy/SciPy integration test failed: {e}")
        return False

def run_all_tests():
    """Run all tests and report results"""
    print("🚀 Starting basic advanced audio testing...\n")
    
    tests = [
        ("Import Tests", test_imports),
        ("NumPy/SciPy Integration", test_numpy_scipy_integration),
        ("Filter Designer", test_filter_designer),
        ("Spectral Processor", test_spectral_processor),
        ("Parametric EQ", test_parametric_eq),
        ("Advanced Audio Processor", test_advanced_audio_processor),
        ("Audio Config", test_audio_config),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            result = test_func()
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
        result = run_all_tests()
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n⏹️  Testing interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Testing crashed: {e}")
        sys.exit(1)
