"""
Persistent Music Control Panel for BunBot
Provides Spotify-like persistent controls for music streaming
"""

import logging
import discord
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from core import ServiceRegistry, StateManager, EventBus
from services.stream_service import StreamService
from audio import IVolumeManager, IEffectsChain

logger = logging.getLogger('ui.persistent_music_panel')

class PersistentMusicPanel(discord.ui.View):
    """
    Persistent control panel for music streaming with full functionality.
    Provides Spotify-like interface with buttons for all music controls.
    """
    
    def __init__(self, service_registry: ServiceRegistry, guild_id: int):
        super().__init__(timeout=None)
        self.service_registry = service_registry
        self.guild_id = guild_id
        
        # Get required services
        self.stream_service = service_registry.get(StreamService)
        self.state_manager = service_registry.get(StateManager)
        self.event_bus = service_registry.get(EventBus)
        self.volume_manager = service_registry.get_optional(IVolumeManager)
        self.effects_chain = service_registry.get_optional(IEffectsChain)
        
        # Initialize button states
        self._update_button_states()
        
        logger.info(f"[{guild_id}]: Persistent music panel initialized")
    
    def _update_button_states(self):
        """Update button states based on current stream status"""
        try:
            guild_state = self.state_manager.get_guild_state(self.guild_id)
            is_playing = guild_state and guild_state.current_stream_url is not None
            
            # Update play/pause button
            play_pause_button = discord.utils.get(self.children, custom_id="music_play_pause")
            if play_pause_button:
                if is_playing:
                    play_pause_button.emoji = "⏸️"
                    play_pause_button.label = "Pause"
                    play_pause_button.style = discord.ButtonStyle.success
                else:
                    play_pause_button.emoji = "▶️"
                    play_pause_button.label = "Play"
                    play_pause_button.style = discord.ButtonStyle.primary
            
            # Update stop button
            stop_button = discord.utils.get(self.children, custom_id="music_stop")
            if stop_button:
                stop_button.disabled = not is_playing
            
            # Update refresh button
            refresh_button = discord.utils.get(self.children, custom_id="music_refresh")
            if refresh_button:
                refresh_button.disabled = not is_playing
                
        except Exception as e:
            logger.error(f"[{self.guild_id}]: Error updating button states: {e}")
    
    @discord.ui.button(
        emoji="▶️", 
        label="Play", 
        style=discord.ButtonStyle.primary, 
        custom_id="music_play_pause",
        row=0
    )
    async def play_pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle play/pause button click"""
        try:
            await interaction.response.defer()
            
            guild_state = self.state_manager.get_guild_state(self.guild_id)
            
            if guild_state and guild_state.current_stream_url:
                # Currently playing - show pause/resume options via modal
                modal = PlayPauseModal(self.service_registry, self.guild_id)
                await interaction.followup.send_modal(modal)
            else:
                # Not playing - show station selection modal
                modal = StationSelectionModal(self.service_registry, self.guild_id)
                await interaction.followup.send_modal(modal)
                
        except Exception as e:
            logger.error(f"[{self.guild_id}]: Error in play_pause: {e}")
            await interaction.followup.send("❌ Error handling play/pause action", ephemeral=True)
    
    @discord.ui.button(
        emoji="⏹️", 
        label="Stop", 
        style=discord.ButtonStyle.danger, 
        custom_id="music_stop",
        row=0
    )
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle stop button click"""
        try:
            await interaction.response.defer()
            
            guild = interaction.guild
            if guild:
                success = await self.stream_service.stop_stream(guild)
                if success:
                    await interaction.followup.send("⏹️ Stream stopped", ephemeral=True)
                    await self._update_panel_display()
                else:
                    await interaction.followup.send("❌ Failed to stop stream", ephemeral=True)
            else:
                await interaction.followup.send("❌ Guild not found", ephemeral=True)
                
        except Exception as e:
            logger.error(f"[{self.guild_id}]: Error in stop: {e}")
            await interaction.followup.send("❌ Error stopping stream", ephemeral=True)
    
    @discord.ui.button(
        emoji="🔄", 
        label="Refresh", 
        style=discord.ButtonStyle.secondary, 
        custom_id="music_refresh",
        row=0
    )
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle refresh button click"""
        try:
            await interaction.response.defer()
            
            success = await self.stream_service.refresh_stream(interaction)
            if success:
                await interaction.followup.send("🔄 Stream refreshed", ephemeral=True)
                await self._update_panel_display()
            else:
                await interaction.followup.send("❌ Failed to refresh stream", ephemeral=True)
                
        except Exception as e:
            logger.error(f"[{self.guild_id}]: Error in refresh: {e}")
            await interaction.followup.send("❌ Error refreshing stream", ephemeral=True)
    
    @discord.ui.button(
        emoji="📻", 
        label="Stations", 
        style=discord.ButtonStyle.secondary, 
        custom_id="music_stations",
        row=0
    )
    async def stations(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle stations button click"""
        try:
            modal = StationSelectionModal(self.service_registry, self.guild_id)
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            logger.error(f"[{self.guild_id}]: Error in stations: {e}")
            await interaction.followup.send("❌ Error opening station selection", ephemeral=True)
    
    @discord.ui.button(
        emoji="⭐", 
        label="Favorites", 
        style=discord.ButtonStyle.secondary, 
        custom_id="music_favorites",
        row=0
    )
    async def favorites(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle favorites button click"""
        try:
            modal = FavoritesModal(self.service_registry, self.guild_id)
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            logger.error(f"[{self.guild_id}]: Error in favorites: {e}")
            await interaction.followup.send("❌ Error opening favorites", ephemeral=True)
    
    @discord.ui.button(
        emoji="🔊", 
        label="Volume", 
        style=discord.ButtonStyle.secondary, 
        custom_id="music_volume",
        row=1
    )
    async def volume_control(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle volume button click"""
        try:
            # Get current volume
            current_volume = 80  # Default
            if self.volume_manager:
                try:
                    current_volume = int(await self.volume_manager.get_master_volume(self.guild_id) * 100)
                except:
                    pass
            
            modal = VolumeModal(self.service_registry, self.guild_id, current_volume)
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            logger.error(f"[{self.guild_id}]: Error in volume_control: {e}")
            await interaction.followup.send("❌ Error opening volume control", ephemeral=True)
    
    @discord.ui.button(
        emoji="🎚️", 
        label="EQ", 
        style=discord.ButtonStyle.secondary, 
        custom_id="music_eq",
        row=1
    )
    async def eq_control(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle EQ button click"""
        try:
            # Get current EQ settings
            current_eq = {'bass': 0.0, 'mid': 0.0, 'treble': 0.0}
            if self.effects_chain:
                try:
                    # Get EQ settings from effects chain
                    if hasattr(self.effects_chain, '_effect_chains') and self.guild_id in self.effects_chain._effect_chains:
                        effects = self.effects_chain._effect_chains[self.guild_id]
                        for effect in effects:
                            if 'equalizer' in str(effect.get('type', '')).lower() and effect.get('enabled', False):
                                current_eq = effect.get('parameters', current_eq)
                                break
                except:
                    pass
            
            modal = EQModal(self.service_registry, self.guild_id, current_eq)
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            logger.error(f"[{self.guild_id}]: Error in eq_control: {e}")
            await interaction.followup.send("❌ Error opening EQ control", ephemeral=True)
    
    @discord.ui.button(
        emoji="🎛️", 
        label="Effects", 
        style=discord.ButtonStyle.secondary, 
        custom_id="music_effects",
        row=1
    )
    async def effects_control(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle effects button click"""
        try:
            modal = EffectsModal(self.service_registry, self.guild_id)
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            logger.error(f"[{self.guild_id}]: Error in effects_control: {e}")
            await interaction.followup.send("❌ Error opening effects control", ephemeral=True)
    
    @discord.ui.button(
        emoji="ℹ️", 
        label="Info", 
        style=discord.ButtonStyle.secondary, 
        custom_id="music_info",
        row=1
    )
    async def info_display(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle info button click"""
        try:
            await interaction.response.defer(ephemeral=True)
            
            # Get current stream info
            song_info = await self.stream_service.get_current_song(self.guild_id)
            guild_state = self.state_manager.get_guild_state(self.guild_id)
            
            embed = discord.Embed(
                title="🎵 Stream Information",
                color=0x00ff00 if song_info else 0xff0000,
                timestamp=datetime.now(timezone.utc)
            )
            
            if song_info:
                embed.add_field(name="🎵 Now Playing", value=song_info.get('song', 'Unknown'), inline=False)
                embed.add_field(name="📻 Station", value=song_info.get('station', 'Unknown'), inline=True)
                embed.add_field(name="🎧 Bitrate", value=f"{song_info.get('bitrate', 'Unknown')} kbps", inline=True)
                embed.add_field(name="🔗 URL", value=song_info.get('url', 'Unknown'), inline=False)
            else:
                embed.add_field(name="Status", value="No stream currently playing", inline=False)
            
            if guild_state:
                if guild_state.start_time:
                    duration = datetime.now(timezone.utc) - guild_state.start_time
                    embed.add_field(name="⏱️ Playing For", value=str(duration).split('.')[0], inline=True)
            
            # Add volume and EQ info
            if self.volume_manager:
                try:
                    volume = await self.volume_manager.get_master_volume(self.guild_id)
                    embed.add_field(name="🔊 Volume", value=f"{int(volume * 100)}%", inline=True)
                except:
                    pass
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"[{self.guild_id}]: Error in info_display: {e}")
            await interaction.followup.send("❌ Error getting stream info", ephemeral=True)
    
    @discord.ui.button(
        emoji="⚙️", 
        label="Settings", 
        style=discord.ButtonStyle.secondary, 
        custom_id="music_settings",
        row=1
    )
    async def settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle settings button click"""
        try:
            modal = SettingsModal(self.service_registry, self.guild_id)
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            logger.error(f"[{self.guild_id}]: Error in settings: {e}")
            await interaction.followup.send("❌ Error opening settings", ephemeral=True)
    
    async def _update_panel_display(self):
        """Update the panel display with current status"""
        try:
            self._update_button_states()
            
            # Note: Panel updates are handled by the PanelManager through the event system
            # This method is kept for potential future direct updates
            logger.debug(f"[{self.guild_id}]: Panel display update requested")
                    
        except Exception as e:
            logger.error(f"[{self.guild_id}]: Error updating panel display: {e}")
    
    async def _create_status_embed(self) -> discord.Embed:
        """Create status embed for the panel"""
        try:
            song_info = await self.stream_service.get_current_song(self.guild_id)
            guild_state = self.state_manager.get_guild_state(self.guild_id)
            
            if song_info:
                embed = discord.Embed(
                    title="🎵 Now Playing",
                    description=f"**{song_info.get('song', 'Unknown Track')}**",
                    color=0x00ff00,
                    timestamp=datetime.now(timezone.utc)
                )
                
                # Add station info
                station_info = f"📻 {song_info.get('station', 'Unknown Station')}"
                if song_info.get('bitrate'):
                    station_info += f" | 🎧 {song_info['bitrate']} kbps"
                
                if guild_state and guild_state.start_time:
                    duration = datetime.now(timezone.utc) - guild_state.start_time
                    station_info += f" | ⏱️ {str(duration).split('.')[0]}"
                
                embed.add_field(name="Stream Info", value=station_info, inline=False)
                
                # Add volume info
                if self.volume_manager:
                    try:
                        volume = await self.volume_manager.get_master_volume(self.guild_id)
                        embed.add_field(name="🔊 Volume", value=f"{int(volume * 100)}%", inline=True)
                    except:
                        pass
                
                # Add status indicator
                embed.add_field(name="📡 Status", value="🟢 Connected", inline=True)
                
            else:
                embed = discord.Embed(
                    title="🎵 Music Control Panel",
                    description="No stream currently playing",
                    color=0x808080,
                    timestamp=datetime.now(timezone.utc)
                )
                embed.add_field(name="📡 Status", value="🔴 Disconnected", inline=True)
            
            embed.set_footer(text="Use the buttons below to control playback")
            return embed
            
        except Exception as e:
            logger.error(f"[{self.guild_id}]: Error creating status embed: {e}")
            return discord.Embed(
                title="🎵 Music Control Panel",
                description="Error loading status",
                color=0xff0000
            )


# Import modal classes (will be defined in separate file)
from .music_modals import (
    PlayPauseModal, StationSelectionModal, FavoritesModal,
    VolumeModal, EQModal, EffectsModal, SettingsModal
)
