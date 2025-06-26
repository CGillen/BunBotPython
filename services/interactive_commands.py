"""
Interactive Command Enhancement Service

Enhances Discord commands with interactive buttons and improved responses.
Provides engaging user experience with clickable controls.
"""

import logging
from typing import Dict, Any, Optional, List
import asyncio
from datetime import datetime

import discord
from discord.ext import commands

from core import ServiceRegistry
from ui.views.base_view import BaseView
from services.stream_service import StreamService
from services.favorites_service import FavoritesService

logger = logging.getLogger('services.interactive_commands')


class InteractivePlayView(BaseView):
    """Enhanced play command response with interactive controls"""
    
    def __init__(self, service_registry: ServiceRegistry, guild_id: int, stream_url: str):
        super().__init__(timeout=60)  # 1 minute timeout
        
        self.service_registry = service_registry
        self.guild_id = guild_id
        self.stream_url = stream_url
        
        self.stream_service = service_registry.get(StreamService)
        self.favorites_service = service_registry.get(FavoritesService)
        
        # Add interactive buttons
        self._setup_buttons()
        
    def _setup_buttons(self):
        """Set up interactive buttons for play response"""
        
        # Stop button
        stop_button = discord.ui.Button(
            label="⏹️ Stop",
            style=discord.ButtonStyle.danger,
            custom_id="stop_stream"
        )
        stop_button.callback = self._stop_callback
        self.add_item(stop_button)
        
        # Refresh button
        refresh_button = discord.ui.Button(
            label="🔄 Refresh",
            style=discord.ButtonStyle.secondary,
            custom_id="refresh_stream"
        )
        refresh_button.callback = self._refresh_callback
        self.add_item(refresh_button)
        
        # Add to favorites button
        favorite_button = discord.ui.Button(
            label="⭐ Add Favorite",
            style=discord.ButtonStyle.primary,
            custom_id="add_favorite"
        )
        favorite_button.callback = self._favorite_callback
        self.add_item(favorite_button)
        
        # Volume controls
        volume_down = discord.ui.Button(
            label="🔉 -10%",
            style=discord.ButtonStyle.secondary,
            custom_id="volume_down"
        )
        volume_down.callback = self._volume_down_callback
        self.add_item(volume_down)
        
        volume_up = discord.ui.Button(
            label="🔊 +10%",
            style=discord.ButtonStyle.secondary,
            custom_id="volume_up"
        )
        volume_up.callback = self._volume_up_callback
        self.add_item(volume_up)
    
    async def _stop_callback(self, interaction: discord.Interaction):
        """Handle stop button click"""
        try:
            await interaction.response.defer()
            
            success = await self.stream_service.stop_stream(self.guild_id)
            
            if success:
                # Disable all buttons
                for item in self.children:
                    item.disabled = True
                
                embed = discord.Embed(
                    title="⏹️ Stream Stopped",
                    description="Stream has been stopped successfully",
                    color=0xff6b6b
                )
                
                await interaction.edit_original_response(embed=embed, view=self)
            else:
                await interaction.followup.send(
                    "❌ Failed to stop stream",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"Error stopping stream: {e}")
            await interaction.followup.send(
                "❌ Error stopping stream",
                ephemeral=True
            )
    
    async def _refresh_callback(self, interaction: discord.Interaction):
        """Handle refresh button click"""
        try:
            await interaction.response.defer()
            
            # Get current stream status
            status = await self.stream_service.get_stream_status(self.guild_id)
            
            if status and status.get('is_playing'):
                embed = discord.Embed(
                    title="🎵 Stream Status Refreshed",
                    description=f"**Currently Playing:** {status.get('current_song', 'Unknown')}\n"
                               f"**Stream:** {status.get('stream_url', 'Unknown')}\n"
                               f"**Volume:** {int(status.get('volume', 0.8) * 100)}%",
                    color=0x51cf66,
                    timestamp=datetime.now()
                )
                
                await interaction.edit_original_response(embed=embed, view=self)
            else:
                embed = discord.Embed(
                    title="📻 No Active Stream",
                    description="No stream is currently playing",
                    color=0x868e96
                )
                
                # Disable all buttons except for play again
                for item in self.children:
                    if item.custom_id != "add_favorite":
                        item.disabled = True
                
                await interaction.edit_original_response(embed=embed, view=self)
                
        except Exception as e:
            logger.error(f"Error refreshing status: {e}")
            await interaction.followup.send(
                "❌ Error refreshing status",
                ephemeral=True
            )
    
    async def _favorite_callback(self, interaction: discord.Interaction):
        """Handle add to favorites button click"""
        try:
            await interaction.response.defer()
            
            # Extract station name from URL or use default
            station_name = self._extract_station_name(self.stream_url)
            
            success = await self.favorites_service.add_favorite(
                guild_id=self.guild_id,
                user_id=interaction.user.id,
                name=station_name,
                url=self.stream_url
            )
            
            if success:
                # Update button to show added
                for item in self.children:
                    if item.custom_id == "add_favorite":
                        item.label = "✅ Added"
                        item.style = discord.ButtonStyle.success
                        item.disabled = True
                        break
                
                await interaction.edit_original_response(view=self)
                await interaction.followup.send(
                    f"⭐ Added **{station_name}** to your favorites!",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ Failed to add to favorites (may already exist)",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"Error adding favorite: {e}")
            await interaction.followup.send(
                "❌ Error adding to favorites",
                ephemeral=True
            )
    
    async def _volume_down_callback(self, interaction: discord.Interaction):
        """Handle volume down button"""
        await self._adjust_volume(interaction, -0.1)
    
    async def _volume_up_callback(self, interaction: discord.Interaction):
        """Handle volume up button"""
        await self._adjust_volume(interaction, +0.1)
    
    async def _adjust_volume(self, interaction: discord.Interaction, delta: float):
        """Adjust volume by delta amount"""
        try:
            await interaction.response.defer()
            
            # Get current volume
            status = await self.stream_service.get_stream_status(self.guild_id)
            current_volume = status.get('volume', 0.8) if status else 0.8
            
            # Calculate new volume
            new_volume = max(0.0, min(1.0, current_volume + delta))
            
            # Set new volume
            success = await self.stream_service.set_volume(self.guild_id, new_volume)
            
            if success:
                await interaction.followup.send(
                    f"🔊 Volume {'increased' if delta > 0 else 'decreased'} to {int(new_volume * 100)}%",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ Failed to adjust volume",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"Error adjusting volume: {e}")
            await interaction.followup.send(
                "❌ Error adjusting volume",
                ephemeral=True
            )
    
    def _extract_station_name(self, url: str) -> str:
        """Extract a friendly station name from URL"""
        try:
            # Simple extraction logic
            if 'radioparadise' in url.lower():
                return "Radio Paradise"
            elif 'soma' in url.lower():
                return "SomaFM"
            elif 'bbc' in url.lower():
                return "BBC Radio"
            elif 'jazz' in url.lower():
                return "Jazz Station"
            else:
                # Extract domain name
                from urllib.parse import urlparse
                parsed = urlparse(url)
                domain = parsed.netloc.replace('www.', '')
                return domain.split('.')[0].title() + " Radio"
        except:
            return "Custom Station"


class InteractiveSongView(BaseView):
    """Enhanced song command response with interactive controls"""
    
    def __init__(self, service_registry: ServiceRegistry, guild_id: int, song_info: Dict[str, Any]):
        super().__init__(timeout=60)  # 1 minute timeout
        
        self.service_registry = service_registry
        self.guild_id = guild_id
        self.song_info = song_info
        
        self.stream_service = service_registry.get(StreamService)
        self.favorites_service = service_registry.get(FavoritesService)
        
        # Add interactive buttons
        self._setup_buttons()
    
    def _setup_buttons(self):
        """Set up interactive buttons for song response"""
        
        # Share button
        share_button = discord.ui.Button(
            label="📤 Share",
            style=discord.ButtonStyle.primary,
            custom_id="share_song"
        )
        share_button.callback = self._share_callback
        self.add_item(share_button)
        
        # Lyrics button (if available)
        lyrics_button = discord.ui.Button(
            label="📜 Lyrics",
            style=discord.ButtonStyle.secondary,
            custom_id="get_lyrics"
        )
        lyrics_button.callback = self._lyrics_callback
        self.add_item(lyrics_button)
        
        # Skip button
        skip_button = discord.ui.Button(
            label="⏭️ Skip",
            style=discord.ButtonStyle.danger,
            custom_id="skip_song"
        )
        skip_button.callback = self._skip_callback
        self.add_item(skip_button)
        
        # Info button
        info_button = discord.ui.Button(
            label="ℹ️ More Info",
            style=discord.ButtonStyle.secondary,
            custom_id="song_info"
        )
        info_button.callback = self._info_callback
        self.add_item(info_button)
    
    async def _share_callback(self, interaction: discord.Interaction):
        """Handle share button click"""
        try:
            song_title = self.song_info.get('title', 'Unknown')
            artist = self.song_info.get('artist', 'Unknown')
            
            share_text = f"🎵 **Now Playing:** {artist} - {song_title}\n"
            share_text += f"Shared by {interaction.user.mention}"
            
            await interaction.response.send_message(share_text)
            
        except Exception as e:
            logger.error(f"Error sharing song: {e}")
            await interaction.response.send_message(
                "❌ Error sharing song",
                ephemeral=True
            )
    
    async def _lyrics_callback(self, interaction: discord.Interaction):
        """Handle lyrics button click"""
        try:
            await interaction.response.defer()
            
            # For now, provide a placeholder response
            song_title = self.song_info.get('title', 'Unknown')
            artist = self.song_info.get('artist', 'Unknown')
            
            embed = discord.Embed(
                title="📜 Lyrics",
                description=f"Lyrics for **{artist} - {song_title}** are not available at this time.\n\n"
                           "You can search for lyrics on:\n"
                           "• [Genius](https://genius.com)\n"
                           "• [AZLyrics](https://azlyrics.com)\n"
                           "• [LyricFind](https://lyricfind.com)",
                color=0x74c0fc
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error getting lyrics: {e}")
            await interaction.followup.send(
                "❌ Error getting lyrics",
                ephemeral=True
            )
    
    async def _skip_callback(self, interaction: discord.Interaction):
        """Handle skip button click"""
        try:
            await interaction.response.defer()
            
            # Refresh the stream (simulating skip)
            success = await self.stream_service.refresh_stream(self.guild_id)
            
            if success:
                await interaction.followup.send(
                    "⏭️ Stream refreshed (skip effect)",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ Failed to refresh stream",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"Error skipping song: {e}")
            await interaction.followup.send(
                "❌ Error skipping song",
                ephemeral=True
            )
    
    async def _info_callback(self, interaction: discord.Interaction):
        """Handle info button click"""
        try:
            await interaction.response.defer()
            
            embed = discord.Embed(
                title="ℹ️ Song Information",
                color=0x51cf66
            )
            
            # Add available song info
            for key, value in self.song_info.items():
                if value and key != 'raw_metadata':
                    embed.add_field(
                        name=key.title().replace('_', ' '),
                        value=str(value),
                        inline=True
                    )
            
            # Add timestamp
            embed.timestamp = datetime.now()
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error getting song info: {e}")
            await interaction.followup.send(
                "❌ Error getting song information",
                ephemeral=True
            )


class InteractiveErrorView(BaseView):
    """Enhanced error response with retry and help options"""
    
    def __init__(self, service_registry: ServiceRegistry, guild_id: int, error_context: str):
        super().__init__(timeout=60)  # 1 minute timeout
        
        self.service_registry = service_registry
        self.guild_id = guild_id
        self.error_context = error_context
        
        # Add interactive buttons
        self._setup_buttons()
    
    def _setup_buttons(self):
        """Set up interactive buttons for error response"""
        
        # Retry button
        retry_button = discord.ui.Button(
            label="🔄 Retry",
            style=discord.ButtonStyle.primary,
            custom_id="retry_action"
        )
        retry_button.callback = self._retry_callback
        self.add_item(retry_button)
        
        # Help button
        help_button = discord.ui.Button(
            label="❓ Help",
            style=discord.ButtonStyle.secondary,
            custom_id="get_help"
        )
        help_button.callback = self._help_callback
        self.add_item(help_button)
        
        # Support button
        support_button = discord.ui.Button(
            label="🆘 Support",
            style=discord.ButtonStyle.secondary,
            custom_id="get_support"
        )
        support_button.callback = self._support_callback
        self.add_item(support_button)
    
    async def _retry_callback(self, interaction: discord.Interaction):
        """Handle retry button click"""
        try:
            await interaction.response.send_message(
                "🔄 To retry, please use the original command again.\n"
                "The system has been notified of the error and may have resolved the issue.",
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error in retry callback: {e}")
    
    async def _help_callback(self, interaction: discord.Interaction):
        """Handle help button click"""
        try:
            embed = discord.Embed(
                title="❓ Help & Troubleshooting",
                description="Here are some common solutions:",
                color=0x74c0fc
            )
            
            embed.add_field(
                name="🔗 Stream URLs",
                value="• Ensure URLs are direct stream links\n"
                      "• Use HTTP/HTTPS protocols\n"
                      "• Avoid playlist or webpage links",
                inline=False
            )
            
            embed.add_field(
                name="🎵 Audio Issues",
                value="• Check if bot is in voice channel\n"
                      "• Verify bot has permissions\n"
                      "• Try refreshing the stream",
                inline=False
            )
            
            embed.add_field(
                name="🤖 Commands",
                value="• Use `/help` for command list\n"
                      "• Use `/support` to contact admins\n"
                      "• Check command syntax",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in help callback: {e}")
            await interaction.response.send_message(
                "❌ Error loading help information",
                ephemeral=True
            )
    
    async def _support_callback(self, interaction: discord.Interaction):
        """Handle support button click"""
        try:
            embed = discord.Embed(
                title="🆘 Support Information",
                description="Need additional help? Here's how to get support:",
                color=0xff6b6b
            )
            
            embed.add_field(
                name="📞 Contact Support",
                value="• Use `/support` command for admin help\n"
                      "• Check server announcements\n"
                      "• Report persistent issues to moderators",
                inline=False
            )
            
            embed.add_field(
                name="🔍 Error Details",
                value=f"Error Context: `{self.error_context}`\n"
                      f"Guild ID: `{self.guild_id}`\n"
                      f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in support callback: {e}")
            await interaction.response.send_message(
                "❌ Error loading support information",
                ephemeral=True
            )


class InteractiveCommandService:
    """Service for creating interactive command responses"""
    
    def __init__(self, service_registry: ServiceRegistry):
        self.service_registry = service_registry
        logger.info("InteractiveCommandService initialized")
    
    def create_play_response(self, guild_id: int, stream_url: str) -> InteractivePlayView:
        """Create interactive response for play command"""
        return InteractivePlayView(self.service_registry, guild_id, stream_url)
    
    def create_song_response(self, guild_id: int, song_info: Dict[str, Any]) -> InteractiveSongView:
        """Create interactive response for song command"""
        return InteractiveSongView(self.service_registry, guild_id, song_info)
    
    def create_error_response(self, guild_id: int, error_context: str) -> InteractiveErrorView:
        """Create interactive response for error scenarios"""
        return InteractiveErrorView(self.service_registry, guild_id, error_context)
