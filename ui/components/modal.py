"""
Modal Dialog Components for BunBot Enhanced UI System

Provides modal dialog implementations for complex user input
and confirmation workflows.
"""

import logging
from typing import List, Optional, Callable, Dict, Any
import discord

from .base_component import BaseComponent
from ..interfaces import ComponentTheme, ComponentState

logger = logging.getLogger('discord.ui.components.modal')

class Modal(discord.ui.Modal):
    """Enhanced modal dialog with theming and validation"""
    
    def __init__(self, title: str, custom_id: str, theme: ComponentTheme):
        super().__init__(title=title, custom_id=custom_id)
        self.theme = theme
        self.result: Dict[str, Any] = {}
        self.callback_func: Optional[Callable] = None
    
    def set_callback(self, callback: Callable) -> None:
        """Set callback function for modal completion"""
        self.callback_func = callback
    
    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Handle modal submission"""
        try:
            # Extract values from modal
            for item in self.children:
                if hasattr(item, 'value'):
                    self.result[item.custom_id] = item.value
            
            if self.callback_func:
                await self.callback_func(interaction, self.result)
            
        except Exception as e:
            logger.error(f"Error in modal submission: {e}")

class ConfirmationModal(Modal):
    """Modal for confirmation with optional reason input"""
    
    def __init__(self, theme: ComponentTheme, action: str, require_reason: bool = False):
        super().__init__(f"Confirm {action}", f"confirm_{action}", theme)
        
        if require_reason:
            self.reason_input = discord.ui.TextInput(
                label="Reason (optional)",
                placeholder="Enter reason for this action...",
                required=False,
                max_length=500,
                custom_id="reason"
            )
            self.add_item(self.reason_input)

class InputModal(Modal):
    """Modal for collecting user input"""
    
    def __init__(self, theme: ComponentTheme, title: str, fields: List[Dict[str, Any]]):
        super().__init__(title, f"input_{title.lower().replace(' ', '_')}", theme)
        
        for field in fields[:5]:  # Discord limit
            text_input = discord.ui.TextInput(
                label=field.get('label', 'Input'),
                placeholder=field.get('placeholder', ''),
                required=field.get('required', False),
                max_length=field.get('max_length', 1000),
                custom_id=field.get('id', f"field_{len(self.children)}")
            )
            self.add_item(text_input)
