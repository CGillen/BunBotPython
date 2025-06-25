"""
Stream Adapter for SL Bridge

Converts SL API calls to Discord service interactions
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

import discord

from core import ServiceRegistry
from services.stream_service import StreamService

logger = logging.getLogger('sl_bridge.adapters.stream')


class MockInteraction:
    """Mock Discord interaction for SL Bridge adapter calls"""
    
    def __init__(self, guild_id: int, channel_id: Optional[int] = None, 
                 user_id: Optional[int] = None):
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.user_id = user_id
        
        # Create mock guild
        self.guild = MockGuild(guild_id)
        
        # Create mock user with voice channel
        self.user = MockUser(user_id, channel_id)
        
        # Mock channel for notifications
        self.channel = MockChannel(channel_id) if channel_id else None


class MockGuild:
    """Mock Discord guild"""
    
    def __init__(self, guild_id: int):
        self.id = guild_id
        self.voice_client = None  # Will be set by Discord.py


class MockUser:
    """Mock Discord user with voice channel"""
    
    def __init__(self, user_id: Optional[int], channel_id: Optional[int]):
        self.id = user_id
        self.voice = MockVoice(channel_id) if channel_id else None


class MockVoice:
    """Mock Discord voice state"""
    
    def __init__(self, channel_id: int):
        self.channel = MockVoiceChannel(channel_id)


class MockVoiceChannel:
    """Mock Discord voice channel"""
    
    def __init__(self, channel_id: int):
        self.id = channel_id
        
    async def connect(self):
        """Mock voice connection - actual connection handled by Discord.py"""
        return None


class MockChannel:
    """Mock Discord text channel"""
    
    def __init__(self, channel_id: int):
        self.id = channel_id


class StreamAdapter:
    """
    Adapter to convert SL Bridge API calls to Discord StreamService calls.
    
    Bridges the gap between SL's simple parameter-based API and Discord's
    interaction-based service architecture.
    """
    
    def __init__(self, service_registry: ServiceRegistry):
        self.service_registry = service_registry
        self.stream_service = service_registry.get(StreamService)
        
        # Track stream state for SL Bridge
        self._stream_status: Dict[int, Dict[str, Any]] = {}
        self._stream_history: Dict[int, List[Dict[str, Any]]] = {}
        
        logger.info("StreamAdapter initialized")
    
    async def play_stream(self, url: str, guild_id: int, 
                         channel_id: Optional[int] = None, 
                         user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Start playing a stream (SL Bridge API).
        
        Args:
            url: Stream URL to play
            guild_id: Discord guild ID
            channel_id: Voice channel ID (optional)
            user_id: User ID making the request (optional)
            
        Returns:
            Result dict with success status and message
        """
        try:
            # Create mock interaction for StreamService
            interaction = MockInteraction(guild_id, channel_id, user_id)
            
            # Call actual StreamService
            success = await self.stream_service.start_stream(interaction, url)
            
            if success:
                # Update SL Bridge status tracking
                self._stream_status[guild_id] = {
                    "is_playing": True,
                    "stream_url": url,
                    "start_time": datetime.now(timezone.utc).isoformat(),
                    "channel_id": channel_id
                }
                
                # Add to history
                self._add_to_history(guild_id, url, "started")
                
                return {
                    "success": True,
                    "message": "Stream started successfully",
                    "data": {
                        "url": url,
                        "guild_id": guild_id,
                        "status": "playing"
                    }
                }
            else:
                return {
                    "success": False,
                    "message": "Failed to start stream",
                    "error": "stream_start_failed"
                }
                
        except Exception as e:
            logger.error(f"Error in play_stream adapter: {e}")
            return {
                "success": False,
                "message": f"Error starting stream: {str(e)}",
                "error": "adapter_error"
            }
    
    async def stop_stream(self, guild_id: int) -> Dict[str, Any]:
        """
        Stop current stream (SL Bridge API).
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            Result dict with success status and message
        """
        try:
            # Get guild from bot (if available)
            bot = getattr(self.service_registry, '_services', {}).get('bot')
            if bot:
                guild = discord.utils.get(bot.guilds, id=guild_id)
                if guild:
                    success = await self.stream_service.stop_stream(guild)
                    
                    if success:
                        # Update SL Bridge status
                        if guild_id in self._stream_status:
                            url = self._stream_status[guild_id].get("stream_url", "unknown")
                            self._add_to_history(guild_id, url, "stopped")
                            del self._stream_status[guild_id]
                        
                        return {
                            "success": True,
                            "message": "Stream stopped successfully",
                            "data": {"guild_id": guild_id, "status": "stopped"}
                        }
            
            # Fallback: manual status update
            if guild_id in self._stream_status:
                url = self._stream_status[guild_id].get("stream_url", "unknown")
                self._add_to_history(guild_id, url, "stopped")
                del self._stream_status[guild_id]
            
            return {
                "success": True,
                "message": "Stream stop requested",
                "data": {"guild_id": guild_id, "status": "stopped"}
            }
            
        except Exception as e:
            logger.error(f"Error in stop_stream adapter: {e}")
            return {
                "success": False,
                "message": f"Error stopping stream: {str(e)}",
                "error": "adapter_error"
            }
    
    async def refresh_stream(self, guild_id: int, 
                           channel_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Refresh current stream (SL Bridge API).
        
        Args:
            guild_id: Discord guild ID
            channel_id: Voice channel ID (optional)
            
        Returns:
            Result dict with success status and message
        """
        try:
            # Create mock interaction
            interaction = MockInteraction(guild_id, channel_id)
            
            # Call actual StreamService
            success = await self.stream_service.refresh_stream(interaction)
            
            if success:
                # Update SL Bridge status
                if guild_id in self._stream_status:
                    self._stream_status[guild_id]["last_refreshed"] = datetime.now(timezone.utc).isoformat()
                    url = self._stream_status[guild_id].get("stream_url", "unknown")
                    self._add_to_history(guild_id, url, "refreshed")
                
                return {
                    "success": True,
                    "message": "Stream refreshed successfully",
                    "data": {"guild_id": guild_id, "status": "refreshed"}
                }
            else:
                return {
                    "success": False,
                    "message": "Failed to refresh stream",
                    "error": "refresh_failed"
                }
                
        except Exception as e:
            logger.error(f"Error in refresh_stream adapter: {e}")
            return {
                "success": False,
                "message": f"Error refreshing stream: {str(e)}",
                "error": "adapter_error"
            }
    
    async def get_stream_status(self, guild_id: int) -> Dict[str, Any]:
        """
        Get current stream status (SL Bridge API).
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            Stream status information
        """
        try:
            # Get current song from StreamService
            song_info = await self.stream_service.get_current_song(guild_id)
            
            # Get SL Bridge status
            sl_status = self._stream_status.get(guild_id, {})
            
            # Combine information
            status = {
                "is_playing": bool(song_info or sl_status.get("is_playing", False)),
                "guild_id": guild_id
            }
            
            if song_info:
                status.update({
                    "current_song": song_info.get("song"),
                    "station_name": song_info.get("station"),
                    "stream_url": song_info.get("url"),
                    "bitrate": song_info.get("bitrate")
                })
            elif sl_status:
                status.update({
                    "stream_url": sl_status.get("stream_url"),
                    "start_time": sl_status.get("start_time"),
                    "channel_id": sl_status.get("channel_id")
                })
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting stream status: {e}")
            return {
                "is_playing": False,
                "guild_id": guild_id,
                "error": f"Status error: {str(e)}"
            }
    
    async def get_stream_history(self, guild_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get stream history for guild (SL Bridge API).
        
        Args:
            guild_id: Discord guild ID
            limit: Maximum number of history items
            
        Returns:
            List of historical stream events
        """
        try:
            history = self._stream_history.get(guild_id, [])
            
            # Sort by timestamp (newest first) and limit
            sorted_history = sorted(history, key=lambda x: x.get("timestamp", ""), reverse=True)
            limited_history = sorted_history[:limit]
            
            return limited_history
            
        except Exception as e:
            logger.error(f"Error getting stream history: {e}")
            return []
    
    def _add_to_history(self, guild_id: int, url: str, action: str) -> None:
        """Add event to stream history"""
        try:
            if guild_id not in self._stream_history:
                self._stream_history[guild_id] = []
            
            history_entry = {
                "url": url,
                "action": action,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "guild_id": guild_id
            }
            
            self._stream_history[guild_id].append(history_entry)
            
            # Limit history size per guild
            if len(self._stream_history[guild_id]) > 50:
                self._stream_history[guild_id] = self._stream_history[guild_id][-50:]
                
        except Exception as e:
            logger.error(f"Error adding to stream history: {e}")
    
    def get_adapter_stats(self) -> Dict[str, Any]:
        """Get adapter statistics"""
        return {
            "active_streams": len(self._stream_status),
            "total_history_entries": sum(len(h) for h in self._stream_history.values()),
            "guilds_with_history": len(self._stream_history),
            "adapter_initialized": True
        }
