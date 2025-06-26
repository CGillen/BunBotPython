"""
State Synchronizer for Cross-Platform BunBot Integration
"""

import logging
import asyncio
from typing import Dict, Any, Optional, List, Set
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from enum import Enum

# Phase 1 Infrastructure
from core.service_registry import ServiceRegistry
from core.state_manager import StateManager
from core.event_bus import EventBus
from core.config_manager import ConfigurationManager

# Phase 3 Audio
from audio import AudioConfig, AudioMetrics

logger = logging.getLogger('sync.state_synchronizer')

class PlatformType(Enum):
    """Supported platforms for synchronization"""
    DISCORD = "discord"
    SECOND_LIFE = "second_life"
    API = "api"
    UNKNOWN = "unknown"

@dataclass
class StateUpdate:
    """Represents a state update from any platform"""
    platform: PlatformType
    guild_id: int
    update_type: str
    data: Dict[str, Any]
    timestamp: datetime
    source_id: Optional[str] = None
    priority: int = 0

@dataclass
class SynchronizedState:
    """Complete synchronized state for a guild"""
    guild_id: int
    audio_config: Optional[AudioConfig] = None
    audio_metrics: Optional[AudioMetrics] = None
    current_stream: Optional[Dict[str, Any]] = None
    volume_level: float = 0.8
    is_playing: bool = False
    last_updated: Optional[datetime] = None
    last_platform: Optional[PlatformType] = None

