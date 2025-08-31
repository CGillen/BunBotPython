"""
Favorites View for BunBot

Provides interactive favorites management with button-based interface,
pagination, and real-time controls for adding/removing favorites.
"""

import logging
import math
from typing import List, Dict, Any, Optional
import discord

from .base_view import BaseView
from ..components.button import FavoriteButton, NavigationButton, ActionButton
from ..interfaces import ComponentTheme

logger = logging.getLogger('discord.ui.views.favorites_view')

class FavoritesView(BaseView):
    """
    Favorites management view with interactive buttons.
    
    Provides a modern interface for browsing and playing favorites
    with pagination, visual feedback, and intuitive controls.
    """
    
    def __init__(self, theme: ComponentTheme, guild_id: int, 
                 favorites_list: List[Dict[str, Any]], service_registry,
                 page: int = 0, favorites_per_page: int = 10):
        super().__init__(timeout=180)
        
        self.theme = theme
        self.guild_id = guild_id
        self.favorites_list = favorites_list
        self.service_registry = service_registry
        self.current_page = page
        self.favorites_per_page = favorites_per_page
        
        # Calculate pagination
        self.total_pages = max(1, math.ceil(len(favorites_list) / favorites_per_page))
        self.current_page = max(0, min(page, self.total_pages - 1))
        
        # Component tracking
        self._favorite_buttons: List[FavoriteButton] = []
        self._navigation_buttons: List[NavigationButton] = []
        self._action_buttons: List[ActionButton] = []
        
        logger.info(f"Created FavoritesView for guild {guild_id}: "
                   f"{len(favorites_list)} favorites, page {self.current_page}/{self.total_pages}")
    
    async def _build_view(self) -> None:
        """Build the complete favorites view with all components"""
        try:
            # Clear existing items
            self.clear_items()
            self._favorite_buttons.clear()
            self._navigation_buttons.clear()
            self._action_buttons.clear()
            
            # Add favorite buttons for current page
            await self._add_favorite_buttons()
            
            # Add navigation buttons if multiple pages
            if self.total_pages > 1:
                await self._add_navigation_buttons()
            
            # Add action buttons (add/remove favorites)
            await self._add_action_buttons()
            
            logger.debug(f"Built FavoritesView: {len(self._favorite_buttons)} favorites, "
                        f"{len(self._navigation_buttons)} nav, {len(self._action_buttons)} actions")
            
        except Exception as e:
            logger.error(f"Error building favorites view: {e}")
    
    async def _add_favorite_buttons(self) -> None:
        """Add favorite station buttons for the current page"""
        try:
            # Calculate page boundaries
            start_index = self.current_page * self.favorites_per_page
            end_index = min(start_index + self.favorites_per_page, len(self.favorites_list))
            
            # Add favorite buttons for current page
            for i in range(start_index, end_index):
                favorite = self.favorites_list[i]
                
                # Create favorite button
                button = FavoriteButton(
                    component_id=f"favorite_{favorite['favorite_number']}",
                    theme=self.theme,
                    favorite_number=favorite['favorite_number'],
                    station_name=favorite['station_name'],
                    stream_url=favorite['stream_url'],
                    service_registry=self.service_registry,
                    category=favorite.get('category')
                )
                
                # Render and add to view
                discord_button = await button.render()
                self.add_item(discord_button)
                self._favorite_buttons.append(button)
            
            # If no favorites on this page, add a message
            if start_index >= len(self.favorites_list):
                # Create an informational button (disabled)
                info_button = discord.ui.Button(
                    style=discord.ButtonStyle.secondary,
                    label="No favorites on this page",
                    emoji="📻",
                    disabled=True
                )
                self.add_item(info_button)
                
        except Exception as e:
            logger.error(f"Error adding favorite buttons: {e}")
    
    async def _add_navigation_buttons(self) -> None:
        """Add pagination navigation buttons"""
        try:
            # Previous page button
            if self.current_page > 0:
                prev_button = NavigationButton(
                    component_id="nav_prev",
                    theme=self.theme,
                    label="◀ Previous",
                    target_view="favorites",
                    current_page=self.current_page,
                    target_page=self.current_page - 1,
                    emoji="◀"
                )
                
                # Custom callback for navigation
                async def prev_callback(interaction: discord.Interaction):
                    await self._navigate_to_page(interaction, self.current_page - 1)
                
                discord_prev = await prev_button.render()
                discord_prev.callback = prev_callback
                self.add_item(discord_prev)
                self._navigation_buttons.append(prev_button)
            
            # Page indicator (disabled button showing current page)
            page_button = discord.ui.Button(
                style=discord.ButtonStyle.secondary,
                label=f"Page {self.current_page + 1}/{self.total_pages}",
                emoji="📄",
                disabled=True
            )
            self.add_item(page_button)
            
            # Next page button
            if self.current_page < self.total_pages - 1:
                next_button = NavigationButton(
                    component_id="nav_next",
                    theme=self.theme,
                    label="Next ▶",
                    target_view="favorites",
                    current_page=self.current_page,
                    target_page=self.current_page + 1,
                    emoji="▶"
                )
                
                # Custom callback for navigation
                async def next_callback(interaction: discord.Interaction):
                    await self._navigate_to_page(interaction, self.current_page + 1)
                
                discord_next = await next_button.render()
                discord_next.callback = next_callback
                self.add_item(discord_next)
                self._navigation_buttons.append(next_button)
                
        except Exception as e:
            logger.error(f"Error adding navigation buttons: {e}")
    
    async def _add_action_buttons(self) -> None:
        """Add action buttons for managing favorites"""
        try:
            # Add favorite button
            async def add_favorite_action(interaction: discord.Interaction, button: ActionButton):
                # This would integrate with the existing add favorite functionality
                await interaction.followup.send(
                    "💡 Use `/set-favorite <url> [name]` to add a new favorite station!",
                    ephemeral=True
                )
            
            add_button = ActionButton(
                component_id="add_favorite",
                theme=self.theme,
                label="Add Favorite",
                action=add_favorite_action,
                confirm_required=False,
                emoji="➕"
            )
            
            discord_add = await add_button.render()
            self.add_item(discord_add)
            self._action_buttons.append(add_button)
            
            # Remove favorite button (only if favorites exist)
            if self.favorites_list:
                async def remove_favorite_action(interaction: discord.Interaction, button: ActionButton):
                    await interaction.followup.send(
                        "💡 Use `/remove-favorite <number>` to remove a favorite station!",
                        ephemeral=True
                    )
                
                remove_button = ActionButton(
                    component_id="remove_favorite",
                    theme=self.theme,
                    label="Remove Favorite",
                    action=remove_favorite_action,
                    confirm_required=False,
                    emoji="🗑️"
                )
                
                # Set warning style for remove button
                remove_button.custom_style = discord.ButtonStyle.secondary
                
                discord_remove = await remove_button.render()
                self.add_item(discord_remove)
                self._action_buttons.append(remove_button)
                
        except Exception as e:
            logger.error(f"Error adding action buttons: {e}")
    
    async def _navigate_to_page(self, interaction: discord.Interaction, new_page: int) -> None:
        """
        Navigate to a different page of favorites.
        
        Args:
            interaction: Discord interaction object
            new_page: Target page number
        """
        try:
            # Validate page number
            new_page = max(0, min(new_page, self.total_pages - 1))
            
            if new_page == self.current_page:
                await interaction.response.send_message(
                    "You're already on this page!",
                    ephemeral=True
                )
                return
            
            # Update current page
            old_page = self.current_page
            self.current_page = new_page
            
            # Rebuild view for new page
            await self._build_view()
            
            # Update the message with new view
            embed = self._create_favorites_embed()
            
            await interaction.response.edit_message(
                embed=embed,
                view=self
            )
            
            logger.info(f"Navigated favorites page: {old_page} -> {new_page}")
            
        except Exception as e:
            logger.error(f"Error navigating to page {new_page}: {e}")
            await interaction.response.send_message(
                "❌ Error navigating to page. Please try again.",
                ephemeral=True
            )
    
    def _create_favorites_embed(self) -> discord.Embed:
        """
        Create the main favorites embed with current page information.
        
        Returns:
            Discord embed for favorites display
        """
        try:
            # Calculate page info
            start_index = self.current_page * self.favorites_per_page
            end_index = min(start_index + self.favorites_per_page, len(self.favorites_list))
            
            # Create embed
            if not self.favorites_list:
                embed = discord.Embed(
                    title="📻 Favorite Stations",
                    description="No favorites set for this server yet!\n\n"
                               "Use `/set-favorite <url> [name]` to add your first favorite station.",
                    color=discord.Color.from_str(self.theme.colors.primary)
                )
            else:
                # Header with page info
                title = f"📻 Favorite Stations"
                if self.total_pages > 1:
                    title += f" (Page {self.current_page + 1}/{self.total_pages})"
                
                # Description with current page favorites
                description_lines = [
                    f"**{len(self.favorites_list)} favorite stations** • Click a button to play!"
                ]
                
                if self.total_pages > 1:
                    description_lines.append(f"Showing favorites {start_index + 1}-{end_index}")
                
                embed = discord.Embed(
                    title=title,
                    description="\n".join(description_lines),
                    color=discord.Color.from_str(self.theme.colors.primary)
                )
                
                # Add favorite list as field (for reference)
                favorites_text = []
                for i in range(start_index, end_index):
                    if i < len(self.favorites_list):
                        fav = self.favorites_list[i]
                        favorites_text.append(f"**{fav['favorite_number']}.** {fav['station_name']}")
                
                if favorites_text:
                    embed.add_field(
                        name="🎵 Current Page",
                        value="\n".join(favorites_text),
                        inline=False
                    )
            
            # Footer with instructions
            embed.set_footer(
                text="💡 Use the buttons below to play favorites or manage your collection"
            )
            
            return embed
            
        except Exception as e:
            logger.error(f"Error creating favorites embed: {e}")
            return discord.Embed(
                title="📻 Favorite Stations",
                description="❌ Error loading favorites",
                color=discord.Color.red()
            )
    
    async def get_embed_and_view(self) -> tuple[discord.Embed, 'FavoritesView']:
        """
        Get the embed and view for sending.
        
        Returns:
            Tuple of (embed, view) ready for Discord message
        """
        embed = self._create_favorites_embed()
        return embed, self
    
    def get_view_stats(self) -> Dict[str, Any]:
        """Get statistics about the current view"""
        return {
            'guild_id': self.guild_id,
            'total_favorites': len(self.favorites_list),
            'current_page': self.current_page,
            'total_pages': self.total_pages,
            'favorites_per_page': self.favorites_per_page,
            'favorite_buttons': len(self._favorite_buttons),
            'navigation_buttons': len(self._navigation_buttons),
            'action_buttons': len(self._action_buttons)
        }
