"""
Settings Routes for SL Bridge

API endpoints for configuration and settings management
"""

import logging
from typing import Dict, Any
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from core import ServiceRegistry
from ..middleware.auth_middleware import get_current_user, require_permission
from ..models.auth_models import TokenData
from ..ui.response_formatter import ResponseFormatter
from ..security.permissions import SLPermissions

logger = logging.getLogger('sl_bridge.routes.settings')

router = APIRouter()


@router.get("/bridge")
async def get_bridge_settings(
    http_request: Request,
    current_user: TokenData = Depends(require_permission(SLPermissions.STREAM_STATUS.value))
) -> JSONResponse:
    """
    Get SL Bridge configuration settings.
    """
    try:
        formatter = ResponseFormatter()
        
        # Default bridge settings (in production these could come from database/config)
        bridge_settings = {
            "guild_id": current_user.guild_id,
            "api": {
                "version": "1.0.0",
                "rate_limit": {
                    "requests_per_minute": 60,
                    "burst_limit": 10
                },
                "response_format": "sl_optimized",
                "max_response_size": 2048
            },
            "audio": {
                "default_volume": 0.8,
                "volume_step": 0.1,
                "eq_enabled": True,
                "normalization_enabled": True
            },
            "favorites": {
                "max_favorites": 50,
                "auto_validation": True
            },
            "security": {
                "jwt_expiry_hours": 24,
                "require_permissions": True,
                "audit_logging": True
            },
            "features": {
                "websocket_events": True,
                "real_time_sync": True,
                "command_history": True
            }
        }
        
        return JSONResponse(
            content=formatter.format_success(
                "Bridge settings retrieved",
                bridge_settings
            )
        )
    
    except Exception as e:
        logger.error(f"Error getting bridge settings: {e}")
        formatter = ResponseFormatter()
        return JSONResponse(
            status_code=500,
            content=formatter.format_error("INTERNAL_ERROR", "Failed to get settings")
        )


@router.get("/permissions")
async def get_user_permissions(
    http_request: Request,
    current_user: TokenData = Depends(get_current_user)
) -> JSONResponse:
    """
    Get current user's permissions and access levels.
    """
    try:
        formatter = ResponseFormatter()
        
        # Get user permissions
        user_permissions = {
            "user_id": getattr(current_user, 'user_id', 'unknown'),
            "avatar_name": getattr(current_user, 'avatar_name', 'SL User'),
            "guild_id": current_user.guild_id,
            "permissions": getattr(current_user, 'permissions', []),
            "access_level": "user",  # Could be determined from permissions
            "token_expires": getattr(current_user, 'exp', None),
            "capabilities": {
                "stream_control": SLPermissions.STREAM_CONTROL.value in getattr(current_user, 'permissions', []),
                "audio_control": SLPermissions.AUDIO_CONTROL.value in getattr(current_user, 'permissions', []),
                "favorites_read": SLPermissions.FAVORITES_READ.value in getattr(current_user, 'permissions', []),
                "favorites_write": SLPermissions.FAVORITES_WRITE.value in getattr(current_user, 'permissions', []),
                "admin_access": SLPermissions.ADMIN_SETTINGS.value in getattr(current_user, 'permissions', [])
            }
        }
        
        return JSONResponse(
            content=formatter.format_success(
                "User permissions retrieved",
                user_permissions
            )
        )
    
    except Exception as e:
        logger.error(f"Error getting user permissions: {e}")
        formatter = ResponseFormatter()
        return JSONResponse(
            status_code=500,
            content=formatter.format_error("INTERNAL_ERROR", "Failed to get permissions")
        )


@router.get("/limits")
async def get_api_limits(
    http_request: Request,
    current_user: TokenData = Depends(get_current_user)
) -> JSONResponse:
    """
    Get API rate limits and usage quotas.
    """
    try:
        formatter = ResponseFormatter()
        
        # API limits and quotas
        api_limits = {
            "guild_id": current_user.guild_id,
            "rate_limits": {
                "requests_per_minute": 60,
                "burst_requests": 10,
                "concurrent_connections": 5
            },
            "quotas": {
                "max_favorites": 50,
                "max_response_size": 2048,
                "max_stream_history": 100
            },
            "current_usage": {
                "requests_this_minute": 0,  # Could track actual usage
                "active_connections": 1,
                "favorites_used": 0  # Could get from FavoritesService
            },
            "restrictions": {
                "websocket_events": len(getattr(current_user, 'permissions', [])) > 2,
                "bulk_operations": SLPermissions.ADMIN_SETTINGS.value in getattr(current_user, 'permissions', []),
                "system_info": SLPermissions.STREAM_STATUS.value in getattr(current_user, 'permissions', [])
            }
        }
        
        return JSONResponse(
            content=formatter.format_success(
                "API limits retrieved",
                api_limits
            )
        )
    
    except Exception as e:
        logger.error(f"Error getting API limits: {e}")
        formatter = ResponseFormatter()
        return JSONResponse(
            status_code=500,
            content=formatter.format_error("INTERNAL_ERROR", "Failed to get limits")
        )


