"""
Favorites Management Routes for SL Bridge

API endpoints for managing favorite radio stations
"""

import logging
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from core import ServiceRegistry
from services.favorites_service import FavoritesService
from ..middleware.auth_middleware import get_current_user, require_permission
from ..models.auth_models import TokenData
from ..models.request_models import FavoriteRequest, FavoritePlayRequest, FavoriteDeleteRequest
from ..ui.response_formatter import ResponseFormatter
from ..security.permissions import SLPermissions

logger = logging.getLogger('sl_bridge.routes.favorites')

router = APIRouter()


@router.get("/list")
async def list_favorites(
    guild_id: int,
    http_request: Request,
    current_user: TokenData = Depends(require_permission(SLPermissions.FAVORITES_READ.value))
) -> JSONResponse:
    """
    Get list of favorite stations.
    
    Equivalent to Discord /favorites command.
    """
    try:
        # Get services from app state
        service_registry: ServiceRegistry = http_request.app.state.service_registry
        favorites_service = service_registry.get(FavoritesService)
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
        
        # Get favorites from service
        favorites = favorites_service.get_all_favorites(guild_id)
        
        # Format for SL consumption
        sl_favorites = []
        for fav in favorites[:20]:  # Limit to 20 for response size
            sl_fav = {
                "number": fav.get("favorite_number", 0),
                "name": formatter._truncate_string(fav.get("station_name", ""), 30),
                "url": formatter._truncate_string(fav.get("stream_url", ""), 60)
            }
            sl_favorites.append(sl_fav)
        
        return JSONResponse(
            content=formatter.format_success(
                f"Found {len(sl_favorites)} favorites",
                {"favorites": sl_favorites, "guild_id": guild_id}
            )
        )
    
    except Exception as e:
        logger.error(f"Error getting favorites list: {e}")
        formatter = ResponseFormatter()
        return JSONResponse(
            status_code=500,
            content=formatter.format_error("INTERNAL_ERROR", "Failed to get favorites")
        )


@router.post("/add")
async def add_favorite(
    request: FavoriteRequest,
    http_request: Request,
    current_user: TokenData = Depends(require_permission(SLPermissions.FAVORITES_WRITE.value))
) -> JSONResponse:
    """
    Add a new favorite station.
    
    Equivalent to Discord /favorite add command.
    """
    try:
        # Get services from app state
        service_registry: ServiceRegistry = http_request.app.state.service_registry
        favorites_service = service_registry.get(FavoritesService)
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
        
        # Add favorite using service
        result = await favorites_service.add_favorite(
            guild_id=request.guild_id,
            url=request.stream_url,
            name=request.station_name,
            user_id=getattr(current_user, 'user_id', None)
        )
        
        if result.get('success', False):
            # Broadcast event to WebSocket clients
            server = http_request.app.state.get('sl_bridge_server')
            if server:
                await server.broadcast_event("favorite_added", {
                    "guild_id": request.guild_id,
                    "favorite_number": request.favorite_number,
                    "station_name": request.station_name,
                    "user": getattr(current_user, 'avatar_name', 'SL User')
                }, request.guild_id)
            
            return JSONResponse(
                content=formatter.format_simple_confirmation(
                    f"Added favorite #{request.favorite_number}: {request.station_name}",
                    request.guild_id
                )
            )
        else:
            return JSONResponse(
                status_code=400,
                content=formatter.format_error(
                    "FAVORITE_ADD_FAILED",
                    f"Failed to add favorite #{request.favorite_number}"
                )
            )
    
    except Exception as e:
        logger.error(f"Error adding favorite: {e}")
        formatter = ResponseFormatter()
        return JSONResponse(
            status_code=500,
            content=formatter.format_error("INTERNAL_ERROR", "Failed to add favorite")
        )


