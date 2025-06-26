"""
External Integrations for BunBot

Provides comprehensive external service integrations including webhooks,
streaming services, social media, and analytics platforms.

Key Components:
- WebhookManager: Outbound webhook system for external notifications
- APIGateway: Third-party API management and rate limiting
- StreamingServices: Integration with Spotify, Last.fm, and other platforms
- SocialMedia: Auto-posting and announcement distribution
- Analytics: Metrics collection and dashboard integration

Features:
- Rate limiting and retry logic for external APIs
- Secure credential management and token refresh
- Event-driven notifications and updates
- Comprehensive error handling and fallback mechanisms
"""

from .webhook_manager import WebhookManager, WebhookEvent, WebhookDelivery
from .api_gateway import APIGateway, APIEndpoint, RateLimiter
from .streaming_services import StreamingServiceManager, SpotifyIntegration, LastFmIntegration
from .social_media import SocialMediaManager, TwitterIntegration, DiscordStatusIntegration
from .analytics import AnalyticsManager, GoogleAnalyticsIntegration, CustomDashboard

__all__ = [
    # Webhook System
    'WebhookManager',
    'WebhookEvent',
    'WebhookDelivery',
    
    # API Management
    'APIGateway',
    'APIEndpoint',
    'RateLimiter',
    
    # Streaming Services
    'StreamingServiceManager',
    'SpotifyIntegration',
    'LastFmIntegration',
    
    # Social Media
    'SocialMediaManager',
    'TwitterIntegration',
    'DiscordStatusIntegration',
    
    # Analytics
    'AnalyticsManager',
    'GoogleAnalyticsIntegration',
    'CustomDashboard'
]