@router.post("/preferences")
async def update_user_preferences(
    preferences: Dict[str, Any],
    http_request: Request,
    current_user: TokenData = Depends(get_current_user)
) -> JSONResponse:
    """
    Update user preferences for SL Bridge.
    
    Note: This is a placeholder - actual preference storage would need implementation.
    """
    try:
        formatter = ResponseFormatter()
        
        # Validate and sanitize preferences
        allowed_preferences = {
            'default_volume',
            'auto_play_favorites',
            'notification_events',
            'response_format',
            'ui_theme'
        }
        
        filtered_preferences = {
            k: v for k, v in preferences.items() 
            if k in allowed_preferences
        }
        
        # In a full implementation, preferences would be stored in database
        # For now, just return confirmation
        
        result = {
            "guild_id": current_user.guild_id,
            "updated_preferences": filtered_preferences,
            "message": "Preferences updated (stored in session)",
            "note": "Persistent storage not implemented"
        }
        
        return JSONResponse(
            content=formatter.format_success(
                "Preferences updated",
                result
            )
        )
    
    except Exception as e:
        logger.error(f"Error updating preferences: {e}")
        formatter = ResponseFormatter()
        return JSONResponse(
            status_code=500,
            content=formatter.format_error("INTERNAL_ERROR", "Failed to update preferences")
        )


@router.get("/endpoints")
async def list_api_endpoints(
    http_request: Request,
    current_user: TokenData = Depends(get_current_user)
) -> JSONResponse:
    """
    List available API endpoints and their permissions.
    """
    try:
        formatter = ResponseFormatter()
        
        # API endpoint documentation
        endpoints = {
            "authentication": {
                "POST /api/v1/auth/token": {
                    "description": "Get JWT token",
                    "permission": "none",
                    "public": True
                }
            },
            "streams": {
                "POST /api/v1/streams/play": {
                    "description": "Start playing stream",
                    "permission": SLPermissions.STREAM_CONTROL.value,
                    "public": False
                },
                "POST /api/v1/streams/stop": {
                    "description": "Stop current stream",
                    "permission": SLPermissions.STREAM_CONTROL.value,
                    "public": False
                },
                "GET /api/v1/streams/status": {
                    "description": "Get stream status",
                    "permission": SLPermissions.STREAM_STATUS.value,
                    "public": False
                },
                "POST /api/v1/streams/refresh": {
                    "description": "Refresh stream connection",
                    "permission": SLPermissions.STREAM_CONTROL.value,
                    "public": False
                },
                "GET /api/v1/streams/history": {
                    "description": "Get stream history",
                    "permission": SLPermissions.STREAM_STATUS.value,
                    "public": False
                }
            },
            "audio": {
                "POST /api/v1/audio/volume": {
                    "description": "Set volume",
                    "permission": SLPermissions.AUDIO_CONTROL.value,
                    "public": False
                },
                "GET /api/v1/audio/volume": {
                    "description": "Get current volume",
                    "permission": SLPermissions.AUDIO_INFO.value,
                    "public": False
                },
                "POST /api/v1/audio/eq": {
                    "description": "Set equalizer",
                    "permission": SLPermissions.AUDIO_CONTROL.value,
                    "public": False
                },
                "GET /api/v1/audio/info": {
                    "description": "Get audio configuration",
                    "permission": SLPermissions.AUDIO_INFO.value,
                    "public": False
                }
            },
            "favorites": {
                "GET /api/v1/favorites/list": {
                    "description": "List favorites",
                    "permission": SLPermissions.FAVORITES_READ.value,
                    "public": False
                },
                "POST /api/v1/favorites/add": {
                    "description": "Add favorite",
                    "permission": SLPermissions.FAVORITES_WRITE.value,
                    "public": False
                },
                "POST /api/v1/favorites/play": {
                    "description": "Play favorite by number",
                    "permission": SLPermissions.STREAM_CONTROL.value,
                    "public": False
                },
                "DELETE /api/v1/favorites/remove": {
                    "description": "Remove favorite",
                    "permission": SLPermissions.FAVORITES_DELETE.value,
                    "public": False
                }
            },
            "status": {
                "GET /api/v1/status/health": {
                    "description": "Health check",
                    "permission": "none",
                    "public": True
                },
                "GET /api/v1/status/info": {
                    "description": "Server information",
                    "permission": SLPermissions.STREAM_STATUS.value,
                    "public": False
                },
                "GET /api/v1/status/version": {
                    "description": "Version information",
                    "permission": "none",
                    "public": True
                }
            }
        }
        
        return JSONResponse(
            content=formatter.format_success(
                "API endpoints listed",
                {
                    "guild_id": current_user.guild_id,
                    "user_permissions": getattr(current_user, 'permissions', []),
                    "endpoints": endpoints
                }
            )
        )
    
    except Exception as e:
        logger.error(f"Error listing endpoints: {e}")
        formatter = ResponseFormatter()
        return JSONResponse(
            status_code=500,
            content=formatter.format_error("INTERNAL_ERROR", "Failed to list endpoints")
        )
