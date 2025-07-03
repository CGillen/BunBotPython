"""
Enhanced Button Components for BunBot Enhanced UI System

Provides various button implementations with theming, state management,
and integration with  audio processing. Includes specialized
buttons for different use cases.

Button Types:
- Button: Basic enhanced button with theming and state
- ActionButton: Button that triggers specific actions
- NavigationButton: Button for navigation between views
- AudioButton: Button integrated with audio controls
- FavoriteButton: Button for favorite station management
"""

import logging
import asyncio
from typing import Optional, Callable, Any, Dict
import discord

from .base_component import BaseComponent
from ..interfaces import ComponentTheme, ComponentState, UI_CONSTANTS

logger = logging.getLogger('discord.ui.components.button')

class Button(BaseComponent):
    """
    Enhanced button component with theming and state management.
    
    Provides a foundation for all button types with consistent styling,
    accessibility features, and mobile optimization.
    """
    
    def __init__(self, component_id: str, theme: ComponentTheme, label: str, 
                 emoji: Optional[str] = None, style: Optional[discord.ButtonStyle] = None):
        super().__init__(component_id, theme)
        self.label = label
        self.emoji = emoji
        self.custom_style = style
        self._original_label = label
        
        # Button-specific settings
        self._max_label_length = UI_CONSTANTS['MAX_BUTTON_LABEL_LENGTH']
        self._show_state_emoji = True
        
        logger.debug(f"Created button {component_id} with label '{label}'")
    
    async def render(self, **kwargs) -> discord.ui.Button:
        """
        Render the button as a Discord UI button.
        
        Returns:
            Discord UI Button component
        """
        try:
            # Determine button style
            style = self.custom_style if self.custom_style else self._get_button_style()
            
            # Prepare label with state emoji if enabled
            display_label = self._prepare_display_label()
            
            # Create Discord button
            button = discord.ui.Button(
                style=style,
                label=display_label,
                emoji=self.emoji,
                disabled=not self.enabled,
                custom_id=self.component_id
            )
            
            # Set interaction callback
            button.callback = self._button_callback
            
            return button
            
        except Exception as e:
            logger.error(f"Error rendering button {self.component_id}: {e}")
            # Return a fallback button
            return discord.ui.Button(
                style=discord.ButtonStyle.secondary,
                label="Error",
                disabled=True,
                custom_id=f"{self.component_id}_error"
            )
    
    async def set_label(self, label: str) -> None:
        """
        Update button label.
        
        Args:
            label: New button label
        """
        old_label = self.label
        self.label = label
        self._original_label = label
        
        logger.debug(f"Button {self.component_id} label changed: '{old_label}' -> '{label}'")
    
    async def set_emoji(self, emoji: Optional[str]) -> None:
        """
        Update button emoji.
        
        Args:
            emoji: New emoji or None to remove
        """
        old_emoji = self.emoji
        self.emoji = emoji
        
        logger.debug(f"Button {self.component_id} emoji changed: '{old_emoji}' -> '{emoji}'")
    
    def set_show_state_emoji(self, show: bool) -> None:
        """
        Set whether to show state emoji in button label.
        
        Args:
            show: Whether to show state emoji
        """
        self._show_state_emoji = show
    
    def _prepare_display_label(self) -> str:
        """
        Prepare the display label with state emoji and truncation.
        
        Returns:
            Formatted label for display
        """
        label = self.label
        
        # Add state emoji if enabled
        if self._show_state_emoji:
            state_emoji = self._get_state_emoji()
            if state_emoji:
                label = f"{state_emoji} {label}"
        
        # Truncate if necessary
        return self._truncate_text(label, self._max_label_length)
    
    async def _button_callback(self, interaction: discord.Interaction) -> None:
        """
        Handle button click interaction.
        
        Args:
            interaction: Discord interaction object
        """
        try:
            # Update button state to show it was clicked
            await self.update_state(ComponentState.ACTIVE)
            
            # Handle the interaction through base class
            await self.handle_interaction(interaction)
            
            # Reset state after a brief moment (if not overridden)
            if self.state == ComponentState.ACTIVE:
                await self.update_state(ComponentState.NORMAL)
                
        except Exception as e:
            logger.error(f"Error in button callback for {self.component_id}: {e}")
            await self.update_state(ComponentState.ERROR)

