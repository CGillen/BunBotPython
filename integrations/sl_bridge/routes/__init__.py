"""
API Routes for SL Bridge

FastAPI route modules for Second Life integration endpoints
"""

from . import audio_routes, favorites_routes, stream_routes, status_routes, settings_routes

__all__ = [
    "audio_routes",
    "favorites_routes", 
    "stream_routes",
    "status_routes",
    "settings_routes"
]
