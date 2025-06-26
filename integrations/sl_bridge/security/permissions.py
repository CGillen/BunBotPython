"""
Permission System for SL Bridge

Manages permissions and access control for Second Life objects
"""

import logging
from enum import Enum
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass

from core import ServiceRegistry

logger = logging.getLogger('sl_bridge.security.permissions')


class SLPermissions(Enum):
    """Available permissions for SL Bridge API"""
    
    # Stream control permissions
    STREAM_CONTROL = "stream_control"
    STREAM_PLAY = "stream_play"
    STREAM_STOP = "stream_stop"
    STREAM_STATUS = "stream_status"
    
    # Favorites permissions
    FAVORITES_READ = "favorites_read"
    FAVORITES_WRITE = "favorites_write"
    FAVORITES_DELETE = "favorites_delete"
    
    # Audio control permissions
    AUDIO_CONTROL = "audio_control"
    AUDIO_VOLUME = "audio_volume"
    AUDIO_EQ = "audio_eq"
    AUDIO_INFO = "audio_info"
    
    # Administrative permissions
    ADMIN_SETTINGS = "admin_settings"
    ADMIN_TOKENS = "admin_tokens"
    ADMIN_USERS = "admin_users"
    
    # WebSocket permissions
    WEBSOCKET_CONNECT = "websocket_connect"
    WEBSOCKET_EVENTS = "websocket_events"


@dataclass
class PermissionSet:
    """Set of permissions with metadata"""
    permissions: Set[str]
    description: str
    is_admin: bool = False
    guild_specific: bool = True


