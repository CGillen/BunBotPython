"""
Stream Management System for BunBot Audio Processing
"""

import logging
import asyncio
import urllib.request
import urllib.error
import time
from typing import Dict, Any, Optional, AsyncGenerator, Tuple
from datetime import datetime, timezone

from core import StateManager, EventBus, ConfigurationManager
from .interfaces import IStreamManager

logger = logging.getLogger('discord.audio.stream_manager')

class StreamManager(IStreamManager):
    """
    Stream management service for BunBot audio processing.
    
    Handles connection management, buffering, and metadata extraction
    for audio streams. Provides reliable stream connectivity with
    monitoring and fallback capabilities.
    """
    
    def __init__(self, state_manager: StateManager, event_bus: EventBus, 
                 config_manager: ConfigurationManager):
        self.state_manager = state_manager
        self.event_bus = event_bus
        self.config_manager = config_manager
        
        # Stream connection tracking
        self._active_streams: Dict[str, Dict[str, Any]] = {}  # stream_id -> stream_info
        self._stream_buffers: Dict[str, bytearray] = {}       # stream_id -> buffer
        self._stream_metadata: Dict[str, Dict[str, Any]] = {} # stream_id -> metadata
        
        # Connection monitoring
        self._connection_health: Dict[str, Dict[str, Any]] = {}  # stream_id -> health_info
        self._retry_attempts: Dict[str, int] = {}                # stream_id -> retry_count
        self._last_connection_time: Dict[str, float] = {}        # stream_id -> timestamp
        
        # Performance tracking
        self._bandwidth_usage: Dict[str, float] = {}  # stream_id -> bytes_per_second
        self._connection_quality: Dict[str, str] = {}  # stream_id -> quality_rating
        
        logger.info("StreamManager initialized")
    
    async def open_stream(self, url: str, buffer_size: int = 8192) -> AsyncGenerator[bytes, None]:
        """
        Open and buffer an audio stream.
        
        Args:
            url: Stream URL to connect to
            buffer_size: Buffer size for reading stream data
            
        Yields:
            Audio data chunks as they become available
        """
        stream_id = self._generate_stream_id(url)
        
        try:
            logger.info(f"Opening stream: {url}")
            
            # Initialize stream tracking
            self._active_streams[stream_id] = {
                'url': url,
                'buffer_size': buffer_size,
                'start_time': time.time(),
                'bytes_read': 0,
                'status': 'connecting'
            }
            
            # Test stream connectivity first
            stream_info = await self.test_stream(url, timeout=10.0)
            if not stream_info.get('accessible', False):
                raise ConnectionError(f"Stream not accessible: {url}")
            
            # Open stream connection
            response = await self._open_stream_connection(url)
            if not response:
                raise ConnectionError(f"Failed to open stream connection: {url}")
            
            # Update stream status
            self._active_streams[stream_id]['status'] = 'connected'
            self._active_streams[stream_id]['response'] = response
            
            # Start streaming data
            async for chunk in self._stream_data_chunks(stream_id, response, buffer_size):
                yield chunk
                
        except Exception as e:
            logger.error(f"Failed to open stream {url}: {e}")
            await self._cleanup_stream(stream_id)
            raise
    
    async def test_stream(self, url: str, timeout: float = 10.0) -> Dict[str, Any]:
        """
        Test stream connectivity and get basic information.
        
        Args:
            url: Stream URL to test
            timeout: Connection timeout in seconds
            
        Returns:
            Dictionary with stream test results and metadata
        """
        try:
            logger.debug(f"Testing stream connectivity: {url}")
            
            start_time = time.time()
            
            # Create request with appropriate headers
            request = urllib.request.Request(url)
            request.add_header('User-Agent', 'BunBot/3.0 Audio Processor')
            request.add_header('Icy-MetaData', '1')  # Request ICY metadata
            
            try:
                # Test connection with HEAD request first
                head_request = urllib.request.Request(url, method='HEAD')
                head_request.add_header('User-Agent', 'BunBot/3.0 Audio Processor')
                
                response = urllib.request.urlopen(head_request, timeout=timeout)
                response.close()
                
                # Connection successful, get detailed info
                response_time = (time.time() - start_time) * 1000  # Convert to ms
                
                return {
                    'accessible': True,
                    'response_time_ms': response_time,
                    'url': url,
                    'status_code': getattr(response, 'status', 200),
                    'headers': dict(response.headers) if hasattr(response, 'headers') else {},
                    'test_time': datetime.now(timezone.utc).isoformat()
                }
                
            except urllib.error.HTTPError as e:
                # Some streams don't support HEAD, try GET with limited read
                if e.code in [405, 501]:  # Method Not Allowed or Not Implemented
                    try:
                        response = urllib.request.urlopen(request, timeout=timeout)
                        # Read just a small amount to test
                        test_data = response.read(1024)
                        response.close()
                        
                        response_time = (time.time() - start_time) * 1000
                        
                        return {
                            'accessible': True,
                            'response_time_ms': response_time,
                            'url': url,
                            'status_code': 200,
                            'headers': dict(response.headers) if hasattr(response, 'headers') else {},
                            'test_data_size': len(test_data),
                            'test_time': datetime.now(timezone.utc).isoformat()
                        }
                    except Exception as get_error:
                        logger.debug(f"GET test also failed: {get_error}")
                        raise e
                else:
                    raise e
                    
        except Exception as e:
            logger.warning(f"Stream test failed for {url}: {e}")
            return {
                'accessible': False,
                'error': str(e),
                'url': url,
                'test_time': datetime.now(timezone.utc).isoformat()
            }
    
    async def get_stream_info(self, url: str) -> Dict[str, Any]:
        """
        Get detailed stream information including metadata.
        
        Args:
            url: Stream URL to analyze
            
        Returns:
            Comprehensive stream information dictionary
        """
        try:
            logger.debug(f"Getting detailed stream info: {url}")
            
            # Use existing streamscrobbler if available
            try:
                from streamscrobbler import streamscrobbler
                station_info = streamscrobbler.get_server_info(url)
                
                if station_info and station_info.get('status', 0) > 0:
                    return {
                        'url': url,
                        'accessible': True,
                        'metadata': station_info.get('metadata', {}),
                        'status': station_info.get('status', 0),
                        'station_info': station_info,
                        'source': 'streamscrobbler',
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    }
            except ImportError:
                logger.debug("streamscrobbler not available, using basic info")
            except Exception as e:
                logger.debug(f"streamscrobbler failed: {e}")
            
            # Fallback to basic test
            basic_info = await self.test_stream(url)
            basic_info['source'] = 'basic_test'
            return basic_info
            
        except Exception as e:
            logger.error(f"Failed to get stream info for {url}: {e}")
            return {
                'url': url,
                'accessible': False,
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
    
    async def close_stream(self, stream_id: str) -> bool:
        """
        Close and cleanup a stream connection.
        
        Args:
            stream_id: Stream identifier to close
            
        Returns:
            True if stream was closed successfully
        """
        try:
            if stream_id not in self._active_streams:
                logger.debug(f"Stream {stream_id} not found for closing")
                return True
            
            await self._cleanup_stream(stream_id)
            logger.info(f"Closed stream: {stream_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to close stream {stream_id}: {e}")
            return False
    
    async def _open_stream_connection(self, url: str):
        """Open a stream connection with proper error handling"""
        try:
            # Create request with appropriate headers
            request = urllib.request.Request(url)
            request.add_header('User-Agent', 'BunBot/3.0 Audio Processor')
            request.add_header('Icy-MetaData', '1')
            
            # Open connection
            response = urllib.request.urlopen(request, timeout=10)
            
            logger.debug(f"Opened stream connection: {url}")
            return response
            
        except Exception as e:
            logger.error(f"Failed to open stream connection {url}: {e}")
            return None
    
    async def _stream_data_chunks(self, stream_id: str, response, buffer_size: int) -> AsyncGenerator[bytes, None]:
        """Stream data chunks from the response with monitoring"""
        try:
            stream_info = self._active_streams[stream_id]
            last_data_time = time.time()
            total_bytes = 0
            
            while True:
                try:
                    # Read data chunk
                    chunk = response.read(buffer_size)
                    
                    if not chunk:
                        logger.info(f"Stream {stream_id} ended (no more data)")
                        break
                    
                    current_time = time.time()
                    total_bytes += len(chunk)
                    
                    # Update stream statistics
                    stream_info['bytes_read'] = total_bytes
                    stream_info['last_data_time'] = current_time
                    
                    # Calculate bandwidth
                    time_elapsed = current_time - stream_info['start_time']
                    if time_elapsed > 0:
                        bandwidth = total_bytes / time_elapsed
                        self._bandwidth_usage[stream_id] = bandwidth
                    
                    # Update connection health
                    self._update_connection_health(stream_id, len(chunk), current_time - last_data_time)
                    last_data_time = current_time
                    
                    yield chunk
                    
                    # Small delay to prevent overwhelming the CPU
                    await asyncio.sleep(0.001)  # 1ms delay
                    
                except Exception as e:
                    logger.error(f"Error reading stream data for {stream_id}: {e}")
                    break
            
        except Exception as e:
            logger.error(f"Error in stream data generator for {stream_id}: {e}")
        finally:
            # Close response if it's still open
            try:
                if response:
                    response.close()
            except Exception as e:
                logger.debug(f"Error closing response for {stream_id}: {e}")
    
    def _update_connection_health(self, stream_id: str, chunk_size: int, read_time: float) -> None:
        """Update connection health metrics"""
        try:
            if stream_id not in self._connection_health:
                self._connection_health[stream_id] = {
                    'chunk_sizes': [],
                    'read_times': [],
                    'quality_score': 1.0,
                    'last_update': time.time()
                }
            
            health = self._connection_health[stream_id]
            
            # Track recent chunk sizes and read times
            health['chunk_sizes'].append(chunk_size)
            health['read_times'].append(read_time)
            
            # Keep only recent measurements
            if len(health['chunk_sizes']) > 20:
                health['chunk_sizes'] = health['chunk_sizes'][-20:]
            if len(health['read_times']) > 20:
                health['read_times'] = health['read_times'][-20:]
            
            # Calculate quality score
            avg_read_time = sum(health['read_times']) / len(health['read_times'])
            avg_chunk_size = sum(health['chunk_sizes']) / len(health['chunk_sizes'])
            
            # Quality based on read time and chunk size consistency
            time_score = max(0.0, 1.0 - (avg_read_time / 0.1))  # 100ms is poor
            size_variance = self._calculate_variance(health['chunk_sizes'])
            size_score = max(0.0, 1.0 - (size_variance / (avg_chunk_size ** 2)))
            
            health['quality_score'] = (time_score + size_score) / 2.0
            health['last_update'] = time.time()
            
            # Update connection quality rating
            if health['quality_score'] > 0.8:
                self._connection_quality[stream_id] = 'excellent'
            elif health['quality_score'] > 0.6:
                self._connection_quality[stream_id] = 'good'
            elif health['quality_score'] > 0.4:
                self._connection_quality[stream_id] = 'fair'
            else:
                self._connection_quality[stream_id] = 'poor'
                
        except Exception as e:
            logger.error(f"Error updating connection health for {stream_id}: {e}")
    
    def _calculate_variance(self, values: list) -> float:
        """Calculate variance of a list of values"""
        if len(values) < 2:
            return 0.0
        
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance
    
    async def _cleanup_stream(self, stream_id: str) -> None:
        """Clean up all resources for a stream"""
        try:
            # Close response if exists
            if stream_id in self._active_streams:
                stream_info = self._active_streams[stream_id]
                response = stream_info.get('response')
                if response:
                    try:
                        response.close()
                    except Exception as e:
                        logger.debug(f"Error closing response for {stream_id}: {e}")
                
                # Remove from active streams
                del self._active_streams[stream_id]
            
            # Clean up associated data
            if stream_id in self._stream_buffers:
                del self._stream_buffers[stream_id]
            if stream_id in self._stream_metadata:
                del self._stream_metadata[stream_id]
            if stream_id in self._connection_health:
                del self._connection_health[stream_id]
            if stream_id in self._bandwidth_usage:
                del self._bandwidth_usage[stream_id]
            if stream_id in self._connection_quality:
                del self._connection_quality[stream_id]
            if stream_id in self._retry_attempts:
                del self._retry_attempts[stream_id]
            if stream_id in self._last_connection_time:
                del self._last_connection_time[stream_id]
            
            logger.debug(f"Cleaned up stream resources: {stream_id}")
            
        except Exception as e:
            logger.error(f"Error cleaning up stream {stream_id}: {e}")
    
    def _generate_stream_id(self, url: str) -> str:
        """Generate a unique stream identifier"""
        import hashlib
        return hashlib.md5(f"{url}_{time.time()}".encode()).hexdigest()[:16]
    
    def get_stream_statistics(self) -> Dict[str, Any]:
        """Get overall stream management statistics"""
        try:
            active_count = len(self._active_streams)
            total_bandwidth = sum(self._bandwidth_usage.values())
            
            quality_counts = {}
            for quality in self._connection_quality.values():
                quality_counts[quality] = quality_counts.get(quality, 0) + 1
            
            return {
                'active_streams': active_count,
                'total_bandwidth_bps': total_bandwidth,
                'quality_distribution': quality_counts,
                'streams_info': {
                    stream_id: {
                        'url': info['url'],
                        'status': info['status'],
                        'bytes_read': info.get('bytes_read', 0),
                        'bandwidth_bps': self._bandwidth_usage.get(stream_id, 0),
                        'quality': self._connection_quality.get(stream_id, 'unknown'),
                        'uptime_seconds': time.time() - info['start_time']
                    }
                    for stream_id, info in self._active_streams.items()
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting stream statistics: {e}")
            return {}
    
    def get_stream_health(self, stream_id: str) -> Dict[str, Any]:
        """Get health information for a specific stream"""
        try:
            if stream_id not in self._active_streams:
                return {'error': 'Stream not found'}
            
            stream_info = self._active_streams[stream_id]
            health_info = self._connection_health.get(stream_id, {})
            
            return {
                'stream_id': stream_id,
                'url': stream_info['url'],
                'status': stream_info['status'],
                'uptime_seconds': time.time() - stream_info['start_time'],
                'bytes_read': stream_info.get('bytes_read', 0),
                'bandwidth_bps': self._bandwidth_usage.get(stream_id, 0),
                'connection_quality': self._connection_quality.get(stream_id, 'unknown'),
                'quality_score': health_info.get('quality_score', 0.0),
                'last_data_time': stream_info.get('last_data_time', 0),
                'health_info': health_info
            }
            
        except Exception as e:
            logger.error(f"Error getting stream health for {stream_id}: {e}")
            return {'error': str(e)}
