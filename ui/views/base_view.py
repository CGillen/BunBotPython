"""
Base View for BunBot UI System
"""

import discord
from typing import Optional, Any
import logging

logger = logging.getLogger('ui.views.base_view')

class BaseView(discord.ui.View):
    """
    Base view class for BunBot UI components.
    Provides common functionality for all views.
    """
    
    def __init__(self, *, timeout: Optional[float] = 180):
        super().__init__(timeout=timeout)
        self.message: Optional[discord.Message] = None
        self.interaction: Optional[discord.Interaction] = None
    
    async def on_timeout(self) -> None:
        """Called when the view times out"""
        try:
            if self.message:
                # Disable all components when timeout occurs
                for item in self.children:
                    if hasattr(item, 'disabled'):
                        item.disabled = True
                
                # Try to edit the message to show disabled state
                await self.message.edit(view=self)
                
        except discord.NotFound:
            # Message was deleted
            pass
        except discord.HTTPException:
            # Other HTTP errors (permissions, etc.)
            pass
        except Exception as e:
            logger.warning(f"Error during view timeout: {e}")
    
    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item[Any]) -> None:
        """Called when an error occurs in view interaction"""
        logger.error(f"View error in {self.__class__.__name__}: {error}")
        
        try:
            # Send ephemeral error message if interaction hasn't been responded to
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ An error occurred while processing your request. Please try again.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ An error occurred while processing your request. Please try again.",
                    ephemeral=True
                )
        except Exception as e:
            logger.error(f"Failed to send error message: {e}")
    
    def set_message(self, message: discord.Message) -> None:
        """Set the message this view is attached to"""
        self.message = message
    
    def set_interaction(self, interaction: discord.Interaction) -> None:
        """Set the interaction that created this view"""
        self.interaction = interaction