class PermissionManager:
    """
    Manages permission checking and validation for SL Bridge.
    
    Provides role-based access control with guild-specific permissions
    and integration with the existing BunBot architecture.
    """
    
    def __init__(self, service_registry: ServiceRegistry):
        self.service_registry = service_registry
        
        # Define permission groups
        self.permission_groups = self._define_permission_groups()
        
        # Permission hierarchy (higher level permissions include lower)
        self.permission_hierarchy = {
            SLPermissions.STREAM_CONTROL: [
                SLPermissions.STREAM_PLAY,
                SLPermissions.STREAM_STOP,
                SLPermissions.STREAM_STATUS
            ],
            SLPermissions.FAVORITES_WRITE: [
                SLPermissions.FAVORITES_READ
            ],
            SLPermissions.AUDIO_CONTROL: [
                SLPermissions.AUDIO_VOLUME,
                SLPermissions.AUDIO_EQ,
                SLPermissions.AUDIO_INFO
            ],
            SLPermissions.ADMIN_SETTINGS: [
                SLPermissions.ADMIN_TOKENS,
                SLPermissions.ADMIN_USERS
            ]
        }
        
        logger.info("PermissionManager initialized")
    
    def _define_permission_groups(self) -> Dict[str, PermissionSet]:
        """Define standard permission groups"""
        return {
            "basic": PermissionSet(
                permissions={
                    SLPermissions.STREAM_STATUS.value,
                    SLPermissions.FAVORITES_READ.value,
                    SLPermissions.AUDIO_INFO.value
                },
                description="Basic read-only access"
            ),
            
            "user": PermissionSet(
                permissions={
                    SLPermissions.STREAM_CONTROL.value,
                    SLPermissions.FAVORITES_READ.value,
                    SLPermissions.AUDIO_VOLUME.value,
                    SLPermissions.WEBSOCKET_CONNECT.value
                },
                description="Standard user access"
            ),
            
            "power_user": PermissionSet(
                permissions={
                    SLPermissions.STREAM_CONTROL.value,
                    SLPermissions.FAVORITES_READ.value,
                    SLPermissions.FAVORITES_WRITE.value,
                    SLPermissions.AUDIO_CONTROL.value,
                    SLPermissions.WEBSOCKET_CONNECT.value,
                    SLPermissions.WEBSOCKET_EVENTS.value
                },
                description="Power user with audio and favorites control"
            ),
            
            "admin": PermissionSet(
                permissions={perm.value for perm in SLPermissions},
                description="Full administrative access",
                is_admin=True
            )
        }
    
    def check_permission(self, required_permission: str, user_permissions: List[str]) -> bool:
        """
        Check if user has required permission.
        
        Args:
            required_permission: Permission to check for
            user_permissions: List of user's permissions
            
        Returns:
            True if user has permission
        """
        try:
            # Direct permission check
            if required_permission in user_permissions:
                return True
            
            # Check permission hierarchy
            for parent_perm, child_perms in self.permission_hierarchy.items():
                if parent_perm.value in user_permissions:
                    if required_permission in [child.value for child in child_perms]:
                        return True
            
            # Check for admin permissions
            if SLPermissions.ADMIN_SETTINGS.value in user_permissions:
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking permission {required_permission}: {e}")
            return False
    
    def check_permissions(self, required_permissions: List[str], user_permissions: List[str]) -> bool:
        """
        Check if user has all required permissions.
        
        Args:
            required_permissions: List of required permissions
            user_permissions: List of user's permissions
            
        Returns:
            True if user has all permissions
        """
        try:
            return all(
                self.check_permission(perm, user_permissions) 
                for perm in required_permissions
            )
        except Exception as e:
            logger.error(f"Error checking permissions {required_permissions}: {e}")
            return False
    
    def get_permissions_for_group(self, group_name: str) -> Optional[Set[str]]:
        """
        Get permissions for a named group.
        
        Args:
            group_name: Name of permission group
            
        Returns:
            Set of permissions or None if group not found
        """
        try:
            permission_set = self.permission_groups.get(group_name)
            return permission_set.permissions if permission_set else None
        except Exception as e:
            logger.error(f"Error getting permissions for group {group_name}: {e}")
            return None
    
    def validate_permissions(self, permissions: List[str]) -> List[str]:
        """
        Validate and filter permissions list.
        
        Args:
            permissions: List of permissions to validate
            
        Returns:
            List of valid permissions
        """
        try:
            valid_permissions = {perm.value for perm in SLPermissions}
            return [perm for perm in permissions if perm in valid_permissions]
        except Exception as e:
            logger.error(f"Error validating permissions: {e}")
            return []
    
    def expand_permissions(self, permissions: List[str]) -> Set[str]:
        """
        Expand permissions to include implied permissions from hierarchy.
        
        Args:
            permissions: Base permissions list
            
        Returns:
            Expanded set of permissions
        """
        try:
            expanded = set(permissions)
            
            # Add implied permissions from hierarchy
            for parent_perm, child_perms in self.permission_hierarchy.items():
                if parent_perm.value in permissions:
                    expanded.update(child.value for child in child_perms)
            
            return expanded
            
        except Exception as e:
            logger.error(f"Error expanding permissions: {e}")
            return set(permissions)
    
    def get_permission_description(self, permission: str) -> Optional[str]:
        """
        Get human-readable description for a permission.
        
        Args:
            permission: Permission string
            
        Returns:
            Description or None if not found
        """
        descriptions = {
            SLPermissions.STREAM_CONTROL.value: "Control audio stream playback",
            SLPermissions.STREAM_PLAY.value: "Start audio streams",
            SLPermissions.STREAM_STOP.value: "Stop audio streams",
            SLPermissions.STREAM_STATUS.value: "View stream status",
            SLPermissions.FAVORITES_READ.value: "View favorite stations",
            SLPermissions.FAVORITES_WRITE.value: "Add/modify favorite stations",
            SLPermissions.FAVORITES_DELETE.value: "Delete favorite stations",
            SLPermissions.AUDIO_CONTROL.value: "Control audio settings",
            SLPermissions.AUDIO_VOLUME.value: "Adjust volume",
            SLPermissions.AUDIO_EQ.value: "Adjust equalizer",
            SLPermissions.AUDIO_INFO.value: "View audio configuration",
            SLPermissions.ADMIN_SETTINGS.value: "Modify system settings",
            SLPermissions.ADMIN_TOKENS.value: "Manage API tokens",
            SLPermissions.ADMIN_USERS.value: "Manage user access",
            SLPermissions.WEBSOCKET_CONNECT.value: "Connect to WebSocket",
            SLPermissions.WEBSOCKET_EVENTS.value: "Receive WebSocket events"
        }
        
        return descriptions.get(permission)
    
    def get_guild_permissions(self, guild_id: int, user_permissions: List[str]) -> Dict[str, Any]:
        """
        Get effective permissions for a specific guild.
        
        Args:
            guild_id: Discord guild ID
            user_permissions: Base user permissions
            
        Returns:
            Dict with effective permissions and metadata
        """
        try:
            # In a more complex system, this would check guild-specific overrides
            # For now, return the expanded permissions
            expanded = self.expand_permissions(user_permissions)
            
            return {
                "guild_id": guild_id,
                "permissions": list(expanded),
                "is_admin": SLPermissions.ADMIN_SETTINGS.value in expanded,
                "can_stream_control": self.check_permission(
                    SLPermissions.STREAM_CONTROL.value, user_permissions
                ),
                "can_manage_favorites": self.check_permission(
                    SLPermissions.FAVORITES_WRITE.value, user_permissions
                ),
                "can_control_audio": self.check_permission(
                    SLPermissions.AUDIO_CONTROL.value, user_permissions
                )
            }
            
        except Exception as e:
            logger.error(f"Error getting guild permissions for {guild_id}: {e}")
            return {
                "guild_id": guild_id,
                "permissions": [],
                "is_admin": False,
                "can_stream_control": False,
                "can_manage_favorites": False,
                "can_control_audio": False
            }
    
    def audit_permission_check(self, user_id: str, permission: str, granted: bool, 
                             context: Optional[Dict[str, Any]] = None) -> None:
        """
        Log permission check for auditing.
        
        Args:
            user_id: User identifier
            permission: Permission checked
            granted: Whether permission was granted
            context: Additional context
        """
        try:
            log_entry = {
                "user_id": user_id,
                "permission": permission,
                "granted": granted,
                "context": context or {}
            }
            
            logger.info(f"Permission check: {log_entry}")
            
            # In production, this would write to an audit log
            
        except Exception as e:
            logger.error(f"Error auditing permission check: {e}")
