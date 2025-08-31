"""
Enhanced Select Menu Components for BunBot Enhanced UI System

Provides dropdown selection components with search, categorization,
and integration with audio processing.

Component Types:
- SelectMenu: Basic enhanced select menu with theming
- StreamSelectMenu: Select menu for stream/station selection  
- PresetSelectMenu: Select menu for EQ and audio presets
"""

import logging
from typing import List, Dict, Any, Optional, Callable
import discord

from .base_component import BaseComponent
from ..interfaces import ComponentTheme, ComponentState, UI_CONSTANTS

logger = logging.getLogger('discord.ui.components.select_menu')

class SelectMenu(BaseComponent):
    """Enhanced select menu component with theming and categorization"""
    
    def __init__(self, component_id: str, theme: ComponentTheme, placeholder: str,
                 options: List[discord.SelectOption], max_values: int = 1):
        super().__init__(component_id, theme)
        self.placeholder = placeholder
        self.options = options
        self.max_values = max_values
        self.selected_values: List[str] = []
        
        logger.debug(f"Created select menu {component_id} with {len(options)} options")
    
    async def render(self, **kwargs) -> discord.ui.Select:
        """Render the select menu as a Discord UI select"""
        try:
            select = discord.ui.Select(
                placeholder=self.placeholder,
                options=self.options[:25],  # Discord limit
                max_values=min(self.max_values, len(self.options)),
                disabled=not self.enabled,
                custom_id=self.component_id
            )
            
            select.callback = self._select_callback
            return select
            
        except Exception as e:
            logger.error(f"Error rendering select menu {self.component_id}: {e}")
            # Return fallback select
            return discord.ui.Select(
                placeholder="Error",
                options=[discord.SelectOption(label="Error", value="error")],
                disabled=True
            )
    
    async def _select_callback(self, interaction: discord.Interaction) -> None:
        """Handle select menu interaction"""
        try:
            self.selected_values = interaction.data.get('values', [])
            await self.set_value(self.selected_values)
            await self.handle_interaction(interaction)
        except Exception as e:
            logger.error(f"Error in select callback for {self.component_id}: {e}")

class StreamSelectMenu(SelectMenu):
    """Specialized select menu for stream/station selection"""
    
    def __init__(self, component_id: str, theme: ComponentTheme, streams: List[Dict[str, Any]]):
        options = []
        for i, stream in enumerate(streams[:25]):  # Discord limit
            options.append(discord.SelectOption(
                label=stream.get('name', f'Stream {i+1}'),
                value=stream.get('url', ''),
                description=stream.get('description', '')[:100],  # Discord limit
                emoji=stream.get('emoji', '🎵')
            ))
        
        super().__init__(component_id, theme, "Select a stream", options)
        self.streams = streams

class PresetSelectMenu(SelectMenu):
    """Specialized select menu for audio presets"""
    
    def __init__(self, component_id: str, theme: ComponentTheme, preset_type: str = "eq"):
        if preset_type == "eq":
            presets = [
                {"name": "Flat", "value": "flat", "emoji": "⚪"},
                {"name": "Rock", "value": "rock", "emoji": "🎸"},
                {"name": "Pop", "value": "pop", "emoji": "🎤"},
                {"name": "Jazz", "value": "jazz", "emoji": "🎷"},
                {"name": "Classical", "value": "classical", "emoji": "🎼"},
                {"name": "Electronic", "value": "electronic", "emoji": "🎛️"},
                {"name": "Vocal", "value": "vocal", "emoji": "🗣️"},
                {"name": "Bass Boost", "value": "bass_boost", "emoji": "🔊"},
                {"name": "Treble Boost", "value": "treble_boost", "emoji": "🔆"}
            ]
        else:
            presets = []
        
        options = [
            discord.SelectOption(
                label=preset["name"],
                value=preset["value"],
                emoji=preset["emoji"]
            ) for preset in presets
        ]
        
        super().__init__(component_id, theme, f"Select {preset_type} preset", options)
        self.preset_type = preset_type
