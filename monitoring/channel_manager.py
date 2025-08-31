"""
Channel Management System for BunBot
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from core import StateManager, EventBus, ConfigurationManager
from .interfaces import IChannelManager

logger = logging.getLogger('discord.monitoring.channel_manager')

class ChannelManager(IChannelManager):
    """
    Channel management service for BunBot announcements.
    
    Manages guild-specific announcement channel configurations
    with intelligent fallback logic for reliable message delivery.
    """
    
    def __init__(self, state_manager: StateManager, event_bus: EventBus, 
                 config_manager: ConfigurationManager, database_connection=None):
        self.state_manager = state_manager
        self.event_bus = event_bus
        self.config_manager = config_manager
        self.db = database_connection
        
        # Cache for channel configurations to reduce database queries
        self._channel_cache: Dict[int, Optional[int]] = {}  # guild_id -> channel_id
        self._cache_expiry = 300  # 5 minutes
        self._last_cache_update = datetime.now(timezone.utc)
        
        logger.info("ChannelManager initialized")
    
    async def set_announcement_channel(self, guild_id: int, channel_id: int) -> bool:
        """
        Set custom announcement channel for a guild.
        
        Args:
            guild_id: Discord guild ID
            channel_id: Discord channel ID for announcements
            
        Returns:
            True if channel was set successfully
        """
        try:
            # Verify channel exists and bot has permissions
            channel = await self._get_and_validate_channel(guild_id, channel_id)
            if not channel:
                return False
            
            # Save to database if available
            if self.db:
                await self.db.execute(
                    "INSERT OR REPLACE INTO guild_monitoring_config "
                    "(guild_id, announcement_channel_id) VALUES (?, ?)",
                    (guild_id, channel_id)
                )
                await self.db.commit()
            
            # Update cache
            self._channel_cache[guild_id] = channel_id
            
            logger.info(f"Set announcement channel for guild {guild_id}: {channel.name} ({channel_id})")
            
            # Emit event for configuration change
            await self.event_bus.emit_async('announcement_channel_set',
                                          guild_id=guild_id,
                                          channel_id=channel_id,
                                          channel_name=channel.name)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to set announcement channel for guild {guild_id}: {e}")
            return False
    
    async def get_announcement_channel(self, guild_id: int):
        """
        Get announcement channel with intelligent fallback logic.
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            Discord TextChannel object or None if no suitable channel found
        """
        try:
            # Check cache first
            await self._refresh_cache_if_needed()
            
            # Try configured announcement channel
            configured_channel_id = await self._get_configured_channel_id(guild_id)
            if configured_channel_id:
                channel = await self._get_and_validate_channel(guild_id, configured_channel_id)
                if channel:
                    logger.debug(f"Using configured announcement channel for guild {guild_id}: {channel.name}")
                    return channel
                else:
                    # Configured channel is invalid, clear it
                    logger.warning(f"Configured announcement channel {configured_channel_id} invalid for guild {guild_id}, clearing")
                    await self.clear_announcement_channel(guild_id)
            
            # Fallback to last active channel from state
            channel = await self._get_last_active_channel(guild_id)
            if channel:
                logger.debug(f"Using last active channel for guild {guild_id}: {channel.name}")
                return channel
            
            # Final fallback to first available channel with send permissions
            channel = await self._get_first_available_channel(guild_id)
            if channel:
                logger.debug(f"Using first available channel for guild {guild_id}: {channel.name}")
                return channel
            
            logger.warning(f"No suitable announcement channel found for guild {guild_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting announcement channel for guild {guild_id}: {e}")
            return None
    
    async def clear_announcement_channel(self, guild_id: int) -> bool:
        """
        Clear custom announcement channel setting for a guild.
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            True if setting was cleared successfully
        """
        try:
            # Clear from database if available
            if self.db:
                await self.db.execute(
                    "UPDATE guild_monitoring_config SET announcement_channel_id = NULL WHERE guild_id = ?",
                    (guild_id,)
                )
                await self.db.commit()
            
            # Clear from cache
            if guild_id in self._channel_cache:
                del self._channel_cache[guild_id]
            
            logger.info(f"Cleared announcement channel setting for guild {guild_id}")
            
            # Emit event for configuration change
            await self.event_bus.emit_async('announcement_channel_cleared',
                                          guild_id=guild_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to clear announcement channel for guild {guild_id}: {e}")
            return False
    
    async def validate_all_channels(self) -> Dict[int, bool]:
        """
        Validate all configured announcement channels.
        
        Returns:
            Dictionary mapping guild_id to validation status
        """
        results = {}
        
        try:
            if not self.db:
                return results
            
            # Get all configured channels
            cursor = await self.db.execute(
                "SELECT guild_id, announcement_channel_id FROM guild_monitoring_config "
                "WHERE announcement_channel_id IS NOT NULL"
            )
            rows = await cursor.fetchall()
            
            for row in rows:
                guild_id, channel_id = row
                try:
                    channel = await self._get_and_validate_channel(guild_id, channel_id)
                    results[guild_id] = channel is not None
                    
                    if not channel:
                        logger.warning(f"Invalid announcement channel {channel_id} for guild {guild_id}")
                        
                except Exception as e:
                    logger.error(f"Error validating channel {channel_id} for guild {guild_id}: {e}")
                    results[guild_id] = False
            
            logger.info(f"Validated {len(results)} configured announcement channels")
            return results
            
        except Exception as e:
            logger.error(f"Error validating announcement channels: {e}")
            return results
    
    async def get_channel_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about channel configurations.
        
        Returns:
            Dictionary with channel configuration statistics
        """
        try:
            stats = {
                'total_guilds': 0,
                'configured_channels': 0,
                'valid_configurations': 0,
                'invalid_configurations': 0,
                'fallback_usage': 0
            }
            
            if not self.db:
                return stats
            
            # Get total configured channels
            cursor = await self.db.execute(
                "SELECT COUNT(*) FROM guild_monitoring_config WHERE announcement_channel_id IS NOT NULL"
            )
            row = await cursor.fetchone()
            stats['configured_channels'] = row[0] if row else 0
            
            # Validate configurations
            validation_results = await self.validate_all_channels()
            stats['valid_configurations'] = sum(1 for valid in validation_results.values() if valid)
            stats['invalid_configurations'] = sum(1 for valid in validation_results.values() if not valid)
            
            # Get total guilds (would need to be calculated from active guilds)
            active_guilds = self.state_manager.get_active_guilds()
            stats['total_guilds'] = len(active_guilds)
            stats['fallback_usage'] = stats['total_guilds'] - stats['valid_configurations']
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting channel statistics: {e}")
            return {
                'total_guilds': 0,
                'configured_channels': 0,
                'valid_configurations': 0,
                'invalid_configurations': 0,
                'fallback_usage': 0
            }
    
    async def _get_configured_channel_id(self, guild_id: int) -> Optional[int]:
        """Get configured channel ID from database or cache"""
        try:
            # Check cache first
            if guild_id in self._channel_cache:
                return self._channel_cache[guild_id]
            
            # Query database
            if self.db:
                cursor = await self.db.execute(
                    "SELECT announcement_channel_id FROM guild_monitoring_config WHERE guild_id = ?",
                    (guild_id,)
                )
                row = await cursor.fetchone()
                
                channel_id = row[0] if row and row[0] else None
                
                # Cache the result
                self._channel_cache[guild_id] = channel_id
                return channel_id
            
            return None
            
        except Exception as e:
            logger.debug(f"Error getting configured channel ID for guild {guild_id}: {e}")
            return None
    
    async def _get_and_validate_channel(self, guild_id: int, channel_id: int):
        """Get channel object and validate permissions"""
        try:
            import bot
            guild = bot.bot.get_guild(guild_id)
            
            if not guild:
                return None
            
            channel = guild.get_channel(channel_id)
            
            if not channel:
                return None
            
            # Check if it's a text channel
            import discord
            if not isinstance(channel, discord.TextChannel):
                return None
            
            # Check if bot has send message permissions
            permissions = channel.permissions_for(guild.me)
            if not permissions.send_messages:
                return None
            
            return channel
            
        except Exception as e:
            logger.debug(f"Error validating channel {channel_id} for guild {guild_id}: {e}")
            return None
    
    async def _get_last_active_channel(self, guild_id: int):
        """Get last active channel from guild state"""
        try:
            state = self.state_manager.get_guild_state(guild_id, create_if_missing=False)
            
            if state and state.text_channel:
                # Validate the channel still exists and has permissions
                channel = state.text_channel
                
                import bot
                guild = bot.bot.get_guild(guild_id)
                if guild and channel in guild.text_channels:
                    permissions = channel.permissions_for(guild.me)
                    if permissions.send_messages:
                        return channel
            
            return None
            
        except Exception as e:
            logger.debug(f"Error getting last active channel for guild {guild_id}: {e}")
            return None
    
    async def _get_first_available_channel(self, guild_id: int):
        """Get first channel with send message permissions"""
        try:
            import bot
            guild = bot.bot.get_guild(guild_id)
            
            if not guild:
                return None
            
            # Find first text channel with send permissions
            for channel in guild.text_channels:
                permissions = channel.permissions_for(guild.me)
                if permissions.send_messages:
                    return channel
            
            return None
            
        except Exception as e:
            logger.debug(f"Error getting first available channel for guild {guild_id}: {e}")
            return None
    
    async def _refresh_cache_if_needed(self) -> None:
        """Refresh cache if it has expired"""
        try:
            current_time = datetime.now(timezone.utc)
            time_since_update = (current_time - self._last_cache_update).total_seconds()
            
            if time_since_update > self._cache_expiry:
                # Clear cache to force refresh on next access
                self._channel_cache.clear()
                self._last_cache_update = current_time
                logger.debug("Refreshed channel cache")
                
        except Exception as e:
            logger.debug(f"Error refreshing channel cache: {e}")
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Get information about the channel cache"""
        return {
            'cached_guilds': len(self._channel_cache),
            'cache_expiry_seconds': self._cache_expiry,
            'last_update': self._last_cache_update.isoformat(),
            'seconds_since_update': (datetime.now(timezone.utc) - self._last_cache_update).total_seconds()
        }
