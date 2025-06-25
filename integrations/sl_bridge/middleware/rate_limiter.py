"""
Rate Limiting Middleware for FastAPI

Integrates the rate limiter with FastAPI request processing
"""

import logging
from typing import Callable, Dict, Any
from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from core import ServiceRegistry
from ..security.rate_limiter import RateLimiter

logger = logging.getLogger('sl_bridge.middleware.rate_limiter')


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for rate limiting requests.
    
    Integrates with the SL Bridge rate limiter to provide
    automatic rate limiting for all API endpoints.
    """
    
    def __init__(self, app, service_registry: ServiceRegistry):
        super().__init__(app)
        self.rate_limiter = RateLimiter(service_registry)
        
        # Endpoint to rate limiting rule mapping
        self.endpoint_rules = {
            "/api/v1/auth/token": "auth.token_create",
            "/api/v1/streams/play": "stream.play",
            "/api/v1/streams/stop": "stream.stop", 
            "/api/v1/streams/status": "stream.status",
            "/api/v1/favorites": "favorites.read",
            "/api/v1/favorites/add": "favorites.write",
            "/api/v1/audio/volume": "audio.volume",
            "/api/v1/audio/eq": "audio.eq",
            "/api/v1/audio/info": "audio.info",
            "/ws/": "websocket.connect"
        }
        
        # Exempt endpoints from rate limiting
        self.exempt_endpoints = {
            "/health", "/docs", "/redoc", "/openapi.json", "/"
        }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Apply rate limiting to requests"""
        try:
            # Skip rate limiting for exempt endpoints
            if any(request.url.path.startswith(endpoint) for endpoint in self.exempt_endpoints):
                return await call_next(request)
            
            # Determine rate limiting key (IP address or user ID)
            rate_limit_key = self._get_rate_limit_key(request)
            
            # Determine rate limiting rule
            rule_name = self._get_rate_limit_rule(request.url.path)
            
            # Check rate limit
            allowed, metadata = await self.rate_limiter.check_rate_limit(
                key=rate_limit_key,
                rule_name=rule_name
            )
            
            if not allowed:
                # Rate limit exceeded
                retry_after = metadata.get("retry_after", 60)
                
                response = Response(
                    content='{"error": "Rate limit exceeded", "retry_after": ' + str(retry_after) + '}',
                    status_code=429,
                    media_type="application/json"
                )
                
                # Add rate limit headers
                response.headers["X-RateLimit-Limit"] = str(metadata.get("limit", "unknown"))
                response.headers["X-RateLimit-Remaining"] = "0"
                response.headers["X-RateLimit-Reset"] = str(metadata.get("reset_time", 0))
                response.headers["Retry-After"] = str(int(retry_after))
                
                return response
            
            # Process request
            response = await call_next(request)
            
            # Add rate limit headers to successful responses
            if "remaining" in metadata:
                response.headers["X-RateLimit-Limit"] = str(metadata.get("limit", "unknown"))
                response.headers["X-RateLimit-Remaining"] = str(metadata["remaining"])
                response.headers["X-RateLimit-Reset"] = str(metadata.get("reset_time", 0))
            
            return response
            
        except Exception as e:
            logger.error(f"Rate limiting middleware error: {e}")
            # Continue with request on error (fail open)
            return await call_next(request)
    
    def _get_rate_limit_key(self, request: Request) -> str:
        """
        Get rate limiting key for the request.
        
        Uses user ID from token if available, otherwise IP address.
        """
        try:
            # Try to get user from token data
            if hasattr(request.state, 'token_data'):
                token_data = request.state.token_data
                guild_id = getattr(token_data, 'guild_id', None)
                if guild_id:
                    return f"guild_{guild_id}"
            
            # Fall back to IP address
            client_ip = request.client.host if request.client else "unknown"
            
            # Check for forwarded IP headers
            forwarded_for = request.headers.get("X-Forwarded-For")
            if forwarded_for:
                client_ip = forwarded_for.split(",")[0].strip()
            
            real_ip = request.headers.get("X-Real-IP")
            if real_ip:
                client_ip = real_ip
            
            return f"ip_{client_ip}"
            
        except Exception as e:
            logger.error(f"Error getting rate limit key: {e}")
            return "unknown"
    
    def _get_rate_limit_rule(self, path: str) -> str:
        """
        Get rate limiting rule name for the request path.
        
        Args:
            path: Request path
            
        Returns:
            Rate limiting rule name
        """
        try:
            # Check for exact matches first
            if path in self.endpoint_rules:
                return self.endpoint_rules[path]
            
            # Check for prefix matches
            for endpoint_prefix, rule_name in self.endpoint_rules.items():
                if path.startswith(endpoint_prefix):
                    return rule_name
            
            # Default rule
            return "default"
            
        except Exception as e:
            logger.error(f"Error getting rate limit rule for path {path}: {e}")
            return "default"
