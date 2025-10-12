"""
Permission management system for BunBot favorites.
Handles role-based permissions with hierarchical levels.
"""

import logging
from typing import List, Dict, Any, Optional
import discord

logger = logging.getLogger('discord')

class PermissionManager:
    """Manages role-based permissions for favorites system"""

    def __init__(self):

    def get_user_permission_level(self, guild_id: int, user: discord.Member) -> int:
        """
        Get highest permission level for user based on their roles

        Args:
            guild_id: Discord guild ID
            user: Discord member object

        Returns:
            Highest permission level (1=user, 2=dj, 3=radio manager, 4=admin)
        """
        max_level = 1  # Default 'user' level

        try:
            # Check each role the user has
            for role in user.roles:
                level = self.get_role_permission_level(guild_id, role.id)
                max_level = max(max_level, level)

            logger.debug(f"User {user.id} in guild {guild_id} has permission level {max_level}")
            return max_level

        except Exception as e:
            logger.error(f"Error getting permission level for user {user.id}: {e}")
            return 1  # Default to user level on error

    def get_role_permission_level(self, guild_id: int, role_id: int) -> int:
        """
        Get permission level for a specific Discord role

        Args:
            guild_id: Discord guild ID
            role_id: Discord role ID

        Returns:
            Permission level for the role (1 if not found)
        """
        try:
            # Query server_roles to get the role mapping
            results = self.db.execute_query("""
                SELECT rh.permission_level
                FROM server_roles sr
                JOIN role_hierarchy rh ON sr.role_name = rh.role_name
                WHERE sr.guild_id = ? AND sr.discord_role_id = ?
            """, (guild_id, role_id))

            if results:
                return results[0]['permission_level']

            return 1  # Default user level

        except Exception as e:
            logger.error(f"Error getting role permission level: {e}")
            return 1

    def has_permission(self, guild_id: int, user: discord.Member, permission: str) -> bool:
        """
        Check if user has a specific permission

        Args:
            guild_id: Discord guild ID
            user: Discord member object
            permission: Permission name (can_set_favorites, can_remove_favorites, can_manage_roles)

        Returns:
            True if user has the permission
        """
        # Whitelist valid permission columns to prevent SQL injection
        valid_permissions = {
            'can_set_favorites',
            'can_remove_favorites',
            'can_manage_roles'
        }

        if permission not in valid_permissions:
            logger.error(f"Invalid permission requested: {permission}")
            return False

        try:
            # Get all permissions for user's roles
            role_ids = [role.id for role in user.roles]
            if not role_ids:
                return False

            # Create placeholders for SQL IN clause
            placeholders = ','.join('?' * len(role_ids))

            # Use parameterized query with whitelisted column name
            query = f"""
                SELECT rh.{permission}
                FROM server_roles sr
                JOIN role_hierarchy rh ON sr.role_name = rh.role_name
                WHERE sr.guild_id = ? AND sr.discord_role_id IN ({placeholders})
                AND rh.{permission} = 1
            """

            results = self.db.execute_query(query, (guild_id, *role_ids))

            has_perm = len(results) > 0
            logger.debug(f"User {user.id} permission check for {permission}: {has_perm}")
            return has_perm

        except Exception as e:
            logger.error(f"Error checking permission {permission} for user {user.id}: {e}")
            return False

    def can_set_favorites(self, guild_id: int, user: discord.Member) -> bool:
        """Check if user can set favorites"""
        return self.has_permission(guild_id, user, 'can_set_favorites')

    def can_remove_favorites(self, guild_id: int, user: discord.Member) -> bool:
        """Check if user can remove favorites"""
        return self.has_permission(guild_id, user, 'can_remove_favorites')

    def can_manage_roles(self, guild_id: int, user: discord.Member) -> bool:
        """Check if user can manage role assignments"""
        return self.has_permission(guild_id, user, 'can_manage_roles')

    def assign_role_permission(self, guild_id: int, role_id: int, role_name: str) -> bool:
        """
        Assign a permission level to a Discord role

        Args:
            guild_id: Discord guild ID
            role_id: Discord role ID
            role_name: Permission role name (user, dj, radio manager, admin)

        Returns:
            True if assignment was successful
        """
        try:
            # Check if role_name exists in hierarchy
            hierarchy_check = self.db.execute_query(
                "SELECT role_name FROM role_hierarchy WHERE role_name = ?",
                (role_name,)
            )

            if not hierarchy_check:
                logger.error(f"Invalid role name: {role_name}")
                return False

            # Insert or update the role assignment
            self.db.execute_non_query("""
                INSERT OR REPLACE INTO server_roles (guild_id, discord_role_id, role_name)
                VALUES (?, ?, ?)
            """, (guild_id, role_id, role_name))

            logger.info(f"Assigned role {role_id} in guild {guild_id} to permission level {role_name}")
            return True

        except Exception as e:
            logger.error(f"Error assigning role permission: {e}")
            return False

    def remove_role_permission(self, guild_id: int, role_id: int) -> bool:
        """
        Remove permission assignment from a Discord role

        Args:
            guild_id: Discord guild ID
            role_id: Discord role ID

        Returns:
            True if removal was successful
        """
        try:
            affected_rows = self.db.execute_non_query("""
                DELETE FROM server_roles
                WHERE guild_id = ? AND discord_role_id = ?
            """, (guild_id, role_id))

            success = affected_rows > 0
            if success:
                logger.info(f"Removed role permission for role {role_id} in guild {guild_id}")
            else:
                logger.warning(f"No permission found for role {role_id} in guild {guild_id}")

            return success

        except Exception as e:
            logger.error(f"Error removing role permission: {e}")
            return False

    def get_server_role_assignments(self, guild_id: int) -> List[Dict[str, Any]]:
        """
        Get all role assignments for a server

        Args:
            guild_id: Discord guild ID

        Returns:
            List of role assignments with permission details
        """
        try:
            results = self.db.execute_query("""
                SELECT sr.discord_role_id, sr.role_name, rh.permission_level,
                       rh.can_set_favorites, rh.can_remove_favorites, rh.can_manage_roles
                FROM server_roles sr
                JOIN role_hierarchy rh ON sr.role_name = rh.role_name
                WHERE sr.guild_id = ?
                ORDER BY rh.permission_level DESC
            """, (guild_id,))

            return results

        except Exception as e:
            logger.error(f"Error getting server role assignments: {e}")
            return []

    def get_available_permission_roles(self) -> List[Dict[str, Any]]:
        """
        Get all available permission roles from hierarchy

        Returns:
            List of available permission roles
        """
        try:
            results = self.db.execute_query("""
                SELECT role_name, permission_level, can_set_favorites,
                       can_remove_favorites, can_manage_roles
                FROM role_hierarchy
                ORDER BY permission_level ASC
            """)

            return results

        except Exception as e:
            logger.error(f"Error getting available permission roles: {e}")
            return []

