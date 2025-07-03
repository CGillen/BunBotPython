"""
Status Routes for SL Bridge

API endpoints for server status, health checks, and system information
"""

import logging
from typing import Dict, Any
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from core import ServiceRegistry
from services.stream_service import StreamService
from services.favorites_service import FavoritesService
from ..adapters import StreamAdapter, AudioAdapter
from ..middleware.auth_middleware import get_current_user, require_permission
from ..models.auth_models import TokenData
from ..ui.response_formatter import ResponseFormatter
from ..security.permissions import SLPermissions

logger = logging.getLogger('sl_bridge.routes.status')

router = APIRouter()


@router.get("/health")
async def health_check() -> JSONResponse:
    """
    Basic health check endpoint.
    
    Public endpoint for monitoring.
    """
    try:
        formatter = ResponseFormatter()
        
        return JSONResponse(
            content=formatter.format_success(
                "SL Bridge is healthy",
                {
                    "status": "healthy",
                    "service": "sl_bridge",
                    "api_version": "1.0.0"
                }
            )
        )
    
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "message": "Service unavailable",
                "error": str(e)
            }
        )


@router.get("/info")
async def get_server_info(
    http_request: Request,
    current_user: TokenData = Depends(require_permission(SLPermissions.STREAM_STATUS.value))
) -> JSONResponse:
    """
    Get comprehensive server information.
    """
    try:
        # Get services from app state
        service_registry: ServiceRegistry = http_request.app.state.service_registry
        formatter = ResponseFormatter()
        
        # Gather system information
        info = {
            "sl_bridge": {
                "version": "1.0.0",
                "status": "operational",
                "uptime": "N/A"  # Could implement actual uptime tracking
            },
            "services": {
                "stream_service": True,
                "favorites_service": True,
                "audio_adapter": True
            },
            "guild_id": current_user.guild_id,
            "permissions": getattr(current_user, 'permissions', [])
        }
        
        # Test service availability
        try:
            stream_service = service_registry.get(StreamService)
            info["services"]["stream_service"] = stream_service is not None
        except Exception:
            info["services"]["stream_service"] = False
        
        try:
            favorites_service = service_registry.get(FavoritesService)
            info["services"]["favorites_service"] = favorites_service is not None
        except Exception:
            info["services"]["favorites_service"] = False
        
        return JSONResponse(
            content=formatter.format_success(
                "Server information retrieved",
                info
            )
        )
    
    except Exception as e:
        logger.error(f"Error getting server info: {e}")
        formatter = ResponseFormatter()
        return JSONResponse(
            status_code=500,
            content=formatter.format_error("INTERNAL_ERROR", "Failed to get server info")
        )


@router.get("/guild/{guild_id}/status")
async def get_guild_status(
    guild_id: int,
    http_request: Request,
    current_user: TokenData = Depends(require_permission(SLPermissions.STREAM_STATUS.value))
) -> JSONResponse:
    """
    Get comprehensive status for a specific guild.
    """
    try:
        # Get services from app state
        service_registry: ServiceRegistry = http_request.app.state.service_registry
        stream_adapter = StreamAdapter(service_registry)
        audio_adapter = AudioAdapter(service_registry)
        formatter = ResponseFormatter()
        
        # Validate guild access
        if current_user.guild_id != guild_id:
            return JSONResponse(
                status_code=403,
                content=formatter.format_error(
                    "ACCESS_DENIED",
                    f"Access denied to guild {guild_id}"
                )
            )
        
        # Get stream status
        stream_status = await stream_adapter.get_stream_status(guild_id)
        
        # Get audio status
        audio_info = await audio_adapter.get_audio_info(guild_id)
        
        # Get favorites count
        try:
            favorites_service = service_registry.get(FavoritesService)
            favorites_count = favorites_service.get_favorites_count(guild_id)
        except Exception:
            favorites_count = 0
        
        # Compile comprehensive status
        guild_status = {
            "guild_id": guild_id,
            "stream": {
                "is_playing": stream_status.get("is_playing", False),
                "current_song": stream_status.get("current_song"),
                "station_name": stream_status.get("station_name"),
                "stream_url": stream_status.get("stream_url")
            },
            "audio": {
                "volume": audio_info.get("volume", 0.8),
                "volume_manager_available": audio_info.get("volume_manager_available", False)
            },
            "favorites": {
                "count": favorites_count
            },
            "bridge": {
                "connected": True,
                "last_activity": "now"  # Could implement actual activity tracking
            }
        }
        
        return JSONResponse(
            content=formatter.format_success(
                f"Guild {guild_id} status retrieved",
                guild_status
            )
        )
    
    except Exception as e:
        logger.error(f"Error getting guild status: {e}")
        formatter = ResponseFormatter()
        return JSONResponse(
            status_code=500,
            content=formatter.format_error("INTERNAL_ERROR", "Failed to get guild status")
        )


@router.get("/stats")
async def get_bridge_stats(
    http_request: Request,
    current_user: TokenData = Depends(require_permission(SLPermissions.STREAM_STATUS.value))
) -> JSONResponse:
    """
    Get SL Bridge usage statistics.
    """
    try:
        # Get services from app state
        service_registry: ServiceRegistry = http_request.app.state.service_registry
        stream_adapter = StreamAdapter(service_registry)
        audio_adapter = AudioAdapter(service_registry)
        formatter = ResponseFormatter()
        
        # Gather statistics
        stats = {
            "adapters": {
                "stream": stream_adapter.get_adapter_stats(),
                "audio": audio_adapter.get_adapter_stats()
            },
            "user": {
                "guild_id": current_user.guild_id,
                "permissions": len(getattr(current_user, 'permissions', [])),
                "authenticated": True
            }
        }
        
        # Add service statistics if available
        try:
            stream_service = service_registry.get(StreamService)
            stats["services"] = {
                "stream": stream_service.get_stream_stats()
            }
        except Exception:
            stats["services"] = {
                "stream": {"error": "service_unavailable"}
            }
        
        return JSONResponse(
            content=formatter.format_success(
                "Bridge statistics retrieved",
                stats
            )
        )
    
    except Exception as e:
        logger.error(f"Error getting bridge stats: {e}")
        formatter = ResponseFormatter()
        return JSONResponse(
            status_code=500,
            content=formatter.format_error("INTERNAL_ERROR", "Failed to get bridge stats")
        )


@router.get("/version")
async def get_version() -> JSONResponse:
    """
    Get SL Bridge version information.
    
    Public endpoint.
    """
    try:
        formatter = ResponseFormatter()
        
        version_info = {
            "sl_bridge_version": "1.0.0",
            "api_version": "v1",
            "protocol_version": "1.0",
            "compatibility": {
                "lsl_version": "any",
                "sl_server": "main_grid"
            },
            "features": [
                "stream_control",
                "audio_control", 
                "favorites_management",
                "real_time_events",
                "secure_authentication"
            ]
        }
        
        return JSONResponse(
            content=formatter.format_success(
                "Version information",
                version_info
            )
        )
    
    except Exception as e:
        logger.error(f"Error getting version: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": "Failed to get version",
                "error": str(e)
            }
        )
