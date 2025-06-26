"""
Stream Control Routes for SL Bridge

API endpoints for stream playback control
"""

import logging
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from core import ServiceRegistry
from audio import IAudioProcessor, IVolumeManager
from ..adapters import StreamAdapter, AudioAdapter
from ..middleware.auth_middleware import get_current_user, require_permission
from ..models.auth_models import TokenData
from ..models.request_models import StreamPlayRequest, StreamControlRequest
from ..ui.response_formatter import ResponseFormatter
from ..security.permissions import SLPermissions

logger = logging.getLogger('sl_bridge.routes.stream')

router = APIRouter()


@router.post("/play")
async def play_stream(
    request: StreamPlayRequest,
    http_request: Request,
    current_user: TokenData = Depends(require_permission(SLPermissions.STREAM_CONTROL.value))
) -> JSONResponse:
    """
    Start playing an audio stream.
    
    Equivalent to Discord /play command.
    """
    try:
        # Get services from app state
        service_registry: ServiceRegistry = http_request.app.state.service_registry
        stream_adapter = StreamAdapter(service_registry)
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
        
        # Start the stream using adapter
        result = await stream_adapter.play_stream(
            url=request.url,
            guild_id=request.guild_id,
            channel_id=request.channel_id
        )
        
        if result.get("success", False):
            # Broadcast event to WebSocket clients
            server = http_request.app.state.get('sl_bridge_server')
            if server:
                await server.broadcast_event("stream_started", {
                    "guild_id": request.guild_id,
                    "url": request.url,
                    "user": getattr(current_user, 'avatar_name', 'SL User')
                }, request.guild_id)
            
            return JSONResponse(
                content=formatter.format_simple_confirmation("Stream started", request.guild_id)
            )
        else:
            return JSONResponse(
                status_code=400,
                content=formatter.format_error(
                    "STREAM_FAILED",
                    result.get("message", "Failed to start stream")
                )
            )
    
    except Exception as e:
        logger.error(f"Error starting stream: {e}")
        formatter = ResponseFormatter()
        return JSONResponse(
            status_code=500,
            content=formatter.format_error("INTERNAL_ERROR", "Failed to start stream")
        )


@router.post("/stop") 
async def stop_stream(
    request: StreamControlRequest,
    http_request: Request,
    current_user: TokenData = Depends(require_permission(SLPermissions.STREAM_CONTROL.value))
) -> JSONResponse:
    """
    Stop the currently playing stream.
    
    Equivalent to Discord /leave command.
    """
    try:
        # Get services from app state
        service_registry: ServiceRegistry = http_request.app.state.service_registry
        stream_adapter = StreamAdapter(service_registry)
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
        
        # Stop the stream using adapter
        result = await stream_adapter.stop_stream(guild_id=request.guild_id)
        
        if result.get("success", False):
            # Broadcast event to WebSocket clients
            server = http_request.app.state.get('sl_bridge_server')
            if server:
                await server.broadcast_event("stream_stopped", {
                    "guild_id": request.guild_id,
                    "user": getattr(current_user, 'avatar_name', 'SL User')
                }, request.guild_id)
            
            return JSONResponse(
                content=formatter.format_simple_confirmation("Stream stopped", request.guild_id)
            )
        else:
            return JSONResponse(
                status_code=400,
                content=formatter.format_error(
                    "STOP_FAILED",
                    result.get("message", "Failed to stop stream")
                )
            )
    
    except Exception as e:
        logger.error(f"Error stopping stream: {e}")
        formatter = ResponseFormatter()
        return JSONResponse(
            status_code=500,
            content=formatter.format_error("INTERNAL_ERROR", "Failed to stop stream")
        )


