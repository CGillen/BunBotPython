"""
Stream Service for BunBot
"""

import logging
import asyncio
import urllib.request
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import discord

from core import ServiceRegistry, StateManager, EventBus
from audio import AudioProcessor, StreamManager, AudioConfig
from monitoring import HealthMonitor
from utils import create_ffmpeg_audio_source, get_ffmpeg_info
import shout_errors
import urllib_hack
from streamscrobbler import streamscrobbler

logger = logging.getLogger('services.stream_service')

class StreamService:
    """
    Core stream management service for BunBot.
    
    Handles all streaming operations including connection, playback,
    disconnection, and error recovery with enhanced audio processing.
    """
    
    def __init__(self, service_registry: ServiceRegistry):
        self.service_registry = service_registry
        self.state_manager = service_registry.get(StateManager)
        self.event_bus = service_registry.get(EventBus)
        
        # Get audio and monitoring services
        self.audio_processor = service_registry.get_optional(AudioProcessor)
        self.stream_manager = service_registry.get_optional(StreamManager) 
        self.health_monitor = service_registry.get_optional(HealthMonitor)
        
        logger.info("StreamService initialized")
    
    async def start_stream(self, interaction: discord.Interaction, url: str) -> bool:
        """
        Start playing a stream in the user's voice channel.
        
        Args:
            interaction: Discord interaction from the command
            url: Stream URL to play
            
        Returns:
            True if stream started successfully, False otherwise
        """
        try:
            guild_id = interaction.guild_id
            if not guild_id:
                raise ValueError("No guild ID available")
            
            logger.info(f"[{guild_id}]: Starting stream {url}")
            
            # Validate URL format
            if not self._is_valid_url(url):
                raise shout_errors.BadArgument("Invalid URL format")
            
            # Check if user is in voice channel
            voice_channel = interaction.user.voice.channel if interaction.user.voice else None
            if not voice_channel:
                raise shout_errors.AuthorNotInVoice("User not in voice channel")
            
            # Check if already playing
            voice_client = interaction.guild.voice_client
            if voice_client and voice_client.is_playing():
                raise shout_errors.AlreadyPlaying("Already playing music")
            
            # Validate stream is online
            station_info = await self._get_station_info(url)
            if station_info['status'] <= 0:
                raise shout_errors.StreamOffline("Stream is not online")
            
            # Get stream connection
            stream_response = await self._get_stream_connection(url)
            if not stream_response:
                raise shout_errors.StreamOffline("Failed to connect to stream")
            
            # Connect to voice channel with retry logic
            if not voice_client:
                voice_client = await self._connect_to_voice_with_retry(voice_channel, guild_id)
            
            # Brief stabilization wait for voice connection
            await asyncio.sleep(0.5)
            
            # Create audio source with enhanced processing
            audio_source = await self._create_audio_source(guild_id, stream_response, url)
            
            # Create cleanup callback with recovery logic
            def stream_finished_callback(error):
                if error:
                    logger.error(f"[{guild_id}]: Stream finished with error: {error}")
                    
                    # Check if this is a recoverable error
                    if self._is_recoverable_error(error):
                        logger.info(f"[{guild_id}]: Attempting automatic recovery for recoverable error")
                        # Schedule recovery attempt
                        asyncio.run_coroutine_threadsafe(
                            self._attempt_stream_recovery(guild_id, str(error)), 
                            asyncio.get_event_loop()
                        )
                    else:
                        logger.info(f"[{guild_id}]: Non-recoverable error, performing cleanup")
                        # Schedule cleanup for non-recoverable errors
                        asyncio.run_coroutine_threadsafe(
                            self._handle_stream_disconnect(guild_id), 
                            asyncio.get_event_loop()
                        )
                else:
                    logger.info(f"[{guild_id}]: Stream finished normally")
                    # Schedule normal cleanup
                    asyncio.run_coroutine_threadsafe(
                        self._handle_stream_disconnect(guild_id), 
                        asyncio.get_event_loop()
                    )
            
            # Start playback
            voice_client.play(audio_source, after=stream_finished_callback)
            
            # Update state with audio source reference
            await self._update_stream_state(guild_id, url, stream_response, interaction.channel, audio_source)
            
            # Emit events
            await self.event_bus.emit_async('stream_started',
                                          guild_id=guild_id,
                                          url=url,
                                          station_info=station_info)
            
            logger.info(f"[{guild_id}]: Stream started successfully")
            return True
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to start stream: {e}")
            await self.event_bus.emit_async('stream_start_failed',
                                          guild_id=guild_id,
                                          url=url,
                                          error=str(e))
            raise
    
    async def stop_stream(self, guild: discord.Guild) -> bool:
        """
        Stop current stream and clean up resources.
        
        Args:
            guild: Discord guild
            
        Returns:
            True if stopped successfully, False otherwise
        """
        try:
            guild_id = guild.id
            logger.info(f"[{guild_id}]: Stopping stream")
            
            # Set cleanup flag
            guild_state = self.state_manager.get_guild_state(guild_id, create_if_missing=True)
            guild_state.cleaning_up = True
            
            # Stop voice client
            voice_client = guild.voice_client
            if voice_client:
                if voice_client.is_playing():
                    voice_client.stop()
                    # Wait for playback to stop
                    while voice_client.is_playing():
                        await asyncio.sleep(0.1)
                
                if voice_client.is_connected():
                    await voice_client.disconnect()
                    # Wait for disconnection
                    while voice_client.is_connected():
                        await asyncio.sleep(0.1)
            
            # Clear state
            await self._clear_stream_state(guild_id)
            
            # Emit event
            await self.event_bus.emit_async('stream_stopped', guild_id=guild_id)
            
            logger.info(f"[{guild_id}]: Stream stopped successfully")
            return True
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Error stopping stream: {e}")
            # Force clear state even on error
            await self._clear_stream_state(guild_id)
            return False
    
    async def refresh_stream(self, interaction: discord.Interaction) -> bool:
        """
        Refresh current stream by stopping and restarting.
        
        Args:
            interaction: Discord interaction
            
        Returns:
            True if refreshed successfully, False otherwise
        """
        try:
            guild_id = interaction.guild_id
            if not guild_id:
                return False
            
            logger.info(f"[{guild_id}]: Refreshing stream")
            
            # Get current stream URL
            guild_state = self.state_manager.get_guild_state(guild_id)
            if not guild_state or not guild_state.current_stream_url:
                raise shout_errors.NoStreamSelected("No stream currently playing")
            
            current_url = guild_state.current_stream_url
            
            # Stop current stream
            await self.stop_stream(interaction.guild)
            
            # Small delay to ensure clean state
            await asyncio.sleep(1.0)
            
            # Restart with same URL
            await self.start_stream(interaction, current_url)
            
            logger.info(f"[{guild_id}]: Stream refreshed successfully")
            return True
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to refresh stream: {e}")
            raise
    
    async def get_current_song(self, guild_id: int) -> Optional[Dict[str, Any]]:
        """
        Get current song information for a guild.
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            Song information or None if not available
        """
        try:
            guild_state = self.state_manager.get_guild_state(guild_id)
            if not guild_state or not guild_state.current_stream_url:
                return None
            
            station_info = await self._get_station_info(guild_state.current_stream_url)
            
            if station_info['status'] <= 0 or not station_info.get('metadata'):
                return None
            
            return {
                'song': station_info['metadata']['song'],
                'station': station_info.get('server_name'),
                'bitrate': station_info['metadata'].get('bitrate'),
                'url': guild_state.current_stream_url
            }
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to get current song: {e}")
            return None
    
    async def _get_station_info(self, url: str) -> Dict[str, Any]:
        """Get station information from stream URL"""
        try:
            station_info = streamscrobbler.get_server_info(url)
            if station_info is None:
                return {'status': 0, 'metadata': None}
            return station_info
        except Exception as e:
            logger.error(f"Failed to get station info for {url}: {e}")
            return {'status': 0, 'metadata': None}
    
    async def _get_stream_connection(self, url: str) -> Optional[any]:
        """Get HTTP connection to stream"""
        try:
            response = urllib.request.urlopen(url, timeout=10)
            return response
        except Exception as e:
            logger.error(f"Failed to connect to stream {url}: {e}")
            return None
    
    async def _create_audio_source(self, guild_id: int, stream_response: any, url: str) -> discord.AudioSource:
        """Create audio source with optional processing and volume control"""
        try:
            # Get current volume setting
            guild_state = self.state_manager.get_guild_state(guild_id, create_if_missing=True)
            volume_level = getattr(guild_state, 'volume_level', 0.8)  # Default to 80%
            
            # Use enhanced audio processing if available
            if self.audio_processor:
                logger.debug(f"[{guild_id}]: Creating enhanced audio source with volume {volume_level:.2f}")
                # Create enhanced audio source with processing and volume
                audio_source = create_ffmpeg_audio_source(
                    stream_response, 
                    pipe=True, 
                    options=f"-filter:a loudnorm=I=-30:LRA=4:TP=-2,volume={volume_level}"
                )
                
                # Wrap with PCMVolumeTransformer for real-time volume control
                audio_source = discord.PCMVolumeTransformer(audio_source, volume=volume_level)
            else:
                logger.debug(f"[{guild_id}]: Creating basic audio source with volume {volume_level:.2f}")
                # Fallback to basic audio source with volume
                audio_source = create_ffmpeg_audio_source(
                    stream_response, 
                    pipe=True, 
                    options=f"-filter:a loudnorm=I=-30:LRA=4:TP=-2,volume={volume_level}"
                )
                
                # Wrap with PCMVolumeTransformer for real-time volume control
                audio_source = discord.PCMVolumeTransformer(audio_source, volume=volume_level)
            
            logger.info(f"[{guild_id}]: Audio source created with volume {volume_level:.2f}")
            return audio_source
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to create audio source with volume control: {e}")
            # Fallback to basic source without processing but with volume
            try:
                guild_state = self.state_manager.get_guild_state(guild_id, create_if_missing=True)
                volume_level = getattr(guild_state, 'volume_level', 0.8)
                
                basic_source = create_ffmpeg_audio_source(stream_response, pipe=True)
                return discord.PCMVolumeTransformer(basic_source, volume=volume_level)
            except Exception as fallback_error:
                logger.error(f"[{guild_id}]: Fallback audio source creation failed: {fallback_error}")
                raise RuntimeError(f"FFmpeg not available. Error: {fallback_error}")
    
    async def _update_stream_state(self, guild_id: int, url: str, response: any, 
                                 channel: discord.TextChannel, audio_source: discord.AudioSource = None) -> None:
        """Update guild state with stream information"""
        try:
            guild_state = self.state_manager.get_guild_state(guild_id, create_if_missing=True)
            
            guild_state.current_stream_url = url
            guild_state.stream_response = response
            guild_state.text_channel = channel
            guild_state.start_time = datetime.now(timezone.utc)
            guild_state.last_updated = datetime.now(timezone.utc)
            guild_state.cleaning_up = False
            
            logger.debug(f"[{guild_id}]: Updated stream state")
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to update stream state: {e}")
    
    async def _clear_stream_state(self, guild_id: int) -> None:
        """Clear stream state for guild"""
        try:
            guild_state = self.state_manager.get_guild_state(guild_id)
            if guild_state:
                guild_state.current_stream_url = None
                guild_state.stream_response = None
                guild_state.text_channel = None
                guild_state.start_time = None
                guild_state.current_song = None
                guild_state.cleaning_up = False
                
            logger.debug(f"[{guild_id}]: Cleared stream state")
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to clear stream state: {e}")
    
    async def _handle_stream_disconnect(self, guild_id: int) -> None:
        """Handle stream disconnection with proper cleanup"""
        try:
            logger.info(f"[{guild_id}]: Handling stream disconnect")
            
            # Get guild state
            guild_state = self.state_manager.get_guild_state(guild_id)
            channel = guild_state.text_channel if guild_state else None
            
            # Try to notify users
            if channel:
                try:
                    if channel.permissions_for(channel.guild.me).send_messages:
                        await channel.send("🔌 Stream disconnected. Use `/play` to start a new stream!")
                except Exception as e:
                    logger.warning(f"[{guild_id}]: Could not send disconnect notification: {e}")
            
            # Get guild for voice client cleanup
            guild = discord.utils.get(self.service_registry.get('bot').guilds, id=guild_id) if 'bot' in self.service_registry._services else None
            
            # Clean up voice client
            if guild and guild.voice_client:
                try:
                    if guild.voice_client.is_connected():
                        await guild.voice_client.disconnect()
                except Exception as e:
                    logger.warning(f"[{guild_id}]: Error disconnecting voice client: {e}")
            
            # Clear state
            await self._clear_stream_state(guild_id)
            
            # Emit disconnect event
            await self.event_bus.emit_async('stream_disconnected', guild_id=guild_id)
            
            logger.info(f"[{guild_id}]: Stream disconnect handled")
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Error handling stream disconnect: {e}")
            # Ensure state is cleared even on error
            await self._clear_stream_state(guild_id)
    
    async def _verify_voice_connection_ready(self, voice_client: discord.VoiceClient, guild_id: int) -> None:
        """
        Verify that the voice connection is stable and ready for audio playback.
        
        This is the core fix for the Discord 4006 error - ensuring the connection
        is truly ready before attempting to play audio.
        
        Args:
            voice_client: The connected voice client
            guild_id: Guild ID for logging
            
        Raises:
            RuntimeError: If connection is not stable
        """
        try:
            logger.info(f"[{guild_id}]: Verifying voice connection stability...")
            
            # Check 1: Verify basic connection state
            if not voice_client or not voice_client.is_connected():
                raise RuntimeError("Voice client is not connected")
            
            # Check 2: Wait for connection to stabilize
            # This prevents the timing issue that causes 4006 errors
            stabilization_time = 2.0
            logger.debug(f"[{guild_id}]: Waiting {stabilization_time}s for connection stabilization...")
            await asyncio.sleep(stabilization_time)
            
            # Check 3: Re-verify connection after stabilization
            if not voice_client.is_connected():
                raise RuntimeError("Voice connection lost during stabilization")
            
            # Check 4: Verify voice client is ready for audio
            # Basic check that websocket exists (Discord.py handles internal state)
            if not hasattr(voice_client, 'ws') or not voice_client.ws:
                raise RuntimeError("Voice websocket is not available")
            
            # Check 5: Test connection health with a small delay
            # This ensures Discord's session is fully established
            health_check_delay = 1.0
            await asyncio.sleep(health_check_delay)
            
            # Final verification
            if not voice_client.is_connected():
                raise RuntimeError("Voice connection failed final health check")
            
            logger.info(f"[{guild_id}]: Voice connection verified and ready for audio")
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Voice connection verification failed: {e}")
            
            # Attempt cleanup on verification failure
            try:
                if voice_client and voice_client.is_connected():
                    await voice_client.disconnect(force=True)
            except:
                pass
            
            raise RuntimeError(f"Voice connection not ready for audio: {e}")

    async def _connect_to_voice_with_retry(self, voice_channel, guild_id: int, max_retries: int = 3) -> discord.VoiceClient:
        """
        Connect to voice channel with retry logic to handle Discord voice connection issues.
        
        Args:
            voice_channel: Discord voice channel to connect to
            guild_id: Guild ID for logging
            max_retries: Maximum number of connection attempts
            
        Returns:
            Connected voice client
            
        Raises:
            Exception: If all connection attempts fail
        """
        last_error = None
        
        for attempt in range(max_retries):
            try:
                logger.info(f"[{guild_id}]: Voice connection attempt {attempt + 1}/{max_retries}")
                
                # Add a small delay between attempts
                if attempt > 0:
                    await asyncio.sleep(2.0 * attempt)
                
                # Try to connect with timeout
                voice_client = await asyncio.wait_for(
                    voice_channel.connect(timeout=30.0, reconnect=True),
                    timeout=35.0
                )
                
                logger.info(f"[{guild_id}]: Voice connection successful on attempt {attempt + 1}")
                return voice_client
                
            except asyncio.TimeoutError as e:
                last_error = e
                logger.warning(f"[{guild_id}]: Voice connection timeout on attempt {attempt + 1}: {e}")
                
            except discord.errors.ConnectionClosed as e:
                last_error = e
                logger.warning(f"[{guild_id}]: Voice connection closed on attempt {attempt + 1}: {e}")
                
                # For code 4006 (session no longer valid), wait longer before retry
                if hasattr(e, 'code') and e.code == 4006:
                    logger.info(f"[{guild_id}]: Session invalid (4006), waiting longer before retry...")
                    await asyncio.sleep(5.0)
                
            except Exception as e:
                last_error = e
                logger.warning(f"[{guild_id}]: Voice connection error on attempt {attempt + 1}: {e}")
        
        # All attempts failed
        logger.error(f"[{guild_id}]: Failed to connect to voice after {max_retries} attempts. Last error: {last_error}")
        raise RuntimeError(f"Failed to connect to voice channel after {max_retries} attempts: {last_error}")

    def _is_recoverable_error(self, error: str) -> bool:
        """
        Determine if an error is recoverable and should trigger automatic reconnection.
        
        Args:
            error: Error message string
            
        Returns:
            True if error is recoverable, False otherwise
        """
        error_lower = error.lower()
        
        # FFmpeg broken pipe errors (most common recoverable error)
        if 'broken pipe' in error_lower:
            return True
        
        # Network-related errors
        if any(keyword in error_lower for keyword in [
            'connection reset',
            'connection timed out',
            'network is unreachable',
            'temporary failure',
            'connection refused',
            'timeout',
            'connection lost',
            'connection dropped'
        ]):
            return True
        
        # FFmpeg specific recoverable errors
        if any(keyword in error_lower for keyword in [
            'av_interleaved_write_frame',
            'error writing trailer',
            'input/output error',
            'resource temporarily unavailable'
        ]):
            return True
        
        # Non-recoverable errors
        if any(keyword in error_lower for keyword in [
            'not found',
            '404',
            'forbidden',
            '403',
            'unauthorized',
            '401',
            'invalid url',
            'malformed',
            'unsupported format',
            'codec not found'
        ]):
            return False
        
        # Default to recoverable for unknown errors (better to try than give up)
        return True
    
    async def _attempt_stream_recovery(self, guild_id: int, error: str, retry_count: int = 0) -> None:
        """
        Attempt to recover from a stream error by reconnecting.
        
        Args:
            guild_id: Discord guild ID
            error: Original error message
            retry_count: Current retry attempt number
        """
        max_retries = 3
        retry_delays = [5, 10, 20]  # Exponential backoff in seconds
        
        try:
            logger.info(f"[{guild_id}]: Starting stream recovery attempt {retry_count + 1}/{max_retries}")
            
            # Get guild state to check if recovery is already in progress
            guild_state = self.state_manager.get_guild_state(guild_id)
            if not guild_state or not guild_state.current_stream_url:
                logger.warning(f"[{guild_id}]: No stream URL available for recovery")
                await self._handle_stream_disconnect(guild_id)
                return
            
            # Check if we've exceeded max retries
            if retry_count >= max_retries:
                logger.error(f"[{guild_id}]: Max recovery attempts ({max_retries}) exceeded")
                await self._notify_recovery_failed(guild_id, guild_state.text_channel)
                await self._handle_stream_disconnect(guild_id)
                return
            
            # Notify users of recovery attempt
            await self._notify_recovery_attempt(guild_id, guild_state.text_channel, retry_count + 1, max_retries)
            
            # Wait before retry (exponential backoff)
            if retry_count < len(retry_delays):
                delay = retry_delays[retry_count]
            else:
                delay = retry_delays[-1]  # Use last delay for any additional attempts
            
            logger.info(f"[{guild_id}]: Waiting {delay}s before recovery attempt")
            await asyncio.sleep(delay)
            
            # Get the original stream URL
            original_url = guild_state.current_stream_url
            
            # Try to reconnect to the stream
            try:
                # Test if stream is back online
                station_info = await self._get_station_info(original_url)
                if station_info['status'] <= 0:
                    logger.warning(f"[{guild_id}]: Stream still offline, will retry")
                    # Schedule next retry
                    await self._attempt_stream_recovery(guild_id, error, retry_count + 1)
                    return
                
                # Get new stream connection
                stream_response = await self._get_stream_connection(original_url)
                if not stream_response:
                    logger.warning(f"[{guild_id}]: Failed to get stream connection, will retry")
                    await self._attempt_stream_recovery(guild_id, error, retry_count + 1)
                    return
                
                # Get voice client (should still be connected)
                bot = self.service_registry.get_optional('bot')
                if not bot:
                    logger.error(f"[{guild_id}]: Bot instance not available for recovery")
                    await self._handle_stream_disconnect(guild_id)
                    return
                
                guild = discord.utils.get(bot.guilds, id=guild_id)
                if not guild or not guild.voice_client:
                    logger.warning(f"[{guild_id}]: Voice client not available, attempting to reconnect")
                    # Try to find the voice channel and reconnect
                    # For now, just fail and let user manually restart
                    await self._notify_recovery_failed(guild_id, guild_state.text_channel)
                    await self._handle_stream_disconnect(guild_id)
                    return
                
                voice_client = guild.voice_client
                
                # Create new audio source
                audio_source = await self._create_audio_source(guild_id, stream_response, original_url)
                
                # Create new callback for the recovered stream
                def recovery_callback(error):
                    if error:
                        logger.error(f"[{guild_id}]: Recovered stream failed again: {error}")
                        if self._is_recoverable_error(str(error)):
                            asyncio.run_coroutine_threadsafe(
                                self._attempt_stream_recovery(guild_id, str(error), retry_count + 1), 
                                asyncio.get_event_loop()
                            )
                        else:
                            asyncio.run_coroutine_threadsafe(
                                self._handle_stream_disconnect(guild_id), 
                                asyncio.get_event_loop()
                            )
                    else:
                        logger.info(f"[{guild_id}]: Recovered stream finished normally")
                        asyncio.run_coroutine_threadsafe(
                            self._handle_stream_disconnect(guild_id), 
                            asyncio.get_event_loop()
                        )
                
                # Start the recovered stream
                voice_client.play(audio_source, after=recovery_callback)
                
                # Update state
                guild_state.last_updated = datetime.now(timezone.utc)
                
                # Notify success
                await self._notify_recovery_success(guild_id, guild_state.text_channel)
                
                logger.info(f"[{guild_id}]: Stream recovery successful on attempt {retry_count + 1}")
                
            except Exception as recovery_error:
                logger.error(f"[{guild_id}]: Recovery attempt {retry_count + 1} failed: {recovery_error}")
                # Try again if we haven't exceeded max retries
                await self._attempt_stream_recovery(guild_id, error, retry_count + 1)
                
        except Exception as e:
            logger.error(f"[{guild_id}]: Critical error in stream recovery: {e}")
            await self._handle_stream_disconnect(guild_id)
    
    async def _notify_recovery_attempt(self, guild_id: int, channel, attempt: int, max_attempts: int) -> None:
        """Notify users of recovery attempt"""
        try:
            if channel and hasattr(channel, 'send'):
                if attempt == 1:
                    message = f"🔄 Stream disconnected, attempting to reconnect... (attempt {attempt}/{max_attempts})"
                else:
                    message = f"🔄 Reconnection attempt {attempt}/{max_attempts}..."
                
                await channel.send(message)
                logger.debug(f"[{guild_id}]: Sent recovery attempt notification")
        except Exception as e:
            logger.warning(f"[{guild_id}]: Failed to send recovery attempt notification: {e}")
    
    async def _notify_recovery_success(self, guild_id: int, channel) -> None:
        """Notify users of successful recovery"""
        try:
            if channel and hasattr(channel, 'send'):
                await channel.send("✅ Stream reconnected successfully!")
                logger.debug(f"[{guild_id}]: Sent recovery success notification")
        except Exception as e:
            logger.warning(f"[{guild_id}]: Failed to send recovery success notification: {e}")
    
    async def _notify_recovery_failed(self, guild_id: int, channel) -> None:
        """Notify users of failed recovery"""
        try:
            if channel and hasattr(channel, 'send'):
                await channel.send("❌ Unable to reconnect to stream. Please use `/play` to start a new stream.")
                logger.debug(f"[{guild_id}]: Sent recovery failed notification")
        except Exception as e:
            logger.warning(f"[{guild_id}]: Failed to send recovery failed notification: {e}")

    def _is_valid_url(self, url: str) -> bool:
        """Validate URL format"""
        try:
            import validators
            result = validators.url(url)
            return bool(result)
        except ImportError:
            # Fallback validation
            return url.startswith(('http://', 'https://'))
    
    def get_active_streams(self) -> Dict[int, Dict[str, Any]]:
        """Get information about all active streams"""
        active_streams = {}
        
        try:
            # Get all guild IDs from state manager
            for guild_id in self.state_manager.get_all_guild_ids():
                guild_state = self.state_manager.get_guild_state(guild_id)
                
                if guild_state and guild_state.current_stream_url:
                    active_streams[guild_id] = {
                        'url': guild_state.current_stream_url,
                        'start_time': guild_state.start_time,
                        'last_updated': guild_state.last_updated,
                        'current_song': guild_state.current_song
                    }
        
        except Exception as e:
            logger.error(f"Error getting active streams: {e}")
        
        return active_streams
    
    def get_active_audio_source(self, guild_id: int) -> Optional[discord.AudioSource]:
        """
        Get the active audio source for a guild.
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            Active audio source or None if not available
        """
        try:
            # Get the bot instance from service registry
            bot = self.service_registry.get_optional('bot')
            if not bot:
                return None
            
            # Find the guild
            guild = discord.utils.get(bot.guilds, id=guild_id)
            if not guild or not guild.voice_client:
                return None
            
            # Return the current audio source
            return getattr(guild.voice_client, 'source', None)
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to get active audio source: {e}")
            return None
    
    def get_stream_stats(self) -> Dict[str, Any]:
        """Get stream service statistics"""
        active_streams = self.get_active_streams()
        
        return {
            'active_streams': len(active_streams),
            'audio_processor_available': self.audio_processor is not None,
            'stream_manager_available': self.stream_manager is not None,
            'health_monitor_available': self.health_monitor is not None,
            'service_initialized': True
        }
