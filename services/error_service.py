"""
Error Service for BunBot
"""

import logging
import asyncio
from typing import Dict, Any, Optional
import discord
from discord.ext import commands

from core import ServiceRegistry, EventBus, StateManager

logger = logging.getLogger('services.error_service')

class ErrorService:
    """
    Centralized error handling service for BunBot.
    
    Handles all Discord command errors, provides user-friendly messages,
    and integrates with monitoring for automatic recovery.
    """
    
    def __init__(self, service_registry: ServiceRegistry):
        self.service_registry = service_registry
        self.event_bus = service_registry.get(EventBus)
        self.state_manager = service_registry.get(StateManager)
        
        # Error message templates
        self.error_messages = {
            'missing_argument': "☠️ Please provide a valid Shoutcast v2 stream link Example: `/play [shoutcast v2 stream link]`",
            'bad_argument': "☠️ The provided link is not a valid URL. Please provide a valid Shoutcast stream link.",
            'already_playing': "😱 I'm already playing music! I can't be in two places at once",
            'stream_offline': "📋 Error fetching stream. Maybe the stream is down?",
            'author_not_in_voice': "😢 You are not in a voice channel. What are you doing? Where am I supposed to go? Don't leave me here",
            'no_stream_selected': "🙄 No stream started, what did you expect me to do?",
            'no_voice_client': "🙇 I'm not playing any music! Please stop harassing me",
            'cooldown': "🥵 Slow down, I can only handle so much!",
            'bot_missing_permissions': "😶 It looks like I'm missing permissions for this channel",
            'cleaning_up': "🔧 Bot is still cleaning up from last session, please wait...",
            'generic': "🤷 An unexpected error occurred while processing your command"
        }
        
        logger.info("ErrorService initialized")
    
    async def handle_command_error(self, interaction: discord.Interaction, error: Exception) -> None:
        """
        Handle Discord command errors with appropriate user feedback.
        
        Args:
            interaction: Discord interaction that caused the error
            error: Exception that occurred
        """
        try:
            # Get the original error if it's wrapped
            original_error = error.original if hasattr(error, 'original') else error
            
            # Categorize and handle the error
            error_info = self._categorize_error(original_error)
            error_message = self._format_error_message(error_info, original_error)
            
            # Log the error for monitoring
            await self._log_error(interaction, original_error, error_info)
            
            # Send user-friendly response
            await self._send_error_response(interaction, error_message)
            
            # Attempt automatic recovery if applicable
            await self._attempt_recovery(interaction, error_info)
            
        except Exception as e:
            logger.error(f"Error in error handler: {e}")
            # Fallback error message
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "🤷 Something went very wrong. Please try again later.",
                        ephemeral=True
                    )
            except:
                pass  # Give up gracefully
    
    def _categorize_error(self, error: Exception) -> Dict[str, Any]:
        """Categorize error for appropriate handling"""
        # Import here to avoid circular imports
        import shout_errors
        
        error_type = type(error).__name__
        
        if isinstance(error, commands.MissingRequiredArgument):
            return {'category': 'missing_argument', 'severity': 'low', 'recoverable': False}
        elif isinstance(error, commands.BadArgument):
            return {'category': 'bad_argument', 'severity': 'low', 'recoverable': False}
        elif isinstance(error, commands.CommandNotFound):
            return {'category': 'command_not_found', 'severity': 'low', 'recoverable': False}
        elif isinstance(error, shout_errors.AlreadyPlaying):
            return {'category': 'already_playing', 'severity': 'medium', 'recoverable': False}
        elif isinstance(error, shout_errors.StreamOffline):
            return {'category': 'stream_offline', 'severity': 'medium', 'recoverable': True}
        elif isinstance(error, shout_errors.AuthorNotInVoice):
            return {'category': 'author_not_in_voice', 'severity': 'low', 'recoverable': False}
        elif isinstance(error, shout_errors.NoStreamSelected):
            return {'category': 'no_stream_selected', 'severity': 'low', 'recoverable': False}
        elif isinstance(error, shout_errors.NoVoiceClient):
            return {'category': 'no_voice_client', 'severity': 'low', 'recoverable': True}
        elif isinstance(error, shout_errors.CleaningUp):
            return {'category': 'cleaning_up', 'severity': 'medium', 'recoverable': True}
        elif isinstance(error, discord.app_commands.errors.CommandOnCooldown):
            return {'category': 'cooldown', 'severity': 'low', 'recoverable': False}
        elif isinstance(error, discord.app_commands.errors.BotMissingPermissions):
            return {'category': 'bot_missing_permissions', 'severity': 'high', 'recoverable': False}
        else:
            return {'category': 'generic', 'severity': 'high', 'recoverable': False}
    
    def _format_error_message(self, error_info: Dict[str, Any], original_error: Exception) -> str:
        """Format user-friendly error message"""
        category = error_info['category']
        
        if category in self.error_messages:
            base_message = self.error_messages[category]
        else:
            base_message = self.error_messages['generic']
        
        # Add specific details for certain error types
        if category == 'bot_missing_permissions':
            if hasattr(original_error, 'missing_permissions'):
                permissions = ', '.join(original_error.missing_permissions)
                base_message += f":\n{permissions}"
        elif category == 'cooldown':
            if hasattr(original_error, 'retry_after'):
                retry_time = round(original_error.retry_after, 1)
                base_message += f" Try again in {retry_time} seconds."
        
        return base_message
    
    async def _send_error_response(self, interaction: discord.Interaction, message: str) -> None:
        """Send error response to user"""
        try:
            if interaction.response.is_done():
                # Try to edit existing response first
                try:
                    original_response = await interaction.original_response()
                    if original_response:
                        original_content = original_response.content or ""
                        # Only append if it's not already an error message
                        if not original_content.startswith("❌"):
                            new_content = f"{original_content}\n{message}".strip()
                            await interaction.edit_original_response(content=new_content)
                        else:
                            # Replace with new error message
                            await interaction.edit_original_response(content=message)
                    else:
                        # No original response, use followup
                        await interaction.followup.send(message, ephemeral=True)
                except discord.NotFound:
                    # Original response was deleted, use followup
                    await interaction.followup.send(message, ephemeral=True)
                except discord.HTTPException as e:
                    # Edit failed, try followup
                    logger.warning(f"Failed to edit response, using followup: {e}")
                    await interaction.followup.send(message, ephemeral=True)
            else:
                # Send new response
                await interaction.response.send_message(message, ephemeral=True)
                
        except discord.HTTPException as e:
            # All Discord API attempts failed
            logger.error(f"Failed to send error response via Discord API: {e}")
        except Exception as e:
            logger.error(f"Unexpected error sending error response: {e}")
    
    async def _log_error(self, interaction: discord.Interaction, error: Exception, 
                        error_info: Dict[str, Any]) -> None:
        """Log error for monitoring and debugging"""
        try:
            guild_id = interaction.guild_id if interaction.guild else None
            user_id = interaction.user.id if interaction.user else None
            
            log_data = {
                'guild_id': guild_id,
                'user_id': user_id,
                'command': getattr(interaction.command, 'name', 'unknown') if interaction.command else 'unknown',
                'error_type': type(error).__name__,
                'error_category': error_info['category'],
                'severity': error_info['severity'],
                'message': str(error)
            }
            
            # Log with appropriate level based on severity
            if error_info['severity'] == 'high':
                logger.error(f"Command error: {log_data}")
            elif error_info['severity'] == 'medium':
                logger.warning(f"Command error: {log_data}")
            else:
                logger.info(f"Command error: {log_data}")
            
            # Emit event for monitoring system
            await self.event_bus.emit_async('command_error_occurred', **log_data)
            
        except Exception as e:
            logger.error(f"Failed to log error: {e}")
    
    async def _attempt_recovery(self, interaction: discord.Interaction, 
                              error_info: Dict[str, Any]) -> None:
        """Attempt automatic recovery for recoverable errors"""
        try:
            if not error_info.get('recoverable', False):
                return
            
            guild_id = interaction.guild_id if interaction.guild else None
            if not guild_id:
                return
            
            category = error_info['category']
            
            if category == 'no_voice_client':
                # Clear stale state
                guild_state = self.state_manager.get_guild_state(guild_id)
                if guild_state:
                    guild_state.current_stream_url = None
                    guild_state.cleaning_up = False
                    logger.info(f"[{guild_id}]: Auto-cleared stale state for no_voice_client error")
            
            elif category == 'cleaning_up':
                # Reset cleanup state after timeout
                await asyncio.sleep(5)  # Wait a bit
                guild_state = self.state_manager.get_guild_state(guild_id)
                if guild_state:
                    guild_state.cleaning_up = False
                    logger.info(f"[{guild_id}]: Auto-reset cleanup state")
            
            # Emit recovery event
            await self.event_bus.emit_async('error_recovery_attempted',
                                          guild_id=guild_id,
                                          error_category=category)
            
        except Exception as e:
            logger.error(f"Failed to attempt recovery: {e}")
    
    def get_error_stats(self) -> Dict[str, Any]:
        """Get error handling statistics"""
        return {
            'error_categories': list(self.error_messages.keys()),
            'total_categories': len(self.error_messages),
            'recovery_enabled': True
        }