class StateSynchronizer:
    """
    Manages real-time state synchronization across platforms.
    
    Ensures that changes made on one platform (Discord or Second Life)
    are immediately reflected on all other connected platforms.
    """
    
    def __init__(self, service_registry: ServiceRegistry):
        self.service_registry = service_registry
        self.state_manager = service_registry.get_service(StateManager)
        self.event_bus = service_registry.get_service(EventBus)
        self.config_manager = service_registry.get_service(ConfigurationManager)
        
        # Synchronized state storage
        self.guild_states: Dict[int, SynchronizedState] = {}
        
        # Update tracking
        self.pending_updates: Dict[str, StateUpdate] = {}
        self.update_lock = asyncio.Lock()
        
        # Platform connections
        self.platform_connections: Dict[PlatformType, Set[str]] = {
            PlatformType.DISCORD: set(),
            PlatformType.SECOND_LIFE: set(),
            PlatformType.API: set()
        }
        
        # Conflict resolution settings
        self.conflict_resolution_timeout = 1.0  # seconds
        self.max_pending_updates = 100
        
        logger.info("State Synchronizer initialized")
    
    async def initialize(self) -> None:
        """Initialize the state synchronizer"""
        try:
            # Subscribe to relevant events from Phase 1 EventBus
            await self.event_bus.subscribe("audio_*", self._on_audio_event)
            await self.event_bus.subscribe("stream_*", self._on_stream_event)
            await self.event_bus.subscribe("favorites_*", self._on_favorites_event)
            await self.event_bus.subscribe("guild_*", self._on_guild_event)
            
            # Load existing guild states
            await self._load_guild_states()
            
            logger.info("State Synchronizer initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing State Synchronizer: {e}")
            raise
    
    async def shutdown(self) -> None:
        """Shutdown the state synchronizer"""
        try:
            # Unsubscribe from events
            await self.event_bus.unsubscribe("audio_*", self._on_audio_event)
            await self.event_bus.unsubscribe("stream_*", self._on_stream_event)
            await self.event_bus.unsubscribe("favorites_*", self._on_favorites_event)
            await self.event_bus.unsubscribe("guild_*", self._on_guild_event)
            
            # Save current states
            await self._save_guild_states()
            
            logger.info("State Synchronizer shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during State Synchronizer shutdown: {e}")
    
    async def register_platform_connection(self, platform: PlatformType, connection_id: str) -> None:
        """Register a platform connection for synchronization"""
        try:
            self.platform_connections[platform].add(connection_id)
            logger.info(f"Registered {platform.value} connection: {connection_id}")
            
            # Send current state to new connection
            await self._send_full_state_to_connection(platform, connection_id)
            
        except Exception as e:
            logger.error(f"Error registering platform connection: {e}")
    
    async def unregister_platform_connection(self, platform: PlatformType, connection_id: str) -> None:
        """Unregister a platform connection"""
        try:
            self.platform_connections[platform].discard(connection_id)
            logger.info(f"Unregistered {platform.value} connection: {connection_id}")
            
        except Exception as e:
            logger.error(f"Error unregistering platform connection: {e}")
    
    async def sync_state_update(self, update: StateUpdate) -> bool:
        """
        Synchronize a state update across all platforms.
        
        Args:
            update: State update to synchronize
            
        Returns:
            True if update was applied successfully
        """
        try:
            async with self.update_lock:
                # Check for conflicts with pending updates
                conflict_update = await self._check_for_conflicts(update)
                if conflict_update:
                    # Resolve conflict
                    resolved_update = await self._resolve_conflict(update, conflict_update)
                    if not resolved_update:
                        logger.warning(f"State update rejected due to conflict: {update.update_type}")
                        return False
                    update = resolved_update
                
                # Apply the update
                success = await self._apply_state_update(update)
                if not success:
                    return False
                
                # Broadcast to all other platforms
                await self._broadcast_state_update(update)
                
                # Clean up pending updates
                await self._cleanup_pending_updates()
                
                return True
                
        except Exception as e:
            logger.error(f"Error synchronizing state update: {e}")
            return False
    
    async def get_guild_state(self, guild_id: int) -> Optional[SynchronizedState]:
        """Get current synchronized state for a guild"""
        try:
            if guild_id not in self.guild_states:
                # Initialize new guild state
                await self._initialize_guild_state(guild_id)
            
            return self.guild_states.get(guild_id)
            
        except Exception as e:
            logger.error(f"Error getting guild state for {guild_id}: {e}")
            return None
    
    async def force_full_sync(self, guild_id: int) -> None:
        """Force a full state synchronization for a guild"""
        try:
            guild_state = await self.get_guild_state(guild_id)
            if not guild_state:
                return
            
            # Create full state update
            update = StateUpdate(
                platform=PlatformType.DISCORD,  # Use Discord as authoritative source
                guild_id=guild_id,
                update_type="full_sync",
                data=asdict(guild_state),
                timestamp=datetime.now(timezone.utc),
                priority=10  # High priority for full sync
            )
            
            # Broadcast to all platforms
            await self._broadcast_state_update(update)
            
            logger.info(f"Full state sync completed for guild {guild_id}")
            
        except Exception as e:
            logger.error(f"Error during full sync for guild {guild_id}: {e}")
    
    async def _on_audio_event(self, event: str, data: Dict[str, Any]) -> None:
        """Handle audio events from Phase 1 EventBus"""
        try:
            guild_id = data.get("guild_id")
            if not guild_id:
                return
            
            # Create state update from audio event
            update = StateUpdate(
                platform=PlatformType.DISCORD,
                guild_id=guild_id,
                update_type=event,
                data=data,
                timestamp=datetime.now(timezone.utc)
            )
            
            # Synchronize the update
            await self.sync_state_update(update)
            
        except Exception as e:
            logger.error(f"Error handling audio event {event}: {e}")
    
    async def _on_stream_event(self, event: str, data: Dict[str, Any]) -> None:
        """Handle stream events from Phase 1 EventBus"""
        try:
            guild_id = data.get("guild_id")
            if not guild_id:
                return
            
            # Create state update from stream event
            update = StateUpdate(
                platform=PlatformType.DISCORD,
                guild_id=guild_id,
                update_type=event,
                data=data,
                timestamp=datetime.now(timezone.utc)
            )
            
            # Synchronize the update
            await self.sync_state_update(update)
            
        except Exception as e:
            logger.error(f"Error handling stream event {event}: {e}")
    
    async def _on_favorites_event(self, event: str, data: Dict[str, Any]) -> None:
        """Handle favorites events from Phase 1 EventBus"""
        try:
            guild_id = data.get("guild_id")
            if not guild_id:
                return
            
            # Create state update from favorites event
            update = StateUpdate(
                platform=PlatformType.DISCORD,
                guild_id=guild_id,
                update_type=event,
                data=data,
                timestamp=datetime.now(timezone.utc)
            )
            
            # Synchronize the update
            await self.sync_state_update(update)
            
        except Exception as e:
            logger.error(f"Error handling favorites event {event}: {e}")
    
    async def _on_guild_event(self, event: str, data: Dict[str, Any]) -> None:
        """Handle guild events from Phase 1 EventBus"""
        try:
            guild_id = data.get("guild_id")
            if not guild_id:
                return
            
            if event == "guild_added":
                await self._initialize_guild_state(guild_id)
            elif event == "guild_removed":
                self.guild_states.pop(guild_id, None)
            
        except Exception as e:
            logger.error(f"Error handling guild event {event}: {e}")
    
    async def _check_for_conflicts(self, update: StateUpdate) -> Optional[StateUpdate]:
        """Check for conflicting updates"""
        try:
            update_key = f"{update.guild_id}_{update.update_type}"
            
            # Check if there's a pending update of the same type
            if update_key in self.pending_updates:
                return self.pending_updates[update_key]
            
            # Add to pending updates
            self.pending_updates[update_key] = update
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking for conflicts: {e}")
            return None
    
    async def _resolve_conflict(self, new_update: StateUpdate, existing_update: StateUpdate) -> Optional[StateUpdate]:
        """Resolve conflict between two updates"""
        try:
            # Priority-based resolution
            if new_update.priority > existing_update.priority:
                return new_update
            elif existing_update.priority > new_update.priority:
                return existing_update
            
            # Timestamp-based resolution (newer wins)
            if new_update.timestamp > existing_update.timestamp:
                return new_update
            else:
                return existing_update
                
        except Exception as e:
            logger.error(f"Error resolving conflict: {e}")
            return None
    
    async def _apply_state_update(self, update: StateUpdate) -> bool:
        """Apply a state update to the guild state"""
        try:
            guild_state = await self.get_guild_state(update.guild_id)
            if not guild_state:
                return False
            
            # Apply update based on type
            if update.update_type.startswith("audio_"):
                await self._apply_audio_update(guild_state, update)
            elif update.update_type.startswith("stream_"):
                await self._apply_stream_update(guild_state, update)
            elif update.update_type.startswith("favorites_"):
                await self._apply_favorites_update(guild_state, update)
            elif update.update_type == "full_sync":
                await self._apply_full_sync_update(guild_state, update)
            
            # Update metadata
            guild_state.last_updated = update.timestamp
            guild_state.last_platform = update.platform
            
            # Persist state
            await self.state_manager.set_guild_state(
                update.guild_id,
                f"synchronized_state",
                asdict(guild_state)
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error applying state update: {e}")
            return False
    
    async def _apply_audio_update(self, guild_state: SynchronizedState, update: StateUpdate) -> None:
        """Apply audio-specific state updates"""
        data = update.data
        
        if "volume" in data:
            guild_state.volume_level = data["volume"]
        
        if "audio_config" in data:
            guild_state.audio_config = data["audio_config"]
        
        if "audio_metrics" in data:
            guild_state.audio_metrics = data["audio_metrics"]
        
        if "is_playing" in data:
            guild_state.is_playing = data["is_playing"]
    
    async def _apply_stream_update(self, guild_state: SynchronizedState, update: StateUpdate) -> None:
        """Apply stream-specific state updates"""
        data = update.data
        
        if "current_stream" in data:
            guild_state.current_stream = data["current_stream"]
        
        if "stream_started" in update.update_type:
            guild_state.is_playing = True
            guild_state.current_stream = data.get("stream")
        
        if "stream_stopped" in update.update_type:
            guild_state.is_playing = False
    
    async def _apply_favorites_update(self, guild_state: SynchronizedState, update: StateUpdate) -> None:
        """Apply favorites-specific state updates"""
        # Favorites updates don't directly affect synchronized state
        # but may trigger stream changes
        pass
    
    async def _apply_full_sync_update(self, guild_state: SynchronizedState, update: StateUpdate) -> None:
        """Apply full synchronization update"""
        data = update.data
        
        # Update all fields from the sync data
        for field, value in data.items():
            if hasattr(guild_state, field):
                setattr(guild_state, field, value)
    
    async def _broadcast_state_update(self, update: StateUpdate) -> None:
        """Broadcast state update to all connected platforms"""
        try:
            # Emit event through Phase 1 EventBus for local handling
            await self.event_bus.emit(f"state_sync_{update.update_type}", {
                "guild_id": update.guild_id,
                "platform": update.platform.value,
                "data": update.data,
                "timestamp": update.timestamp.isoformat()
            })
            
            logger.debug(f"Broadcasted state update: {update.update_type} for guild {update.guild_id}")
            
        except Exception as e:
            logger.error(f"Error broadcasting state update: {e}")
    
    async def _send_full_state_to_connection(self, platform: PlatformType, connection_id: str) -> None:
        """Send full current state to a new connection"""
        try:
            # This would be implemented to send current state to specific connections
            # For now, we'll emit a general event that can be handled by the appropriate platform
            await self.event_bus.emit("platform_connection_registered", {
                "platform": platform.value,
                "connection_id": connection_id,
                "guild_states": {guild_id: asdict(state) for guild_id, state in self.guild_states.items()}
            })
            
        except Exception as e:
            logger.error(f"Error sending full state to connection: {e}")
    
    async def _initialize_guild_state(self, guild_id: int) -> None:
        """Initialize synchronized state for a new guild"""
        try:
            # Load existing state from StateManager
            existing_state = await self.state_manager.get_guild_state(guild_id, "synchronized_state")
            
            if existing_state:
                # Restore from saved state
                self.guild_states[guild_id] = SynchronizedState(**existing_state)
            else:
                # Create new state
                self.guild_states[guild_id] = SynchronizedState(
                    guild_id=guild_id,
                    last_updated=datetime.now(timezone.utc)
                )
            
            logger.info(f"Initialized synchronized state for guild {guild_id}")
            
        except Exception as e:
            logger.error(f"Error initializing guild state for {guild_id}: {e}")
    
    async def _load_guild_states(self) -> None:
        """Load all existing guild states"""
        try:
            # This would load from Phase 1 StateManager
            # For now, we'll start with empty states
            logger.info("Guild states loaded")
            
        except Exception as e:
            logger.error(f"Error loading guild states: {e}")
    
    async def _save_guild_states(self) -> None:
        """Save all guild states"""
        try:
            for guild_id, guild_state in self.guild_states.items():
                await self.state_manager.set_guild_state(
                    guild_id,
                    "synchronized_state", 
                    asdict(guild_state)
                )
            
            logger.info("Guild states saved")
            
        except Exception as e:
            logger.error(f"Error saving guild states: {e}")
    
    async def _cleanup_pending_updates(self) -> None:
        """Clean up old pending updates"""
        try:
            current_time = datetime.now(timezone.utc)
            expired_keys = []
            
            for key, update in self.pending_updates.items():
                if (current_time - update.timestamp).total_seconds() > self.conflict_resolution_timeout:
                    expired_keys.append(key)
            
            for key in expired_keys:
                self.pending_updates.pop(key, None)
            
            # Limit pending updates
            if len(self.pending_updates) > self.max_pending_updates:
                # Remove oldest updates
                sorted_updates = sorted(
                    self.pending_updates.items(),
                    key=lambda x: x[1].timestamp
                )
                
                for key, _ in sorted_updates[:-self.max_pending_updates]:
                    self.pending_updates.pop(key, None)
            
        except Exception as e:
            logger.error(f"Error cleaning up pending updates: {e}")
