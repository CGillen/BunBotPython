"""
Stream validation system for BunBot favorites.
Validates streams and extracts station names using existing streamscrobbler integration.
"""

import logging
import urllib.parse
from typing import Dict, Any
from streamscrobbler import streamscrobbler

logger = logging.getLogger('discord')

class StreamValidator:
    """Validates radio streams and extracts metadata"""
    
    def validate_stream(self, url: str) -> Dict[str, Any]:
        """
        Validate stream and return metadata
        
        Returns:
            Dict with keys: 'valid', 'station_name', 'metadata', 'error'
        """
        try:
            logger.info(f"Validating stream: {url}")
            
            # Use existing streamscrobbler validation
            stationinfo = streamscrobbler.get_server_info(url)
            
            if stationinfo['status'] <= 0:
                logger.warning(f"Stream validation failed - status: {stationinfo['status']}")
                return {
                    'valid': False,
                    'error': "Stream is offline or unreachable",
                    'station_name': None,
                    'metadata': None
                }
                
            station_name = self.extract_station_name(url, stationinfo)
            
            logger.info(f"Stream validation successful - station: {station_name}")
            return {
                'valid': True,
                'station_name': station_name,
                'metadata': stationinfo['metadata'],
                'error': None
            }
            
        except Exception as e:
            logger.error(f"Stream validation error for {url}: {e}")
            return {
                'valid': False,
                'error': f"Validation error: {str(e)}",
                'station_name': None,
                'metadata': None
            }
    
    def extract_station_name(self, url: str, stationinfo: Dict) -> str:
        """
        Extract station name from stream metadata or URL
        
        Args:
            url: Stream URL
            stationinfo: Stream information from streamscrobbler
            
        Returns:
            Station name string
        """
        metadata = stationinfo.get('metadata', {})
        
        if metadata:
            # Try various metadata fields for station name
            for field in ['station_name', 'icy-name', 'server_name', 'title', 'name']:
                if metadata.get(field):
                    name = str(metadata[field]).strip()
                    if name and name.lower() != 'unknown':
                        logger.debug(f"Found station name in metadata field '{field}': {name}")
                        return name
        
        # Fallback to URL-based name extraction
        return self.extract_name_from_url(url)
    
    def extract_name_from_url(self, url: str) -> str:
        """
        Extract a reasonable station name from URL
        
        Args:
            url: Stream URL
            
        Returns:
            Station name extracted from URL
        """
        try:
            parsed = urllib.parse.urlparse(url)
            
            # Try to get hostname without www
            hostname = parsed.hostname or parsed.netloc
            if hostname:
                hostname = hostname.lower()
                if hostname.startswith('www.'):
                    hostname = hostname[4:]
                
                # Remove common streaming domains and get the main part
                if '.' in hostname:
                    parts = hostname.split('.')
                    # Use the main domain part (usually the second-to-last part)
                    if len(parts) >= 2:
                        main_part = parts[-2]  # e.g., 'example' from 'stream.example.com'
                        
                        # Clean up common streaming prefixes/suffixes
                        main_part = main_part.replace('stream', '').replace('radio', '').replace('cast', '')
                        main_part = main_part.strip('-_')
                        
                        if main_part:
                            # Capitalize first letter
                            return main_part.capitalize() + " Radio"
            
            # If hostname extraction fails, use the full hostname
            if hostname:
                return hostname.capitalize() + " Radio"
                
        except Exception as e:
            logger.warning(f"Failed to extract name from URL {url}: {e}")
        
        # Final fallback
        return "Unknown Station"
    
    def is_valid_stream_url(self, url: str) -> bool:
        """
        Quick check if URL looks like a valid stream URL
        
        Args:
            url: URL to check
            
        Returns:
            True if URL appears to be a valid stream URL
        """
        try:
            parsed = urllib.parse.urlparse(url)
            
            # Must have scheme and netloc
            if not parsed.scheme or not parsed.netloc:
                return False
            
            # Must be http or https
            if parsed.scheme.lower() not in ['http', 'https']:
                return False
            
            # Should have a port or path (most streams do)
            if not parsed.port and not parsed.path:
                return False
                
            return True
            
        except Exception:
            return False

# Global validator instance
_validator_instance = None

def get_stream_validator() -> StreamValidator:
    """Get global stream validator instance"""
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = StreamValidator()
    return _validator_instance
