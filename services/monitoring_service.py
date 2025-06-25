"""
Monitoring Service for BunBot
"""

import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from discord.ext import tasks

from core import ServiceRegistry, StateManager, EventBus
from .stream_service import StreamService
from .ui_service import UIService
from streamscrobbler import streamscrobbler

logger = logging.getLogger('services.monitoring_service')

class MonitoringService:
    """
    Background monitoring service for BunBot.
    
    Monitors active streams for metadata changes, health status,
    and automatically handles stream disconnections.
    """
    
    def __init__(self, service_registry: ServiceRegistry):
        self.service_registry = service_registry
        self.state_manager = service_registry.get(StateManager)
        self.event_bus = service_registry.get(EventBus)
        
        # Get related services
        self.stream_service = service_registry.get(StreamService)
        self.ui_service = service_registry.get(UIService)
        
        # Monitoring state
        self._monitoring_active = False
        self._check_interval = 15  # seconds
        
        logger.info("MonitoringService initialized")
    
    async def start_monitoring(self) -> None:
        """Start background monitoring tasks"""
        try:
            if self._monitoring_active:
                logger.warning("Monitoring already active")
                return
            
            self._monitoring_active = True
            
            # Start the metadata monitoring task
            self.monitor_metadata.start()
            
            logger.info("Background monitoring started")
            
        except Exception as e:
            logger.error(f"Failed to start monitoring: {e}")
            raise
    
    async def stop_monitoring(self) -> None:
        """Stop background monitoring tasks"""
        try:
            if not self._monitoring_active:
                logger.debug("Monitoring not active")
                return
            
            self._monitoring_active = False
            
            # Stop the monitoring task
            if self.monitor_metadata.is_running():
                self.monitor_metadata.cancel()
            
            logger.info("Background monitoring stopped")
            
        except Exception as e:
            logger.error(f"Error stopping monitoring: {e}")
    
    @tasks.loop(seconds=15)
    async def monitor_metadata(self):
        """
        Monitor metadata for all active streams.
        
        This replaces the original monitor_metadata() task from bot.py
        with enhanced error handling and service integration.
        """
        try:
            if not self._monitoring_active:
                return
            
            logger.debug("Checking metadata for all streams")
            
            # Get active streams from StreamService
            active_streams = self.stream_service.get_active_streams()
            
            for guild_id, stream_info in active_streams.items():
                try:
                    await self._monitor_guild_stream(guild_id, stream_info)
                except Exception as e:
                    logger.error(f"[{guild_id}]: Error monitoring stream: {e}")
                    # Handle stream error but continue monitoring other guilds
                    await self._handle_stream_error(guild_id, e)
            
        except Exception as e:
            logger.error(f"Unhandled error in metadata monitor: {e}")
    
    async def _monitor_guild_stream(self, guild_id: int, stream_info: Dict[str, Any]) -> None:
        """Monitor a specific guild's stream"""
        try:
            logger.debug(f"[{guild_id}]: Checking metadata")
            
            guild_state = self.state_manager.get_guild_state(guild_id)
            if not guild_state or not guild_state.current_stream_url:
                logger.warning(f"[{guild_id}]: No stream URL in state")
                return
            
            current_song = guild_state.current_song
            url = guild_state.current_stream_url
            
            # Get station information
            station_info = streamscrobbler.get_server_info(url)
            
            if station_info is None:
                logger.warning(f"[{guild_id}]: Streamscrobbler returned None")
                return
            
            if station_info['status'] <= 0:
                logger.info(f"[{guild_id}]: Stream ended, disconnecting")
                await self._handle_stream_offline(guild_id, station_info)
                return
            
            if not station_info.get('metadata'):
                logger.warning(f"[{guild_id}]: No metadata from server")
                return
            
            # Check for song changes
            new_song = station_info['metadata'].get('song')
            if isinstance(new_song, str):
                logger.info(f"[{guild_id}]: Station info: {station_info}")
                
                if current_song is None:
                    # First song detection
                    guild_state.current_song = new_song
                    logger.info(f"[{guild_id}]: Initial song detected: {new_song}")
                    
                elif current_song != new_song:
                    # Song changed - send update
                    await self._send_song_update(guild_id, station_info)
                    guild_state.current_song = new_song
                    logger.info(f"[{guild_id}]: Song changed to: {new_song}")
            else:
                logger.warning(f"[{guild_id}]: Received non-string song value")
                
        except Exception as e:
            logger.error(f"[{guild_id}]: Stream monitoring error: {e}")
            raise
    
    async def _send_song_update(self, guild_id: int, station_info: Dict[str, Any]) -> None:
        """Send song update to the guild's text channel"""
        try:
            guild_state = self.state_manager.get_guild_state(guild_id)
            if not guild_state or not guild_state.text_channel:
                logger.warning(f"[{guild_id}]: No text channel for song update")
                return
            
            channel = guild_state.text_channel
            
            # Use UIService to send enhanced now playing embed
            message = await self.ui_service.send_now_playing(
                channel, 
                guild_id, 
                station_info
            )
            
            if message:
                logger.info(f"[{guild_id}]: Sent song update: {station_info['metadata']['song']}")
                
                # Update last updated timestamp
                guild_state.last_updated = datetime.now(timezone.utc)
                
                # Emit event for other systems
                await self.event_bus.emit_async('song_updated',
                                              guild_id=guild_id,
                                              song=station_info['metadata']['song'],
                                              channel_id=channel.id)
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to send song update: {e}")
    
    async def _handle_stream_offline(self, guild_id: int, station_info: Dict[str, Any]) -> None:
        """Handle when a stream goes offline"""
        try:
            logger.info(f"[{guild_id}]: Stream went offline: {station_info}")
            
            guild_state = self.state_manager.get_guild_state(guild_id)
            channel = guild_state.text_channel if guild_state else None
            
            # Try to notify users
            if channel:
                try:
                    if channel.permissions_for(channel.guild.me).send_messages:
                        await channel.send("😰 The stream went offline, I gotta go!")
                    else:
                        logger.warning(f"[{guild_id}]: No permission to send offline message")
                except Exception as e:
                    logger.warning(f"[{guild_id}]: Could not send offline notification: {e}")
            
            # Stop the stream through StreamService
            guild = self._get_guild_by_id(guild_id)
            if guild:
                await self.stream_service.stop_stream(guild)
            
            # Emit event
            await self.event_bus.emit_async('stream_went_offline',
                                          guild_id=guild_id,
                                          reason='stream_offline')
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Error handling stream offline: {e}")
    
    async def _handle_stream_error(self, guild_id: int, error: Exception) -> None:
        """Handle stream monitoring errors"""
        try:
            logger.error(f"[{guild_id}]: Stream error occurred: {error}")
            
            guild_state = self.state_manager.get_guild_state(guild_id)
            channel = guild_state.text_channel if guild_state else None
            
            # Try to notify users
            if channel:
                try:
                    if channel.permissions_for(channel.guild.me).send_messages:
                        await channel.send("😰 Something happened to the stream! I uhhh... gotta go!")
                    else:
                        logger.warning(f"[{guild_id}]: No permission to send error message")
                except Exception as e:
                    logger.warning(f"[{guild_id}]: Could not send error notification: {e}")
            
            # Stop the stream through StreamService
            guild = self._get_guild_by_id(guild_id)
            if guild:
                await self.stream_service.stop_stream(guild)
            
            # Emit event
            await self.event_bus.emit_async('stream_error_occurred',
                                          guild_id=guild_id,
                                          error=str(error))
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Error in error handler: {e}")
    
    def _get_guild_by_id(self, guild_id: int):
        """Get Discord guild by ID"""
        try:
            # Try to get bot from service registry
            bot = self.service_registry.get_optional('bot')
            if bot and hasattr(bot, 'guilds'):
                return next((guild for guild in bot.guilds if guild.id == guild_id), None)
            return None
        except Exception as e:
            logger.debug(f"Could not get guild {guild_id}: {e}")
            return None
    
    def get_monitoring_stats(self) -> Dict[str, Any]:
        """Get monitoring service statistics"""
        active_streams = self.stream_service.get_active_streams()
        
        return {
            'monitoring_active': self._monitoring_active,
            'check_interval_seconds': self._check_interval,
            'task_running': self.monitor_metadata.is_running() if hasattr(self, 'monitor_metadata') else False,
            'active_streams_monitored': len(active_streams),
            'service_initialized': True
        }
    
    async def force_metadata_check(self, guild_id: int) -> Dict[str, Any]:
        """Force an immediate metadata check for a specific guild"""
        try:
            guild_state = self.state_manager.get_guild_state(guild_id)
            if not guild_state or not guild_state.current_stream_url:
                return {
                    'success': False,
                    'error': 'No active stream for guild'
                }
            
            stream_info = {
                'url': guild_state.current_stream_url,
                'start_time': guild_state.start_time,
                'current_song': guild_state.current_song
            }
            
            await self._monitor_guild_stream(guild_id, stream_info)
            
            return {
                'success': True,
                'guild_id': guild_id,
                'checked_at': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed force metadata check: {e}")
            return {
                'success': False,
                'error': str(e)
            }