class ActionButton(Button):
    """
    Button that triggers specific actions with confirmation and feedback.
    
    Provides enhanced functionality for buttons that perform important
    actions, including optional confirmation dialogs and success/error feedback.
    """
    
    def __init__(self, component_id: str, theme: ComponentTheme, label: str,
                 action: Callable, confirm_required: bool = False,
                 success_message: Optional[str] = None,
                 error_message: Optional[str] = None,
                 emoji: Optional[str] = None):
        super().__init__(component_id, theme, label, emoji)
        self.action = action
        self.confirm_required = confirm_required
        self.success_message = success_message or f"✅ {label} completed"
        self.error_message = error_message or f"❌ {label} failed"
        
        # Set default styling for action buttons
        self.custom_style = discord.ButtonStyle.primary
        
        logger.debug(f"Created action button {component_id}: confirm_required={confirm_required}")
    
    async def _button_callback(self, interaction: discord.Interaction) -> None:
        """
        Handle action button click with confirmation and feedback.
        
        Args:
            interaction: Discord interaction object
        """
        try:
            # Show confirmation if required
            if self.confirm_required:
                confirmed = await self._show_confirmation(interaction)
                if not confirmed:
                    return
            
            # Update state to show action is in progress
            await self.update_state(ComponentState.LOADING)
            
            # Acknowledge the interaction first
            if not interaction.response.is_done():
                await interaction.response.defer()
            
            # Execute the action
            try:
                result = None
                if self.action:
                    if asyncio.iscoroutinefunction(self.action):
                        result = await self.action(interaction, self)
                    else:
                        result = self.action(interaction, self)
                
                # Show success state and message
                await self.update_state(ComponentState.SUCCESS)
                
                # Send success message if not already responded
                if interaction.followup:
                    await interaction.followup.send(
                        self.success_message,
                        ephemeral=True
                    )
                
                # Reset state after success
                asyncio.create_task(self._reset_state_after_delay(2.0))
                
            except Exception as action_error:
                logger.error(f"Action failed for button {self.component_id}: {action_error}")
                
                # Show error state and message
                await self.update_state(ComponentState.ERROR)
                
                if interaction.followup:
                    await interaction.followup.send(
                        f"{self.error_message}: {str(action_error)}",
                        ephemeral=True
                    )
                
                # Reset state after error
                asyncio.create_task(self._reset_state_after_delay(3.0))
            
            # Handle the interaction through base class
            await self.handle_interaction(interaction)
            
        except Exception as e:
            logger.error(f"Error in action button callback for {self.component_id}: {e}")
            await self.update_state(ComponentState.ERROR)
    
    async def _show_confirmation(self, interaction: discord.Interaction) -> bool:
        """
        Show confirmation dialog for the action.
        
        Args:
            interaction: Discord interaction object
            
        Returns:
            True if user confirmed, False otherwise
        """
        try:
            # Create confirmation embed
            embed = discord.Embed(
                title="Confirm Action",
                description=f"Are you sure you want to {self.label.lower()}?",
                color=self._get_component_color()
            )
            
            # Create confirmation view
            view = ConfirmationView()
            
            # Send confirmation message
            await interaction.response.send_message(
                embed=embed,
                view=view,
                ephemeral=True
            )
            
            # Wait for user response
            await view.wait()
            
            return view.confirmed
            
        except Exception as e:
            logger.error(f"Error showing confirmation for {self.component_id}: {e}")
            return False
    
    async def _reset_state_after_delay(self, delay: float) -> None:
        """
        Reset button state to normal after a delay.
        
        Args:
            delay: Delay in seconds
        """
        try:
            await asyncio.sleep(delay)
            if self.state in [ComponentState.SUCCESS, ComponentState.ERROR]:
                await self.update_state(ComponentState.NORMAL)
        except Exception as e:
            logger.error(f"Error resetting state for {self.component_id}: {e}")

class NavigationButton(Button):
    """
    Button for navigation between views and pages.
    
    Provides specialized functionality for navigation, including
    page tracking and disabled state management.
    """
    
    def __init__(self, component_id: str, theme: ComponentTheme, label: str,
                 target_view: str, current_page: int = 0, target_page: int = 0,
                 emoji: Optional[str] = None):
        super().__init__(component_id, theme, label, emoji)
        self.target_view = target_view
        self.current_page = current_page
        self.target_page = target_page
        
        # Set default styling for navigation buttons
        self.custom_style = discord.ButtonStyle.secondary
        
        # Disable if navigating to current page
        if current_page == target_page:
            self.enabled = False
        
        logger.debug(f"Created navigation button {component_id}: {current_page} -> {target_page}")
    
    async def set_pages(self, current_page: int, target_page: int) -> None:
        """
        Update page information and enabled state.
        
        Args:
            current_page: Current page number
            target_page: Target page number
        """
        self.current_page = current_page
        self.target_page = target_page
        
        # Update enabled state based on page comparison
        await self.set_enabled(current_page != target_page)
        
        logger.debug(f"Navigation button {self.component_id} pages updated: {current_page} -> {target_page}")

