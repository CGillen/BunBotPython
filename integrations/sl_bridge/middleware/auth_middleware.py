"""
Authentication Middleware for SL Bridge

FastAPI middleware and dependencies for JWT authentication
"""

import logging
from typing import Optional, Annotated
from fastapi import HTTPException, Depends, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from core import ServiceRegistry
from ..security.token_manager import TokenManager
from ..security.permissions import PermissionManager
from ..models.auth_models import TokenData
from ..models.response_models import ErrorResponse

logger = logging.getLogger('sl_bridge.middleware.auth')

# HTTP Bearer security scheme
security = HTTPBearer(auto_error=False)


class SLAuthMiddleware(BaseHTTPMiddleware):
    """
    Authentication middleware for SL Bridge.
    
    Handles JWT token validation and user context setup
    for all API requests.
    """
    
    def __init__(self, app, token_manager: TokenManager):
        super().__init__(app)
        self.token_manager = token_manager
        
        # Public endpoints that don't require authentication
        self.public_endpoints = {
            "/docs", "/redoc", "/openapi.json", 
            "/health", "/", "/api/v1/auth/token"
        }
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """Process authentication for each request"""
        try:
            # Skip authentication for public endpoints
            if any(request.url.path.startswith(endpoint) for endpoint in self.public_endpoints):
                return await call_next(request)
            
            # Get authorization header
            auth_header = request.headers.get("Authorization")
            if not auth_header:
                return Response(
                    content='{"error": "Missing Authorization header"}',
                    status_code=401,
                    media_type="application/json"
                )
            
            # Extract token
            try:
                scheme, token = auth_header.split(" ", 1)
                if scheme.lower() != "bearer":
                    raise ValueError("Invalid auth scheme")
            except ValueError:
                return Response(
                    content='{"error": "Invalid Authorization header format"}',
                    status_code=401,
                    media_type="application/json"
                )
            
            # Verify token
            token_data = await self.token_manager.verify_token(token)
            if not token_data:
                return Response(
                    content='{"error": "Invalid or expired token"}',
                    status_code=401,
                    media_type="application/json"
                )
            
            # Add token data to request state
            request.state.token_data = token_data
            request.state.guild_id = token_data.guild_id
            request.state.permissions = token_data.permissions
            
            # Continue with request
            response = await call_next(request)
            return response
            
        except Exception as e:
            logger.error(f"Auth middleware error: {e}")
            return Response(
                content='{"error": "Authentication failed"}',
                status_code=500,
                media_type="application/json"
            )


async def verify_token(credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(security)],
                      request: Request) -> TokenData:
    """
    FastAPI dependency to verify JWT token.
    
    Args:
        credentials: HTTP Bearer credentials
        request: FastAPI request object
        
    Returns:
        Token data if valid
        
    Raises:
        HTTPException: If token is invalid
    """
    try:
        # Check if token data is already in request state (from middleware)
        if hasattr(request.state, 'token_data'):
            return request.state.token_data
        
        # Fallback token verification if middleware didn't handle it
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Get token manager from app state
        token_manager = getattr(request.app.state, 'token_manager', None)
        if not token_manager:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication service unavailable"
            )
        
        # Verify token
        token_data = await token_manager.verify_token(credentials.credentials)
        if not token_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return token_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token verification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token verification failed"
        )


async def get_current_user(token_data: Annotated[TokenData, Depends(verify_token)]) -> TokenData:
    """
    FastAPI dependency to get current authenticated user.
    
    Args:
        token_data: Verified token data
        
    Returns:
        Token data with user information
    """
    return token_data


def require_permission(permission: str):
    """
    Create a dependency that requires a specific permission.
    
    Args:
        permission: Required permission string
        
    Returns:
        FastAPI dependency function
    """
    async def permission_dependency(token_data: Annotated[TokenData, Depends(verify_token)],
                                  request: Request) -> TokenData:
        try:
            # Get permission manager from app state
            permission_manager = getattr(request.app.state, 'permission_manager', None)
            if not permission_manager:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Permission service unavailable"
                )
            
            # Check permission
            if not permission_manager.check_permission(permission, token_data.permissions):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Missing required permission: {permission}"
                )
            
            return token_data
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Permission check error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Permission check failed"
            )
    
    return permission_dependency


def require_permissions(permissions: list[str]):
    """
    Create a dependency that requires multiple permissions.
    
    Args:
        permissions: List of required permission strings
        
    Returns:
        FastAPI dependency function
    """
    async def permissions_dependency(token_data: Annotated[TokenData, Depends(verify_token)],
                                   request: Request) -> TokenData:
        try:
            # Get permission manager from app state
            permission_manager = getattr(request.app.state, 'permission_manager', None)
            if not permission_manager:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Permission service unavailable"
                )
            
            # Check all permissions
            if not permission_manager.check_permissions(permissions, token_data.permissions):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Missing required permissions: {', '.join(permissions)}"
                )
            
            return token_data
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Permissions check error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Permissions check failed"
            )
    
    return permissions_dependency


def require_guild_access(token_data: Annotated[TokenData, Depends(verify_token)],
                        request: Request) -> TokenData:
    """
    Dependency to ensure user has access to the specified guild.
    
    Args:
        token_data: Verified token data
        request: FastAPI request object
        
    Returns:
        Token data if guild access is valid
        
    Raises:
        HTTPException: If guild access is denied
    """
    try:
        # Extract guild_id from request (path parameter, query parameter, or body)
        guild_id = None
        
        # Check path parameters
        if hasattr(request, 'path_params') and 'guild_id' in request.path_params:
            guild_id = int(request.path_params['guild_id'])
        
        # Check query parameters
        elif 'guild_id' in request.query_params:
            guild_id = int(request.query_params['guild_id'])
        
        # If no guild_id in request, use token's guild_id
        if guild_id is None:
            return token_data
        
        # Check if token's guild matches requested guild
        if token_data.guild_id != guild_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied to guild {guild_id}"
            )
        
        return token_data
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid guild_id format"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Guild access check error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Guild access check failed"
        )
