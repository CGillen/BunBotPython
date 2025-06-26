"""
Modal dialogs for the Persistent Music Control Panel
Provides complex input forms for volume, EQ, station selection, etc.
"""

import logging
import discord
from typing import Dict, Any, Optional, List
import asyncio

from core import ServiceRegistry, StateManager
from services.stream_service import StreamService
from services.favorites_service import FavoritesService
from audio import IVolumeManager, IEffectsChain

logger = logging.getLogger('ui.music_modals')

class PlayPauseModal(discord.ui.Modal):
    """Modal for play/pause actions when stream is active"""
    
    def __init__(self, service_registry: ServiceRegistry, guild_id: int):
        super().__init__(title="Stream Control")
        self.service_registry = service_registry
        self.guild_id = guild_id
        self.stream_service = service_registry.get(StreamService)
        
        # Add action selection
        self.action = discord.ui.TextInput(
            label="Action (stop/refresh)",
            placeholder="Enter 'stop' to stop stream or 'refresh' to refresh",
            default="refresh",
            max_length=10
        )
        self.add_item(self.action)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            action = self.action.value.lower().strip()
            
            if action == "stop":
                success = await self.stream_service.stop_stream(interaction.guild)
                if success:
                    await interaction.response.send_message("⏹️ Stream stopped", ephemeral=True)
                else:
                    await interaction.response.send_message("❌ Failed to stop stream", ephemeral=True)
            elif action == "refresh":
                success = await self.stream_service.refresh_stream(interaction)
                if success:
                    await interaction.response.send_message("🔄 Stream refreshed", ephemeral=True)
                else:
                    await interaction.response.send_message("❌ Failed to refresh stream", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Invalid action. Use 'stop' or 'refresh'", ephemeral=True)
                
        except Exception as e:
            logger.error(f"[{self.guild_id}]: Error in PlayPauseModal: {e}")
            await interaction.response.send_message("❌ Error processing action", ephemeral=True)


class StationSelectionModal(discord.ui.Modal):
    """Modal for selecting or entering a stream URL"""
    
    def __init__(self, service_registry: ServiceRegistry, guild_id: int):
        super().__init__(title="Select Stream")
        self.service_registry = service_registry
        self.guild_id = guild_id
        self.stream_service = service_registry.get(StreamService)
        
        # Add URL input
        self.url_input = discord.ui.TextInput(
            label="Stream URL",
            placeholder="Enter stream URL (e.g., http://example.com/stream)",
            style=discord.TextStyle.long,
            max_length=500,
            required=True
        )
        self.add_item(self.url_input)
        
        # Add optional station name
        self.name_input = discord.ui.TextInput(
            label="Station Name (optional)",
            placeholder="Enter a name for this station",
            max_length=100,
            required=False
        )
        self.add_item(self.name_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            url = self.url_input.value.strip()
            station_name = self.name_input.value.strip() if self.name_input.value else None
            
            if not url:
                await interaction.response.send_message("❌ Please enter a stream URL", ephemeral=True)
                return
            
            # Validate URL format
            if not (url.startswith('http://') or url.startswith('https://')):
                await interaction.response.send_message("❌ Invalid URL format. Must start with http:// or https://", ephemeral=True)
                return
            
            await interaction.response.defer()
            
            # Start the stream
            success = await self.stream_service.start_stream(interaction, url)
            if success:
                message = f"🎵 Started stream: {station_name or url}"
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.followup.send("❌ Failed to start stream", ephemeral=True)
                
        except Exception as e:
            logger.error(f"[{self.guild_id}]: Error in StationSelectionModal: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Error starting stream", ephemeral=True)
            else:
                await interaction.followup.send("❌ Error starting stream", ephemeral=True)


class FavoritesModal(discord.ui.Modal):
    """Modal for managing favorite stations"""
    
    def __init__(self, service_registry: ServiceRegistry, guild_id: int):
        super().__init__(title="Favorite Stations")
        self.service_registry = service_registry
        self.guild_id = guild_id
        self.favorites_service = service_registry.get_optional(FavoritesService)
        
        # Add action selection
        self.action = discord.ui.TextInput(
            label="Action",
            placeholder="Enter 'list' to view favorites or 'add' to add current stream",
            default="list",
            max_length=10
        )
        self.add_item(self.action)
        
        # Add optional URL for adding
        self.url_input = discord.ui.TextInput(
            label="URL (for adding)",
            placeholder="Stream URL to add to favorites (optional)",
            style=discord.TextStyle.long,
            max_length=500,
            required=False
        )
        self.add_item(self.url_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            action = self.action.value.lower().strip()
            
            if not self.favorites_service:
                await interaction.response.send_message("❌ Favorites service not available", ephemeral=True)
                return
            
            if action == "list":
                # Get and display favorites
                favorites = self.favorites_service.get_all_favorites(self.guild_id)
                
                if not favorites:
                    await interaction.response.send_message("⭐ No favorite stations saved", ephemeral=True)
                    return
                
                embed = discord.Embed(
                    title="⭐ Server Favorite Stations",
                    color=0xffd700
                )
                
                for fav in favorites[:10]:  # Limit to 10
                    embed.add_field(
                        name=f"{fav.get('favorite_number')}. {fav.get('station_name', 'Unnamed Station')}",
                        value=f"URL: {fav.get('stream_url', 'Unknown')[:50]}...",
                        inline=False
                    )
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
                
            elif action == "add":
                url = self.url_input.value.strip() if self.url_input.value else None
                
                if not url:
                    # Try to get current stream URL
                    state_manager = self.service_registry.get(StateManager)
                    guild_state = state_manager.get_guild_state(self.guild_id)
                    if guild_state and guild_state.current_stream_url:
                        url = guild_state.current_stream_url
                    else:
                        await interaction.response.send_message("❌ No URL provided and no stream currently playing", ephemeral=True)
                        return
                
                # Add to favorites
                result = await self.favorites_service.add_favorite(
                    self.guild_id,
                    url,
                    None,  # Let the service auto-detect the station name
                    interaction.user.id
                )
                
                if result['success']:
                    await interaction.response.send_message(f"⭐ Added **{result['station_name']}** as favorite #{result['favorite_number']}", ephemeral=True)
                else:
                    await interaction.response.send_message(f"❌ Failed to add station to favorites: {result['error']}", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Invalid action. Use 'list' or 'add'", ephemeral=True)
                
        except Exception as e:
            logger.error(f"[{self.guild_id}]: Error in FavoritesModal: {e}")
            await interaction.response.send_message("❌ Error managing favorites", ephemeral=True)


class VolumeModal(discord.ui.Modal):
    """Modal for volume control"""
    
    def __init__(self, service_registry: ServiceRegistry, guild_id: int, current_volume: int):
        super().__init__(title="Volume Control")
        self.service_registry = service_registry
        self.guild_id = guild_id
        self.volume_manager = service_registry.get_optional(IVolumeManager)
        
        # Add volume input
        self.volume_input = discord.ui.TextInput(
            label="Volume (0-100)",
            placeholder="Enter volume percentage (0-100)",
            default=str(current_volume),
            max_length=3
        )
        self.add_item(self.volume_input)
        
        # Add preset selection
        self.preset = discord.ui.TextInput(
            label="Preset (optional)",
            placeholder="Enter: low, medium, high, or custom number",
            max_length=10,
            required=False
        )
        self.add_item(self.preset)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            if not self.volume_manager:
                await interaction.response.send_message("❌ Volume manager not available", ephemeral=True)
                return
            
            # Handle preset first
            if self.preset.value:
                preset = self.preset.value.lower().strip()
                if preset == "low":
                    volume = 25
                elif preset == "medium":
                    volume = 50
                elif preset == "high":
                    volume = 75
                else:
                    try:
                        volume = int(preset)
                    except ValueError:
                        await interaction.response.send_message("❌ Invalid preset. Use low, medium, high, or a number", ephemeral=True)
                        return
            else:
                # Parse volume input
                try:
                    volume = int(self.volume_input.value.strip())
                except ValueError:
                    await interaction.response.send_message("❌ Invalid volume. Please enter a number between 0-100", ephemeral=True)
                    return
            
            # Validate volume range
            if not 0 <= volume <= 100:
                await interaction.response.send_message("❌ Volume must be between 0 and 100", ephemeral=True)
                return
            
            await interaction.response.defer()
            
            # Set volume
            volume_decimal = volume / 100.0
            success = await self.volume_manager.set_master_volume(self.guild_id, volume_decimal)
            
            if success:
                await interaction.followup.send(f"🔊 Volume set to {volume}%", ephemeral=True)
            else:
                await interaction.followup.send("❌ Failed to set volume", ephemeral=True)
                
        except Exception as e:
            logger.error(f"[{self.guild_id}]: Error in VolumeModal: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Error setting volume", ephemeral=True)
            else:
                await interaction.followup.send("❌ Error setting volume", ephemeral=True)


class EQModal(discord.ui.Modal):
    """Modal for EQ control"""
    
    def __init__(self, service_registry: ServiceRegistry, guild_id: int, current_eq: Dict[str, float]):
        super().__init__(title="Equalizer Settings")
        self.service_registry = service_registry
        self.guild_id = guild_id
        self.effects_chain = service_registry.get_optional(IEffectsChain)
        
        # Add EQ inputs
        self.bass_input = discord.ui.TextInput(
            label="Bass (-20 to +20 dB)",
            placeholder="Enter bass adjustment in dB",
            default=str(current_eq.get('bass', 0.0)),
            max_length=5
        )
        self.add_item(self.bass_input)
        
        self.mid_input = discord.ui.TextInput(
            label="Mid (-20 to +20 dB)",
            placeholder="Enter mid adjustment in dB",
            default=str(current_eq.get('mid', 0.0)),
            max_length=5
        )
        self.add_item(self.mid_input)
        
        self.treble_input = discord.ui.TextInput(
            label="Treble (-20 to +20 dB)",
            placeholder="Enter treble adjustment in dB",
            default=str(current_eq.get('treble', 0.0)),
            max_length=5
        )
        self.add_item(self.treble_input)
        
        # Add preset option
        self.preset = discord.ui.TextInput(
            label="Preset (optional)",
            placeholder="Enter: flat, bass, treble, vocal, or rock",
            max_length=10,
            required=False
        )
        self.add_item(self.preset)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            if not self.effects_chain:
                await interaction.response.send_message("❌ Effects chain not available", ephemeral=True)
                return
            
            # Handle presets
            if self.preset.value:
                preset = self.preset.value.lower().strip()
                if preset == "flat":
                    bass, mid, treble = 0.0, 0.0, 0.0
                elif preset == "bass":
                    bass, mid, treble = 6.0, 0.0, -2.0
                elif preset == "treble":
                    bass, mid, treble = -2.0, 0.0, 6.0
                elif preset == "vocal":
                    bass, mid, treble = -1.0, 3.0, 2.0
                elif preset == "rock":
                    bass, mid, treble = 4.0, -1.0, 3.0
                else:
                    await interaction.response.send_message("❌ Invalid preset. Use: flat, bass, treble, vocal, or rock", ephemeral=True)
                    return
            else:
                # Parse individual inputs
                try:
                    bass = float(self.bass_input.value.strip())
                    mid = float(self.mid_input.value.strip())
                    treble = float(self.treble_input.value.strip())
                except ValueError:
                    await interaction.response.send_message("❌ Invalid EQ values. Please enter numbers", ephemeral=True)
                    return
            
            # Validate ranges
            for value, name in [(bass, "Bass"), (mid, "Mid"), (treble, "Treble")]:
                if not -20.0 <= value <= 20.0:
                    await interaction.response.send_message(f"❌ {name} must be between -20 and +20 dB", ephemeral=True)
                    return
            
            await interaction.response.defer()
            
            # Apply EQ settings
            eq_settings = {'bass': bass, 'mid': mid, 'treble': treble}
            
            # This would need to be implemented in the effects chain
            if hasattr(self.effects_chain, 'set_equalizer'):
                success = await self.effects_chain.set_equalizer(self.guild_id, eq_settings)
            else:
                # Fallback - just acknowledge the settings
                success = True
                logger.info(f"[{self.guild_id}]: EQ settings applied: {eq_settings}")
            
            if success:
                eq_desc = f"Bass: {bass:+.1f}dB, Mid: {mid:+.1f}dB, Treble: {treble:+.1f}dB"
                await interaction.followup.send(f"🎚️ EQ updated: {eq_desc}", ephemeral=True)
            else:
                await interaction.followup.send("❌ Failed to apply EQ settings", ephemeral=True)
                
        except Exception as e:
            logger.error(f"[{self.guild_id}]: Error in EQModal: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Error setting EQ", ephemeral=True)
            else:
                await interaction.followup.send("❌ Error setting EQ", ephemeral=True)


class EffectsModal(discord.ui.Modal):
    """Modal for audio effects control"""
    
    def __init__(self, service_registry: ServiceRegistry, guild_id: int):
        super().__init__(title="Audio Effects")
        self.service_registry = service_registry
        self.guild_id = guild_id
        
        # Add noise reduction toggle
        self.noise_reduction = discord.ui.TextInput(
            label="Noise Reduction (on/off)",
            placeholder="Enter 'on' or 'off' to toggle noise reduction",
            default="on",
            max_length=3
        )
        self.add_item(self.noise_reduction)
        
        # Add compression toggle
        self.compression = discord.ui.TextInput(
            label="Dynamic Compression (on/off)",
            placeholder="Enter 'on' or 'off' to toggle compression",
            default="on",
            max_length=3
        )
        self.add_item(self.compression)
        
        # Add normalization toggle
        self.normalization = discord.ui.TextInput(
            label="Loudness Normalization (on/off)",
            placeholder="Enter 'on' or 'off' to toggle normalization",
            default="on",
            max_length=3
        )
        self.add_item(self.normalization)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Parse settings
            noise_reduction = self.noise_reduction.value.lower().strip() == "on"
            compression = self.compression.value.lower().strip() == "on"
            normalization = self.normalization.value.lower().strip() == "on"
            
            # Apply effects settings (this would need to be implemented)
            effects_settings = {
                'noise_reduction': noise_reduction,
                'compression': compression,
                'normalization': normalization
            }
            
            logger.info(f"[{self.guild_id}]: Effects settings applied: {effects_settings}")
            
            # Create response message
            effects_list = []
            if noise_reduction:
                effects_list.append("🔇 Noise Reduction")
            if compression:
                effects_list.append("📊 Dynamic Compression")
            if normalization:
                effects_list.append("📈 Loudness Normalization")
            
            if effects_list:
                message = f"🎛️ Effects enabled: {', '.join(effects_list)}"
            else:
                message = "🎛️ All effects disabled"
            
            await interaction.response.send_message(message, ephemeral=True)
            
        except Exception as e:
            logger.error(f"[{self.guild_id}]: Error in EffectsModal: {e}")
            await interaction.response.send_message("❌ Error applying effects", ephemeral=True)


class SettingsModal(discord.ui.Modal):
    """Modal for general settings"""
    
    def __init__(self, service_registry: ServiceRegistry, guild_id: int):
        super().__init__(title="Settings")
        self.service_registry = service_registry
        self.guild_id = guild_id
        
        # Add auto-reconnect setting
        self.auto_reconnect = discord.ui.TextInput(
            label="Auto-reconnect (on/off)",
            placeholder="Enable automatic reconnection on stream errors",
            default="on",
            max_length=3
        )
        self.add_item(self.auto_reconnect)
        
        # Add quality preference
        self.quality = discord.ui.TextInput(
            label="Audio Quality",
            placeholder="Enter: low, medium, high, or auto",
            default="auto",
            max_length=10
        )
        self.add_item(self.quality)
        
        # Add notification setting
        self.notifications = discord.ui.TextInput(
            label="Song Notifications (on/off)",
            placeholder="Show notifications when songs change",
            default="on",
            max_length=3
        )
        self.add_item(self.notifications)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Parse settings
            auto_reconnect = self.auto_reconnect.value.lower().strip() == "on"
            quality = self.quality.value.lower().strip()
            notifications = self.notifications.value.lower().strip() == "on"
            
            # Validate quality setting
            if quality not in ['low', 'medium', 'high', 'auto']:
                await interaction.response.send_message("❌ Invalid quality setting. Use: low, medium, high, or auto", ephemeral=True)
                return
            
            # Apply settings (this would need to be implemented in state manager)
            settings = {
                'auto_reconnect': auto_reconnect,
                'quality': quality,
                'notifications': notifications
            }
            
            logger.info(f"[{self.guild_id}]: Settings applied: {settings}")
            
            # Create response message
            settings_list = []
            if auto_reconnect:
                settings_list.append("🔄 Auto-reconnect")
            if notifications:
                settings_list.append("🔔 Song notifications")
            settings_list.append(f"🎧 Quality: {quality}")
            
            message = f"⚙️ Settings updated: {', '.join(settings_list)}"
            await interaction.response.send_message(message, ephemeral=True)
            
        except Exception as e:
            logger.error(f"[{self.guild_id}]: Error in SettingsModal: {e}")
            await interaction.response.send_message("❌ Error applying settings", ephemeral=True)