class AudioButton(Button):
    """
    Button integrated with  audio processing system.
    
    Provides audio-specific functionality and integration with
    the audio processing pipeline.
    """
    
    def __init__(self, component_id: str, theme: ComponentTheme, label: str,
                 audio_action: str, stream_id: Optional[str] = None,
                 emoji: Optional[str] = None):
        super().__init__(component_id, theme, label, emoji)
        self.audio_action = audio_action
        self.stream_id = stream_id
        
        # Set audio-specific styling
        audio_style_map = {
            'play': discord.ButtonStyle.success,
            'pause': discord.ButtonStyle.secondary,
            'stop': discord.ButtonStyle.danger,
            'skip': discord.ButtonStyle.primary,
            'volume': discord.ButtonStyle.secondary
        }
        self.custom_style = audio_style_map.get(audio_action, discord.ButtonStyle.secondary)
        
        logger.debug(f"Created audio button {component_id}: action={audio_action}")
    
    async def _button_callback(self, interaction: discord.Interaction) -> None:
        """
        Handle audio button interaction.
        
        Args:
            interaction: Discord interaction object
        """
        try:
            # Update state to show audio action is in progress
            await self.update_state(ComponentState.LOADING)
            
            # Execute audio action through  audio system
            success = await self._execute_audio_action(interaction)
            
            if success:
                await self.update_state(ComponentState.SUCCESS)
                asyncio.create_task(self._reset_state_after_delay(1.5))
            else:
                await self.update_state(ComponentState.ERROR)
                asyncio.create_task(self._reset_state_after_delay(2.0))
            
            # Handle the interaction through base class
            await self.handle_interaction(interaction)
            
        except Exception as e:
            logger.error(f"Error in audio button callback for {self.component_id}: {e}")
            await self.update_state(ComponentState.ERROR)
    
    async def _execute_audio_action(self, interaction: discord.Interaction) -> bool:
        """
        Execute the audio action through  audio system.
        
        Args:
            interaction: Discord interaction object
            
        Returns:
            True if action was successful
        """
        try:
            # This would integrate with  audio system
            # For now, return success for demonstration
            guild_id = interaction.guild.id if interaction.guild else None
            
            logger.info(f"Executing audio action '{self.audio_action}' for guild {guild_id}")
            
            # Placeholder for audio system integration
            # In actual implementation, this would call:
            # - audio_processor.start_processing() for play
            # - audio_processor.stop_processing() for stop
            # - volume_manager.set_master_volume() for volume
            # - etc.
            
            return True
            
        except Exception as e:
            logger.error(f"Audio action failed for {self.component_id}: {e}")
            return False
    
    async def _reset_state_after_delay(self, delay: float) -> None:
        """Reset button state after delay"""
        try:
            await asyncio.sleep(delay)
            if self.state in [ComponentState.SUCCESS, ComponentState.ERROR]:
                await self.update_state(ComponentState.NORMAL)
        except Exception as e:
            logger.error(f"Error resetting audio button state: {e}")

