"""
JWT Token Manager for SL Bridge

Handles JWT token generation, validation, and refresh
Based on testdrivenio/fastapi-jwt patterns but adapted for BunBot
"""

import os
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any
from jose import JWTError, jwt
from passlib.context import CryptContext

from core import ServiceRegistry, ConfigurationManager
from ..models.auth_models import TokenData, SLToken, TokenRequest

logger = logging.getLogger('sl_bridge.security.token_manager')


class TokenManager:
    """
    JWT token management for SL Bridge authentication.
    
    Provides secure token generation, validation, and refresh
    with integration to BunBot's service architecture.
    """
    
    def __init__(self, service_registry: ServiceRegistry):
        self.service_registry = service_registry
        self.config_manager = service_registry.get(ConfigurationManager)
        
        # JWT configuration
        self.secret_key = os.getenv('SL_BRIDGE_SECRET_KEY', self._generate_secret_key())
        self.algorithm = "HS256"
        self.access_token_expire_minutes = int(os.getenv('SL_ACCESS_TOKEN_EXPIRE_MINUTES', '60'))
        self.refresh_token_expire_days = int(os.getenv('SL_REFRESH_TOKEN_EXPIRE_DAYS', '7'))
        
        # Password context for API key hashing
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        
        # In-memory store for revoked tokens (in production, use Redis)
        self._revoked_tokens: set = set()
        
        # Valid API keys (in production, store in database)
        self._api_keys: Dict[str, Dict[str, Any]] = self._load_api_keys()
        
        logger.info("TokenManager initialized")
    
    def _generate_secret_key(self) -> str:
        """Generate a secure secret key if none provided"""
        import secrets
        key = secrets.token_urlsafe(32)
        logger.warning("Generated new JWT secret key. Store SL_BRIDGE_SECRET_KEY in environment for production!")
        return key
    
    def _load_api_keys(self) -> Dict[str, Dict[str, Any]]:
        """
        Load API keys from configuration.
        In production, this would come from a database.
        """
        # Default API keys for development
        default_keys = {
            "dev_key_123": {
                "name": "Development Key",
                "permissions": ["stream_control", "favorites_read", "favorites_write", "audio_control"],
                "guild_ids": [],  # Empty list means all guilds
                "created_at": datetime.now(timezone.utc),
                "last_used": None
            }
        }
        
        # Try to load from environment or config
        custom_keys = os.getenv('SL_API_KEYS')
        if custom_keys:
            try:
                custom_keys_dict = json.loads(custom_keys)
                default_keys.update(custom_keys_dict)
            except json.JSONDecodeError:
                logger.warning("Invalid SL_API_KEYS format, using defaults")
        
        return default_keys
    
    async def verify_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """
        Verify API key and return key information.
        
        Args:
            api_key: API key to verify
            
        Returns:
            API key information if valid, None otherwise
        """
        try:
            key_info = self._api_keys.get(api_key)
            if key_info:
                # Update last used timestamp
                key_info["last_used"] = datetime.now(timezone.utc)
                logger.debug(f"Valid API key used: {key_info['name']}")
                return key_info
            
            logger.warning(f"Invalid API key attempted: {api_key[:8]}...")
            return None
            
        except Exception as e:
            logger.error(f"Error verifying API key: {e}")
            return None
    
    async def create_access_token(self, token_request: TokenRequest) -> Optional[SLToken]:
        """
        Create JWT access token.
        
        Args:
            token_request: Token creation request
            
        Returns:
            SL Token if successful, None otherwise
        """
        try:
            # Verify API key first
            key_info = await self.verify_api_key(token_request.api_key)
            if not key_info:
                return None
            
            # Check guild permissions
            if key_info["guild_ids"] and token_request.guild_id not in key_info["guild_ids"]:
                logger.warning(f"API key does not have access to guild {token_request.guild_id}")
                return None
            
            # Validate requested permissions
            available_permissions = key_info["permissions"]
            requested_permissions = token_request.permissions or []
            
            granted_permissions = [
                perm for perm in requested_permissions 
                if perm in available_permissions
            ]
            
            if not granted_permissions:
                granted_permissions = ["stream_control", "favorites_read"]  # Default minimal permissions
            
            # Create token data
            now = datetime.now(timezone.utc)
            expires_at = now + timedelta(minutes=self.access_token_expire_minutes)
            
            token_data = TokenData(
                guild_id=token_request.guild_id,
                permissions=granted_permissions,
                avatar_name=token_request.avatar_name,
                avatar_key=token_request.avatar_key,
                issued_at=now,
                expires_at=expires_at
            )
            
            # Create JWT payload
            payload = {
                "sub": str(token_request.guild_id),
                "guild_id": token_request.guild_id,
                "permissions": granted_permissions,
                "avatar_name": token_request.avatar_name,
                "avatar_key": token_request.avatar_key,
                "iat": int(now.timestamp()),
                "exp": int(expires_at.timestamp()),
                "type": "access_token"
            }
            
            # Generate JWT
            access_token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
            
            # Create response
            sl_token = SLToken(
                access_token=access_token,
                expires_in=self.access_token_expire_minutes * 60,
                permissions=granted_permissions,
                guild_id=token_request.guild_id
            )
            
            logger.info(f"Created access token for guild {token_request.guild_id} with permissions: {granted_permissions}")
            return sl_token
            
        except Exception as e:
            logger.error(f"Error creating access token: {e}")
            return None
    
    async def verify_token(self, token: str) -> Optional[TokenData]:
        """
        Verify and decode JWT token.
        
        Args:
            token: JWT token to verify
            
        Returns:
            Token data if valid, None otherwise
        """
        try:
            # Check if token is revoked
            if token in self._revoked_tokens:
                logger.warning("Attempted to use revoked token")
                return None
            
            # Decode JWT
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            # Validate token type
            if payload.get("type") != "access_token":
                logger.warning("Invalid token type")
                return None
            
            # Extract token data
            token_data = TokenData(
                guild_id=payload["guild_id"],
                permissions=payload.get("permissions", []),
                avatar_name=payload.get("avatar_name"),
                avatar_key=payload.get("avatar_key"),
                issued_at=datetime.fromtimestamp(payload["iat"], tz=timezone.utc),
                expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
            )
            
            # Check expiration
            if token_data.expires_at < datetime.now(timezone.utc):
                logger.warning("Token has expired")
                return None
            
            return token_data
            
        except JWTError as e:
            logger.warning(f"JWT verification failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Error verifying token: {e}")
            return None
    
    async def revoke_token(self, token: str) -> bool:
        """
        Revoke a JWT token.
        
        Args:
            token: JWT token to revoke
            
        Returns:
            True if revoked successfully
        """
        try:
            # Verify token first to ensure it's valid
            token_data = await self.verify_token(token)
            if token_data:
                self._revoked_tokens.add(token)
                logger.info(f"Revoked token for guild {token_data.guild_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error revoking token: {e}")
            return False
    
    async def refresh_token(self, refresh_token: str) -> Optional[SLToken]:
        """
        Refresh an access token using a refresh token.
        
        Args:
            refresh_token: Refresh token
            
        Returns:
            New SL Token if successful
        """
        try:
            # Decode refresh token
            payload = jwt.decode(refresh_token, self.secret_key, algorithms=[self.algorithm])
            
            # Validate token type
            if payload.get("type") != "refresh_token":
                logger.warning("Invalid refresh token type")
                return None
            
            # Create new access token
            guild_id = payload["guild_id"]
            permissions = payload.get("permissions", [])
            
            # Create token request for new token
            token_request = TokenRequest(
                guild_id=guild_id,
                api_key="refresh",  # Special marker for refresh
                permissions=permissions,
                avatar_name=payload.get("avatar_name"),
                avatar_key=payload.get("avatar_key")
            )
            
            # Generate new access token (skip API key verification for refresh)
            now = datetime.now(timezone.utc)
            expires_at = now + timedelta(minutes=self.access_token_expire_minutes)
            
            payload = {
                "sub": str(guild_id),
                "guild_id": guild_id,
                "permissions": permissions,
                "avatar_name": token_request.avatar_name,
                "avatar_key": token_request.avatar_key,
                "iat": int(now.timestamp()),
                "exp": int(expires_at.timestamp()),
                "type": "access_token"
            }
            
            access_token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
            
            sl_token = SLToken(
                access_token=access_token,
                expires_in=self.access_token_expire_minutes * 60,
                permissions=permissions,
                guild_id=guild_id
            )
            
            logger.info(f"Refreshed access token for guild {guild_id}")
            return sl_token
            
        except JWTError as e:
            logger.warning(f"Refresh token verification failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Error refreshing token: {e}")
            return None
    
    def get_token_info(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Get token information without full verification.
        
        Args:
            token: JWT token
            
        Returns:
            Token information if decodable
        """
        try:
            # Decode without verification to get info
            unverified_payload = jwt.get_unverified_claims(token)
            
            return {
                "guild_id": unverified_payload.get("guild_id"),
                "permissions": unverified_payload.get("permissions", []),
                "issued_at": datetime.fromtimestamp(unverified_payload["iat"], tz=timezone.utc),
                "expires_at": datetime.fromtimestamp(unverified_payload["exp"], tz=timezone.utc),
                "avatar_name": unverified_payload.get("avatar_name"),
                "is_revoked": token in self._revoked_tokens
            }
            
        except Exception as e:
            logger.error(f"Error getting token info: {e}")
            return None
    
    def cleanup_revoked_tokens(self) -> None:
        """Clean up expired revoked tokens to prevent memory leaks"""
        try:
            # In a real implementation, this would clean up expired tokens
            # from the revoked tokens store
            logger.debug("Token cleanup completed")
        except Exception as e:
            logger.error(f"Error during token cleanup: {e}")
