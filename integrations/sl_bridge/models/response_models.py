"""
API Response Models for SL Bridge

Pydantic models for all API response payloads
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field


class SLResponse(BaseModel):
    """Standard response wrapper for all SL Bridge API responses"""
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Human-readable status message")
    data: Optional[Dict[str, Any]] = Field(None, description="Response data")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Operation completed successfully",
                "data": {"result": "example"},
                "timestamp": "2024-12-20T17:30:00Z"
            }
        }


class ErrorResponse(BaseModel):
    """Error response model"""
    success: bool = Field(False, description="Always false for errors")
    error_code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        json_schema_extra = {
            "example": {
                "success": False,
                "error_code": "INVALID_REQUEST",
                "message": "The provided URL is invalid",
                "details": {"field": "url", "value": "invalid-url"},
                "timestamp": "2024-12-20T17:30:00Z"
            }
        }


class StreamStatusResponse(BaseModel):
    """Response for stream status requests"""
    is_playing: bool = Field(..., description="Whether a stream is currently playing")
    stream_url: Optional[str] = Field(None, description="Current stream URL")
    station_name: Optional[str] = Field(None, description="Current station name")
    current_song: Optional[str] = Field(None, description="Currently playing song")
    duration: Optional[int] = Field(None, description="Stream duration in seconds")
    volume: Optional[float] = Field(None, description="Current volume (0.0-1.0)")
    guild_id: int = Field(..., description="Discord guild ID")
    voice_channel_id: Optional[int] = Field(None, description="Current voice channel ID")
    connected_users: Optional[int] = Field(None, description="Number of users in voice channel")
    
    class Config:
        json_schema_extra = {
            "example": {
                "is_playing": True,
                "stream_url": "http://ice1.somafm.com/groovesalad-256-mp3",
                "station_name": "SomaFM Groove Salad",
                "current_song": "Artist - Song Title",
                "duration": 1235,
                "volume": 0.8,
                "guild_id": 123456789012345678,
                "voice_channel_id": 987654321098765432,
                "connected_users": 3
            }
        }


class FavoriteItem(BaseModel):
    """Individual favorite item"""
    favorite_number: int = Field(..., description="Favorite slot number")
    station_name: str = Field(..., description="Station display name")
    stream_url: str = Field(..., description="Stream URL")
    category: Optional[str] = Field(None, description="Category")
    created_at: Optional[datetime] = Field(None, description="When favorite was created")
    last_played: Optional[datetime] = Field(None, description="When favorite was last played")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class FavoritesListResponse(BaseModel):
    """Response for favorites list requests"""
    favorites: List[FavoriteItem] = Field(..., description="List of favorite stations")
    total_count: int = Field(..., description="Total number of favorites")
    guild_id: int = Field(..., description="Discord guild ID")
    page: Optional[int] = Field(None, description="Current page (if paginated)")
    per_page: Optional[int] = Field(None, description="Items per page (if paginated)")
    total_pages: Optional[int] = Field(None, description="Total pages (if paginated)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "favorites": [
                    {
                        "favorite_number": 1,
                        "station_name": "SomaFM Groove Salad",
                        "stream_url": "http://ice1.somafm.com/groovesalad-256-mp3",
                        "category": "Ambient",
                        "created_at": "2024-12-01T10:00:00Z",
                        "last_played": "2024-12-20T16:30:00Z"
                    }
                ],
                "total_count": 5,
                "guild_id": 123456789012345678,
                "page": 1,
                "per_page": 10,
                "total_pages": 1
            }
        }


class AudioConfig(BaseModel):
    """Audio configuration data"""
    master_volume: float = Field(..., description="Master volume (0.0-1.0)")
    eq_bass: float = Field(..., description="Bass EQ (-12.0 to 12.0 dB)")
    eq_mid: float = Field(..., description="Mid EQ (-12.0 to 12.0 dB)")
    eq_treble: float = Field(..., description="Treble EQ (-12.0 to 12.0 dB)")
    eq_enabled: bool = Field(..., description="Whether EQ is enabled")
    normalization_enabled: bool = Field(..., description="Whether normalization is enabled")
    auto_gain_control: bool = Field(..., description="Whether AGC is enabled")
    dynamic_range_compression: float = Field(..., description="Compression ratio (0.0-1.0)")
    sample_rate: int = Field(..., description="Audio sample rate")
    channels: int = Field(..., description="Number of audio channels")
    bit_depth: int = Field(..., description="Audio bit depth")
    quality: str = Field(..., description="Audio quality setting")


class AudioInfoResponse(BaseModel):
    """Response for audio info requests"""
    config: AudioConfig = Field(..., description="Current audio configuration")
    metrics: Optional[Dict[str, Any]] = Field(None, description="Audio processing metrics")
    guild_id: int = Field(..., description="Discord guild ID")
    
    class Config:
        json_schema_extra = {
            "example": {
                "config": {
                    "master_volume": 0.8,
                    "eq_bass": 2.0,
                    "eq_mid": 0.0,
                    "eq_treble": 1.5,
                    "eq_enabled": True,
                    "normalization_enabled": True,
                    "auto_gain_control": True,
                    "dynamic_range_compression": 0.3,
                    "sample_rate": 48000,
                    "channels": 2,
                    "bit_depth": 16,
                    "quality": "medium"
                },
                "metrics": {
                    "processing_latency_ms": 15.2,
                    "cpu_usage_percent": 12.5,
                    "quality_score": 0.85
                },
                "guild_id": 123456789012345678
            }
        }


class WebSocketMessage(BaseModel):
    """WebSocket message format"""
    type: str = Field(..., description="Message type")
    event_type: Optional[str] = Field(None, description="Event type for event messages")
    data: Dict[str, Any] = Field(..., description="Message data")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    guild_id: Optional[int] = Field(None, description="Guild ID for guild-specific events")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ServerInfoResponse(BaseModel):
    """Server information response"""
    status: str = Field(..., description="Server status")
    version: str = Field(..., description="Server version")
    uptime_seconds: float = Field(..., description="Server uptime in seconds")
    active_connections: int = Field(..., description="Number of active WebSocket connections")
    supported_features: List[str] = Field(..., description="List of supported features")
    api_version: str = Field(default="v1", description="API version")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "running",
                "version": "1.0.0",
                "uptime_seconds": 86400.5,
                "active_connections": 3,
                "supported_features": [
                    "stream_control", "favorites_management", 
                    "audio_processing", "websocket_events"
                ],
                "api_version": "v1"
            }
        }


class HealthCheckResponse(BaseModel):
    """Health check response"""
    status: str = Field(..., description="Health status")
    checks: Dict[str, Dict[str, Any]] = Field(..., description="Individual health checks")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "checks": {
                    "database": {"status": "healthy", "response_time_ms": 5.2},
                    "discord_bot": {"status": "healthy", "guilds": 150},
                    "audio_processor": {"status": "healthy", "active_streams": 3}
                },
                "timestamp": "2024-12-20T17:30:00Z"
            }
        }
