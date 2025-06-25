"""
Abstract Interfaces and Data Structures for BunBot Enhanced UI System

Defines the core abstractions and data models used throughout the enhanced UI
system to ensure consistent interfaces and enable dependency injection.

Key Abstractions:
- UI component interfaces for modular design
- Layout management interfaces for responsive design
- Theme management interfaces for customization
- Event handling interfaces for real-time updates
- Configuration structures for UI settings
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone
import discord

logger = logging.getLogger('discord.ui.interfaces')

class DeviceType(Enum):
    """Device types for responsive design"""
    DESKTOP = "desktop"
    MOBILE = "mobile"
    TABLET = "tablet"
    UNKNOWN = "unknown"

class LayoutMode(Enum):
    """Layout modes for different screen sizes"""
    COMPACT = "compact"        # Mobile/small screens
    NORMAL = "normal"          # Standard desktop
    EXPANDED = "expanded"      # Large screens/wide layouts
    MINIMAL = "minimal"        # Minimal UI elements

class ComponentState(Enum):
    """Component state for visual feedback"""
    NORMAL = "normal"
    ACTIVE = "active"
    DISABLED = "disabled"
    LOADING = "loading"
    ERROR = "error"
    SUCCESS = "success"

class UIEvent(Enum):
    """UI events for component communication"""
    COMPONENT_CLICKED = "component_clicked"
    COMPONENT_CHANGED = "component_changed"
    VIEW_OPENED = "view_opened"
    VIEW_CLOSED = "view_closed"
    LAYOUT_CHANGED = "layout_changed"
    THEME_CHANGED = "theme_changed"
    DEVICE_CHANGED = "device_changed"

@dataclass
class ColorScheme:
    """Color scheme for UI theming"""
    primary: str = "#5865F2"          # Discord blurple
    secondary: str = "#4F545C"        # Discord gray
    success: str = "#57F287"          # Discord green
    warning: str = "#FEE75C"          # Discord yellow
    error: str = "#ED4245"            # Discord red
    background: str = "#36393F"       # Discord dark background
    surface: str = "#2F3136"          # Discord surface
    text_primary: str = "#FFFFFF"     # Primary text
    text_secondary: str = "#B9BBBE"   # Secondary text
    accent: str = "#00D4AA"           # Custom accent color

@dataclass
class FontSettings:
    """Font settings for UI components"""
    family: str = "Whitney, 'Helvetica Neue', Helvetica, Arial, sans-serif"
    size_small: int = 12
    size_normal: int = 14
    size_large: int = 16
    size_title: int = 20
    weight_normal: str = "400"
    weight_bold: str = "600"

@dataclass
class ComponentTheme:
    """Theme settings for UI components"""
    colors: ColorScheme = field(default_factory=ColorScheme)
    fonts: FontSettings = field(default_factory=FontSettings)
    border_radius: int = 4
    spacing_small: int = 4
    spacing_normal: int = 8
    spacing_large: int = 16
    shadow_enabled: bool = True
    animations_enabled: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'colors': {
                'primary': self.colors.primary,
                'secondary': self.colors.secondary,
                'success': self.colors.success,
                'warning': self.colors.warning,
                'error': self.colors.error,
                'background': self.colors.background,
                'surface': self.colors.surface,
                'text_primary': self.colors.text_primary,
                'text_secondary': self.colors.text_secondary,
                'accent': self.colors.accent
            },
            'fonts': {
                'family': self.fonts.family,
                'size_small': self.fonts.size_small,
                'size_normal': self.fonts.size_normal,
                'size_large': self.fonts.size_large,
                'size_title': self.fonts.size_title,
                'weight_normal': self.fonts.weight_normal,
                'weight_bold': self.fonts.weight_bold
            },
            'border_radius': self.border_radius,
            'spacing_small': self.spacing_small,
            'spacing_normal': self.spacing_normal,
            'spacing_large': self.spacing_large,
            'shadow_enabled': self.shadow_enabled,
            'animations_enabled': self.animations_enabled
        }

@dataclass
class AccessibilityFeatures:
    """Accessibility features configuration"""
    high_contrast: bool = False
    large_text: bool = False
    reduced_motion: bool = False
    screen_reader_support: bool = True
    keyboard_navigation: bool = True
    focus_indicators: bool = True
    alt_text_enabled: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'high_contrast': self.high_contrast,
            'large_text': self.large_text,
            'reduced_motion': self.reduced_motion,
            'screen_reader_support': self.screen_reader_support,
            'keyboard_navigation': self.keyboard_navigation,
            'focus_indicators': self.focus_indicators,
            'alt_text_enabled': self.alt_text_enabled
        }

@dataclass
class UIConfig:
    """UI configuration for a guild"""
    # Theme settings
    theme_name: str = "default"
    custom_theme: Optional[ComponentTheme] = None
    
    # Layout settings
    default_layout: LayoutMode = LayoutMode.NORMAL
    mobile_layout: LayoutMode = LayoutMode.COMPACT
    auto_detect_device: bool = True
    
    # Behavior settings
    auto_refresh_interval: float = 30.0    # seconds
    animation_duration: float = 0.3        # seconds
    tooltip_delay: float = 1.0             # seconds
    
    # Accessibility settings
    accessibility: AccessibilityFeatures = field(default_factory=AccessibilityFeatures)
    
    # Audio UI settings
    show_realtime_controls: bool = True
    show_eq_controls: bool = True
    show_mixer_controls: bool = False      # Advanced feature
    
    # Favorites UI settings
    favorites_per_page: int = 20
    show_categories: bool = True
    quick_access_count: int = 5
    
    # Mobile settings
    touch_friendly_buttons: bool = True
    swipe_gestures_enabled: bool = True
    haptic_feedback: bool = False          # If supported
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'theme_name': self.theme_name,
            'custom_theme': self.custom_theme.to_dict() if self.custom_theme else None,
            'default_layout': self.default_layout.value,
            'mobile_layout': self.mobile_layout.value,
            'auto_detect_device': self.auto_detect_device,
            'auto_refresh_interval': self.auto_refresh_interval,
            'animation_duration': self.animation_duration,
            'tooltip_delay': self.tooltip_delay,
            'accessibility': self.accessibility.to_dict(),
            'show_realtime_controls': self.show_realtime_controls,
            'show_eq_controls': self.show_eq_controls,
            'show_mixer_controls': self.show_mixer_controls,
            'favorites_per_page': self.favorites_per_page,
            'show_categories': self.show_categories,
            'quick_access_count': self.quick_access_count,
            'touch_friendly_buttons': self.touch_friendly_buttons,
            'swipe_gestures_enabled': self.swipe_gestures_enabled,
            'haptic_feedback': self.haptic_feedback
        }

class IUIComponent(ABC):
    """Abstract interface for UI components"""
    
    @abstractmethod
    def __init__(self, component_id: str, theme: ComponentTheme):
        """Initialize component with ID and theme"""
        pass
    
    @abstractmethod
    async def render(self, **kwargs) -> discord.ui.Item:
        """Render the component as a Discord UI item"""
        pass
    
    @abstractmethod
    async def update_state(self, state: ComponentState) -> None:
        """Update component visual state"""
        pass
    
    @abstractmethod
    async def set_enabled(self, enabled: bool) -> None:
        """Enable or disable the component"""
        pass
    
    @abstractmethod
    async def get_value(self) -> Any:
        """Get current component value"""
        pass
    
    @abstractmethod
    async def set_value(self, value: Any) -> None:
        """Set component value"""
        pass

class IView(ABC):
    """Abstract interface for UI views"""
    
    @abstractmethod
    def __init__(self, view_id: str, config: UIConfig):
        """Initialize view with ID and configuration"""
        pass
    
    @abstractmethod
    async def create_embed(self) -> discord.Embed:
        """Create the main embed for this view"""
        pass
    
    @abstractmethod
    async def create_view(self) -> discord.ui.View:
        """Create the Discord UI view with components"""
        pass
    
    @abstractmethod
    async def handle_interaction(self, interaction: discord.Interaction) -> None:
        """Handle user interactions"""
        pass
    
    @abstractmethod
    async def refresh(self) -> None:
        """Refresh view data and components"""
        pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """Clean up view resources"""
        pass

class ILayout(ABC):
    """Abstract interface for layout managers"""
    
    @abstractmethod
    async def arrange_components(self, components: List[IUIComponent], 
                               device_type: DeviceType) -> List[List[IUIComponent]]:
        """Arrange components for the given device type"""
        pass
    
    @abstractmethod
    async def get_max_components_per_row(self, device_type: DeviceType) -> int:
        """Get maximum components per row for device type"""
        pass
    
    @abstractmethod
    async def should_use_compact_layout(self, device_type: DeviceType) -> bool:
        """Determine if compact layout should be used"""
        pass

class IThemeManager(ABC):
    """Abstract interface for theme management"""
    
    @abstractmethod
    async def get_theme(self, theme_name: str) -> ComponentTheme:
        """Get theme by name"""
        pass
    
    @abstractmethod
    async def set_custom_theme(self, guild_id: int, theme: ComponentTheme) -> bool:
        """Set custom theme for guild"""
        pass
    
    @abstractmethod
    async def get_guild_theme(self, guild_id: int) -> ComponentTheme:
        """Get current theme for guild"""
        pass
    
    @abstractmethod
    async def list_available_themes(self) -> List[str]:
        """List all available theme names"""
        pass
    
    @abstractmethod
    async def apply_accessibility_features(self, theme: ComponentTheme, 
                                         features: AccessibilityFeatures) -> ComponentTheme:
        """Apply accessibility modifications to theme"""
        pass

# Component-specific interfaces

class IVolumeControl(ABC):
    """Interface for volume control components"""
    
    @abstractmethod
    async def set_volume(self, volume: float) -> None:
        """Set volume level (0.0 to 1.0)"""
        pass
    
    @abstractmethod
    async def get_volume(self) -> float:
        """Get current volume level"""
        pass
    
    @abstractmethod
    async def set_muted(self, muted: bool) -> None:
        """Set mute state"""
        pass

class IEqualizerControl(ABC):
    """Interface for equalizer control components"""
    
    @abstractmethod
    async def set_eq_values(self, bass: float, mid: float, treble: float) -> None:
        """Set EQ values (-12 to +12 dB)"""
        pass
    
    @abstractmethod
    async def get_eq_values(self) -> Tuple[float, float, float]:
        """Get current EQ values"""
        pass
    
    @abstractmethod
    async def apply_preset(self, preset_name: str) -> bool:
        """Apply EQ preset"""
        pass

class IStreamSelector(ABC):
    """Interface for stream selection components"""
    
    @abstractmethod
    async def set_available_streams(self, streams: List[Dict[str, Any]]) -> None:
        """Set list of available streams"""
        pass
    
    @abstractmethod
    async def get_selected_stream(self) -> Optional[str]:
        """Get currently selected stream URL"""
        pass
    
    @abstractmethod
    async def set_current_stream(self, stream_url: str) -> None:
        """Set currently playing stream"""
        pass

# Event handling types
UIEventHandler = Callable[[UIEvent, Dict[str, Any]], None]
ComponentInteractionHandler = Callable[[discord.Interaction, IUIComponent], None]
ViewInteractionHandler = Callable[[discord.Interaction, IView], None]

# Device detection utilities
def detect_device_type(user_agent: Optional[str] = None) -> DeviceType:
    """Detect device type from user agent or other indicators"""
    if not user_agent:
        return DeviceType.UNKNOWN
    
    user_agent_lower = user_agent.lower()
    
    if any(mobile in user_agent_lower for mobile in ['mobile', 'android', 'iphone', 'ipod']):
        return DeviceType.MOBILE
    elif any(tablet in user_agent_lower for tablet in ['tablet', 'ipad']):
        return DeviceType.TABLET
    else:
        return DeviceType.DESKTOP

def get_optimal_layout(device_type: DeviceType, user_preference: Optional[LayoutMode] = None) -> LayoutMode:
    """Get optimal layout mode for device type and user preference"""
    if user_preference:
        return user_preference
    
    if device_type == DeviceType.MOBILE:
        return LayoutMode.COMPACT
    elif device_type == DeviceType.TABLET:
        return LayoutMode.NORMAL
    elif device_type == DeviceType.DESKTOP:
        return LayoutMode.EXPANDED
    else:
        return LayoutMode.NORMAL

# UI Constants
UI_CONSTANTS = {
    'MAX_EMBED_FIELDS': 25,
    'MAX_EMBED_FIELD_LENGTH': 1024,
    'MAX_EMBED_DESCRIPTION_LENGTH': 4096,
    'MAX_BUTTON_LABEL_LENGTH': 80,
    'MAX_SELECT_OPTION_LABEL_LENGTH': 100,
    'MAX_COMPONENTS_PER_ROW': 5,
    'MAX_ROWS_PER_VIEW': 5,
    'INTERACTION_TIMEOUT': 900,  # 15 minutes
    'AUTO_REFRESH_INTERVAL': 30,  # 30 seconds
    'ANIMATION_DURATION_SHORT': 0.15,  # 150ms
    'ANIMATION_DURATION_NORMAL': 0.3,  # 300ms
    'ANIMATION_DURATION_LONG': 0.5,   # 500ms
}

# UI Event Constants
UI_EVENTS = {
    'component_clicked': 'ui_component_clicked',
    'component_changed': 'ui_component_changed',
    'view_opened': 'ui_view_opened',
    'view_closed': 'ui_view_closed',
    'layout_changed': 'ui_layout_changed',
    'theme_changed': 'ui_theme_changed',
    'device_changed': 'ui_device_changed',
    'accessibility_changed': 'ui_accessibility_changed'
}