@router.post("/play")
async def play_favorite(
    request: FavoritePlayRequest,
    http_request: Request,
    current_user: TokenData = Depends(require_permission(SLPermissions.STREAM_CONTROL.value))
) -> JSONResponse:
    """
    Play a favorite station by number.
    
    Equivalent to Discord /play favorite command.
    """
    try:
        # Get services from app state
        service_registry: ServiceRegistry = http_request.app.state.service_registry
        favorites_service = service_registry.get(FavoritesService)
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
        
        # Get favorite details
        favorite = favorites_service.get_favorite_by_number(
            guild_id=request.guild_id,
            number=request.favorite_number
        )
        
        if not favorite:
            return JSONResponse(
                status_code=404,
                content=formatter.format_error(
                    "FAVORITE_NOT_FOUND",
                    f"Favorite #{request.favorite_number} not found"
                )
            )
        
        # Use stream adapter to play the favorite
        from ..adapters import StreamAdapter
        stream_adapter = StreamAdapter(service_registry)
        
        result = await stream_adapter.play_stream(
            url=favorite["stream_url"],
            guild_id=request.guild_id
        )
        
        if result.get("success", False):
            # Broadcast event to WebSocket clients
            server = http_request.app.state.get('sl_bridge_server')
            if server:
                await server.broadcast_event("favorite_played", {
                    "guild_id": request.guild_id,
                    "favorite_number": request.favorite_number,
                    "station_name": favorite["station_name"],
                    "user": getattr(current_user, 'avatar_name', 'SL User')
                }, request.guild_id)
            
            return JSONResponse(
                content=formatter.format_simple_confirmation(
                    f"Playing favorite #{request.favorite_number}: {favorite['station_name']}",
                    request.guild_id
                )
            )
        else:
            return JSONResponse(
                status_code=400,
                content=formatter.format_error(
                    "FAVORITE_PLAY_FAILED",
                    result.get("message", "Failed to play favorite")
                )
            )
    
    except Exception as e:
        logger.error(f"Error playing favorite: {e}")
        formatter = ResponseFormatter()
        return JSONResponse(
            status_code=500,
            content=formatter.format_error("INTERNAL_ERROR", "Failed to play favorite")
        )


@router.delete("/remove")
async def remove_favorite(
    request: FavoriteDeleteRequest,
    http_request: Request,
    current_user: TokenData = Depends(require_permission(SLPermissions.FAVORITES_DELETE.value))
) -> JSONResponse:
    """
    Remove a favorite station.
    
    Equivalent to Discord /favorite remove command.
    """
    try:
        # Get services from app state
        service_registry: ServiceRegistry = http_request.app.state.service_registry
        favorites_service = service_registry.get(FavoritesService)
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
        
        # Remove favorite using service
        result = await favorites_service.remove_favorite(
            guild_id=request.guild_id,
            number=request.favorite_number
        )
        
        if result.get('success', False):
            # Broadcast event to WebSocket clients
            server = http_request.app.state.get('sl_bridge_server')
            if server:
                await server.broadcast_event("favorite_removed", {
                    "guild_id": request.guild_id,
                    "favorite_number": request.favorite_number,
                    "user": getattr(current_user, 'avatar_name', 'SL User')
                }, request.guild_id)
            
            return JSONResponse(
                content=formatter.format_simple_confirmation(
                    f"Removed favorite #{request.favorite_number}",
                    request.guild_id
                )
            )
        else:
            return JSONResponse(
                status_code=404,
                content=formatter.format_error(
                    "FAVORITE_NOT_FOUND",
                    f"Favorite #{request.favorite_number} not found"
                )
            )
    
    except Exception as e:
        logger.error(f"Error removing favorite: {e}")
        formatter = ResponseFormatter()
        return JSONResponse(
            status_code=500,
            content=formatter.format_error("INTERNAL_ERROR", "Failed to remove favorite")
        )


@router.get("/get/{favorite_number}")
async def get_favorite(
    favorite_number: int,
    guild_id: int,
    http_request: Request,
    current_user: TokenData = Depends(require_permission(SLPermissions.FAVORITES_READ.value))
) -> JSONResponse:
    """
    Get details of a specific favorite.
    """
    try:
        # Get services from app state
        service_registry: ServiceRegistry = http_request.app.state.service_registry
        favorites_service = service_registry.get(FavoritesService)
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
        
        # Get favorite details
        favorite = favorites_service.get_favorite_by_number(
            guild_id=guild_id,
            number=favorite_number
        )
        
        if not favorite:
            return JSONResponse(
                status_code=404,
                content=formatter.format_error(
                    "FAVORITE_NOT_FOUND",
                    f"Favorite #{favorite_number} not found"
                )
            )
        
        # Format for SL response
        sl_favorite = {
            "number": favorite.get("favorite_number", favorite_number),
            "name": formatter._truncate_string(favorite.get("station_name", ""), 40),
            "url": formatter._truncate_string(favorite.get("stream_url", ""), 80),
            "category": favorite.get("category", ""),
            "guild_id": guild_id
        }
        
        return JSONResponse(
            content=formatter.format_success(
                f"Favorite #{favorite_number}: {favorite['station_name']}",
                sl_favorite
            )
        )
    
    except Exception as e:
        logger.error(f"Error getting favorite: {e}")
        formatter = ResponseFormatter()
        return JSONResponse(
            status_code=500,
            content=formatter.format_error("INTERNAL_ERROR", "Failed to get favorite")
        )
