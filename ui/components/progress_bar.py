"""
Progress Bar Components for BunBot Enhanced UI System
"""

import logging
from typing import Optional
from .base_component import BaseComponent
from ..interfaces import ComponentTheme, ComponentState

logger = logging.getLogger('discord.ui.components.progress_bar')

class ProgressBar(BaseComponent):
    """Progress bar component for visual feedback"""
    
    def __init__(self, component_id: str, theme: ComponentTheme, max_value: float = 100.0):
        super().__init__(component_id, theme)
        self.max_value = max_value
        self.current_value = 0.0
    
    async def render(self, **kwargs):
        """Render progress bar as text representation"""
        progress = min(self.current_value / self.max_value, 1.0)
        filled_blocks = int(progress * 20)
        empty_blocks = 20 - filled_blocks
        
        bar = "█" * filled_blocks + "░" * empty_blocks
        percentage = int(progress * 100)
        
        return f"{bar} {percentage}%"

class VolumeProgressBar(ProgressBar):
    """Progress bar specifically for volume display"""
    
    def __init__(self, component_id: str, theme: ComponentTheme):
        super().__init__(component_id, theme, max_value=100.0)
