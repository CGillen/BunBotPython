"""
Authentication Models for SL Bridge

JWT token and authentication related data structures
"""

from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field


class TokenRequest(BaseModel):
    """Request for JWT token generation"""
    guild_id: int = Field(..., description="Discord guild ID")
    api_key: str = Field(..., description="API key for authentication")
    permissions: Optional[List[str]] = Field(
        default=["stream_control", "favorites_read"], 
        description="Requested permissions"
    )
    avatar_name: Optional[str] = Field(None, description="Second Life avatar name")
    avatar_key: Optional[str] = Field(None, description="Second Life avatar UUID")


class TokenData(BaseModel):
    """JWT token payload data"""
    guild_id: int
    permissions: List[str]
    avatar_name: Optional[str] = None
    avatar_key: Optional[str] = None
    issued_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class SLToken(BaseModel):
    """JWT token response"""
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")
    permissions: List[str] = Field(..., description="Granted permissions")
    guild_id: int = Field(..., description="Associated Discord guild ID")
    
    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                "token_type": "bearer",
                "expires_in": 3600,
                "permissions": ["stream_control", "favorites_read"],
                "guild_id": 123456789012345678
            }
        }


class TokenRefreshRequest(BaseModel):
    """Request for token refresh"""
    refresh_token: str = Field(..., description="Refresh token")


class PermissionRequest(BaseModel):
    """Request for permission verification"""
    required_permissions: List[str] = Field(..., description="Required permissions")
    guild_id: Optional[int] = Field(None, description="Guild ID for guild-specific permissions")
