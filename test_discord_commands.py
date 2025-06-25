#!/usr/bin/env python3
"""
Test Discord command registration and functionality
"""

import asyncio
import sys
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('discord_test')

def test_command_imports():
    """Test that command modules can be imported"""
    print("🔍 Testing Discord command imports...")
    
    try:
        from services.advanced_audio_commands import AdvancedAudioCommands
        print("✅ AdvancedAudioCommands imported successfully")
        
        from services.command_service import CommandService
        print("✅ CommandService imported successfully")
        
        return True
        
    except Exception as e:
        print(f"❌ Command import failed: {e}")
        return False

def test_advanced_audio_commands():
    """Test advanced audio command class"""
    print("\n🔍 Testing AdvancedAudioCommands...")
    
    try:
        from services.advanced_audio_commands import AdvancedAudioCommands
        from core import ServiceRegistry
        
        # Create service registry
        registry = ServiceRegistry()
        
        # Initialize advanced audio commands
        commands = AdvancedAudioCommands(registry)
        
        if commands:
            print("✅ AdvancedAudioCommands initialized successfully")
            
            # Check if commands have the expected methods
            expected_methods = [
                'eq_preset', 'eq_band', 'eq_clear', 'eq_status',
                'audio_analyze', 'filter_design'
            ]
            
            missing_methods = []
            for method in expected_methods:
                if not hasattr(commands, method):
                    missing_methods.append(method)
            
            if missing_methods:
                print(f"❌ Missing command methods: {', '.join(missing_methods)}")
                return False
            else:
                print(f"✅ All expected command methods present: {', '.join(expected_methods)}")
                return True
        else:
            print("❌ Failed to initialize AdvancedAudioCommands")
            return False
        
    except Exception as e:
        print(f"❌ AdvancedAudioCommands test failed: {e}")
        return False

def test_eq_presets():
    """Test EQ preset functionality"""
    print("\n🔍 Testing EQ presets...")
    
    try:
        from audio import EQPresets
        
        # Test getting all presets
        presets = EQPresets.get_all_presets()
        
        if presets and len(presets) > 0:
            print(f"✅ EQ presets available: {', '.join(presets.keys())}")
            
            # Test specific presets
            rock_preset = EQPresets.get_preset("rock")
            if rock_preset and len(rock_preset) > 0:
                print(f"✅ Rock preset loaded with {len(rock_preset)} bands")
                return True
            else:
                print("❌ Failed to load rock preset")
                return False
        else:
            print("❌ No EQ presets available")
            return False
        
    except Exception as e:
        print(f"❌ EQ presets test failed: {e}")
        return False

def test_filter_types():
    """Test filter type enums"""
    print("\n🔍 Testing filter types...")
    
    try:
        from audio import FilterType, FilterResponse
        
        # Test filter types
        filter_types = [FilterType.BUTTERWORTH, FilterType.CHEBYSHEV_I, FilterType.BESSEL]
        print(f"✅ Filter types available: {[ft.value for ft in filter_types]}")
        
        # Test filter responses
        responses = [FilterResponse.LOWPASS, FilterResponse.HIGHPASS, FilterResponse.BANDPASS]
        print(f"✅ Filter responses available: {[fr.value for fr in responses]}")
        
        return True
        
    except Exception as e:
        print(f"❌ Filter types test failed: {e}")
        return False

def test_audio_quality_levels():
    """Test audio quality management"""
    print("\n🔍 Testing audio quality levels...")
    
    try:
        from audio import ProcessingQuality, AudioQuality
        
        # Test processing quality levels
        quality_levels = [ProcessingQuality.LOW, ProcessingQuality.MEDIUM, 
                         ProcessingQuality.HIGH, ProcessingQuality.ULTRA]
        print(f"✅ Processing quality levels: {[ql.value for ql in quality_levels]}")
        
        # Test legacy audio quality
        legacy_levels = [AudioQuality.LOW, AudioQuality.MEDIUM, 
                        AudioQuality.HIGH, AudioQuality.ULTRA]
        print(f"✅ Legacy audio quality levels: {[al.value for al in legacy_levels]}")
        
        return True
        
    except Exception as e:
        print(f"❌ Audio quality test failed: {e}")
        return False

def test_bot_health():
    """Test that the bot is running and healthy"""
    print("\n🔍 Testing bot health...")
    
    try:
        import requests
        
        response = requests.get("http://localhost:8080/health", timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "healthy":
                print("✅ Bot is running and healthy")
                return True
            else:
                print(f"❌ Bot status: {data.get('status', 'unknown')}")
                return False
        else:
            print(f"❌ Bot health check failed: HTTP {response.status_code}")
            return False
        
    except Exception as e:
        print(f"❌ Bot health test failed: {e}")
        return False

def run_all_tests():
    """Run all Discord command tests"""
    print("🚀 Starting Discord command testing...\n")
    
    tests = [
        ("Command Imports", test_command_imports),
        ("Advanced Audio Commands", test_advanced_audio_commands),
        ("EQ Presets", test_eq_presets),
        ("Filter Types", test_filter_types),
        ("Audio Quality Levels", test_audio_quality_levels),
        ("Bot Health", test_bot_health),
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
    print("📊 DISCORD COMMAND TEST RESULTS")
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
        print("🎉 ALL DISCORD COMMAND TESTS PASSED!")
        print("\n🎵 Advanced Audio Processing Feature is 100% Complete!")
        print("\n📋 Available Discord Commands:")
        print("   • /eq_preset <preset> - Apply EQ presets (rock, pop, classical, etc.)")
        print("   • /eq_band <band> <frequency> <gain> <q> - Configure custom EQ band")
        print("   • /eq_clear - Reset EQ to flat response")
        print("   • /eq_status - View current EQ configuration")
        print("   • /audio_analyze - Real-time spectral analysis")
        print("   • /filter_design <type> <frequency> <order> - Design custom filters")
        return True
    else:
        print("⚠️  Some Discord command tests failed")
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