class FavoriteButton(Button):
    """
    Button for favorite station management with enhanced features.
    
    Modernized version of the existing FavoriteButton with theming,
    state management, and integration with the enhanced UI system.
    """
    
    def __init__(self, component_id: str, theme: ComponentTheme, 
                 favorite_number: int, station_name: str, stream_url: str,
                 service_registry, category: Optional[str] = None):
        # Create label with favorite number and station name
        label = f"{favorite_number}. {station_name}"
        
        super().__init__(component_id, theme, label, emoji="🎵")
        
        self.favorite_number = favorite_number
        self.station_name = station_name
        self.stream_url = stream_url
        self.category = category
        self.service_registry = service_registry
        
        # Get StreamService from service registry using proper class type
        try:
            from services.stream_service import StreamService
            self.stream_service = service_registry.get_optional(StreamService)
        except ImportError:
            logger.warning(f"Could not import StreamService for button {component_id}")
            self.stream_service = None
        
        if not self.stream_service:
            logger.warning(f"StreamService not available for button {component_id}")
        
        # Set styling for favorite buttons
        self.custom_style = discord.ButtonStyle.primary
        
        logger.debug(f"Created favorite button {component_id}: #{favorite_number} {station_name}")
    
    async def _button_callback(self, interaction: discord.Interaction) -> None:
        """
        Handle favorite button click to play the station.
        
        Args:
            interaction: Discord interaction object
        """
        try:
            # Update state to show action is in progress
            await self.update_state(ComponentState.LOADING)
            
            # Acknowledge interaction
            await interaction.response.send_message(
                f"🎵 Starting **{self.station_name}** (Favorite #{self.favorite_number})",
                ephemeral=False
            )
            
            # Start playing the favorite through existing system
            success = await self._play_favorite(interaction)
            
            if success:
                await self.update_state(ComponentState.SUCCESS)
                asyncio.create_task(self._reset_state_after_delay(2.0))
            else:
                await self.update_state(ComponentState.ERROR)
                
                if interaction.followup:
                    await interaction.followup.send(
                        f"❌ Failed to play {self.station_name}",
                        ephemeral=True
                    )
                asyncio.create_task(self._reset_state_after_delay(3.0))
            
            # Handle the interaction through base class
            await self.handle_interaction(interaction)
            
        except Exception as e:
            logger.error(f"Error in favorite button callback for {self.component_id}: {e}")
            await self.update_state(ComponentState.ERROR)
    
    async def _play_favorite(self, interaction: discord.Interaction) -> bool:
        """
        Play the favorite station using StreamService through service registry.
        
        Args:
            interaction: Discord interaction object
            
        Returns:
            True if successful
        """
        try:
            # Check if user is in voice channel (handle both Member and User types)
            user_voice = getattr(interaction.user, 'voice', None)
            if not user_voice or not user_voice.channel:
                if interaction.followup:
                    await interaction.followup.send(
                        "😢 You are not in a voice channel. Where am I supposed to go?",
                        ephemeral=True
                    )
                return False
            
            # Check if bot is already playing
            if interaction.guild:
                voice_client = interaction.guild.voice_client
                if voice_client and hasattr(voice_client, 'is_playing') and voice_client.is_playing():
                    if interaction.followup:
                        await interaction.followup.send(
                            "😱 I'm already playing music! I can't be in two places at once",
                            ephemeral=True
                        )
                    return False
            
            # Use StreamService instead of direct bot import
            if self.stream_service:
                try:
                    await self.stream_service.start_stream(interaction, self.stream_url)
                    return True
                except Exception as stream_error:
                    logger.error(f"StreamService failed for favorite {self.favorite_number}: {stream_error}")
                    return False
            else:
                # Fallback: try to access StreamService differently
                try:
                    from services.stream_service import StreamService
                    stream_service = self.service_registry.get(StreamService)
                    await stream_service.start_stream(interaction, self.stream_url)
                    return True
                except Exception as fallback_error:
                    logger.error(f"Fallback StreamService access failed: {fallback_error}")
                    
                    # Final fallback: log error and inform user
                    if interaction.followup:
                        await interaction.followup.send(
                            f"❌ StreamService not available. Please use `/play {self.stream_url}` instead.",
                            ephemeral=True
                        )
                    return False
            
        except Exception as e:
            logger.error(f"Error playing favorite {self.favorite_number}: {e}")
            return False
    
    async def _reset_state_after_delay(self, delay: float) -> None:
        """Reset favorite button state after delay"""
        try:
            await asyncio.sleep(delay)
            if self.state in [ComponentState.SUCCESS, ComponentState.ERROR]:
                await self.update_state(ComponentState.NORMAL)
        except Exception as e:
            logger.error(f"Error resetting favorite button state: {e}")

# Helper view for confirmation dialogs
class ConfirmationView(discord.ui.View):
    """Simple confirmation view for ActionButton confirmations"""
    
    def __init__(self):
        super().__init__(timeout=60)
        self.confirmed = False
    
    @discord.ui.button(label="✅ Confirm", style=discord.ButtonStyle.success)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = True
        self.stop()
        await interaction.response.edit_message(content="✅ Confirmed", view=None)
    
    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = False
        self.stop()
        await interaction.response.edit_message(content="❌ Cancelled", view=None)
