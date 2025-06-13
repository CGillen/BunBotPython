"""
Discord UI components for BunBot favorites system.
Handles interactive buttons and views for favorites management.
"""

import logging
import discord
from typing import List, Dict, Any
from favorites_manager import get_favorites_manager
from permissions import get_permission_manager

logger = logging.getLogger('discord')

class FavoritesView(discord.ui.View):
    """Discord view with buttons for each favorite station"""
    
    def __init__(self, favorites: List[Dict[str, Any]], page: int = 0):
        super().__init__(timeout=300)  # 5 minute timeout
        self.favorites = favorites
        self.page = page
        self.max_buttons = 20  # Leave room for navigation buttons
        
        # Calculate pagination
        start_idx = page * self.max_buttons
        end_idx = start_idx + self.max_buttons
        page_favorites = favorites[start_idx:end_idx]
        
        # Add button for each favorite on this page
        for favorite in page_favorites:
            button = FavoriteButton(
                favorite['favorite_number'], 
                favorite['station_name'],
                favorite['stream_url']
            )
            self.add_item(button)
        
        # Add navigation buttons if needed
        total_pages = (len(favorites) + self.max_buttons - 1) // self.max_buttons
        
        if total_pages > 1:
            # Previous page button
            if page > 0:
                prev_button = NavigationButton("◀️ Previous", page - 1, favorites)
                self.add_item(prev_button)
            
            # Next page button
            if page < total_pages - 1:
                next_button = NavigationButton("Next ▶️", page + 1, favorites)
                self.add_item(next_button)
    
    async def on_timeout(self):
        """Called when the view times out"""
        # Disable all buttons
        for item in self.children:
            item.disabled = True
        
        # Note: We can't edit the message here since we don't have access to it
        # The bot command should handle timeout by catching the timeout exception

class FavoriteButton(discord.ui.Button):
    """Button for playing a specific favorite station"""
    
    def __init__(self, number: int, name: str, url: str):
        # Truncate long names to fit Discord's button label limit (80 chars)
        display_name = name[:70] if len(name) > 70 else name
        label = f"{number}. {display_name}"
        
        super().__init__(
            label=label,
            style=discord.ButtonStyle.primary,
            custom_id=f"fav_{number}",
            emoji="🎵"
        )
        self.favorite_number = number
        self.station_name = name
        self.stream_url = url
    
    async def callback(self, interaction: discord.Interaction):
        """Handle button click to play favorite"""
        try:
            # Import here to avoid circular imports
            from bot import play_stream
            
            # Check if user is in a voice channel
            if not interaction.user.voice or not interaction.user.voice.channel:
                await interaction.response.send_message(
                    "😢 You are not in a voice channel. Where am I supposed to go? Don't leave me here",
                    ephemeral=True
                )
                return
            
            # Check if bot is already playing
            voice_client = interaction.guild.voice_client
            if voice_client and voice_client.is_playing():
                await interaction.response.send_message(
                    "😱 I'm already playing music! I can't be in two places at once",
                    ephemeral=True
                )
                return
            
            # Start playing the favorite
            await interaction.response.send_message(
                f"🎵 Starting favorite #{self.favorite_number}: **{self.station_name}**"
            )
            
            # Use the existing play_stream function
            await play_stream(interaction, self.stream_url)
            
        except Exception as e:
            logger.error(f"Error playing favorite #{self.favorite_number}: {e}")
            
            if interaction.response.is_done():
                await interaction.followup.send(
                    f"❌ Error playing {self.station_name}: {str(e)}",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"❌ Error playing {self.station_name}: {str(e)}",
                    ephemeral=True
                )

class NavigationButton(discord.ui.Button):
    """Button for navigating between pages of favorites"""
    
    def __init__(self, label: str, target_page: int, all_favorites: List[Dict[str, Any]]):
        super().__init__(
            label=label,
            style=discord.ButtonStyle.secondary,
            custom_id=f"nav_{target_page}"
        )
        self.target_page = target_page
        self.all_favorites = all_favorites
    
    async def callback(self, interaction: discord.Interaction):
        """Handle navigation button click"""
        try:
            # Create new view for the target page
            new_view = FavoritesView(self.all_favorites, self.target_page)
            new_embed = create_favorites_embed(
                self.all_favorites, 
                self.target_page, 
                interaction.guild.name
            )
            
            await interaction.response.edit_message(embed=new_embed, view=new_view)
            
        except Exception as e:
            logger.error(f"Error navigating to page {self.target_page}: {e}")
            await interaction.response.send_message(
                "❌ Error navigating pages",
                ephemeral=True
            )

class ConfirmationView(discord.ui.View):
    """View for confirmation dialogs (e.g., removing favorites)"""
    
    def __init__(self, action: str, target: str):
        super().__init__(timeout=60)  # 1 minute timeout
        self.action = action
        self.target = target
        self.confirmed = False
    
    @discord.ui.button(label="✅ Confirm", style=discord.ButtonStyle.danger)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle confirmation"""
        self.confirmed = True
        self.stop()
        
        # Disable all buttons
        for item in self.children:
            item.disabled = True
        
        await interaction.response.edit_message(
            content=f"✅ Confirmed: {self.action} {self.target}",
            view=self
        )
    
    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle cancellation"""
        self.confirmed = False
        self.stop()
        
        # Disable all buttons
        for item in self.children:
            item.disabled = True
        
        await interaction.response.edit_message(
            content=f"❌ Cancelled: {self.action} {self.target}",
            view=self
        )

