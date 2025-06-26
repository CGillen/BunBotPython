"""
Layout System for BunBot UI
"""

from .responsive_layout import ResponsiveLayout

# Create aliases for all layout types
MobileLayout = ResponsiveLayout
DesktopLayout = ResponsiveLayout
CompactLayout = ResponsiveLayout
ExpandedLayout = ResponsiveLayout
TabletLayout = ResponsiveLayout
GridLayout = ResponsiveLayout

__all__ = [
    'ResponsiveLayout', 
    'MobileLayout', 
    'DesktopLayout', 
    'CompactLayout',
    'ExpandedLayout',
    'TabletLayout',
    'GridLayout'
]
