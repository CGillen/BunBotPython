"""
State Synchronizer for SL Bridge

Handles cross-platform state synchronization between Discord and Second Life
"""

import logging
from typing import Dict, Any, Set, Optional
from datetime import datetime
import asyncio

from core import ServiceRegistry, StateManager, EventBus

logger = logging.getLogger('sl_bridge.state_sync')


class StateSynchronizer:
    """
    Synchronizes state between Discord and Second Life platforms.
    
    Ensures that actions performed on one platform are reflected
    in real-time on the other platform through event-driven updates.
    """
    
    def __init__(self, service_registry: ServiceRegistry):
        self.service_registry = service_registry
        self.state_manager = service_registry.get(StateManager)
        self.event_bus = service_registry.get(EventBus)
        
        # Track active SL connections
        self.sl_connections: Dict[int, Set[str]] = {}  # guild_id -> set of connection_ids
        self.connection_metadata: Dict[str, Dict[str, Any]] = {}
        
        # Sync configuration
        self.sync_enabled = True
        self.sync_delay = 0.1  # Small delay to batch rapid updates
        
        # Pending sync operations
        self.pending_syncs: Dict[str, Dict[str, Any]] = {}
        self.sync_task: Optional[asyncio.Task] = None
        
        logger.info("State Synchronizer initialized")
    
    async def initialize(self) -> None:
        """Initialize the state synchronizer"""
        try:
            # Subscribe to relevant events for synchronization
            await self.event_bus.subscribe("stream_*", self._on_stream_event)
            await self.event_bus.subscribe("audio_*", self._on_audio_event)
            await self.event_bus.subscribe("favorites_*", self._on_favorites_event)
            await self.event_bus.subscribe("sl_connection_*", self._on_connection_event)
            
            # Start sync processing task
            self.sync_task = asyncio.create_task(self._process_sync_queue())
            
            logger.info("State Synchronizer initialized and listening for events")
            
        except Exception as e:
            logger.error(f"Error initializing State Synchronizer: {e}")
            raise
    
    async def shutdown(self) -> None:
        """Shutdown the state synchronizer"""
        try:
            # Unsubscribe from events
            await self.event_bus.unsubscribe("stream_*", self._on_stream_event)
            await self.event_bus.unsubscribe("audio_*", self._on_audio_event)
            await self.event_bus.unsubscribe("favorites_*", self._on_favorites_event)
            await self.event_bus.unsubscribe("sl_connection_*", self._on_connection_event)
            
            # Stop sync task
            if self.sync_task:
                self.sync_task.cancel()
                try:
                    await self.sync_task
                except asyncio.CancelledError:
                    pass
            
            logger.info("State Synchronizer shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during State Synchronizer shutdown: {e}")
    
    def register_sl_connection(self, guild_id: int, connection_id: str, 
                             metadata: Dict[str, Any] = None) -> None:
        """Register a new SL connection for state sync"""
        try:
            if guild_id not in self.sl_connections:
                self.sl_connections[guild_id] = set()
            
            self.sl_connections[guild_id].add(connection_id)
            self.connection_metadata[connection_id] = metadata or {}
            
            logger.info(f"Registered SL connection {connection_id} for guild {guild_id}")
            
        except Exception as e:
            logger.error(f"Error registering SL connection: {e}")
    
    def unregister_sl_connection(self, guild_id: int, connection_id: str) -> None:
        """Unregister an SL connection"""
        try:
            if guild_id in self.sl_connections:
                self.sl_connections[guild_id].discard(connection_id)
                
                # Clean up empty guild entries
                if not self.sl_connections[guild_id]:
                    del self.sl_connections[guild_id]
            
            self.connection_metadata.pop(connection_id, None)
            
            logger.info(f"Unregistered SL connection {connection_id} for guild {guild_id}")
            
        except Exception as e:
            logger.error(f"Error unregistering SL connection: {e}")
    
    async def sync_state_to_sl(self, guild_id: int, state_type: str, 
                             state_data: Dict[str, Any]) -> None:
        """Sync state changes to Second Life connections"""
        try:
            if not self.sync_enabled:
                return
            
            # Check if there are SL connections for this guild
            if guild_id not in self.sl_connections or not self.sl_connections[guild_id]:
                return
            
            # Create sync message
            sync_message = {
                'type': 'state_sync',
                'state_type': state_type,
                'guild_id': guild_id,
                'data': state_data,
                'timestamp': datetime.now().isoformat()
            }
            
            # Queue for batched processing
            sync_key = f"{guild_id}:{state_type}"
            self.pending_syncs[sync_key] = sync_message
            
            logger.debug(f"Queued state sync for guild {guild_id}: {state_type}")
            
        except Exception as e:
            logger.error(f"Error syncing state to SL: {e}")
    
    async def sync_state_from_sl(self, guild_id: int, state_type: str, 
                               state_data: Dict[str, Any]) -> None:
        """Sync state changes from Second Life to Discord"""
        try:
            if not self.sync_enabled:
                return
            
            # Update local state
            await self.state_manager.set_state(
                f"sl_sync:{guild_id}:{state_type}",
                state_data
            )
            
            # Emit event for Discord components to pick up
            await self.event_bus.emit(f"sl_state_sync:{state_type}", {
                'guild_id': guild_id,
                'data': state_data,
                'source': 'second_life'
            })
            
            logger.debug(f"Synced state from SL for guild {guild_id}: {state_type}")
            
        except Exception as e:
            logger.error(f"Error syncing state from SL: {e}")
    
    async def _process_sync_queue(self) -> None:
        """Process pending sync operations"""
        while True:
            try:
                if self.pending_syncs:
                    # Process all pending syncs
                    current_syncs = dict(self.pending_syncs)
                    self.pending_syncs.clear()
                    
                    for sync_key, sync_message in current_syncs.items():
                        await self._send_sync_to_connections(sync_message)
                
                # Wait before next processing cycle
                await asyncio.sleep(self.sync_delay)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in sync queue processing: {e}")
                await asyncio.sleep(1)  # Brief pause on error
    
    async def _send_sync_to_connections(self, sync_message: Dict[str, Any]) -> None:
        """Send sync message to relevant SL connections"""
        try:
            guild_id = sync_message['guild_id']
            
            if guild_id not in self.sl_connections:
                return
            
            # Get SL Bridge server for WebSocket broadcasting
            # This would typically be injected or retrieved from service registry
            from .server import SLBridgeServer
            sl_bridge_server = self.service_registry.get_optional(SLBridgeServer)
            
            if sl_bridge_server:
                await sl_bridge_server.broadcast_event(
                    "state_sync",
                    sync_message,
                    guild_id
                )
            
            logger.debug(f"Sent sync message to SL connections for guild {guild_id}")
            
        except Exception as e:
            logger.error(f"Error sending sync to connections: {e}")
    
    async def _on_stream_event(self, event: str, data: Dict[str, Any]) -> None:
        """Handle stream events for synchronization"""
        try:
            guild_id = data.get('guild_id')
            if not guild_id:
                return
            
            # Extract relevant state data
            state_data = {
                'is_playing': data.get('is_playing', False),
                'current_song': data.get('current_song'),
                'station_name': data.get('station_name'),
                'stream_url': data.get('stream_url'),
                'event': event
            }
            
            await self.sync_state_to_sl(guild_id, 'stream', state_data)
            
        except Exception as e:
            logger.error(f"Error handling stream event for sync: {e}")
    
    async def _on_audio_event(self, event: str, data: Dict[str, Any]) -> None:
        """Handle audio events for synchronization"""
        try:
            guild_id = data.get('guild_id')
            if not guild_id:
                return
            
            # Extract relevant state data
            state_data = {
                'volume': data.get('volume'),
                'bass': data.get('bass'),
                'mid': data.get('mid'),
                'treble': data.get('treble'),
                'event': event
            }
            
            await self.sync_state_to_sl(guild_id, 'audio', state_data)
            
        except Exception as e:
            logger.error(f"Error handling audio event for sync: {e}")
    
    async def _on_favorites_event(self, event: str, data: Dict[str, Any]) -> None:
        """Handle favorites events for synchronization"""
        try:
            guild_id = data.get('guild_id')
            if not guild_id:
                return
            
            # Extract relevant state data
            state_data = {
                'favorite_number': data.get('favorite_number'),
                'station_name': data.get('station_name'),
                'stream_url': data.get('stream_url'),
                'event': event
            }
            
            await self.sync_state_to_sl(guild_id, 'favorites', state_data)
            
        except Exception as e:
            logger.error(f"Error handling favorites event for sync: {e}")
    
    async def _on_connection_event(self, event: str, data: Dict[str, Any]) -> None:
        """Handle SL connection events"""
        try:
            if event == "sl_connection_established":
                guild_id = data.get('guild_id')
                connection_id = data.get('connection_id')
                metadata = data.get('metadata', {})
                
                if guild_id and connection_id:
                    self.register_sl_connection(guild_id, connection_id, metadata)
            
            elif event == "sl_connection_closed":
                guild_id = data.get('guild_id')
                connection_id = data.get('connection_id')
                
                if guild_id and connection_id:
                    self.unregister_sl_connection(guild_id, connection_id)
            
        except Exception as e:
            logger.error(f"Error handling connection event for sync: {e}")
    
    def get_sync_stats(self) -> Dict[str, Any]:
        """Get synchronization statistics"""
        try:
            total_connections = sum(len(connections) for connections in self.sl_connections.values())
            
            return {
                'sync_enabled': self.sync_enabled,
                'active_guilds': len(self.sl_connections),
                'total_connections': total_connections,
                'pending_syncs': len(self.pending_syncs),
                'sync_delay': self.sync_delay,
                'connections_by_guild': {
                    guild_id: len(connections) 
                    for guild_id, connections in self.sl_connections.items()
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting sync stats: {e}")
            return {
                'sync_enabled': False,
                'error': str(e)
            }
    
    def set_sync_enabled(self, enabled: bool) -> None:
        """Enable or disable state synchronization"""
        self.sync_enabled = enabled
        logger.info(f"State synchronization {'enabled' if enabled else 'disabled'}")
    
    def set_sync_delay(self, delay: float) -> None:
        """Set the synchronization batching delay"""
        if delay >= 0.0:
            self.sync_delay = delay
            logger.info(f"Sync delay set to {delay} seconds")