def create_favorites_embed(favorites: List[Dict[str, Any]], page: int = 0, guild_name: str = "Server") -> discord.Embed:
    """
    Create an embed displaying favorites
    
    Args:
        favorites: List of favorite data
        page: Current page number
        guild_name: Name of the Discord server
        
    Returns:
        Discord embed object
    """
    max_buttons = 20
    total_pages = (len(favorites) + max_buttons - 1) // max_buttons if favorites else 1
    
    # Create embed
    embed = discord.Embed(
        title="📻 Radio Station Favorites",
        color=0x0099ff,
        description=f"Click a button below to start playing a station!"
    )
    
    if not favorites:
        embed.add_field(
            name="No Favorites",
            value="No radio stations have been added to favorites yet.\nUse `/set-favorite` to add some!",
            inline=False
        )
    else:
        # Calculate which favorites to show on this page
        start_idx = page * max_buttons
        end_idx = start_idx + max_buttons
        page_favorites = favorites[start_idx:end_idx]
        
        # Add field showing current page favorites
        favorites_text = []
        for fav in page_favorites:
            favorites_text.append(f"**{fav['favorite_number']}.** {fav['station_name']}")
        
        embed.add_field(
            name=f"Favorites ({len(favorites)} total)",
            value="\n".join(favorites_text),
            inline=False
        )
        
        # Add pagination info if multiple pages
        if total_pages > 1:
            embed.set_footer(text=f"Page {page + 1} of {total_pages}")
    
    embed.set_author(name=guild_name, icon_url=None)
    
    return embed

def create_favorites_list_embed(favorites: List[Dict[str, Any]], guild_name: str = "Server") -> discord.Embed:
    """
    Create a text-only embed listing all favorites (for mobile users)
    
    Args:
        favorites: List of favorite data
        guild_name: Name of the Discord server
        
    Returns:
        Discord embed object
    """
    embed = discord.Embed(
        title="📻 Radio Station Favorites (Text List)",
        color=0x0099ff,
        description="Complete list of saved radio stations"
    )
    
    if not favorites:
        embed.add_field(
            name="No Favorites",
            value="No radio stations have been added to favorites yet.\nUse `/set-favorite` to add some!",
            inline=False
        )
    else:
        # Split favorites into chunks to avoid Discord's field value limit
        chunk_size = 10
        for i in range(0, len(favorites), chunk_size):
            chunk = favorites[i:i + chunk_size]
            
            favorites_text = []
            for fav in chunk:
                favorites_text.append(
                    f"**{fav['favorite_number']}.** {fav['station_name']}\n"
                    f"    🔗 `{fav['stream_url']}`"
                )
            
            field_name = f"Favorites {i + 1}-{min(i + chunk_size, len(favorites))}"
            embed.add_field(
                name=field_name,
                value="\n\n".join(favorites_text),
                inline=False
            )
    
    embed.set_footer(text=f"Total: {len(favorites)} favorites | Use /play-favorite <number> to play")
    embed.set_author(name=guild_name, icon_url=None)
    
    return embed

def create_role_setup_embed(role_assignments: List[Dict[str, Any]], available_roles: List[Dict[str, Any]], guild_name: str = "Server") -> discord.Embed:
    """
    Create an embed showing current role assignments and available permission levels
    
    Args:
        role_assignments: Current role assignments for the server
        available_roles: Available permission roles from hierarchy
        guild_name: Name of the Discord server
        
    Returns:
        Discord embed object
    """
    embed = discord.Embed(
        title="🔧 Favorites Permission Setup",
        color=0xffa500,
        description="Configure which Discord roles can manage favorites"
    )
    
    # Current assignments
    if role_assignments:
        assignments_text = []
        for assignment in role_assignments:
            role_mention = f"<@&{assignment['discord_role_id']}>"
            permissions = []
            if assignment['can_set_favorites']:
                permissions.append("Set")
            if assignment['can_remove_favorites']:
                permissions.append("Remove")
            if assignment['can_manage_roles']:
                permissions.append("Manage")
            
            perm_text = ", ".join(permissions) if permissions else "None"
            assignments_text.append(f"{role_mention} → **{assignment['role_name']}** ({perm_text})")
        
        embed.add_field(
            name="Current Role Assignments",
            value="\n".join(assignments_text),
            inline=False
        )
    else:
        embed.add_field(
            name="Current Role Assignments",
            value="No roles assigned yet",
            inline=False
        )
    
    # Available permission levels
    levels_text = []
    for role in available_roles:
        permissions = []
        if role['can_set_favorites']:
            permissions.append("Set")
        if role['can_remove_favorites']:
            permissions.append("Remove")
        if role['can_manage_roles']:
            permissions.append("Manage")
        
        perm_text = ", ".join(permissions) if permissions else "None"
        levels_text.append(f"**{role['role_name']}** (Level {role['permission_level']}) - {perm_text}")
    
    embed.add_field(
        name="Available Permission Levels",
        value="\n".join(levels_text),
        inline=False
    )
    
    embed.add_field(
        name="Usage",
        value="Use `/setup-roles @role permission_level` to assign permissions\nExample: `/setup-roles @DJ dj`",
        inline=False
    )
    
    embed.set_author(name=guild_name, icon_url=None)
    
    return embed
