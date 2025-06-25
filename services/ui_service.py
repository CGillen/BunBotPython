"""
UI Service for BunBot
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import discord

from core import ServiceRegistry, StateManager, EventBus
from ui.components import Button, SelectMenu, ProgressBar, StatusIndicator

logger = logging.getLogger('services.ui_service')

class UIService:
    """
    Enhanced Discord UI service for BunBot.
    
    Provides rich embeds, interactive components, and consistent
    user interface elements across all bot interactions.
    """
    
    def __init__(self, service_registry: ServiceRegistry):
        self.service_registry = service_registry
        self.state_manager = service_registry.get(StateManager)
        self.event_bus = service_registry.get(EventBus)
        
        # UI theme configuration
        self.colors = {
            'primary': 0x0099ff,
            'success': 0x00ff00,
            'warning': 0xffaa00,
            'error': 0xff0000,
            'info': 0xF0E9DE,
            'neutral': 0x99AAB5
        }
        
        # Emoji constants
        self.emojis = {
            'music': '🎶',
            'play': '▶️',
            'stop': '⏹️',
            'pause': '⏸️',
            'skip': '⏭️',
            'volume_up': '🔊',
            'volume_down': '🔉',
            'mute': '🔇',
            'radio': '📻',
            'star': '⭐',
            'heart': '❤️',
            'fire': '🔥',
            'note': '🎵',
            'headphones': '🎧',
            'speaker': '🔊',
            'microphone': '🎤',
            'loading': '⏳',
            'success': '✅',
            'error': '❌',
            'warning': '⚠️',
            'info': 'ℹ️'
        }
        
        logger.info("UIService initialized")
    
    async def send_now_playing(self, channel: discord.TextChannel, guild_id: int, 
                              station_info: Dict[str, Any]) -> Optional[discord.Message]:
        """
        Send enhanced now playing embed with interactive components.
        
        Args:
            channel: Discord text channel to send to
            guild_id: Discord guild ID
            station_info: Station metadata information
            
        Returns:
            Sent message or None if failed
        """
        try:
            # Check permissions
            if not channel.permissions_for(channel.guild.me).send_messages:
                logger.warning(f"No permission to send messages in {channel}")
                return None
            
            # Get current stream info
            guild_state = self.state_manager.get_guild_state(guild_id)
            stream_url = guild_state.current_stream_url if guild_state else None
            
            if not station_info.get('metadata'):
                logger.warning("No metadata available for now playing embed")
                return None
            
            # Create embed
            embed = discord.Embed(
                title="Now Playing",
                description=f"{self.emojis['music']} {station_info['metadata']['song']} {self.emojis['music']}",
                color=self.colors['primary'],
                timestamp=datetime.now(timezone.utc)
            )
            
            # Add station information
            if station_info.get('server_name'):
                embed.add_field(
                    name=f"{self.emojis['radio']} Station",
                    value=station_info['server_name'],
                    inline=True
                )
            
            if station_info.get('metadata', {}).get('bitrate'):
                embed.add_field(
                    name=f"{self.emojis['headphones']} Quality",
                    value=f"{station_info['metadata']['bitrate']} kbps",
                    inline=True
                )
            
            # Add stream URL as footer
            if stream_url:
                embed.set_footer(text=f"Source: {stream_url}")
            
            # Create interactive components
            view = self._create_now_playing_view(guild_id)
            
            # Send the message
            message = await channel.send(embed=embed, view=view)
            
            # Emit event for monitoring
            await self.event_bus.emit_async('now_playing_sent',
                                          guild_id=guild_id,
                                          song=station_info['metadata']['song'],
                                          channel_id=channel.id)
            
            logger.info(f"[{guild_id}]: Sent now playing: {station_info['metadata']['song']}")
            return message
            
        except Exception as e:
            logger.error(f"Failed to send now playing embed: {e}")
            return None
    
    async def send_stream_status(self, channel: discord.TextChannel, guild_id: int,
                               status: str, details: Optional[str] = None) -> Optional[discord.Message]:
        """
        Send stream status update embed.
        
        Args:
            channel: Discord text channel
            guild_id: Discord guild ID  
            status: Status type ('starting', 'connected', 'disconnected', 'error')
            details: Optional additional details
            
        Returns:
            Sent message or None if failed
        """
        try:
            # Status configuration
            status_config = {
                'starting': {
                    'title': 'Starting Stream',
                    'color': self.colors['info'],
                    'emoji': self.emojis['loading'],
                    'description': 'Connecting to stream...'
                },
                'connected': {
                    'title': 'Stream Connected',
                    'color': self.colors['success'],
                    'emoji': self.emojis['success'],
                    'description': 'Successfully connected to stream!'
                },
                'disconnected': {
                    'title': 'Stream Disconnected',
                    'color': self.colors['warning'],
                    'emoji': self.emojis['stop'],
                    'description': 'Stream has been disconnected.'
                },
                'error': {
                    'title': 'Stream Error',
                    'color': self.colors['error'],
                    'emoji': self.emojis['error'],
                    'description': 'An error occurred with the stream.'
                }
            }
            
            config = status_config.get(status, status_config['info'])
            
            embed = discord.Embed(
                title=f"{config['emoji']} {config['title']}",
                description=config['description'],
                color=config['color'],
                timestamp=datetime.now(timezone.utc)
            )
            
            # Add details if provided
            if details:
                embed.add_field(name="Details", value=details, inline=False)
            
            # Add guild info
            guild_state = self.state_manager.get_guild_state(guild_id)
            if guild_state and guild_state.current_stream_url:
                embed.set_footer(text=f"Stream: {guild_state.current_stream_url}")
            
            return await channel.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Failed to send stream status embed: {e}")
            return None
    
    async def create_favorites_embed(self, guild_id: int, favorites: List[Dict[str, Any]], 
                                   page: int = 0) -> discord.Embed:
        """
        Create enhanced favorites list embed with pagination.
        
        Args:
            guild_id: Discord guild ID
            favorites: List of favorite stations
            page: Current page number
            
        Returns:
            Discord embed for favorites
        """
        try:
            # Guild name will be passed from the calling context
            guild_name = "Server"
            
            if not favorites:
                embed = discord.Embed(
                    title=f"{self.emojis['radio']} Favorites - {guild_name}",
                    description="No favorites set for this server yet!\nUse `/set-favorite` to add some.",
                    color=self.colors['info']
                )
                return embed
            
            # Pagination
            items_per_page = 10
            total_pages = (len(favorites) + items_per_page - 1) // items_per_page
            page = max(0, min(page, total_pages - 1))
            
            start_idx = page * items_per_page
            end_idx = min(start_idx + items_per_page, len(favorites))
            page_favorites = favorites[start_idx:end_idx]
            
            # Create embed
            embed = discord.Embed(
                title=f"{self.emojis['radio']} Favorites - {guild_name}",
                description=f"Page {page + 1} of {total_pages}",
                color=self.colors['primary']
            )
            
            # Add favorites to embed
            for favorite in page_favorites:
                number = favorite.get('favorite_number', '?')
                name = favorite.get('station_name', 'Unknown Station')
                url = favorite.get('stream_url', '')
                
                # Truncate long URLs for display
                display_url = url[:50] + "..." if len(url) > 50 else url
                
                embed.add_field(
                    name=f"{self.emojis['star']} #{number} - {name}",
                    value=f"Use `/play-favorite {number}` or click the button below\n`{display_url}`",
                    inline=False
                )
            
            # Add pagination info
            if total_pages > 1:
                embed.set_footer(text=f"Page {page + 1}/{total_pages} • Total: {len(favorites)} favorites")
            else:
                embed.set_footer(text=f"Total: {len(favorites)} favorites")
            
            return embed
            
        except Exception as e:
            logger.error(f"Failed to create favorites embed: {e}")
            # Return error embed
            return discord.Embed(
                title="Error",
                description="Failed to load favorites",
                color=self.colors['error']
            )
    
    async def create_support_embed(self) -> discord.Embed:
        """Create enhanced support information embed"""
        embed = discord.Embed(
            title="BunBot Support",
            color=self.colors['info'],
            description="Get help and support for BunBot"
        )
        
        embed.add_field(
            name=f"{self.emojis['info']} Got a question?",
            value="Join us at https://discord.gg/ksZbX723Jn\nThe team is always happy to help!",
            inline=False
        )
        
        embed.add_field(
            name=f"{self.emojis['warning']} Found an issue?",
            value="Please create a ticket at\nhttps://github.com/CGillen/BunBotPython/issues\nWe'll appreciate it!",
            inline=False
        )
        
        embed.add_field(
            name=f"{self.emojis['heart']} Like what we're doing?",
            value="Support us on Ko-Fi: https://ko-fi.com/bunbot",
            inline=False
        )
        
        embed.set_footer(text="BunBot is open source under GPLv3 license")
        
        return embed
    
    def _create_now_playing_view(self, guild_id: int) -> discord.ui.View:
        """Create interactive view for now playing embed"""
        view = discord.ui.View(timeout=300)  # 5 minute timeout
        
        # Add control buttons
        # Note: These would need to be connected to actual command handlers
        # For now, they're placeholders that show the UI structure
        
        return view
    
    async def send_error_embed(self, channel: discord.TextChannel, title: str, 
                             description: str, details: Optional[str] = None) -> Optional[discord.Message]:
        """
        Send standardized error embed.
        
        Args:
            channel: Discord text channel
            title: Error title
            description: Error description
            details: Optional additional details
            
        Returns:
            Sent message or None if failed
        """
        try:
            embed = discord.Embed(
                title=f"{self.emojis['error']} {title}",
                description=description,
                color=self.colors['error'],
                timestamp=datetime.now(timezone.utc)
            )
            
            if details:
                embed.add_field(name="Details", value=details, inline=False)
            
            return await channel.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Failed to send error embed: {e}")
            return None
    
    async def send_success_embed(self, channel: discord.TextChannel, title: str,
                               description: str) -> Optional[discord.Message]:
        """
        Send standardized success embed.
        
        Args:
            channel: Discord text channel
            title: Success title
            description: Success description
            
        Returns:
            Sent message or None if failed
        """
        try:
            embed = discord.Embed(
                title=f"{self.emojis['success']} {title}",
                description=description,
                color=self.colors['success'],
                timestamp=datetime.now(timezone.utc)
            )
            
            return await channel.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Failed to send success embed: {e}")
            return None
    
    async def create_interactive_favorites_view(self, guild_id: int, favorites_list: List[Dict[str, Any]], 
                                              page: int = 0) -> tuple[discord.Embed, Optional[discord.ui.View]]:
        """
        Create enhanced interactive favorites view with buttons and pagination.
        
        Args:
            guild_id: Discord guild ID
            favorites_list: List of favorite stations
            page: Current page number
            
        Returns:
            Tuple of (embed, view) for interactive favorites
        """
        try:
            # Import the new favorites view
            from ui.views.favorites_view import FavoritesView
            from ui.interfaces import ComponentTheme, ColorScheme
            
            # Create default theme
            theme = ComponentTheme()
            
            # Create the interactive view with service registry
            favorites_view = FavoritesView(
                theme=theme,
                guild_id=guild_id,
                favorites_list=favorites_list,
                service_registry=self.service_registry,
                page=page,
                favorites_per_page=10
            )
            
            # Build the view components
            await favorites_view._build_view()
            
            # Get embed and view
            embed, view = await favorites_view.get_embed_and_view()
            
            logger.info(f"[{guild_id}]: Created interactive favorites view with {len(favorites_list)} favorites")
            return embed, view
            
        except Exception as e:
            # Error logging with full stack trace
            logger.error(f"Failed to create interactive favorites view for guild {guild_id}: {e}", exc_info=True)
            logger.error(f"Favorites list count: {len(favorites_list) if favorites_list else 0}")
            logger.error(f"Requested page: {page}")
            logger.error(f"Service registry available: {self.service_registry is not None}")
            
            # Fallback to basic embed
            try:
                embed = await self.create_favorites_embed(guild_id, favorites_list, page)
                logger.warning(f"[{guild_id}]: Fell back to basic favorites embed (no interactive buttons)")
                return embed, None
            except Exception as fallback_error:
                logger.error(f"Even fallback embed creation failed for guild {guild_id}: {fallback_error}", exc_info=True)
                # Return minimal error embed
                error_embed = discord.Embed(
                    title="❌ Error Loading Favorites",
                    description="Failed to load favorites. Please try again.",
                    color=self.colors['error']
                )
                return error_embed, None
    
    def get_ui_stats(self) -> Dict[str, Any]:
        """Get UI service statistics"""
        return {
            'colors_configured': len(self.colors),
            'emojis_available': len(self.emojis),
            'service_initialized': True
        }
