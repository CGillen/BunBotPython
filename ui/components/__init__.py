"""
Core UI Components for BunBot Enhanced UI System

Provides modular, reusable UI components that implement the IUIComponent interface.
These components serve as building blocks for more complex views and interfaces.

Components:
- BaseComponent: Abstract base implementation
- Button: Enhanced button with theming and state management
- SelectMenu: Dropdown selection with search and categorization
- Modal: Modal dialogs for complex interactions
- ProgressBar: Visual progress indicators
- VolumeSlider: Audio volume control component
- ToggleSwitch: Binary state toggle component
- StatusIndicator: Visual status and health indicators
"""

from .base_component import BaseComponent
from .button import Button, ActionButton, NavigationButton
from .select_menu import SelectMenu, StreamSelectMenu, PresetSelectMenu
from .modal import Modal, ConfirmationModal, InputModal
from .progress_bar import ProgressBar, VolumeProgressBar
from .volume_slider import VolumeSlider, ChannelVolumeSlider
from .toggle_switch import ToggleSwitch, EffectToggle
from .status_indicator import StatusIndicator, ConnectionStatus, AudioStatus

__all__ = [
    # Base
    'BaseComponent',
    
    # Buttons
    'Button',
    'ActionButton', 
    'NavigationButton',
    
    # Select Menus
    'SelectMenu',
    'StreamSelectMenu',
    'PresetSelectMenu',
    
    # Modals
    'Modal',
    'ConfirmationModal',
    'InputModal',
    
    # Progress Bars
    'ProgressBar',
    'VolumeProgressBar',
    
    # Volume Controls
    'VolumeSlider',
    'ChannelVolumeSlider',
    
    # Toggles
    'ToggleSwitch',
    'EffectToggle',
    
    # Status Indicators
    'StatusIndicator',
    'ConnectionStatus',
    'AudioStatus'
]
