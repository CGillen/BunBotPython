"""
Enhanced UI System for BunBot

Provides modernized Discord UI components with real-time audio controls,
mobile optimization, and Rich Presence integration. Built on the solid
foundation of Phases 1-3 infrastructure.

Key Features:
- Real-time audio control interfaces integrated with Phase 3 audio processing
- Mobile-optimized responsive layouts and touch-friendly controls
- Enhanced favorites management with categorization and quick access
- Rich Presence integration for improved Discord experience
- Accessibility features and theme customization
- Modular, reusable component architecture

Architecture:
- Built on Phase 1 ServiceRegistry, StateManager, EventBus, and ConfigurationManager
- Seamless integration with Phase 2 monitoring and Phase 3 audio systems
- Component-based design with abstract interfaces for extensibility
- Responsive layout system for optimal mobile experience
- Event-driven UI updates for real-time responsiveness
"""

from .interfaces import (
    UIConfig, ComponentTheme, LayoutMode, DeviceType,
    IUIComponent, IView, ILayout, IThemeManager,
    UIEvent, ComponentState, AccessibilityFeatures
)
from .components import (
    BaseComponent, Button, SelectMenu, Modal, ProgressBar,
    VolumeSlider, ToggleSwitch, StatusIndicator
)
from .views import (
    BaseView, AudioControlView, FavoritesView, SettingsView,
    StreamBrowserView, StatusView
)
from .layouts import (
    ResponsiveLayout, MobileLayout, DesktopLayout,
    CompactLayout, ExpandedLayout
)
from .themes import (
    ThemeManager, DefaultTheme, DarkTheme, HighContrastTheme,
    ColorScheme, FontSettings
)

# Audio-specific UI components
from .audio import (
    AudioControlPanel, EqualizerView, MixerView,
    StreamBrowser, EffectsPanel, VolumeControls
)

# Enhanced favorites system
from .favorites import (
    FavoritesManager, QuickAccess, CategoryOrganizer,
    FavoriteButton, PlaylistView
)

# Mobile optimization
from .mobile import (
    MobileLayout, TouchControls, CompactViews,
    SwipeGestures, MobileNavigation
)

# Rich Presence integration
from .presence import (
    PresenceManager, ActivityManager, NowPlayingDisplay,
    StreamInfoDisplay, StatusBroadcaster
)

__all__ = [
    # Core Interfaces
    'UIConfig',
    'ComponentTheme', 
    'LayoutMode',
    'DeviceType',
    'IUIComponent',
    'IView',
    'ILayout', 
    'IThemeManager',
    'UIEvent',
    'ComponentState',
    'AccessibilityFeatures',
    
    # Base Components
    'BaseComponent',
    'Button',
    'SelectMenu',
    'Modal',
    'ProgressBar',
    'VolumeSlider',
    'ToggleSwitch',
    'StatusIndicator',
    
    # Views
    'BaseView',
    'AudioControlView',
    'FavoritesView',
    'SettingsView',
    'StreamBrowserView',
    'StatusView',
    
    # Layouts
    'ResponsiveLayout',
    'MobileLayout',
    'DesktopLayout',
    'CompactLayout',
    'ExpandedLayout',
    
    # Themes
    'ThemeManager',
    'DefaultTheme',
    'DarkTheme',
    'HighContrastTheme',
    'ColorScheme',
    'FontSettings',
    
    # Audio UI
    'AudioControlPanel',
    'EqualizerView',
    'MixerView',
    'StreamBrowser',
    'EffectsPanel',
    'VolumeControls',
    
    # Favorites UI
    'FavoritesManager',
    'QuickAccess',
    'CategoryOrganizer',
    'FavoriteButton',
    'PlaylistView',
    
    # Mobile UI
    'MobileLayout',
    'TouchControls',
    'CompactViews',
    'SwipeGestures',
    'MobileNavigation',
    
    # Rich Presence
    'PresenceManager',
    'ActivityManager',
    'NowPlayingDisplay',
    'StreamInfoDisplay',
    'StatusBroadcaster'
]
