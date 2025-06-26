"""
Core Infrastructure for BunBot

Provides foundational services including dependency injection, configuration management,
state management, and event-driven communication for scalable, testable, and 
maintainable Discord bot architecture.

Key Components:
- ServiceRegistry: Dependency injection container for all services
- ConfigurationManager: Centralized configuration with environment support  
- StateManager: Persistent state management replacing global variables
- EventBus: Internal event system for component communication

Architecture:
- Service-oriented design with dependency injection
- Event-driven communication between components
- Persistent state management with validation
- Comprehensive configuration with environment support
"""

from .service_registry import ServiceRegistry, ServiceLifetime, ServiceNotFound, get_service_registry
from .config_manager import ConfigurationManager, ConfigurationError, get_config_manager
from .state_manager import StateManager, GuildState, get_state_manager
from .event_bus import EventBus, Event, get_event_bus

__all__ = [
    'ServiceRegistry',
    'ServiceLifetime',
    'ServiceNotFound', 
    'get_service_registry',
    'ConfigurationManager',
    'ConfigurationError',
    'get_config_manager',
    'StateManager',
    'GuildState',
    'get_state_manager',
    'EventBus',
    'Event',
    'get_event_bus'
]
