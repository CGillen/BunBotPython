"""
API Request Models for SL Bridge

Pydantic models for all API request payloads
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator


class StreamPlayRequest(BaseModel):
    """Request to start playing a stream"""
    url: str = Field(..., description="Stream URL to play")
    guild_id: int = Field(..., description="Discord guild ID")
    channel_id: Optional[int] = Field(None, description="Voice channel ID (optional)")
    
    @validator('url')
    def validate_url(cls, v):
        if not v or not v.strip():
            raise ValueError('URL cannot be empty')
        # Basic URL validation
        if not (v.startswith('http://') or v.startswith('https://')):
            raise ValueError('URL must start with http:// or https://')
        return v.strip()


class StreamControlRequest(BaseModel):
    """Request for stream control actions"""
    action: str = Field(..., description="Control action: stop, pause, resume")
    guild_id: int = Field(..., description="Discord guild ID")
    
    @validator('action')
    def validate_action(cls, v):
        allowed_actions = ['stop', 'pause', 'resume', 'refresh']
        if v.lower() not in allowed_actions:
            raise ValueError(f'Action must be one of: {allowed_actions}')
        return v.lower()


class VolumeRequest(BaseModel):
    """Request to set volume"""
    volume: float = Field(..., description="Volume level (0.0 to 1.0)")
    guild_id: int = Field(..., description="Discord guild ID")
    
    @validator('volume')
    def validate_volume(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError('Volume must be between 0.0 and 1.0')
        return v


class EQRequest(BaseModel):
    """Request to set equalizer settings"""
    bass: Optional[float] = Field(None, description="Bass adjustment (-12.0 to 12.0 dB)")
    mid: Optional[float] = Field(None, description="Mid adjustment (-12.0 to 12.0 dB)")
    treble: Optional[float] = Field(None, description="Treble adjustment (-12.0 to 12.0 dB)")
    preset: Optional[str] = Field(None, description="EQ preset name")
    guild_id: int = Field(..., description="Discord guild ID")
    
    @validator('bass', 'mid', 'treble')
    def validate_eq_values(cls, v):
        if v is not None and not -12.0 <= v <= 12.0:
            raise ValueError('EQ values must be between -12.0 and 12.0 dB')
        return v
    
    @validator('preset')
    def validate_preset(cls, v):
        if v is not None:
            allowed_presets = [
                'flat', 'rock', 'pop', 'jazz', 'classical', 
                'electronic', 'bass_boost', 'treble_boost', 'vocal'
            ]
            if v.lower() not in allowed_presets:
                raise ValueError(f'Preset must be one of: {allowed_presets}')
            return v.lower()
        return v


class FavoriteRequest(BaseModel):
    """Request to add/update a favorite"""
    favorite_number: int = Field(..., description="Favorite slot number (1-99)")
    station_name: str = Field(..., description="Station display name")
    stream_url: str = Field(..., description="Stream URL")
    guild_id: int = Field(..., description="Discord guild ID")
    category: Optional[str] = Field(None, description="Optional category")
    
    @validator('favorite_number')
    def validate_favorite_number(cls, v):
        if not 1 <= v <= 99:
            raise ValueError('Favorite number must be between 1 and 99')
        return v
    
    @validator('station_name')
    def validate_station_name(cls, v):
        if not v or not v.strip():
            raise ValueError('Station name cannot be empty')
        return v.strip()
    
    @validator('stream_url')
    def validate_stream_url(cls, v):
        if not v or not v.strip():
            raise ValueError('Stream URL cannot be empty')
        if not (v.startswith('http://') or v.startswith('https://')):
            raise ValueError('Stream URL must start with http:// or https://')
        return v.strip()


class FavoritePlayRequest(BaseModel):
    """Request to play a favorite by number"""
    favorite_number: int = Field(..., description="Favorite slot number to play")
    guild_id: int = Field(..., description="Discord guild ID")
    
    @validator('favorite_number')
    def validate_favorite_number(cls, v):
        if not 1 <= v <= 99:
            raise ValueError('Favorite number must be between 1 and 99')
        return v


class FavoriteDeleteRequest(BaseModel):
    """Request to delete a favorite"""
    favorite_number: int = Field(..., description="Favorite slot number to delete")
    guild_id: int = Field(..., description="Discord guild ID")
    
    @validator('favorite_number')
    def validate_favorite_number(cls, v):
        if not 1 <= v <= 99:
            raise ValueError('Favorite number must be between 1 and 99')
        return v


class AudioInfoRequest(BaseModel):
    """Request for audio configuration info"""
    guild_id: int = Field(..., description="Discord guild ID")


class StatusRequest(BaseModel):
    """Request for current status"""
    guild_id: int = Field(..., description="Discord guild ID")
    include_metadata: bool = Field(default=True, description="Include stream metadata")
    include_audio_config: bool = Field(default=False, description="Include audio configuration")


class WebSocketSubscribeRequest(BaseModel):
    """Request to subscribe to WebSocket events"""
    events: List[str] = Field(..., description="List of events to subscribe to")
    guild_id: Optional[int] = Field(None, description="Guild ID for guild-specific events")
    
    @validator('events')
    def validate_events(cls, v):
        allowed_events = [
            'stream_started', 'stream_stopped', 'stream_changed',
            'volume_changed', 'eq_changed', 'favorite_added', 
            'favorite_removed', 'audio_config_changed'
        ]
        for event in v:
            if event not in allowed_events:
                raise ValueError(f'Event "{event}" not allowed. Must be one of: {allowed_events}')
        return v
