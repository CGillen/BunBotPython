"""
Base Component Implementation for BunBot Enhanced UI System

Provides the abstract base implementation of IUIComponent interface
that all UI components inherit from. Handles common functionality
like theming, state management, and event handling.

Key Features:
- Consistent theming across all components
- State management with visual feedback
- Event handling and callback registration
- Accessibility support
- Mobile-responsive design
"""

import logging
import asyncio
from typing import Dict, Any, Optional, Callable
from datetime import datetime, timezone
import discord

from ..interfaces import IUIComponent, ComponentTheme, ComponentState, UIEvent

logger = logging.getLogger('discord.ui.components.base')

class BaseComponent(IUIComponent):
    """
    Abstract base implementation for all UI components.
    
    Provides common functionality including theming, state management,
    event handling, and accessibility features that all components need.
    """
    
    def __init__(self, component_id: str, theme: ComponentTheme):
        self.component_id = component_id
        self.theme = theme
        self.state = ComponentState.NORMAL
        self.enabled = True
        self.visible = True
        self.value = None
        
        # Event handling
        self._event_handlers: Dict[UIEvent, list] = {}
        self._interaction_callback: Optional[Callable] = None
        
        # Accessibility
        self._accessibility_label: Optional[str] = None
        self._accessibility_description: Optional[str] = None
        
        # Mobile optimization
        self._touch_friendly = True
        self._mobile_optimized = True
        
        # Component metadata
        self._created_at = datetime.now(timezone.utc)
        self._last_updated = datetime.now(timezone.utc)
        
        logger.debug(f"Created component {component_id}")
    
    async def render(self, **kwargs) -> discord.ui.Item:
        """
        Render the component as a Discord UI item.
        
        This is an abstract method that must be implemented by subclasses.
        """
        raise NotImplementedError("Subclasses must implement render()")
    
    async def update_state(self, state: ComponentState) -> None:
        """
        Update component visual state.
        
        Args:
            state: New component state
        """
        old_state = self.state
        self.state = state
        self._last_updated = datetime.now(timezone.utc)
        
        # Emit state change event
        await self._emit_event(UIEvent.COMPONENT_CHANGED, {
            'component_id': self.component_id,
            'old_state': old_state.value,
            'new_state': state.value,
            'timestamp': self._last_updated
        })
        
        logger.debug(f"Component {self.component_id} state changed: {old_state.value} -> {state.value}")
    
    async def set_enabled(self, enabled: bool) -> None:
        """
        Enable or disable the component.
        
        Args:
            enabled: Whether the component should be enabled
        """
        old_enabled = self.enabled
        self.enabled = enabled
        self._last_updated = datetime.now(timezone.utc)
        
        # Update state based on enabled status
        if not enabled and self.state != ComponentState.DISABLED:
            await self.update_state(ComponentState.DISABLED)
        elif enabled and self.state == ComponentState.DISABLED:
            await self.update_state(ComponentState.NORMAL)
        
        logger.debug(f"Component {self.component_id} enabled: {old_enabled} -> {enabled}")
    
    async def get_value(self) -> Any:
        """Get current component value"""
        return self.value
    
    async def set_value(self, value: Any) -> None:
        """
        Set component value.
        
        Args:
            value: New value for the component
        """
        old_value = self.value
        self.value = value
        self._last_updated = datetime.now(timezone.utc)
        
        # Emit value change event
        await self._emit_event(UIEvent.COMPONENT_CHANGED, {
            'component_id': self.component_id,
            'old_value': old_value,
            'new_value': value,
            'timestamp': self._last_updated
        })
        
        logger.debug(f"Component {self.component_id} value changed: {old_value} -> {value}")
    
    async def set_visible(self, visible: bool) -> None:
        """
        Set component visibility.
        
        Args:
            visible: Whether the component should be visible
        """
        old_visible = self.visible
        self.visible = visible
        self._last_updated = datetime.now(timezone.utc)
        
        logger.debug(f"Component {self.component_id} visibility: {old_visible} -> {visible}")
    
    def set_accessibility_label(self, label: str) -> None:
        """
        Set accessibility label for screen readers.
        
        Args:
            label: Accessibility label text
        """
        self._accessibility_label = label
        logger.debug(f"Component {self.component_id} accessibility label: {label}")
    
    def set_accessibility_description(self, description: str) -> None:
        """
        Set accessibility description for screen readers.
        
        Args:
            description: Accessibility description text
        """
        self._accessibility_description = description
        logger.debug(f"Component {self.component_id} accessibility description: {description}")
    
    def add_event_handler(self, event: UIEvent, handler: Callable) -> None:
        """
        Add event handler for component events.
        
        Args:
            event: UI event type
            handler: Event handler function
        """
        if event not in self._event_handlers:
            self._event_handlers[event] = []
        self._event_handlers[event].append(handler)
        
        logger.debug(f"Added event handler for {event.value} on component {self.component_id}")
    
    def remove_event_handler(self, event: UIEvent, handler: Callable) -> bool:
        """
        Remove event handler for component events.
        
        Args:
            event: UI event type
            handler: Event handler function to remove
            
        Returns:
            True if handler was removed, False if not found
        """
        if event in self._event_handlers and handler in self._event_handlers[event]:
            self._event_handlers[event].remove(handler)
            logger.debug(f"Removed event handler for {event.value} on component {self.component_id}")
            return True
        return False
    
    def set_interaction_callback(self, callback: Callable) -> None:
        """
        Set callback for Discord interaction events.
        
        Args:
            callback: Callback function for interactions
        """
        self._interaction_callback = callback
        logger.debug(f"Set interaction callback for component {self.component_id}")
    
    async def handle_interaction(self, interaction: discord.Interaction) -> None:
        """
        Handle Discord interaction for this component.
        
        Args:
            interaction: Discord interaction object
        """
        try:
            # Emit interaction event
            await self._emit_event(UIEvent.COMPONENT_CLICKED, {
                'component_id': self.component_id,
                'user_id': interaction.user.id,
                'guild_id': interaction.guild.id if interaction.guild else None,
                'timestamp': datetime.now(timezone.utc)
            })
            
            # Call registered interaction callback
            if self._interaction_callback:
                if asyncio.iscoroutinefunction(self._interaction_callback):
                    await self._interaction_callback(interaction, self)
                else:
                    self._interaction_callback(interaction, self)
            
        except Exception as e:
            logger.error(f"Error handling interaction for component {self.component_id}: {e}")
            # Update component to error state
            await self.update_state(ComponentState.ERROR)
    
    async def _emit_event(self, event: UIEvent, data: Dict[str, Any]) -> None:
        """
        Emit event to registered handlers.
        
        Args:
            event: Event type
            data: Event data
        """
        try:
            if event in self._event_handlers:
                for handler in self._event_handlers[event]:
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            await handler(event, data)
                        else:
                            handler(event, data)
                    except Exception as e:
                        logger.error(f"Error in event handler for {event.value}: {e}")
        except Exception as e:
            logger.error(f"Error emitting event {event.value}: {e}")
    
    def _get_button_style(self) -> discord.ButtonStyle:
        """
        Get appropriate Discord button style based on component state.
        
        Returns:
            Discord button style
        """
        if self.state == ComponentState.DISABLED:
            return discord.ButtonStyle.secondary
        elif self.state == ComponentState.ACTIVE:
            return discord.ButtonStyle.primary
        elif self.state == ComponentState.ERROR:
            return discord.ButtonStyle.danger
        elif self.state == ComponentState.SUCCESS:
            return discord.ButtonStyle.success
        else:
            return discord.ButtonStyle.secondary
    
    def _get_component_color(self) -> int:
        """
        Get appropriate color for embeds based on component state.
        
        Returns:
            Color integer for Discord embeds
        """
        if self.state == ComponentState.ACTIVE:
            return int(self.theme.colors.primary.replace('#', ''), 16)
        elif self.state == ComponentState.ERROR:
            return int(self.theme.colors.error.replace('#', ''), 16)
        elif self.state == ComponentState.SUCCESS:
            return int(self.theme.colors.success.replace('#', ''), 16)
        elif self.state == ComponentState.LOADING:
            return int(self.theme.colors.warning.replace('#', ''), 16)
        else:
            return int(self.theme.colors.secondary.replace('#', ''), 16)
    
    def _should_use_emoji(self) -> bool:
        """
        Determine if emoji should be used based on theme and accessibility settings.
        
        Returns:
            True if emoji should be used
        """
        # Check accessibility settings - some users prefer no emoji
        # This would be configured in the accessibility features
        return True  # Default to using emoji
    
    def _get_state_emoji(self) -> Optional[str]:
        """
        Get emoji representing current component state.
        
        Returns:
            Emoji string or None
        """
        if not self._should_use_emoji():
            return None
        
        state_emojis = {
            ComponentState.NORMAL: None,
            ComponentState.ACTIVE: "🔵",
            ComponentState.DISABLED: "⚫",
            ComponentState.LOADING: "🔄",
            ComponentState.ERROR: "❌",
            ComponentState.SUCCESS: "✅"
        }
        
        return state_emojis.get(self.state)
    
    def _truncate_text(self, text: str, max_length: int) -> str:
        """
        Truncate text to fit Discord limits while preserving readability.
        
        Args:
            text: Text to truncate
            max_length: Maximum allowed length
            
        Returns:
            Truncated text
        """
        if len(text) <= max_length:
            return text
        
        # Try to truncate at word boundary
        if max_length > 3:
            truncated = text[:max_length - 3]
            last_space = truncated.rfind(' ')
            if last_space > max_length // 2:  # Only use word boundary if it's not too short
                return truncated[:last_space] + "..."
        
        return text[:max_length - 3] + "..."
    
    def get_component_info(self) -> Dict[str, Any]:
        """
        Get component information for debugging and monitoring.
        
        Returns:
            Dictionary with component information
        """
        return {
            'component_id': self.component_id,
            'state': self.state.value,
            'enabled': self.enabled,
            'visible': self.visible,
            'value': self.value,
            'created_at': self._created_at.isoformat(),
            'last_updated': self._last_updated.isoformat(),
            'has_accessibility_label': self._accessibility_label is not None,
            'has_accessibility_description': self._accessibility_description is not None,
            'touch_friendly': self._touch_friendly,
            'mobile_optimized': self._mobile_optimized,
            'event_handler_count': sum(len(handlers) for handlers in self._event_handlers.values())
        }
