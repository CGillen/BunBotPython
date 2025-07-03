"""
EventBridge for Cross-Platform Communication

Bridges EventBus events to external platforms like Second Life,
enabling real-time synchronization of bot state and commands.
"""

import logging
from typing import Dict, Any, Callable, List, Optional
import asyncio
from datetime import datetime

from core import ServiceRegistry, EventBus

logger = logging.getLogger('integrations.sync.event_bridge')


class EventBridge:
    """
    Bridges internal EventBus events to external platforms.
    
    Provides a clean interface for external systems to subscribe to
    internal bot events and ensures proper event formatting and delivery.
    """
    
    def __init__(self, service_registry: ServiceRegistry):
        self.service_registry = service_registry
        self.event_bus = service_registry.get(EventBus)
        
        # External platform handlers
        self.external_handlers: Dict[str, List[Callable]] = {}
        self.platform_connections: Dict[str, Dict[str, Any]] = {}
        
        # Event processing configuration
        self.event_queue_max_size = 1000
        self.batch_size = 10
        self.processing_interval = 0.1  # seconds
        
        # Event queue for batching
        self.event_queue: asyncio.Queue = asyncio.Queue(maxsize=self.event_queue_max_size)
        self.processing_task: Optional[asyncio.Task] = None
        self.is_running = False
        
        logger.info("EventBridge initialized")
    
    async def start(self) -> None:
        """Start the event bridge processing"""
        if not self.is_running:
            self.is_running = True
            self.processing_task = asyncio.create_task(self._process_event_queue())
            logger.info("EventBridge started")
    
    async def stop(self) -> None:
        """Stop the event bridge processing"""
        if self.is_running:
            self.is_running = False
            if self.processing_task:
                self.processing_task.cancel()
                try:
                    await self.processing_task
                except asyncio.CancelledError:
                    pass
            logger.info("EventBridge stopped")
    
    def register_platform(self, platform_id: str, connection_info: Dict[str, Any]) -> None:
        """Register an external platform for event bridging"""
        self.platform_connections[platform_id] = {
            'connection_info': connection_info,
            'registered_at': datetime.now(),
            'active': True
        }
        logger.info(f"Registered platform: {platform_id}")
    
    def unregister_platform(self, platform_id: str) -> None:
        """Unregister an external platform"""
        if platform_id in self.platform_connections:
            del self.platform_connections[platform_id]
            logger.info(f"Unregistered platform: {platform_id}")
    
    def subscribe_to_event(self, event_pattern: str, handler: Callable, platform_id: str) -> None:
        """
        Subscribe an external platform to specific events.
        
        Args:
            event_pattern: Event pattern to match (supports wildcards)
            handler: Async callable to handle the event
            platform_id: ID of the platform subscribing
        """
        if event_pattern not in self.external_handlers:
            self.external_handlers[event_pattern] = []
        
        handler_info = {
            'handler': handler,
            'platform_id': platform_id,
            'registered_at': datetime.now()
        }
        
        self.external_handlers[event_pattern].append(handler_info)
        logger.info(f"Platform {platform_id} subscribed to {event_pattern}")
    
    async def bridge_event(self, event_name: str, data: Dict[str, Any]) -> None:
        """
        Bridge an internal event to external platforms.
        
        Args:
            event_name: Name of the event to bridge
            data: Event data to send to external platforms
        """
        try:
            if not self.is_running:
                return
            
            # Create bridged event
            bridged_event = {
                'event_name': event_name,
                'data': data,
                'timestamp': datetime.now().isoformat(),
                'source': 'BunBot_internal'
            }
            
            # Queue event for processing
            try:
                self.event_queue.put_nowait(bridged_event)
            except asyncio.QueueFull:
                logger.warning(f"Event queue full, dropping event: {event_name}")
            
        except Exception as e:
            logger.error(f"Error bridging event {event_name}: {e}")
    
    async def _process_event_queue(self) -> None:
        """Process queued events in batches"""
        while self.is_running:
            try:
                events_batch = []
                
                # Collect events for batch processing
                for _ in range(self.batch_size):
                    try:
                        event = await asyncio.wait_for(
                            self.event_queue.get(), 
                            timeout=self.processing_interval
                        )
                        events_batch.append(event)
                    except asyncio.TimeoutError:
                        break
                
                # Process collected events
                if events_batch:
                    await self._process_events_batch(events_batch)
                
                # Brief pause between processing cycles
                if not events_batch:
                    await asyncio.sleep(self.processing_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in event queue processing: {e}")
                await asyncio.sleep(1)  # Brief pause on error
    
    async def _process_events_batch(self, events: List[Dict[str, Any]]) -> None:
        """Process a batch of events"""
        for event in events:
            try:
                await self._deliver_event_to_handlers(event)
            except Exception as e:
                logger.error(f"Error delivering event {event.get('event_name')}: {e}")
    
    async def _deliver_event_to_handlers(self, event: Dict[str, Any]) -> None:
        """Deliver an event to all matching handlers"""
        event_name = event['event_name']
        
        # Find matching handlers
        matching_handlers = []
        for pattern, handlers in self.external_handlers.items():
            if self._event_matches_pattern(event_name, pattern):
                matching_handlers.extend(handlers)
        
        # Deliver to handlers
        for handler_info in matching_handlers:
            try:
                platform_id = handler_info['platform_id']
                
                # Check if platform is still active
                if platform_id in self.platform_connections:
                    if self.platform_connections[platform_id]['active']:
                        handler = handler_info['handler']
                        await handler(event)
                    
            except Exception as e:
                logger.error(f"Error in event handler for {handler_info['platform_id']}: {e}")
    
    def _event_matches_pattern(self, event_name: str, pattern: str) -> bool:
        """Check if an event name matches a pattern (supports wildcards)"""
        if pattern == "*":
            return True
        
        if pattern.endswith("*"):
            prefix = pattern[:-1]
            return event_name.startswith(prefix)
        
        if pattern.startswith("*"):
            suffix = pattern[1:]
            return event_name.endswith(suffix)
        
        return event_name == pattern
    
    def get_bridge_stats(self) -> Dict[str, Any]:
        """Get statistics about the event bridge"""
        return {
            'is_running': self.is_running,
            'registered_platforms': len(self.platform_connections),
            'event_patterns': len(self.external_handlers),
            'total_handlers': sum(len(handlers) for handlers in self.external_handlers.values()),
            'queue_size': self.event_queue.qsize(),
            'platforms': list(self.platform_connections.keys())
        }
    
    async def setup_internal_event_forwarding(self) -> None:
        """Set up forwarding of internal EventBus events to external platforms"""
        try:
            # Subscribe to relevant internal events
            event_patterns = [
                "stream_*",
                "audio_*", 
                "favorites_*",
                "guild_*",
                "bot_*"
            ]
            
            for pattern in event_patterns:
                await self.event_bus.subscribe(pattern, self._on_internal_event)
            
            logger.info("Internal event forwarding configured")
            
        except Exception as e:
            logger.error(f"Error setting up internal event forwarding: {e}")
    
    async def _on_internal_event(self, event_name: str, data: Dict[str, Any]) -> None:
        """Handle internal events and bridge them to external platforms"""
        try:
            # Add internal event metadata
            bridging_data = {
                **data,
                'internal_event': True,
                'original_event': event_name
            }
            
            await self.bridge_event(event_name, bridging_data)
            
        except Exception as e:
            logger.error(f"Error handling internal event {event_name}: {e}")
