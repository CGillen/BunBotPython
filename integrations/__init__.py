"""
External Integrations for BunBot

Provides integration capabilities with external platforms and services.
Built on the solid foundation of Phases 1-4 infrastructure.

Key Integrations:
- Second Life bridge server with FastAPI
- Cross-platform synchronization system
- Webhook management for external services
- API gateways for third-party integrations

Architecture:
- Built on Phase 1 ServiceRegistry, StateManager, EventBus, and ConfigurationManager
- Seamless integration with Phase 2 monitoring and Phase 3 audio systems
- Leverages Phase 4 UI components for cross-platform interfaces
- Secure authentication and rate limiting for external access
"""

from .sl_bridge import SLBridgeServer, SLCommandProcessor, StateSynchronizer
from .sync import EventBridge, ConflictResolver, NotificationBridge

__all__ = [
    # Second Life Integration
    'SLBridgeServer',
    'SLCommandProcessor', 
    'StateSynchronizer',
    
    # Cross-Platform Synchronization
    'EventBridge',
    'ConflictResolver',
    'NotificationBridge'
]