@router.get("/status")
async def get_stream_status(
    guild_id: int,
    http_request: Request,
    current_user: TokenData = Depends(require_permission(SLPermissions.STREAM_STATUS.value))
) -> JSONResponse:
    """
    Get current stream status.
    
    Equivalent to Discord /song command.
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
        
        # Get stream status using adapter
        status = await stream_adapter.get_stream_status(guild_id=guild_id)
        
        # Get current volume using adapter
        volume_info = await audio_adapter.get_volume(guild_id=guild_id)
        current_volume = volume_info.get("volume", 0.8)
        
        return JSONResponse(
            content=formatter.format_stream_status(
                is_playing=status.get("is_playing", False),
                stream_url=status.get("stream_url"),
                station_name=status.get("station_name"),
                current_song=status.get("current_song"),
                volume=current_volume,
                guild_id=guild_id
            )
        )
    
    except Exception as e:
        logger.error(f"Error getting stream status: {e}")
        formatter = ResponseFormatter()
        return JSONResponse(
            status_code=500,
            content=formatter.format_error("INTERNAL_ERROR", "Failed to get stream status")
        )


@router.post("/refresh")
async def refresh_stream(
    request: StreamControlRequest,
    http_request: Request,
    current_user: TokenData = Depends(require_permission(SLPermissions.STREAM_CONTROL.value))
) -> JSONResponse:
    """
    Refresh the current stream connection.
    
    Equivalent to Discord /refresh command.
    """
    try:
        # Get services from app state
        service_registry: ServiceRegistry = http_request.app.state.service_registry
        stream_adapter = StreamAdapter(service_registry)
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
        
        # Refresh the stream using adapter
        result = await stream_adapter.refresh_stream(guild_id=request.guild_id)
        
        if result.get("success", False):
            # Broadcast event to WebSocket clients
            server = http_request.app.state.get('sl_bridge_server')
            if server:
                await server.broadcast_event("stream_refreshed", {
                    "guild_id": request.guild_id,
                    "user": getattr(current_user, 'avatar_name', 'SL User')
                }, request.guild_id)
            
            return JSONResponse(
                content=formatter.format_simple_confirmation("Stream refreshed", request.guild_id)
            )
        else:
            return JSONResponse(
                status_code=400,
                content=formatter.format_error(
                    "REFRESH_FAILED",
                    result.get("message", "Failed to refresh stream")
                )
            )
    
    except Exception as e:
        logger.error(f"Error refreshing stream: {e}")
        formatter = ResponseFormatter()
        return JSONResponse(
            status_code=500,
            content=formatter.format_error("INTERNAL_ERROR", "Failed to refresh stream")
        )


@router.get("/history")
async def get_stream_history(
    guild_id: int,
    http_request: Request,
    limit: int = 10,
    current_user: TokenData = Depends(require_permission(SLPermissions.STREAM_STATUS.value))
) -> JSONResponse:
    """
    Get recent stream history for the guild.
    """
    try:
        # Get services from app state
        service_registry: ServiceRegistry = http_request.app.state.service_registry
        stream_adapter = StreamAdapter(service_registry)
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
        
        # Get stream history using adapter
        history = await stream_adapter.get_stream_history(
            guild_id=guild_id, 
            limit=min(limit, 20)  # Limit to 20 for SL
        )
        
        # Format for SL consumption
        sl_history = []
        for item in history[:10]:  # Further limit for response size
            sl_item = {
                "url": formatter._truncate_string(item.get("url", ""), 80),
                "name": formatter._truncate_string(item.get("action", ""), 40),
                "time": item.get("timestamp", "")[:19]  # Truncate timestamp
            }
            sl_history.append(sl_item)
        
        return JSONResponse(
            content=formatter.format_success(
                f"Found {len(sl_history)} recent streams",
                {
                    "history": sl_history,
                    "guild_id": guild_id
                }
            )
        )
    
    except Exception as e:
        logger.error(f"Error getting stream history: {e}")
        formatter = ResponseFormatter()
        return JSONResponse(
            status_code=500,
            content=formatter.format_error("INTERNAL_ERROR", "Failed to get stream history")
        )
