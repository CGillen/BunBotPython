"""
Response Formatter for SL Bridge

Formats API responses consistently for Second Life consumption
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from ..models.response_models import SLResponse, ErrorResponse

logger = logging.getLogger('sl_bridge.ui.response_formatter')


class ResponseFormatter:
    """
    Formats API responses for consistent consumption by Second Life scripts.
    
    Provides standardized response formatting with SL-specific optimizations
    like size limits and simplified JSON structures.
    """
    
    def __init__(self):
        # LSL has a 2048 byte limit for HTTP responses
        self.max_response_size = 2048
        self.max_string_length = 200  # Conservative string limit
        
    def format_success(self, message: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Format a successful response.
        
        Args:
            message: Success message
            data: Optional response data
            
        Returns:
            Formatted response dictionary
        """
        try:
            response = SLResponse(
                success=True,
                message=self._truncate_string(message),
                data=self._optimize_data(data) if data else None,
                timestamp=datetime.now(timezone.utc)
            )
            
            return self._ensure_size_limit(response.dict())
            
        except Exception as e:
            logger.error(f"Error formatting success response: {e}")
            return self._format_error("Response formatting failed")
    
    def format_error(self, error_code: str, message: str, 
                    details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Format an error response.
        
        Args:
            error_code: Machine-readable error code
            message: Human-readable error message
            details: Optional error details
            
        Returns:
            Formatted error response dictionary
        """
        try:
            response = ErrorResponse(
                success=False,
                error_code=error_code,
                message=self._truncate_string(message),
                details=self._optimize_data(details) if details else None,
                timestamp=datetime.now(timezone.utc)
            )
            
            return self._ensure_size_limit(response.dict())
            
        except Exception as e:
            logger.error(f"Error formatting error response: {e}")
            return self._format_error("Error formatting failed")
    
    def _format_error(self, message: str) -> Dict[str, Any]:
        """Internal error formatting fallback"""
        return {
            "success": False,
            "error_code": "INTERNAL_ERROR",
            "message": self._truncate_string(message),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def format_stream_status(self, is_playing: bool, stream_url: Optional[str] = None,
                           station_name: Optional[str] = None, current_song: Optional[str] = None,
                           volume: Optional[float] = None, guild_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Format stream status response optimized for SL.
        
        Args:
            is_playing: Whether stream is playing
            stream_url: Current stream URL
            station_name: Station display name
            current_song: Current song info
            volume: Current volume level
            guild_id: Discord guild ID
            
        Returns:
            Formatted stream status
        """
        try:
            data = {
                "playing": is_playing,
                "volume": round(volume, 2) if volume is not None else None,
                "guild_id": guild_id
            }
            
            # Add optional fields with truncation
            if stream_url:
                data["url"] = self._truncate_string(stream_url, 100)
            if station_name:
                data["station"] = self._truncate_string(station_name, 50)
            if current_song:
                data["song"] = self._truncate_string(current_song, 80)
            
            return self.format_success("Stream status retrieved", data)
            
        except Exception as e:
            logger.error(f"Error formatting stream status: {e}")
            return self.format_error("STATUS_ERROR", "Failed to format stream status")
    
    def format_favorites_list(self, favorites: List[Dict[str, Any]], 
                            total_count: int, guild_id: int) -> Dict[str, Any]:
        """
        Format favorites list optimized for SL display.
        
        Args:
            favorites: List of favorite items
            total_count: Total number of favorites
            guild_id: Discord guild ID
            
        Returns:
            Formatted favorites list
        """
        try:
            # Optimize favorites for SL consumption
            sl_favorites = []
            for fav in favorites[:20]:  # Limit to 20 for size
                sl_fav = {
                    "num": fav.get("favorite_number"),
                    "name": self._truncate_string(fav.get("station_name", ""), 30),
                    "url": self._truncate_string(fav.get("stream_url", ""), 80)
                }
                
                # Add category if present and short
                if fav.get("category"):
                    sl_fav["cat"] = self._truncate_string(fav["category"], 15)
                
                sl_favorites.append(sl_fav)
            
            data = {
                "favorites": sl_favorites,
                "total": min(total_count, 99),  # Limit display
                "guild_id": guild_id
            }
            
            return self.format_success(f"Found {len(sl_favorites)} favorites", data)
            
        except Exception as e:
            logger.error(f"Error formatting favorites list: {e}")
            return self.format_error("FAVORITES_ERROR", "Failed to format favorites")
    
    def format_audio_info(self, volume: float, eq_settings: Dict[str, float],
                         guild_id: int) -> Dict[str, Any]:
        """
        Format audio configuration info for SL.
        
        Args:
            volume: Current volume level
            eq_settings: EQ settings (bass, mid, treble)
            guild_id: Discord guild ID
            
        Returns:
            Formatted audio info
        """
        try:
            data = {
                "volume": round(volume, 2),
                "eq": {
                    "bass": round(eq_settings.get("bass", 0), 1),
                    "mid": round(eq_settings.get("mid", 0), 1),
                    "treble": round(eq_settings.get("treble", 0), 1)
                },
                "guild_id": guild_id
            }
            
            return self.format_success("Audio info retrieved", data)
            
        except Exception as e:
            logger.error(f"Error formatting audio info: {e}")
            return self.format_error("AUDIO_ERROR", "Failed to format audio info")
    
    def format_simple_confirmation(self, action: str, guild_id: int) -> Dict[str, Any]:
        """
        Format simple confirmation response.
        
        Args:
            action: Action that was performed
            guild_id: Discord guild ID
            
        Returns:
            Simple confirmation response
        """
        try:
            data = {
                "action": self._truncate_string(action, 30),
                "guild_id": guild_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            return self.format_success(f"{action} completed", data)
            
        except Exception as e:
            logger.error(f"Error formatting confirmation: {e}")
            return self.format_error("CONFIRM_ERROR", "Failed to confirm action")
    
    def _truncate_string(self, text: str, max_length: Optional[int] = None) -> str:
        """
        Truncate string to fit SL constraints.
        
        Args:
            text: Text to truncate
            max_length: Maximum length (uses default if None)
            
        Returns:
            Truncated string
        """
        if not text:
            return ""
        
        limit = max_length or self.max_string_length
        if len(text) <= limit:
            return text
        
        return text[:limit-3] + "..."
    
    def _optimize_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Optimize data structure for SL consumption.
        
        Args:
            data: Data to optimize
            
        Returns:
            Optimized data structure
        """
        if not data:
            return {}
        
        optimized = {}
        
        for key, value in data.items():
            # Shorten common key names
            short_key = self._shorten_key(key)
            
            if isinstance(value, str):
                optimized[short_key] = self._truncate_string(value)
            elif isinstance(value, (int, float, bool)):
                optimized[short_key] = value
            elif isinstance(value, dict):
                optimized[short_key] = self._optimize_data(value)
            elif isinstance(value, list):
                # Limit list size and optimize items
                optimized[short_key] = [
                    self._optimize_data(item) if isinstance(item, dict) else item
                    for item in value[:10]  # Limit to 10 items
                ]
            else:
                # Convert other types to string and truncate
                optimized[short_key] = self._truncate_string(str(value))
        
        return optimized
    
    def _shorten_key(self, key: str) -> str:
        """
        Shorten common key names to save space.
        
        Args:
            key: Original key name
            
        Returns:
            Shortened key name
        """
        key_mapping = {
            "favorite_number": "num",
            "station_name": "name",
            "stream_url": "url",
            "current_song": "song", 
            "guild_id": "guild",
            "timestamp": "time",
            "is_playing": "playing",
            "connected_users": "users",
            "voice_channel_id": "channel"
        }
        
        return key_mapping.get(key, key)
    
    def _ensure_size_limit(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ensure response fits within LSL size limits.
        
        Args:
            response: Response dictionary
            
        Returns:
            Size-optimized response
        """
        try:
            import json
            
            # First attempt with current response
            response_json = json.dumps(response, separators=(',', ':'))
            
            if len(response_json) <= self.max_response_size:
                return response
            
            # Response too large, need to trim
            logger.warning(f"Response too large ({len(response_json)} bytes), trimming")
            
            # Remove optional fields in order of priority
            if "data" in response and isinstance(response["data"], dict):
                data = response["data"].copy()
                
                # Remove fields in order of importance (least to most important)
                removal_order = ["timestamp", "details", "metadata", "description", "category"]
                
                for field in removal_order:
                    if field in data:
                        del data[field]
                        response["data"] = data
                        
                        response_json = json.dumps(response, separators=(',', ':'))
                        if len(response_json) <= self.max_response_size:
                            return response
                
                # If still too large, truncate string values more aggressively
                for key, value in data.items():
                    if isinstance(value, str) and len(value) > 20:
                        data[key] = value[:15] + "..."
                        
                response["data"] = data
                response_json = json.dumps(response, separators=(',', ':'))
                
                if len(response_json) <= self.max_response_size:
                    return response
            
            # Last resort: minimal response
            return {
                "success": response.get("success", False),
                "message": self._truncate_string(response.get("message", ""), 50),
                "error": "Response truncated for SL"
            }
            
        except Exception as e:
            logger.error(f"Error ensuring size limit: {e}")
            return {
                "success": False,
                "error": "Size optimization failed"
            }
