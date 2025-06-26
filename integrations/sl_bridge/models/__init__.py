"""
SL Bridge Data Models

Pydantic models for API request/response handling
"""

from .auth_models import SLToken, TokenData, TokenRequest
from .request_models import (
    StreamPlayRequest, StreamControlRequest, VolumeRequest, 
    EQRequest, FavoriteRequest, FavoritePlayRequest
)
from .response_models import (
    SLResponse, ErrorResponse, StreamStatusResponse, 
    FavoritesListResponse, AudioInfoResponse
)

__all__ = [
    # Authentication models
    "SLToken", "TokenData", "TokenRequest",
    
    # Request models  
    "StreamPlayRequest", "StreamControlRequest", "VolumeRequest",
    "EQRequest", "FavoriteRequest", "FavoritePlayRequest",
    
    # Response models
    "SLResponse", "ErrorResponse", "StreamStatusResponse",
    "FavoritesListResponse", "AudioInfoResponse"
]
