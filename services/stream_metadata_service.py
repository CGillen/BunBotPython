"""
Stream Metadata Service for BunBot
Provides resilient stream metadata operations with timeout protection
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from core import ServiceRegistry
from core.network_service import get_network_service, NetworkTimeoutError, CircuitBreakerOpenError, NetworkError

logger = logging.getLogger('services.stream_metadata_service')

class StreamMetadataService:
    """
    Resilient stream metadata service.
    
    Wraps streamscrobbler operations with resilience:
    - Async timeout protection
    - Circuit breaker integration
    - Graceful degradation
    - Health monitoring
    - Error classification
    """
    
    def __init__(self, service_registry: ServiceRegistry):
        self.service_registry = service_registry
        self.network_service = get_network_service()
        
        # Import streamscrobbler with fallback
        try:
            from streamscrobbler import streamscrobbler
            self.streamscrobbler = streamscrobbler
            self._streamscrobbler_available = True
            logger.info("streamscrobbler module loaded successfully")
        except ImportError as e:
            logger.warning(f"streamscrobbler not available: {e}")
            self.streamscrobbler = None
            self._streamscrobbler_available = False
        
        # Metadata cache for graceful degradation
        self._metadata_cache: Dict[str, Dict[str, Any]] = {}
        self._last_successful_fetch: Dict[str, datetime] = {}
        
        logger.info("StreamMetadataService initialized")
    
    async def get_station_info(
        self, 
        url: str, 
        timeout: Optional[int] = None,
        use_cache_on_failure: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Get station information with full resilience protection.
        
        Args:
            url: Stream URL to check
            timeout: Request timeout (uses config default if None)
            use_cache_on_failure: Whether to return cached data on failure
            
        Returns:
            Station info dictionary or None if unavailable
        """
        if not self._streamscrobbler_available:
            logger.warning("streamscrobbler not available, cannot fetch station info")
            return self._get_cached_metadata(url) if use_cache_on_failure else None
        
        try:
            # Get station info with timeout protection
            station_info = await self._get_station_info_with_timeout(url, timeout)
            
            if station_info:
                # Cache successful result
                self._cache_metadata(url, station_info)
                self._last_successful_fetch[url] = datetime.now(timezone.utc)
                
                logger.debug(f"Successfully fetched station info for {self._get_service_name(url)}")
                return station_info
            else:
                logger.warning(f"streamscrobbler returned None for {url}")
                return self._get_cached_metadata(url) if use_cache_on_failure else None
                
        except NetworkTimeoutError as e:
            logger.warning(f"Timeout fetching station info for {url}: {e}")
            return self._get_cached_metadata(url) if use_cache_on_failure else None
            
        except CircuitBreakerOpenError as e:
            logger.warning(f"Circuit breaker open for {url}: {e}")
            return self._get_cached_metadata(url) if use_cache_on_failure else None
            
        except NetworkError as e:
            logger.error(f"Network error fetching station info for {url}: {e}")
            return self._get_cached_metadata(url) if use_cache_on_failure else None
            
        except Exception as e:
            logger.error(f"Unexpected error fetching station info for {url}: {e}")
            return self._get_cached_metadata(url) if use_cache_on_failure else None
    
    async def _get_station_info_with_timeout(
        self, 
        url: str, 
        timeout: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Get station info with async timeout protection"""
        
        # Use metadata timeout from config
        config = self.service_registry.get_optional('ConfigurationManager')
        if config:
            timeout = timeout or config.get_configuration().metadata_timeout
        else:
            timeout = timeout or 5  # Fallback timeout
        
        try:
            # Run streamscrobbler in executor with timeout
            station_info = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    self.streamscrobbler.get_server_info,
                    url
                ),
                timeout=timeout
            )
            
            return station_info
            
        except asyncio.TimeoutError as e:
            raise NetworkTimeoutError(f"streamscrobbler timeout after {timeout}s") from e
        except Exception as e:
            # Let other exceptions bubble up to be handled by caller
            raise
    
    def _cache_metadata(self, url: str, station_info: Dict[str, Any]) -> None:
        """Cache metadata for graceful degradation"""
        try:
            # Store essential metadata
            cached_data = {
                'status': station_info.get('status', 0),
                'metadata': station_info.get('metadata', {}),
                'server_name': station_info.get('server_name', 'Unknown'),
                'cached_at': datetime.now(timezone.utc).isoformat(),
                'original_url': url
            }
            
            self._metadata_cache[url] = cached_data
            logger.debug(f"Cached metadata for {self._get_service_name(url)}")
            
        except Exception as e:
            logger.warning(f"Failed to cache metadata for {url}: {e}")
    
    def _get_cached_metadata(self, url: str) -> Optional[Dict[str, Any]]:
        """Get cached metadata for graceful degradation"""
        try:
            cached_data = self._metadata_cache.get(url)
            if cached_data:
                logger.info(f"Using cached metadata for {self._get_service_name(url)}")
                
                # Add cache indicator
                result = cached_data.copy()
                result['from_cache'] = True
                return result
            
            return None
            
        except Exception as e:
            logger.warning(f"Failed to retrieve cached metadata for {url}: {e}")
            return None
    
    def _get_service_name(self, url: str) -> str:
        """Extract service name from URL"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc
        except Exception:
            return "unknown_service"
    
    def get_metadata_health(self, url: str) -> Dict[str, Any]:
        """Get metadata service health for a specific URL"""
        service_name = self._get_service_name(url)
        
        # Get network service health
        network_health = self.network_service.get_service_health(service_name)
        
        # Add metadata-specific information
        last_fetch = self._last_successful_fetch.get(url)
        has_cache = url in self._metadata_cache
        
        return {
            'url': url,
            'service_name': service_name,
            'streamscrobbler_available': self._streamscrobbler_available,
            'network_health': network_health,
            'last_successful_fetch': last_fetch.isoformat() if last_fetch else None,
            'has_cached_data': has_cache,
            'cache_age_seconds': (
                (datetime.now(timezone.utc) - last_fetch).total_seconds()
                if last_fetch else None
            )
        }
    
    def get_all_metadata_health(self) -> Dict[str, Dict[str, Any]]:
        """Get metadata health for all tracked URLs"""
        health_data = {}
        
        # Include all URLs we've attempted to fetch
        all_urls = set(self._metadata_cache.keys()) | set(self._last_successful_fetch.keys())
        
        for url in all_urls:
            health_data[url] = self.get_metadata_health(url)
        
        return health_data
    
    def clear_cache(self, url: Optional[str] = None) -> None:
        """Clear metadata cache"""
        try:
            if url:
                # Clear cache for specific URL
                self._metadata_cache.pop(url, None)
                self._last_successful_fetch.pop(url, None)
                logger.info(f"Cleared cache for {url}")
            else:
                # Clear all cache
                self._metadata_cache.clear()
                self._last_successful_fetch.clear()
                logger.info("Cleared all metadata cache")
                
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            'cached_urls': len(self._metadata_cache),
            'successful_fetches': len(self._last_successful_fetch),
            'streamscrobbler_available': self._streamscrobbler_available,
            'cache_entries': list(self._metadata_cache.keys())
        }

# Service factory function for dependency injection
def create_stream_metadata_service(service_registry: ServiceRegistry) -> StreamMetadataService:
    """Create StreamMetadataService instance"""
    return StreamMetadataService(service_registry)
