"""
Event Bus System for BunBot
"""

import logging
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Callable, Union, TypeVar, Generic, Type
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import inspect
import weakref

logger = logging.getLogger('discord.core.event_bus')

T = TypeVar('T')

class EventPriority(Enum):
    """Event handler priority levels"""
    CRITICAL = 0    # System-critical events (errors, cleanup)
    HIGH = 10       # Important business logic
    NORMAL = 50     # Standard application events
    LOW = 100       # Non-critical events (logging, metrics)

@dataclass
class Event:
    """
    Base event class with metadata and routing information.
    
    All events should inherit from this class to ensure proper
    metadata tracking and event bus compatibility.
    """
    
    # Event identification
    event_type: str
    event_id: str = field(default_factory=lambda: str(datetime.now(timezone.utc).timestamp()))
    
    # Event metadata
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: Optional[str] = None
    correlation_id: Optional[str] = None
    
    # Event data
    data: Dict[str, Any] = field(default_factory=dict)
    
    # Event routing
    target_handlers: Optional[List[str]] = None  # Specific handlers to target
    exclude_handlers: Optional[List[str]] = None  # Handlers to exclude
    
    # Event control
    propagate: bool = True  # Whether to continue propagation after handling
    async_only: bool = False  # Whether to only send to async handlers
    
    def __post_init__(self):
        """Post-initialization validation and setup"""
        if not self.event_type:
            self.event_type = self.__class__.__name__
    
    def get_event_data(self, key: str, default: Any = None) -> Any:
        """Get event data with fallback"""
        return self.data.get(key, default)
    
    def set_event_data(self, key: str, value: Any):
        """Set event data"""
        self.data[key] = value
    
    def stop_propagation(self):
        """Stop event propagation to remaining handlers"""
        self.propagate = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization"""
        return {
            'event_type': self.event_type,
            'event_id': self.event_id,
            'timestamp': self.timestamp.isoformat(),
            'source': self.source,
            'correlation_id': self.correlation_id,
            'data': self.data,
            'target_handlers': self.target_handlers,
            'exclude_handlers': self.exclude_handlers,
            'propagate': self.propagate,
            'async_only': self.async_only
        }

class BotEvent(Event):
    """Base class for bot-specific events"""
    
    def __init__(self, event_type: str, guild_id: Optional[int] = None, **kwargs):
        super().__init__(event_type=event_type, **kwargs)
        if guild_id:
            self.data['guild_id'] = guild_id
        self.source = 'bot'

class StateChangeEvent(BotEvent):
    """Event fired when state changes occur"""
    
    def __init__(self, guild_id: int, field: str, old_value: Any, new_value: Any, **kwargs):
        super().__init__('state_change', guild_id=guild_id, **kwargs)
        self.data.update({
            'field': field,
            'old_value': old_value,
            'new_value': new_value
        })

class AudioEvent(BotEvent):
    """Events related to audio streaming"""
    pass

class StreamStartEvent(AudioEvent):
    """Event fired when audio stream starts"""
    
    def __init__(self, guild_id: int, stream_url: str, **kwargs):
        super().__init__('stream_start', guild_id=guild_id, **kwargs)
        self.data.update({
            'stream_url': stream_url
        })

class StreamEndEvent(AudioEvent):
    """Event fired when audio stream ends"""
    
    def __init__(self, guild_id: int, reason: str = 'unknown', **kwargs):
        super().__init__('stream_end', guild_id=guild_id, **kwargs)
        self.data.update({
            'reason': reason
        })

class HealthEvent(BotEvent):
    """Events related to bot health monitoring"""
    pass

class HealthCheckEvent(HealthEvent):
    """Event fired during health checks"""
    
    def __init__(self, health_status: str, metrics: Dict[str, Any], **kwargs):
        super().__init__('health_check', **kwargs)
        self.data.update({
            'health_status': health_status,
            'metrics': metrics
        })

@dataclass
class EventHandler:
    """Event handler registration information"""
    
    handler_id: str
    handler_func: Callable
    event_types: List[str]
    priority: EventPriority = EventPriority.NORMAL
    async_handler: bool = False
    filter_func: Optional[Callable[[Event], bool]] = None
    
    def __post_init__(self):
        """Post-initialization setup"""
        self.async_handler = asyncio.iscoroutinefunction(self.handler_func)
    
    def can_handle(self, event: Event) -> bool:
        """Check if this handler can handle the given event"""
        # Check event type
        if event.event_type not in self.event_types and '*' not in self.event_types:
            return False
        
        # Check targeting
        if event.target_handlers and self.handler_id not in event.target_handlers:
            return False
        
        # Check exclusions
        if event.exclude_handlers and self.handler_id in event.exclude_handlers:
            return False
        
        # Check async requirements
        if event.async_only and not self.async_handler:
            return False
        
        # Check custom filter
        if self.filter_func and not self.filter_func(event):
            return False
        
        return True

class EventBus:
    """
    Centralized event bus for decoupled component communication.
    
    Provides pub/sub pattern with type safety, error isolation,
    and comprehensive event management capabilities.
    """
    
    def __init__(self, max_history: int = 1000):
        self._handlers: Dict[str, EventHandler] = {}
        self._event_history: List[Event] = []
        self._max_history = max_history
        self._error_handlers: List[Callable] = []
        self._middleware: List[Callable] = []
        self._stats = {
            'events_published': 0,
            'events_handled': 0,
            'handler_errors': 0
        }
        
        logger.info("EventBus initialized")
    
    def subscribe(
        self,
        event_types: Union[str, List[str]],
        handler: Callable,
        handler_id: Optional[str] = None,
        priority: EventPriority = EventPriority.NORMAL,
        filter_func: Optional[Callable[[Event], bool]] = None
    ) -> str:
        """
        Subscribe to events with a handler function.
        
        Args:
            event_types: Event type(s) to subscribe to ('*' for all)
            handler: Handler function (sync or async)
            handler_id: Unique handler ID (auto-generated if None)
            priority: Handler priority level
            filter_func: Optional filter function
            
        Returns:
            Handler ID for later unsubscription
        """
        # Normalize event types
        if isinstance(event_types, str):
            event_types = [event_types]
        
        # Generate handler ID if not provided
        if handler_id is None:
            handler_id = f"{handler.__name__}_{id(handler)}"
        
        # Create handler registration
        event_handler = EventHandler(
            handler_id=handler_id,
            handler_func=handler,
            event_types=event_types,
            priority=priority,
            filter_func=filter_func
        )
        
        self._handlers[handler_id] = event_handler
        
        logger.debug(f"Subscribed handler {handler_id} to events: {event_types}")
        return handler_id
    
    def unsubscribe(self, handler_id: str) -> bool:
        """
        Unsubscribe a handler by ID.
        
        Args:
            handler_id: Handler ID to unsubscribe
            
        Returns:
            True if handler was found and removed
        """
        if handler_id in self._handlers:
            del self._handlers[handler_id]
            logger.debug(f"Unsubscribed handler {handler_id}")
            return True
        return False
    
    def publish(self, event: Event) -> int:
        """
        Publish an event to all applicable handlers.
        
        Args:
            event: Event to publish
            
        Returns:
            Number of handlers that processed the event
        """
        self._stats['events_published'] += 1
        
        # Add to history
        self._add_to_history(event)
        
        # Apply middleware
        for middleware in self._middleware:
            try:
                event = middleware(event)
                if event is None:
                    logger.debug("Event stopped by middleware")
                    return 0
            except Exception as e:
                logger.error(f"Error in middleware: {e}")
        
        # Find applicable handlers
        applicable_handlers = self._get_applicable_handlers(event)
        
        # Sort by priority
        applicable_handlers.sort(key=lambda h: h.priority.value)
        
        handled_count = 0
        
        # Process handlers
        for handler in applicable_handlers:
            if not event.propagate:
                break
            
            try:
                if handler.async_handler:
                    # Schedule async handler
                    asyncio.create_task(self._handle_async(handler, event))
                else:
                    # Call sync handler directly
                    handler.handler_func(event)
                
                handled_count += 1
                self._stats['events_handled'] += 1
                
            except Exception as e:
                self._stats['handler_errors'] += 1
                logger.error(f"Error in handler {handler.handler_id}: {e}")
                self._handle_error(handler, event, e)
        
        logger.debug(f"Published event {event.event_type} to {handled_count} handlers")
        return handled_count
    
    async def publish_async(self, event: Event) -> int:
        """
        Publish an event and wait for all async handlers to complete.
        
        Args:
            event: Event to publish
            
        Returns:
            Number of handlers that processed the event
        """
        self._stats['events_published'] += 1
        
        # Add to history
        self._add_to_history(event)
        
        # Apply middleware
        for middleware in self._middleware:
            try:
                if asyncio.iscoroutinefunction(middleware):
                    event = await middleware(event)
                else:
                    event = middleware(event)
                if event is None:
                    logger.debug("Event stopped by middleware")
                    return 0
            except Exception as e:
                logger.error(f"Error in middleware: {e}")
        
        # Find applicable handlers
        applicable_handlers = self._get_applicable_handlers(event)
        
        # Sort by priority
        applicable_handlers.sort(key=lambda h: h.priority.value)
        
        handled_count = 0
        async_tasks = []
        
        # Process handlers
        for handler in applicable_handlers:
            if not event.propagate:
                break
            
            try:
                if handler.async_handler:
                    # Create async task
                    task = asyncio.create_task(self._handle_async(handler, event))
                    async_tasks.append(task)
                else:
                    # Call sync handler directly
                    handler.handler_func(event)
                
                handled_count += 1
                self._stats['events_handled'] += 1
                
            except Exception as e:
                self._stats['handler_errors'] += 1
                logger.error(f"Error in handler {handler.handler_id}: {e}")
                self._handle_error(handler, event, e)
        
        # Wait for all async tasks
        if async_tasks:
            await asyncio.gather(*async_tasks, return_exceptions=True)
        
        logger.debug(f"Published event {event.event_type} to {handled_count} handlers")
        return handled_count
    
    def emit(self, event_type: str, **data) -> int:
        """
        Convenience method to create and publish an event.
        
        Args:
            event_type: Type of event to create
            **data: Event data
            
        Returns:
            Number of handlers that processed the event
        """
        event = Event(event_type=event_type, data=data)
        return self.publish(event)
    
    async def emit_async(self, event_type: str, **data) -> int:
        """
        Convenience method to create and publish an event asynchronously.
        
        Args:
            event_type: Type of event to create
            **data: Event data
            
        Returns:
            Number of handlers that processed the event
        """
        event = Event(event_type=event_type, data=data)
        return await self.publish_async(event)
    
    def add_middleware(self, middleware: Callable[[Event], Optional[Event]]):
        """
        Add middleware to process events before handling.
        
        Args:
            middleware: Middleware function that can modify or filter events
        """
        self._middleware.append(middleware)
        logger.debug(f"Added middleware: {middleware.__name__}")
    
    def add_error_handler(self, error_handler: Callable):
        """
        Add error handler for handler exceptions.
        
        Args:
            error_handler: Function to handle errors
        """
        self._error_handlers.append(error_handler)
        logger.debug(f"Added error handler: {error_handler.__name__}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get event bus statistics"""
        return {
            **self._stats,
            'active_handlers': len(self._handlers),
            'history_size': len(self._event_history)
        }
    
    def get_handlers(self) -> List[str]:
        """Get list of registered handler IDs"""
        return list(self._handlers.keys())
    
    def get_event_history(self, limit: Optional[int] = None) -> List[Event]:
        """
        Get recent event history.
        
        Args:
            limit: Maximum number of events to return
            
        Returns:
            List of recent events
        """
        if limit:
            return self._event_history[-limit:]
        return self._event_history.copy()
    
    def clear_history(self):
        """Clear event history"""
        self._event_history.clear()
        logger.debug("Cleared event history")
    
    def _get_applicable_handlers(self, event: Event) -> List[EventHandler]:
        """Get handlers that can handle the given event"""
        applicable = []
        
        for handler in self._handlers.values():
            if handler.can_handle(event):
                applicable.append(handler)
        
        return applicable
    
    async def _handle_async(self, handler: EventHandler, event: Event):
        """Handle async event handler execution with error handling"""
        try:
            await handler.handler_func(event)
        except Exception as e:
            self._stats['handler_errors'] += 1
            logger.error(f"Error in async handler {handler.handler_id}: {e}")
            self._handle_error(handler, event, e)
    
    def _handle_error(self, handler: EventHandler, event: Event, error: Exception):
        """Handle errors from event handlers"""
        for error_handler in self._error_handlers:
            try:
                if asyncio.iscoroutinefunction(error_handler):
                    asyncio.create_task(error_handler(handler, event, error))
                else:
                    error_handler(handler, event, error)
            except Exception as e:
                logger.error(f"Error in error handler: {e}")
    
    def _add_to_history(self, event: Event):
        """Add event to history with size management"""
        self._event_history.append(event)
        
        # Trim history if needed
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]


# Global event bus instance
_global_event_bus: Optional[EventBus] = None

def get_event_bus() -> EventBus:
    """Get the global event bus instance"""
    global _global_event_bus
    if _global_event_bus is None:
        _global_event_bus = EventBus()
    return _global_event_bus

def subscribe(event_types: Union[str, List[str]], handler: Callable, **kwargs) -> str:
    """Convenience function to subscribe to events"""
    return get_event_bus().subscribe(event_types, handler, **kwargs)

def unsubscribe(handler_id: str) -> bool:
    """Convenience function to unsubscribe from events"""
    return get_event_bus().unsubscribe(handler_id)

def publish(event: Event) -> int:
    """Convenience function to publish an event"""
    return get_event_bus().publish(event)

async def publish_async(event: Event) -> int:
    """Convenience function to publish an event asynchronously"""
    return await get_event_bus().publish_async(event)

def emit(event_type: str, **data) -> int:
    """Convenience function to emit an event"""
    return get_event_bus().emit(event_type, **data)

async def emit_async(event_type: str, **data) -> int:
    """Convenience function to emit an event asynchronously"""
    return await get_event_bus().emit_async(event_type, **data)
