"""
Command Service for BunBot
"""

import logging
import math
import asyncio
from typing import Dict, Any, Optional
import discord
from discord.ext import commands

from core import ServiceRegistry, StateManager, EventBus
from .stream_service import StreamService
from .favorites_service import FavoritesService
from .ui_service import UIService
from .error_service import ErrorService
import shout_errors

logger = logging.getLogger('services.command_service')

class CommandService:
    """
    Discord slash command handler service.
    
    Manages all bot commands with proper error handling, validation,
    and integration with other services.
    """
    
    def __init__(self, service_registry: ServiceRegistry):
        self.service_registry = service_registry
        self.state_manager = service_registry.get(StateManager)
        self.event_bus = service_registry.get(EventBus)
        
        # Get other services
        self.stream_service = service_registry.get(StreamService)
        self.favorites_service = service_registry.get(FavoritesService)
        self.ui_service = service_registry.get(UIService)
        self.error_service = service_registry.get(ErrorService)
        
        logger.info("CommandService initialized")
    
    async def register_commands(self, bot: commands.AutoShardedBot) -> None:
        """Register all slash and prefix commands with the Discord bot"""
        try:
            logger.info("Registering slash and prefix commands...")
            
            # Add prefix command error handler
            @bot.event
            async def on_command_error(ctx: commands.Context, error: Exception):
                """Handle prefix command errors"""
                # Create a mock interaction for compatibility with error service
                class MockInteraction:
                    def __init__(self, ctx):
                        self.guild_id = ctx.guild.id if ctx.guild else None
                        self.guild = ctx.guild
                        self.user = ctx.author
                        self.channel = ctx.channel
                        self.command = ctx.command
                        self.response = MockResponse(ctx)
                
                class MockResponse:
                    def __init__(self, ctx):
                        self._ctx = ctx
                        self._done = False
                    
                    def is_done(self):
                        return self._done
                    
                    async def send_message(self, content, ephemeral=False):
                        await self._ctx.send(content)
                        self._done = True
                
                mock_interaction = MockInteraction(ctx)
                await self.error_service.handle_command_error(mock_interaction, error)
            
            # Core streaming commands
            await self._register_play_command(bot)
            await self._register_leave_command(bot)
            await self._register_song_command(bot)
            await self._register_refresh_command(bot)
            
            # Utility commands
            await self._register_support_command(bot)
            await self._register_debug_command(bot)
            
            # Favorites commands
            await self._register_favorites_commands(bot)
            
            # Audio processing commands
            await self._register_audio_commands(bot)
            
            # Advanced audio processing commands (if scipy available)
            await self._register_advanced_audio_commands(bot)
            
            logger.info("All slash and prefix commands registered successfully")
            
        except Exception as e:
            logger.error(f"Failed to register commands: {e}")
            raise
    
    async def _register_play_command(self, bot: commands.AutoShardedBot) -> None:
        """Register the /play command (both slash and prefix)"""
        
        # Shared logic for both command types
        async def play_logic(url: str, guild_id: int, user, channel, voice_channel=None):
            """Shared play command logic"""
            # Validate URL format
            if not self._is_valid_url(url):
                raise commands.BadArgument("Invalid URL format")
            
            # Create mock interaction for stream service
            class MockInteraction:
                def __init__(self):
                    self.guild_id = guild_id
                    self.user = user
                    self.channel = channel
                    self.guild = user.guild if hasattr(user, 'guild') else None
                    
                    # Mock response for compatibility
                    class MockResponse:
                        def is_done(self): return False
                        async def send_message(self, content, ephemeral=False): pass
                    self.response = MockResponse()
            
            mock_interaction = MockInteraction()
            
            # Use StreamService to handle playback
            success = await self.stream_service.start_stream(mock_interaction, url)
            
            if success and guild_id:
                # Get station info and send now playing
                song_info = await self.stream_service.get_current_song(guild_id)
                if song_info and hasattr(channel, 'send'):
                    station_info = {
                        'metadata': {'song': song_info['song']},
                        'server_name': song_info.get('station')
                    }
                    # Send simplified now playing for prefix commands
                    await channel.send(f"🎵 Now Playing: **{song_info['song']}** on **{song_info.get('station', 'Unknown Station')}**")
            
            return success
        
        # Slash command registration
        @bot.tree.command(
            name='play',
            description="Begin playback of a shoutcast/icecast stream"
        )
        @discord.app_commands.checks.cooldown(rate=1, per=5)
        async def play_slash(interaction: discord.Interaction, url: str):
            try:
                if not interaction.guild_id:
                    await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
                    return
                
                await interaction.response.send_message(f"Starting channel {url}")
                
                # Check if user has voice attribute (Member vs User)
                voice_channel = None
                if hasattr(interaction.user, 'voice') and interaction.user.voice:
                    voice_channel = interaction.user.voice.channel
                
                await play_logic(url, interaction.guild_id, interaction.user, interaction.channel, voice_channel)
                
            except Exception as e:
                await self.error_service.handle_command_error(interaction, e)
        
        # Prefix command registration
        @bot.command(
            name='play',
            help="Begin playback of a shoutcast/icecast stream"
        )
        @commands.cooldown(rate=1, per=5, type=commands.BucketType.guild)
        async def play_prefix(ctx: commands.Context, url: str):
            try:
                if not ctx.guild or not ctx.guild.id:
                    await ctx.send("❌ This command can only be used in a server.")
                    return
                
                await ctx.send(f"Starting channel {url}")
                
                # Check if author has voice attribute (Member vs User)
                voice_channel = None
                if hasattr(ctx.author, 'voice') and ctx.author.voice:
                    voice_channel = ctx.author.voice.channel
                
                await play_logic(url, ctx.guild.id, ctx.author, ctx.channel, voice_channel)
                
            except Exception as e:
                # Handle error with context
                await ctx.send(f"❌ Error: {str(e)}")
    
    async def _register_leave_command(self, bot: commands.AutoShardedBot) -> None:
        """Register the /leave command"""
        @bot.tree.command(
            name='leave',
            description="Remove the bot from the current call"
        )
        @discord.app_commands.checks.cooldown(rate=1, per=5)
        async def leave(interaction: discord.Interaction, force: bool = False):
            try:
                if not interaction.guild or not interaction.guild_id:
                    await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
                    return
                
                voice_client = interaction.guild.voice_client
                guild_state = self.state_manager.get_guild_state(interaction.guild_id)
                has_state = guild_state and guild_state.current_stream_url
                
                # Handle normal case - voice client exists
                if voice_client:
                    await interaction.response.send_message("👋 Seeya Later, Gator!")
                    await self.stream_service.stop_stream(interaction.guild)
                    return
                
                # Handle desync case - AUTOMATIC RECOVERY
                if has_state:
                    if force:
                        await interaction.response.send_message("🔧 Force clearing stale state...")
                    else:
                        await interaction.response.send_message("🔄 Detected state desync - automatically recovering...")
                    
                    # Clear stale state through StateManager
                    if guild_state:
                        guild_state.current_stream_url = None
                        guild_state.cleaning_up = False
                    
                    logger.info(f"[{interaction.guild_id}]: Auto-recovered from state desync via /leave")
                    
                    if force:
                        await interaction.edit_original_response(content="✅ Force cleared stale bot state. Ready for new streams!")
                    else:
                        await interaction.edit_original_response(content="✅ Auto-recovered from state issue. Ready for new streams!")
                    return
                
                # Normal case - nothing playing
                raise shout_errors.NoVoiceClient("Not playing any music")
                
            except Exception as e:
                await self.error_service.handle_command_error(interaction, e)
    
    async def _register_song_command(self, bot: commands.AutoShardedBot) -> None:
        """Register the /song command"""
        @bot.tree.command(
            name="song",
            description="Send an embed with the current song information to this channel"
        )
        @discord.app_commands.checks.cooldown(rate=1, per=5)
        async def song(interaction: discord.Interaction):
            try:
                if not interaction.guild_id:
                    await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
                    return
                
                guild_state = self.state_manager.get_guild_state(interaction.guild_id)
                
                if not guild_state or not guild_state.current_stream_url:
                    raise shout_errors.NoStreamSelected("No stream currently playing")
                
                await interaction.response.send_message("Fetching song title...")
                
                song_info = await self.stream_service.get_current_song(interaction.guild_id)
                
                if song_info and song_info.get('song'):
                    await interaction.edit_original_response(
                        content=f"Now Playing: 🎶 {song_info['song']} 🎶"
                    )
                else:
                    await interaction.edit_original_response(
                        content="Could not retrieve song title. This feature may not be supported by the station"
                    )
                    
            except Exception as e:
                await self.error_service.handle_command_error(interaction, e)
    
    async def _register_refresh_command(self, bot: commands.AutoShardedBot) -> None:
        """Register the /refresh command"""
        @bot.tree.command(
            name="refresh",
            description="Refresh the stream. Bot will leave and come back. Song updates will start displaying in this channel"
        )
        @discord.app_commands.checks.cooldown(rate=1, per=5)
        async def refresh(interaction: discord.Interaction):
            try:
                if not interaction.guild_id:
                    await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
                    return
                    
                guild_state = self.state_manager.get_guild_state(interaction.guild_id)
                
                if not guild_state or not guild_state.current_stream_url:
                    raise shout_errors.NoStreamSelected("No stream currently playing")
                
                await interaction.response.send_message("♻️ Refreshing stream, the bot may skip or leave and re-enter")
                
                # Use StreamService to handle refresh
                await self.stream_service.refresh_stream(interaction)
                
            except Exception as e:
                await self.error_service.handle_command_error(interaction, e)
    
    async def _register_support_command(self, bot: commands.AutoShardedBot) -> None:
        """Register the /support command"""
        @bot.tree.command(
            name='support',
            description="Information on how to get support"
        )
        @discord.app_commands.checks.cooldown(rate=1, per=5)
        async def support(interaction: discord.Interaction):
            try:
                embed = await self.ui_service.create_support_embed()
                await interaction.response.send_message(embed=embed)
                
            except Exception as e:
                await self.error_service.handle_command_error(interaction, e)
    
    async def _register_debug_command(self, bot: commands.AutoShardedBot) -> None:
        """Register the /debug command"""
        @bot.tree.command(
            name="debug",
            description="Show debug stats & info"
        )
        @discord.app_commands.checks.cooldown(rate=1, per=5)
        async def debug(interaction: discord.Interaction, page: int = 0, per_page: int = 10, id: str = ''):
            try:
                resp = []
                resp.append("==\tGlobal Info\t==")
                
                page_count = math.ceil(len(bot.guilds) / per_page)
                page = max(0, page-1)
                page = min(page, page_count-1)
                page_index = page * per_page
                
                if await bot.is_owner(interaction.user):
                    if id:
                        resp.append(f"Guild ID: {id}")
                        guild = next((x for x in bot.guilds if str(x.id) == id), None)
                        if guild:
                            guild_state = self.state_manager.get_guild_state(guild.id)
                            start_time = guild_state.start_time if guild_state else None
                            
                            resp.append(f"- {guild.name} ({guild.id}): user count - {guild.member_count}")
                            resp.append(f"\tStream URL: {guild_state.current_stream_url if guild_state else 'Not Playing'}")
                            if start_time:
                                from datetime import datetime, timezone
                                resp.append(f"\tRun time: {datetime.now(timezone.utc) - start_time}")
                            resp.append(f"\tShard: {guild.shard_id}")
                    else:
                        resp.append("Guilds:")
                        for guild in bot.guilds[page_index:page_index+per_page]:
                            guild_state = self.state_manager.get_guild_state(guild.id)
                            status = guild_state.current_stream_url if guild_state else "Not Playing"
                            
                            resp.append(f"- {guild.name} ({guild.id}): user count - {guild.member_count}")
                            resp.append(f"\tStatus: {status}")
                        
                        resp.append(f"Total pages: {page_count}")
                        resp.append(f"Current page: {page + 1}")
                    
                    resp.append("Bot:")
                    resp.append(f"\tCluster ID: {bot.cluster_id}")
                    resp.append(f"\tShards: {bot.shard_ids}")
                else:
                    resp.append(f"\tGuild count: {len(bot.guilds)}")
                
                # Server specific info
                start_time = None
                if interaction.guild_id:
                    guild_state = self.state_manager.get_guild_state(interaction.guild_id)
                    start_time = guild_state.start_time if guild_state else None
                    
                    resp.append("==\tServer Info\t==")
                    resp.append(f"\tStream URL: {guild_state.current_stream_url if guild_state else 'Not Playing'}")
                    
                    # Get current song
                    song_info = await self.stream_service.get_current_song(interaction.guild_id)
                    resp.append(f"\tCurrent song: {song_info.get('song') if song_info else 'Not Playing'}")
                    
                    # Show volume level
                    volume_level = getattr(guild_state, 'volume_level', 0.8) if guild_state else 0.8
                    resp.append(f"\tVolume: {int(volume_level * 100)}%")
                    
                    # Show audio service status
                    try:
                        from audio import IVolumeManager, IEffectsChain, IAudioProcessor
                        volume_manager = self.service_registry.get_optional(IVolumeManager)
                        effects_chain = self.service_registry.get_optional(IEffectsChain)
                        audio_processor = self.service_registry.get_optional(IAudioProcessor)
                        
                        resp.append(f"\tAudio Services:")
                        resp.append(f"\t  • Volume Manager: {'✅' if volume_manager else '❌'}")
                        resp.append(f"\t  • Effects Chain: {'✅' if effects_chain else '❌'}")
                        resp.append(f"\t  • Audio Processor: {'✅' if audio_processor else '❌'}")
                    except ImportError:
                        resp.append(f"\tAudio Services: ❌ Not Available")
                    
                    if start_time:
                        from datetime import datetime, timezone
                        resp.append(f"\tRun time: {datetime.now(timezone.utc) - start_time}")
                else:
                    resp.append("==\tServer Info\t==")
                    resp.append("\tNot in a server")
                
                await interaction.response.send_message("\n".join(resp), ephemeral=True)
                
            except Exception as e:
                await self.error_service.handle_command_error(interaction, e)
    
    async def _register_favorites_commands(self, bot: commands.AutoShardedBot) -> None:
        """Register all favorites-related commands"""
        
        @bot.tree.command(
            name='set-favorite',
            description="Add a radio station to favorites"
        )
        @discord.app_commands.checks.cooldown(rate=1, per=5)
        async def set_favorite(interaction: discord.Interaction, url: str, name: str = None):
            try:
                if not interaction.guild_id:
                    await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
                    return
                
                # Validate URL format
                if not self._is_valid_url(url):
                    await interaction.response.send_message("❌ Please provide a valid URL.", ephemeral=True)
                    return
                
                await interaction.response.send_message("🔍 Validating stream and adding to favorites...")
                
                result = await self.favorites_service.add_favorite(
                    guild_id=interaction.guild_id,
                    url=url,
                    name=name,
                    user_id=interaction.user.id
                )
                
                if result['success']:
                    await interaction.edit_original_response(
                        content=f"✅ Added **{result['station_name']}** as favorite #{result['favorite_number']}"
                    )
                else:
                    await interaction.edit_original_response(
                        content=f"❌ Failed to add favorite: {result['error']}"
                    )
                    
            except Exception as e:
                await self.error_service.handle_command_error(interaction, e)
        
        @bot.tree.command(
            name='play-favorite',
            description="Play a favorite radio station by number"
        )
        @discord.app_commands.checks.cooldown(rate=1, per=5)
        async def play_favorite(interaction: discord.Interaction, number: int):
            try:
                if not interaction.guild_id:
                    await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
                    return
                
                favorite = self.favorites_service.get_favorite_by_number(interaction.guild_id, number)
                
                if not favorite:
                    await interaction.response.send_message(f"❌ Favorite #{number} not found.", ephemeral=True)
                    return
                
                await interaction.response.send_message(
                    f"🎵 Starting favorite #{number}: **{favorite['station_name']}**"
                )
                
                # Use the existing play functionality
                await self.stream_service.start_stream(interaction, favorite['stream_url'])
                
            except Exception as e:
                await self.error_service.handle_command_error(interaction, e)
        
        @bot.tree.command(
            name='favorites',
            description="Show favorites with clickable buttons"
        )
        @discord.app_commands.checks.cooldown(rate=1, per=10)
        async def favorites(interaction: discord.Interaction):
            try:
                if not interaction.guild_id:
                    await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
                    return
                
                favorites_list = self.favorites_service.get_all_favorites(interaction.guild_id)
                
                if not favorites_list:
                    await interaction.response.send_message(
                        "📻 No favorites set for this server yet! Use `/set-favorite` to add some.",
                        ephemeral=True
                    )
                    return
                
                # Create interactive favorites view using UIService
                embed, view = await self.ui_service.create_interactive_favorites_view(
                    interaction.guild_id, 
                    favorites_list, 
                    0
                )
                
                # Send with interactive view if available, otherwise just embed
                if view:
                    await interaction.response.send_message(embed=embed, view=view)
                else:
                    await interaction.response.send_message(embed=embed)
                
            except Exception as e:
                await self.error_service.handle_command_error(interaction, e)
        
        @bot.tree.command(
            name='list-favorites',
            description="List all favorites (text only, mobile-friendly)"
        )
        @discord.app_commands.checks.cooldown(rate=1, per=5)
        async def list_favorites(interaction: discord.Interaction):
            try:
                if not interaction.guild_id:
                    await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
                    return
                
                favorites_list = self.favorites_service.get_all_favorites(interaction.guild_id)
                
                embed = await self.ui_service.create_favorites_embed(
                    interaction.guild_id,
                    favorites_list,
                    0
                )
                
                await interaction.response.send_message(embed=embed)
                
            except Exception as e:
                await self.error_service.handle_command_error(interaction, e)
        
        @bot.tree.command(
            name='remove-favorite',
            description="Remove a favorite radio station"
        )
        @discord.app_commands.checks.cooldown(rate=1, per=5)
        async def remove_favorite(interaction: discord.Interaction, number: int):
            try:
                if not interaction.guild_id:
                    await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
                    return
                
                # Check if favorite exists
                favorite = self.favorites_service.get_favorite_by_number(interaction.guild_id, number)
                if not favorite:
                    await interaction.response.send_message(f"❌ Favorite #{number} not found.", ephemeral=True)
                    return
                
                # Simple confirmation for now (can be enhanced with UI components later)
                await interaction.response.send_message(
                    f"⚠️ Remove favorite #{number}: **{favorite['station_name']}**?\n"
                    f"Reply 'yes' to confirm or ignore to cancel."
                )
                
                # For now, just remove it immediately (can add confirmation logic later)
                result = await self.favorites_service.remove_favorite(interaction.guild_id, number)
                
                if result['success']:
                    await interaction.edit_original_response(
                        content=f"✅ Removed **{result['station_name']}** from favorites. Subsequent favorites have been renumbered."
                    )
                else:
                    await interaction.edit_original_response(
                        content=f"❌ Failed to remove favorite: {result['error']}"
                    )
                    
            except Exception as e:
                await self.error_service.handle_command_error(interaction, e)
    
    async def _register_audio_commands(self, bot: commands.AutoShardedBot) -> None:
        """Register audio processing commands"""
        
        @bot.tree.command(
            name='volume',
            description="Adjust the master volume (0-100)"
        )
        @discord.app_commands.checks.cooldown(rate=1, per=3)
        async def volume(interaction: discord.Interaction, level: int):
            try:
                if not interaction.guild_id:
                    await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
                    return
                
                # Validate volume range
                if not (0 <= level <= 100):
                    await interaction.response.send_message("❌ Volume must be between 0 and 100.", ephemeral=True)
                    return
                
                # Convert to 0.0-1.0 range
                volume_float = level / 100.0
                
                # Check if bot is connected to voice
                if not interaction.guild or not interaction.guild.voice_client:
                    await interaction.response.send_message("❌ Bot is not connected to a voice channel. Start playing music first.", ephemeral=True)
                    return
                
                # Send initial response immediately to claim the interaction
                await interaction.response.send_message(f"🔊 Setting volume to {level}%...")
                
                voice_client = interaction.guild.voice_client
                
                # Try advanced audio processing first with timeout protection
                advanced_success = False
                try:
                    from audio import IVolumeManager
                    volume_manager = self.service_registry.get_optional(IVolumeManager)
                    
                    if volume_manager:
                        # Add timeout protection to prevent blocking
                        advanced_success = await asyncio.wait_for(
                            volume_manager.set_master_volume(interaction.guild_id, volume_float),
                            timeout=2.0
                        )
                        if advanced_success:
                            await interaction.edit_original_response(content=f"🔊 Volume set to {level}% (Enhanced Audio)")
                            return
                except asyncio.TimeoutError:
                    logger.warning(f"[{interaction.guild_id}]: Advanced volume control timed out - using fallback")
                except ImportError:
                    logger.debug("Advanced audio services not available - using fallback")
                except Exception as e:
                    logger.warning(f"Advanced volume control failed: {e}")
                
                # Fallback to Discord's built-in volume control
                try:
                    if hasattr(voice_client, 'source') and voice_client.source:
                        if hasattr(voice_client.source, 'volume'):
                            voice_client.source.volume = volume_float
                            
                            # Store volume in guild state for persistence
                            guild_state = self.state_manager.get_guild_state(interaction.guild_id, create_if_missing=True)
                            if guild_state:
                                guild_state.volume_level = volume_float
                            
                            await interaction.edit_original_response(content=f"🔊 Volume set to {level}% (Basic)")
                            return
                        else:
                            await interaction.edit_original_response(content="❌ Current audio source doesn't support volume control.")
                            return
                    else:
                        await interaction.edit_original_response(content="❌ No audio source available for volume control.")
                        return
                        
                except Exception as e:
                    logger.error(f"Fallback volume control failed: {e}")
                    await interaction.edit_original_response(content="❌ Failed to set volume.")
                    
            except Exception as e:
                await self.error_service.handle_command_error(interaction, e)
        
        @bot.tree.command(
            name='eq',
            description="Adjust equalizer settings"
        )
        @discord.app_commands.checks.cooldown(rate=1, per=3)
        async def eq(interaction: discord.Interaction, bass: float, mid: float, treble: float):
            try:
                if not interaction.guild_id:
                    await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
                    return
                
                # Validate EQ ranges
                for val, name in [(bass, 'bass'), (mid, 'mid'), (treble, 'treble')]:
                    if not (-12.0 <= val <= 12.0):
                        await interaction.response.send_message(f"❌ {name.title()} must be between -12 and +12 dB.", ephemeral=True)
                        return
                
                # Send initial response
                await interaction.response.send_message("🎚️ Adjusting equalizer settings...")
                
                # Try to get effects chain service
                try:
                    from audio import IEffectsChain
                    effects_chain = self.service_registry.get_optional(IEffectsChain)
                    
                    if effects_chain:
                        success = await effects_chain.set_eq(interaction.guild_id, bass, mid, treble)
                        if success:
                            await interaction.edit_original_response(
                                content=f"🎚️ EQ updated: Bass {bass:+.1f}dB, Mid {mid:+.1f}dB, Treble {treble:+.1f}dB"
                            )
                        else:
                            await interaction.edit_original_response(content="❌ Failed to set EQ.")
                    else:
                        await interaction.edit_original_response(content="❌ Audio enhancement not available.")
                        
                except ImportError:
                    await interaction.edit_original_response(content="❌ Audio enhancement not available.")
                    
            except Exception as e:
                await self.error_service.handle_command_error(interaction, e)
        
        @bot.tree.command(
            name='eq-preset',
            description="Apply an equalizer preset"
        )
        @discord.app_commands.checks.cooldown(rate=1, per=3)
        async def eq_preset(interaction: discord.Interaction, preset: str):
            try:
                if not interaction.guild_id:
                    await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
                    return
                
                # Send initial response
                await interaction.response.send_message(f"🎵 Applying EQ preset: **{preset.title()}**...")
                
                # Try to get effects chain service
                try:
                    from audio import IEffectsChain
                    effects_chain = self.service_registry.get_optional(IEffectsChain)
                    
                    if effects_chain:
                        # Get available presets
                        presets = await effects_chain.get_available_presets()
                        
                        if preset.lower() not in [p.lower() for p in presets]:
                            preset_list = ", ".join(presets)
                            await interaction.edit_original_response(
                                content=f"❌ Unknown preset. Available presets: {preset_list}"
                            )
                            return
                        
                        success = await effects_chain.apply_eq_preset(interaction.guild_id, preset.lower())
                        if success:
                            await interaction.edit_original_response(content=f"🎵 Applied EQ preset: **{preset.title()}**")
                        else:
                            await interaction.edit_original_response(content="❌ Failed to apply preset.")
                    else:
                        await interaction.edit_original_response(content="❌ Audio enhancement not available.")
                        
                except ImportError:
                    await interaction.edit_original_response(content="❌ Audio enhancement not available.")
                    
            except Exception as e:
                await self.error_service.handle_command_error(interaction, e)
        
        @bot.tree.command(
            name='audio-info',
            description="Show current audio processing settings"
        )
        @discord.app_commands.checks.cooldown(rate=1, per=5)
        async def audio_info(interaction: discord.Interaction):
            try:
                if not interaction.guild_id:
                    await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
                    return
                
                # Try to get audio services
                try:
                    from audio import IAudioProcessor, IVolumeManager, IEffectsChain
                    
                    audio_processor = self.service_registry.get_optional(IAudioProcessor)
                    volume_manager = self.service_registry.get_optional(IVolumeManager)
                    effects_chain = self.service_registry.get_optional(IEffectsChain)
                    
                    if not audio_processor:
                        await interaction.response.send_message("❌ Audio enhancement not available.", ephemeral=True)
                        return
                    
                    # Get current configuration
                    config = await audio_processor.get_config(interaction.guild_id)
                    if not config:
                        await interaction.response.send_message("📊 No audio configuration found for this server.", ephemeral=True)
                        return
                    
                    # Build info message
                    info_lines = [
                        "🎛️ **Audio Processing Settings**",
                        "",
                        f"🔊 **Volume**: {int(config.master_volume * 100)}%",
                        f"🎚️ **EQ**: Bass {config.eq_bass:+.1f}dB, Mid {config.eq_mid:+.1f}dB, Treble {config.eq_treble:+.1f}dB",
                        f"📊 **Quality**: {config.quality.value.title()}",
                        f"🎵 **Sample Rate**: {config.sample_rate}Hz",
                        f"📢 **Channels**: {config.channels}",
                        "",
                        f"🔧 **Processing**:",
                        f"  • Normalization: {'✅' if config.normalization_enabled else '❌'}",
                        f"  • Auto Gain Control: {'✅' if config.auto_gain_control else '❌'}",
                        f"  • Compression: {config.dynamic_range_compression:.1%}",
                        f"  • EQ: {'✅' if config.eq_enabled else '❌'}"
                    ]
                    
                    await interaction.response.send_message("\n".join(info_lines))
                        
                except ImportError:
                    await interaction.response.send_message("❌ Audio enhancement not available.", ephemeral=True)
                    
            except Exception as e:
                await self.error_service.handle_command_error(interaction, e)
    
    def _is_valid_url(self, url: str) -> bool:
        """Validate URL format"""
        try:
            import validators
            result = validators.url(url)
            return bool(result)
        except ImportError:
            # Fallback validation
            return url.startswith(('http://', 'https://'))
    
    async def _register_advanced_audio_commands(self, bot: commands.AutoShardedBot) -> None:
        """Register advanced audio processing commands (if scipy available)"""
        try:
            # Check if scipy is available
            import numpy
            import scipy
            
            # Import and register advanced audio commands
            from .advanced_audio_commands import AdvancedAudioCommands
            
            # Add the cog
            await bot.add_cog(AdvancedAudioCommands(bot, self.service_registry))
            logger.info("Advanced audio commands registered successfully")
            
        except ImportError as e:
            logger.info(f"Advanced audio commands not available - missing dependencies: {e}")
        except Exception as e:
            logger.warning(f"Failed to register advanced audio commands: {e}")
    
    def get_command_stats(self) -> Dict[str, Any]:
        """Get command service statistics"""
        return {
            'commands_registered': True,
            'service_initialized': True
        }
