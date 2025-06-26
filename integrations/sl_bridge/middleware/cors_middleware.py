"""
CORS Middleware for SL Bridge

Configures Cross-Origin Resource Sharing for Second Life integration
"""

import logging
from typing import Dict, Any, List
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger('sl_bridge.middleware.cors')


def setup_cors(app: FastAPI, config: Dict[str, Any] | None = None) -> None:
    """
    Configure CORS middleware for SL Bridge.
    
    Args:
        app: FastAPI application instance
        config: Optional CORS configuration
    """
    try:
        # Default CORS configuration for SL Bridge
        default_config = {
            "allow_origins": ["*"],  # In production, specify actual SL viewer origins
            "allow_credentials": True,
            "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": [
                "Authorization",
                "Content-Type",
                "X-Guild-ID",
                "X-SL-Object-Key",
                "X-SL-Avatar-Key",
                "X-Request-ID"
            ],
            "expose_headers": [
                "X-Rate-Limit-Remaining",
                "X-Rate-Limit-Reset",
                "X-Response-Time"
            ]
        }
        
        # Merge with provided config
        if config:
            default_config.update(config)
        
        # Add CORS middleware
        app.add_middleware(
            CORSMiddleware,
            **default_config
        )
        
        logger.info("CORS middleware configured for SL Bridge")
        
    except Exception as e:
        logger.error(f"Error configuring CORS middleware: {e}")
        raise


def get_cors_config_for_sl() -> Dict[str, Any]:
    """
    Get CORS configuration optimized for Second Life integration.
    
    Returns:
        CORS configuration dictionary
    """
    return {
        "allow_origins": [
            "*"  # Second Life doesn't have a fixed origin
        ],
        "allow_credentials": True,
        "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"],
        "allow_headers": [
            "Authorization",
            "Content-Type", 
            "Accept",
            "X-Guild-ID",
            "X-SL-Object-Key",
            "X-SL-Avatar-Key",
            "X-SL-Avatar-Name",
            "X-Request-ID",
            "X-Client-Version",
            "User-Agent"
        ],
        "expose_headers": [
            "X-Rate-Limit-Remaining",
            "X-Rate-Limit-Reset", 
            "X-Response-Time",
            "X-API-Version",
            "X-Guild-Status"
        ],
        "max_age": 86400  # Cache preflight requests for 24 hours
    }


def validate_sl_origin(origin: str) -> bool:
    """
    Validate if origin is from a legitimate Second Life source.
    
    Args:
        origin: Origin header value
        
    Returns:
        True if origin is valid for SL
    """
    try:
        # Second Life HTTP requests may not have a traditional origin
        # or may have various client-generated origins
        if not origin:
            return True  # Allow requests without origin (common for SL)
        
        # Allow localhost for testing
        if "localhost" in origin or "127.0.0.1" in origin:
            return True
        
        # Allow null origin (common for direct HTTP requests)
        if origin.lower() == "null":
            return True
            
        # In production, you might want to validate against
        # known SL viewer signatures or object keys
        
        return True  # For now, allow all origins
        
    except Exception as e:
        logger.warning(f"Error validating SL origin {origin}: {e}")
        return False


class SLCorsHandler:
    """
    Advanced CORS handler with SL-specific features.
    """
    
    def __init__(self, strict_mode: bool = False):
        self.strict_mode = strict_mode
        self.allowed_object_keys: List[str] = []
        
    def add_allowed_object_key(self, object_key: str) -> None:
        """Add an allowed SL object key for CORS validation"""
        if object_key not in self.allowed_object_keys:
            self.allowed_object_keys.append(object_key)
    
    def remove_allowed_object_key(self, object_key: str) -> None:
        """Remove an allowed SL object key"""
        if object_key in self.allowed_object_keys:
            self.allowed_object_keys.remove(object_key)
    
    def validate_request(self, headers: Dict[str, str]) -> bool:
        """
        Validate SL request based on headers.
        
        Args:
            headers: Request headers
            
        Returns:
            True if request is valid
        """
        try:
            if not self.strict_mode:
                return True
            
            # Check for SL object key if in strict mode
            object_key = headers.get("X-SL-Object-Key")
            if object_key and object_key in self.allowed_object_keys:
                return True
                
            # Check for SL avatar key
            avatar_key = headers.get("X-SL-Avatar-Key")
            if avatar_key:
                # Could validate against known avatar keys
                return True
            
            return not self.strict_mode
            
        except Exception as e:
            logger.warning(f"Error validating SL request: {e}")
            return not self.strict_mode