# Global permission manager instance
_permission_manager = None

def get_permission_manager() -> PermissionManager:
    """Get global permission manager instance"""
    global _permission_manager
    if _permission_manager is None:
        _permission_manager = PermissionManager()
    return _permission_manager

# Decorator for checking permissions
def requires_permission(permission_check):
    """
    Decorator to check permissions before executing a command

    Args:
        permission_check: Function that takes (guild_id, user) and returns bool
    """
    def decorator(func):
        async def wrapper(interaction: discord.Interaction, *args, **kwargs):
            perm_manager = get_permission_manager()

            if not permission_check(interaction.guild.id, interaction.user):
                await interaction.response.send_message(
                    "❌ You don't have permission to use this command.",
                    ephemeral=True
                )
                return

            return await func(interaction, *args, **kwargs)
        return wrapper
    return decorator

# Common permission check functions
def can_set_favorites_check(guild_id: int, user: discord.Member) -> bool:
    """Permission check function for setting favorites"""
    return get_permission_manager().can_set_favorites(guild_id, user)

def can_remove_favorites_check(guild_id: int, user: discord.Member) -> bool:
    """Permission check function for removing favorites"""
    return get_permission_manager().can_remove_favorites(guild_id, user)

def can_manage_roles_check(guild_id: int, user: discord.Member) -> bool:
    """Permission check function for managing roles"""
    return get_permission_manager().can_manage_roles(guild_id, user)
