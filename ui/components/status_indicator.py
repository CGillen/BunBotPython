"""
Status Indicator Components for BunBot Enhanced UI System
"""

import logging
from .base_component import BaseComponent
from ..interfaces import ComponentTheme, ComponentState

logger = logging.getLogger('discord.ui.components.status_indicator')

class StatusIndicator(BaseComponent):
    """Status indicator component"""
    
    def __init__(self, component_id: str, theme: ComponentTheme):
        super().__init__(component_id, theme)
        self.status = "normal"
    
    async def render(self, **kwargs):
        emoji_map = {
            "normal": "🟢",
            "warning": "🟡", 
            "error": "🔴",
            "loading": "🔄"
        }
        return f"{emoji_map.get(self.status, '⚪')} {self.status.title()}"

class ConnectionStatus(StatusIndicator):
    """Connection status indicator"""
    pass

class AudioStatus(StatusIndicator):
    """Audio system status indicator"""
    pass
