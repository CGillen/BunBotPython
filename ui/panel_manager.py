"""
Panel Manager for Persistent Music Control Panel
Handles panel lifecycle, state management, and integration with services
"""

import logging
import discord
from typing import Dict, Any, Optional, TYPE_CHECKING
from datetime import datetime, timezone

from core import ServiceRegistry, StateManager, EventBus
from .persistent_music_panel import PersistentMusicPanel

if TYPE_CHECKING:
    from services.ui_service import UIService

logger = logging.getLogger('ui.panel_manager')

class PanelManager:
    """
    Manages persistent music control panels across guilds.
    Handles creation, updates, persistence, and cleanup.
    """
    
    def __init__(self, service_registry: ServiceRegistry):
        self.service_registry = service_registry
        self.state_manager = service_registry.get(StateManager)
        self.event_bus = service_registry.get(EventBus)
        
        # Track active panels
        self.active_panels: Dict[int, PersistentMusicPanel] = {}
        
        # Register event handlers
        self._register_event_handlers()
        
        logger.info("PanelManager initialized")
    
    def _get_ui_service(self):
        """Lazy load UIService to avoid circular dependency"""
        try:
            from services.ui_service import UIService
            return self.service_registry.get_optional(UIService)
        except:
            return None
    
    def _register_event_handlers(self):
        """Register event handlers for panel updates"""
        try:
            # Listen for stream events to update panels
            self.event_bus.subscribe('stream_started', self._handle_stream_started)
            self.event_bus.subscribe('stream_stopped', self._handle_stream_stopped)
            self.event_bus.subscribe('stream_disconnected', self._handle_stream_disconnected)
            self.event_bus.subscribe('song_changed', self._handle_song_changed)
            
            logger.debug("Panel event handlers registered")
        except Exception as e:
            logger.error(f"Error registering panel event handlers: {e}")
    
    async def create_panel(self, guild_id: int, channel: discord.TextChannel) -> bool:
        """
        Create a persistent music control panel in the specified channel.
        
        Args:
            guild_id: Discord guild ID
            channel: Text channel to create panel in
            
        Returns:
            True if panel created successfully, False otherwise
        """
        try:
            logger.info(f"[{guild_id}]: Creating persistent music panel in #{channel.name}")
            
            # Check if panel already exists
            if guild_id in self.active_panels:
                logger.warning(f"[{guild_id}]: Panel already exists, removing old panel first")
                await self.remove_panel(guild_id)
            
            # Create new panel
            panel = PersistentMusicPanel(self.service_registry, guild_id)
            
            # Create status embed
            embed = await panel._create_status_embed()
            
            # Send panel message
            message = await channel.send(embed=embed, view=panel)
            
            # Store panel and message info
            self.active_panels[guild_id] = panel
            
            # Update guild state with panel info
            guild_state = self.state_manager.get_guild_state(guild_id, create_if_missing=True)
            guild_state.panel_message_id = message.id
            guild_state.panel_channel_id = channel.id
            guild_state.panel_created_at = datetime.now(timezone.utc)
            
            logger.info(f"[{guild_id}]: Persistent music panel created successfully (Message ID: {message.id})")
            return True
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Error creating persistent music panel: {e}")
            return False
    
    async def remove_panel(self, guild_id: int) -> bool:
        """
        Remove the persistent music control panel for a guild.
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            True if panel removed successfully, False otherwise
        """
        try:
            logger.info(f"[{guild_id}]: Removing persistent music panel")
            
            # Remove from active panels
            if guild_id in self.active_panels:
                del self.active_panels[guild_id]
            
            # Clear panel info from guild state
            guild_state = self.state_manager.get_guild_state(guild_id)
            if guild_state:
                if hasattr(guild_state, 'panel_message_id'):
                    # Try to delete the message
                    try:
                        from discord.ext import commands
                        bot = self.service_registry.get_optional(commands.AutoShardedBot)
                        if bot and hasattr(guild_state, 'panel_channel_id'):
                            channel = bot.get_channel(guild_state.panel_channel_id)
                            if channel:
                                message = await channel.fetch_message(guild_state.panel_message_id)
                                await message.delete()
                                logger.debug(f"[{guild_id}]: Panel message deleted")
                    except Exception as e:
                        logger.warning(f"[{guild_id}]: Could not delete panel message: {e}")
                
                # Clear panel state
                guild_state.panel_message_id = None
                guild_state.panel_channel_id = None
                guild_state.panel_created_at = None
            
            logger.info(f"[{guild_id}]: Persistent music panel removed successfully")
            return True
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Error removing persistent music panel: {e}")
            return False
    
    async def update_panel(self, guild_id: int, force_update: bool = False) -> bool:
        """
        Update the persistent music control panel for a guild.
        
        Args:
            guild_id: Discord guild ID
            force_update: Force update even if no changes detected
            
        Returns:
            True if panel updated successfully, False otherwise
        """
        try:
            # Check if panel exists
            if guild_id not in self.active_panels:
                logger.debug(f"[{guild_id}]: No active panel to update")
                return False
            
            panel = self.active_panels[guild_id]
            guild_state = self.state_manager.get_guild_state(guild_id)
            
            if not guild_state or not hasattr(guild_state, 'panel_message_id') or not guild_state.panel_message_id:
                logger.warning(f"[{guild_id}]: Panel exists but no message ID stored")
                return False
            
            # Update button states
            panel._update_button_states()
            
            # Create updated embed
            embed = await panel._create_status_embed()
            
            # Get the message and update it
            try:
                from discord.ext import commands
                bot = self.service_registry.get_optional(commands.AutoShardedBot)
                if not bot:
                    logger.error(f"[{guild_id}]: Bot instance not available for panel update")
                    return False
                
                channel = bot.get_channel(guild_state.panel_channel_id)
                if not channel:
                    logger.warning(f"[{guild_id}]: Panel channel not found, removing panel")
                    await self.remove_panel(guild_id)
                    return False
                
                message = await channel.fetch_message(guild_state.panel_message_id)
                await message.edit(embed=embed, view=panel)
                
                logger.debug(f"[{guild_id}]: Panel updated successfully")
                return True
                
            except discord.NotFound:
                logger.warning(f"[{guild_id}]: Panel message not found, removing panel")
                await self.remove_panel(guild_id)
                return False
            except Exception as e:
                logger.error(f"[{guild_id}]: Error updating panel message: {e}")
                return False
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Error updating persistent music panel: {e}")
            return False
    
    async def restore_panels(self) -> int:
        """
        Restore persistent panels after bot restart.
        
        Returns:
            Number of panels successfully restored
        """
        try:
            logger.info("Restoring persistent music panels after restart...")
            
            restored_count = 0
            from discord.ext import commands
            bot = self.service_registry.get_optional(commands.AutoShardedBot)
            
            if not bot:
                logger.error("Bot instance not available for panel restoration")
                return 0
            
            # Get all guild states with panel info
            for guild_id in self.state_manager.get_all_guild_ids():
                try:
                    guild_state = self.state_manager.get_guild_state(guild_id)
                    
                    if (guild_state and 
                        hasattr(guild_state, 'panel_message_id') and 
                        guild_state.panel_message_id and
                        hasattr(guild_state, 'panel_channel_id') and
                        guild_state.panel_channel_id):
                        
                        # Try to restore the panel
                        channel = bot.get_channel(guild_state.panel_channel_id)
                        if not channel:
                            logger.warning(f"[{guild_id}]: Panel channel not found during restoration")
                            continue
                        
                        try:
                            message = await channel.fetch_message(guild_state.panel_message_id)
                            
                            # Create new panel instance
                            panel = PersistentMusicPanel(self.service_registry, guild_id)
                            
                            # Update the message with the new view
                            embed = await panel._create_status_embed()
                            await message.edit(embed=embed, view=panel)
                            
                            # Store the restored panel
                            self.active_panels[guild_id] = panel
                            
                            logger.info(f"[{guild_id}]: Panel restored successfully")
                            restored_count += 1
                            
                        except discord.NotFound:
                            logger.warning(f"[{guild_id}]: Panel message not found during restoration, clearing state")
                            guild_state.panel_message_id = None
                            guild_state.panel_channel_id = None
                            guild_state.panel_created_at = None
                        except Exception as e:
                            logger.error(f"[{guild_id}]: Error restoring panel: {e}")
                
                except Exception as e:
                    logger.error(f"[{guild_id}]: Error processing guild during panel restoration: {e}")
            
            logger.info(f"Panel restoration complete: {restored_count} panels restored")
            return restored_count
            
        except Exception as e:
            logger.error(f"Error during panel restoration: {e}")
            return 0
    
    def get_panel(self, guild_id: int) -> Optional[PersistentMusicPanel]:
        """
        Get the active panel for a guild.
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            Panel instance or None if not found
        """
        return self.active_panels.get(guild_id)
    
    def has_panel(self, guild_id: int) -> bool:
        """
        Check if a guild has an active panel.
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            True if panel exists, False otherwise
        """
        return guild_id in self.active_panels
    
    def get_panel_count(self) -> int:
        """
        Get the number of active panels.
        
        Returns:
            Number of active panels
        """
        return len(self.active_panels)
    
    def get_panel_stats(self) -> Dict[str, Any]:
        """
        Get statistics about active panels.
        
        Returns:
            Dictionary with panel statistics
        """
        return {
            'active_panels': len(self.active_panels),
            'guild_ids': list(self.active_panels.keys()),
            'total_guilds_with_state': len(self.state_manager.get_all_guild_ids())
        }
    
    # Event handlers
    async def _handle_stream_started(self, event):
        """Handle stream started event"""
        try:
            guild_id = event.get_event_data('guild_id')
            if guild_id and guild_id in self.active_panels:
                await self.update_panel(guild_id)
                logger.debug(f"[{guild_id}]: Panel updated for stream started")
        except Exception as e:
            logger.error(f"Error handling stream started event: {e}")
    
    async def _handle_stream_stopped(self, event):
        """Handle stream stopped event"""
        try:
            guild_id = event.get_event_data('guild_id')
            if guild_id and guild_id in self.active_panels:
                await self.update_panel(guild_id)
                logger.debug(f"[{guild_id}]: Panel updated for stream stopped")
        except Exception as e:
            logger.error(f"Error handling stream stopped event: {e}")
    
    async def _handle_stream_disconnected(self, event):
        """Handle stream disconnected event"""
        try:
            guild_id = event.get_event_data('guild_id')
            if guild_id and guild_id in self.active_panels:
                await self.update_panel(guild_id)
                logger.debug(f"[{guild_id}]: Panel updated for stream disconnected")
        except Exception as e:
            logger.error(f"Error handling stream disconnected event: {e}")
    
    async def _handle_song_changed(self, event):
        """Handle song changed event"""
        try:
            guild_id = event.get_event_data('guild_id')
            if guild_id and guild_id in self.active_panels:
                await self.update_panel(guild_id)
                logger.debug(f"[{guild_id}]: Panel updated for song changed")
        except Exception as e:
            logger.error(f"Error handling song changed event: {e}")
