"""
Audio Control Routes for SL Bridge

API endpoints for audio control (volume, EQ, etc.)
"""

import logging
from typing import Dict, Any
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from core import ServiceRegistry
from ..adapters import AudioAdapter
from ..middleware.auth_middleware import get_current_user, require_permission
from ..models.auth_models import TokenData
from ..models.request_models import VolumeRequest, EQRequest
from ..ui.response_formatter import ResponseFormatter
from ..security.permissions import SLPermissions

logger = logging.getLogger('sl_bridge.routes.audio')

router = APIRouter()


@router.post("/volume")
async def set_volume(
    request: VolumeRequest,
    http_request: Request,
    current_user: TokenData = Depends(require_permission(SLPermissions.AUDIO_CONTROL.value))
) -> JSONResponse:
    """
    Set master volume level.
    
    Equivalent to Discord /volume command.
    """
    try:
        # Get services from app state
        service_registry: ServiceRegistry = http_request.app.state.service_registry
        audio_adapter = AudioAdapter(service_registry)
        formatter = ResponseFormatter()
        
        # Validate guild access
        if current_user.guild_id != request.guild_id:
            return JSONResponse(
                status_code=403,
                content=formatter.format_error(
                    "ACCESS_DENIED",
                    f"Access denied to guild {request.guild_id}"
                )
            )
        
        # Set volume using adapter
        result = await audio_adapter.set_volume(
            guild_id=request.guild_id,
            volume=request.volume
        )
        
        if result.get("success", False):
            # Broadcast event to WebSocket clients
            server = http_request.app.state.get('sl_bridge_server')
            if server:
                await server.broadcast_event("volume_changed", {
                    "guild_id": request.guild_id,
                    "volume": request.volume,
                    "user": getattr(current_user, 'avatar_name', 'SL User')
                }, request.guild_id)
            
            return JSONResponse(
                content=formatter.format_simple_confirmation(
                    f"Volume set to {request.volume:.1%}", 
                    request.guild_id
                )
            )
        else:
            return JSONResponse(
                status_code=400,
                content=formatter.format_error(
                    "VOLUME_FAILED",
                    result.get("message", "Failed to set volume")
                )
            )
    
    except Exception as e:
        logger.error(f"Error setting volume: {e}")
        formatter = ResponseFormatter()
        return JSONResponse(
            status_code=500,
            content=formatter.format_error("INTERNAL_ERROR", "Failed to set volume")
        )


@router.get("/volume")
async def get_volume(
    guild_id: int,
    http_request: Request,
    current_user: TokenData = Depends(require_permission(SLPermissions.AUDIO_INFO.value))
) -> JSONResponse:
    """
    Get current volume level.
    """
    try:
        # Get services from app state
        service_registry: ServiceRegistry = http_request.app.state.service_registry
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
        
        # Get volume using adapter
        volume_info = await audio_adapter.get_volume(guild_id=guild_id)
        
        return JSONResponse(
            content=formatter.format_success(
                f"Current volume: {volume_info.get('volume', 0.8):.1%}",
                volume_info
            )
        )
    
    except Exception as e:
        logger.error(f"Error getting volume: {e}")
        formatter = ResponseFormatter()
        return JSONResponse(
            status_code=500,
            content=formatter.format_error("INTERNAL_ERROR", "Failed to get volume")
        )


@router.post("/eq")
async def set_equalizer(
    request: EQRequest,
    http_request: Request,
    current_user: TokenData = Depends(require_permission(SLPermissions.AUDIO_CONTROL.value))
) -> JSONResponse:
    """
    Set equalizer settings.
    
    Equivalent to Discord /eq command.
    """
    try:
        # Get services from app state
        service_registry: ServiceRegistry = http_request.app.state.service_registry
        audio_adapter = AudioAdapter(service_registry)
        formatter = ResponseFormatter()
        
        # Validate guild access
        if current_user.guild_id != request.guild_id:
            return JSONResponse(
                status_code=403,
                content=formatter.format_error(
                    "ACCESS_DENIED",
                    f"Access denied to guild {request.guild_id}"
                )
            )
        
        # Set EQ using adapter
        result = await audio_adapter.set_equalizer(
            guild_id=request.guild_id,
            bass=request.bass or 0.0,
            mid=request.mid or 0.0,
            treble=request.treble or 0.0
        )
        
        if result.get("success", False):
            # Broadcast event to WebSocket clients
            server = http_request.app.state.get('sl_bridge_server')
            if server:
                await server.broadcast_event("eq_changed", {
                    "guild_id": request.guild_id,
                    "bass": request.bass,
                    "mid": request.mid,
                    "treble": request.treble,
                    "user": getattr(current_user, 'avatar_name', 'SL User')
                }, request.guild_id)
            
            return JSONResponse(
                content=formatter.format_simple_confirmation("EQ settings updated", request.guild_id)
            )
        else:
            return JSONResponse(
                status_code=400,
                content=formatter.format_error(
                    "EQ_FAILED",
                    result.get("message", "Failed to set EQ")
                )
            )
    
    except Exception as e:
        logger.error(f"Error setting EQ: {e}")
        formatter = ResponseFormatter()
        return JSONResponse(
            status_code=500,
            content=formatter.format_error("INTERNAL_ERROR", "Failed to set EQ")
        )


@router.get("/info")
async def get_audio_info(
    guild_id: int,
    http_request: Request,
    current_user: TokenData = Depends(require_permission(SLPermissions.AUDIO_INFO.value))
) -> JSONResponse:
    """
    Get comprehensive audio information.
    
    Equivalent to Discord /audio-info command.
    """
    try:
        # Get services from app state
        service_registry: ServiceRegistry = http_request.app.state.service_registry
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
        
        # Get audio info using adapter
        audio_info = await audio_adapter.get_audio_info(guild_id=guild_id)
        
        return JSONResponse(
            content=formatter.format_audio_info(
                volume=audio_info.get("volume", 0.8),
                eq_settings=audio_info.get("equalizer", {"bass": 0, "mid": 0, "treble": 0}),
                guild_id=guild_id
            )
        )
    
    except Exception as e:
        logger.error(f"Error getting audio info: {e}")
        formatter = ResponseFormatter()
        return JSONResponse(
            status_code=500,
            content=formatter.format_error("INTERNAL_ERROR", "Failed to get audio info")
        )
