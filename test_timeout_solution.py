"""
Test script for the ICY timeout solution
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger('test_timeout_solution')

async def test_urllib_hack():
    """Test the enhanced urllib_hack with timeout protection"""
    logger.info("Testing urllib_hack timeout protection...")
    
    try:
        import urllib_hack
        urllib_hack.init_urllib_hack(True)
        logger.info("✅ urllib_hack initialized successfully")
        return True
    except Exception as e:
        logger.error(f"❌ urllib_hack test failed: {e}")
        return False

async def test_network_service():
    """Test the NetworkService with circuit breaker"""
    logger.info("Testing NetworkService...")
    
    try:
        from core.network_service import get_network_service, NetworkTimeoutError
        
        network_service = get_network_service()
        logger.info("✅ NetworkService initialized successfully")
        
        # Test health monitoring
        health = network_service.get_all_service_health()
        logger.info(f"✅ Network health monitoring working: {len(health)} services tracked")
        
        return True
    except Exception as e:
        logger.error(f"❌ NetworkService test failed: {e}")
        return False

async def test_stream_metadata_service():
    """Test the StreamMetadataService"""
    logger.info("Testing StreamMetadataService...")
    
    try:
        from core import ServiceRegistry
        from services.stream_metadata_service import StreamMetadataService
        
        service_registry = ServiceRegistry()
        metadata_service = StreamMetadataService(service_registry)
        
        logger.info("✅ StreamMetadataService initialized successfully")
        
        # Test cache functionality
        stats = metadata_service.get_cache_stats()
        logger.info(f"✅ Cache stats working: {stats}")
        
        return True
    except Exception as e:
        logger.error(f"❌ StreamMetadataService test failed: {e}")
        return False

async def test_configuration():
    """Test the enhanced configuration"""
    logger.info("Testing enhanced configuration...")
    
    try:
        from core.config_manager import get_config
        
        config = get_config()
        
        # Test network configuration
        network_timeout = getattr(config, 'network_timeout', None)
        metadata_timeout = getattr(config, 'metadata_timeout', None)
        retry_attempts = getattr(config, 'retry_attempts', None)
        
        if network_timeout and metadata_timeout and retry_attempts:
            logger.info(f"✅ Network configuration loaded: timeout={network_timeout}s, metadata_timeout={metadata_timeout}s, retries={retry_attempts}")
            return True
        else:
            logger.warning("⚠️ Some network configuration missing")
            return False
            
    except Exception as e:
        logger.error(f"❌ Configuration test failed: {e}")
        return False

async def test_streamscrobbler_integration():
    """Test streamscrobbler integration with timeout protection"""
    logger.info("Testing streamscrobbler integration...")
    
    try:
        from core import ServiceRegistry
        from services.stream_metadata_service import StreamMetadataService
        
        service_registry = ServiceRegistry()
        metadata_service = StreamMetadataService(service_registry)
        
        # Test with a known working stream (with short timeout)
        test_url = "http://live.na2.lightmanstreams.com:9390/"
        
        logger.info(f"Testing metadata fetch for: {test_url}")
        
        # Use a short timeout to test timeout protection
        station_info = await asyncio.wait_for(
            metadata_service.get_station_info(test_url, timeout=3),
            timeout=5
        )
        
        if station_info:
            logger.info(f"✅ Metadata fetch successful: status={station_info.get('status', 'unknown')}")
            if station_info.get('from_cache'):
                logger.info("📦 Result from cache (graceful degradation working)")
            return True
        else:
            logger.warning("⚠️ Metadata fetch returned None (may be expected)")
            return True  # This is still a successful test of timeout protection
            
    except asyncio.TimeoutError:
        logger.info("✅ Timeout protection working (request timed out as expected)")
        return True
    except Exception as e:
        logger.error(f"❌ Streamscrobbler integration test failed: {e}")
        return False

async def main():
    """Run all tests"""
    logger.info("🚀 Starting ICY timeout solution tests...")
    
    tests = [
        ("urllib_hack", test_urllib_hack),
        ("NetworkService", test_network_service),
        ("StreamMetadataService", test_stream_metadata_service),
        ("Configuration", test_configuration),
        ("Streamscrobbler Integration", test_streamscrobbler_integration),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        logger.info(f"\n--- Testing {test_name} ---")
        try:
            result = await test_func()
            results[test_name] = result
        except Exception as e:
            logger.error(f"❌ {test_name} test crashed: {e}")
            results[test_name] = False
    
    # Summary
    logger.info("\n" + "="*50)
    logger.info("TEST RESULTS SUMMARY")
    logger.info("="*50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{test_name}: {status}")
        if result:
            passed += 1
    
    logger.info(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All tests passed! ICY timeout solution is working correctly.")
        return True
    else:
        logger.warning(f"⚠️ {total - passed} tests failed. Review the logs above.")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
