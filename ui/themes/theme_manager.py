"""
Theme Manager for BunBot UI
"""

import discord

class ThemeManager:
    """Simple theme management for Discord embeds and components"""
    
    def __init__(self):
        self.themes = {
            'default': {
                'primary_color': discord.Color.blue(),
                'success_color': discord.Color.green(),
                'error_color': discord.Color.red(),
                'warning_color': discord.Color.orange(),
                'info_color': discord.Color.blurple()
            }
        }
        self.current_theme = 'default'
    
    def get_color(self, color_type: str) -> discord.Color:
        """Get a color from the current theme"""
        theme = self.themes.get(self.current_theme, self.themes['default'])
        return theme.get(f'{color_type}_color', discord.Color.default())
    
    def set_theme(self, theme_name: str) -> bool:
        """Set the current theme"""
        if theme_name in self.themes:
            self.current_theme = theme_name
            return True
        return False
