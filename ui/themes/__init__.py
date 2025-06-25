"""
Theme System for BunBot UI
"""

from .theme_manager import ThemeManager

# Aliases for UI theme-related classes
DefaultTheme = ThemeManager
DarkTheme = ThemeManager
LightTheme = ThemeManager
HighContrastTheme = ThemeManager
ColorScheme = ThemeManager
FontSettings = ThemeManager
IconTheme = ThemeManager
AnimationSettings = ThemeManager
LayoutTheme = ThemeManager
CustomTheme = ThemeManager

__all__ = [
    'ThemeManager', 'DefaultTheme', 'DarkTheme', 'LightTheme', 
    'HighContrastTheme', 'ColorScheme', 'FontSettings', 'IconTheme',
    'AnimationSettings', 'LayoutTheme', 'CustomTheme'
]
