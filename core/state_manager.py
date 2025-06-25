"""
State Management System for BunBot
"""

import logging
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Set, List, TypeVar, Generic
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
import json

logger = logging.getLogger('discord.core.state_manager')

T = TypeVar('T')

class StateType(Enum):
    """Types of state that can be managed"""
    STREAMING = "streaming"
    AUDIO = "audio"
    TEMPORARY = "temporary"
    PERSISTENT = "persistent"

@dataclass
class GuildState:
    """
    Type-safe guild state container replacing the old server_state dict.
    
    Contains all state information for a specific Discord guild.
    """
    
    # Guild identification
    guild_id: int
    
    # Streaming state
    current_stream_url: Optional[str] = None
    current_stream_response: Any = None  # http.client.HTTPResponse object
    current_song: Optional[str] = None
    start_time: Optional[datetime] = None
    
    # Discord integration
    text_channel: Any = None  # discord.TextChannel object
    voice_client: Any = None  # discord.VoiceClient object
    
    # Control state
    cleaning_up: bool = False
    metadata_listener_active: bool = False
    
    # Audio settings (per-guild customization)
    volume_level: float = 1.0
    audio_effects_enabled: bool = True
    crossfade_enabled: bool = True
    audio_config: Any = None  # AudioConfig from audio processing system
    
    # Session tracking
    session_start: Optional[datetime] = None
    total_play_time: float = 0.0
    streams_played: int = 0
    
    # Custom state storage for extensions
    custom_data: Dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def __post_init__(self):
        """Post-initialization validation and setup"""
        if self.session_start is None:
            self.session_start = datetime.now(timezone.utc)
    
    def is_streaming(self) -> bool:
        """Check if guild is currently streaming"""
        return (self.current_stream_url is not None and 
                not self.cleaning_up)
    
    def is_active(self) -> bool:
        """Check if guild has any active state"""
        return (self.is_streaming() or 
                self.voice_client is not None or
                self.metadata_listener_active)
    
    def get_runtime(self) -> float:
        """Get current session runtime in seconds"""
        if self.start_time:
            return (datetime.now(timezone.utc) - self.start_time).total_seconds()
        return 0.0
    
    def update_last_activity(self):
        """Update last activity timestamp"""
        self.last_updated = datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization (excluding non-serializable objects)"""
        return {
            'guild_id': self.guild_id,
            'current_stream_url': self.current_stream_url,
            'current_song': self.current_song,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'cleaning_up': self.cleaning_up,
            'metadata_listener_active': self.metadata_listener_active,
            'volume_level': self.volume_level,
            'audio_effects_enabled': self.audio_effects_enabled,
            'crossfade_enabled': self.crossfade_enabled,
            'session_start': self.session_start.isoformat() if self.session_start else None,
            'total_play_time': self.total_play_time,
            'streams_played': self.streams_played,
            'custom_data': self.custom_data,
            'last_updated': self.last_updated.isoformat(),
            'created_at': self.created_at.isoformat()
        }

class StateChangeEvent:
    """Event fired when state changes occur"""
    
    def __init__(self, guild_id: int, field: str, old_value: Any, new_value: Any):
        self.guild_id = guild_id
        self.field = field
        self.old_value = old_value
        self.new_value = new_value
        self.timestamp = datetime.now(timezone.utc)

class StateManager:
    """
    Centralized state management system for BunBot.
    
    Replaces the global server_state dictionary with a type-safe,
    persistent, and event-driven state management system.
    """
    
    def __init__(self, persistence_enabled: bool = True):
        self._guild_states: Dict[int, GuildState] = {}
        self._locks: Dict[int, Lock] = {}  # Per-guild locks for thread safety
        self._global_lock = Lock()
        self._persistence_enabled = persistence_enabled
        self._cleanup_task: Optional[asyncio.Task] = None
        self._event_listeners: List[Any] = []  # Event listeners for state changes
        
        logger.info("StateManager initialized")
    
    def get_guild_state(self, guild_id: int, create_if_missing: bool = True) -> Optional[GuildState]:
        """
        Get state for a specific guild.
        
        Args:
            guild_id: Discord guild ID
            create_if_missing: Create new state if it doesn't exist
            
        Returns:
            Guild state or None if not found and create_if_missing is False
        """
        with self._get_guild_lock(guild_id):
            if guild_id not in self._guild_states:
                if create_if_missing:
                    self._guild_states[guild_id] = GuildState(guild_id=guild_id)
                    logger.debug(f"Created new state for guild {guild_id}")
                else:
                    return None
            
            state = self._guild_states[guild_id]
            if state is not None:
                state.update_last_activity()
            return state
    
    def update_guild_state(
        self, 
        guild_id: int, 
        updates: Dict[str, Any], 
        merge_custom: bool = True
    ) -> GuildState:
        """
        Update guild state with new values.
        
        Args:
            guild_id: Discord guild ID
            updates: Dictionary of field updates
            merge_custom: Whether to merge custom_data instead of replacing
            
        Returns:
            Updated guild state
        """
        with self._get_guild_lock(guild_id):
            state = self.get_guild_state(guild_id, create_if_missing=True)
            
            # Ensure we have a valid state (should never be None when create_if_missing=True)
            if state is None:
                raise ValueError(f"Failed to create or retrieve state for guild {guild_id}")
            
            # Track changes for events
            changes = []
            
            for field, new_value in updates.items():
                if hasattr(state, field):
                    old_value = getattr(state, field)
                    
                    # Special handling for custom_data merging
                    if field == 'custom_data' and merge_custom and isinstance(old_value, dict):
                        if isinstance(new_value, dict):
                            merged_data = old_value.copy()
                            merged_data.update(new_value)
                            setattr(state, field, merged_data)
                            changes.append(StateChangeEvent(guild_id, field, old_value, merged_data))
                        else:
                            setattr(state, field, new_value)
                            changes.append(StateChangeEvent(guild_id, field, old_value, new_value))
                    else:
                        setattr(state, field, new_value)
                        changes.append(StateChangeEvent(guild_id, field, old_value, new_value))
                else:
                    logger.warning(f"Attempted to set unknown field '{field}' on guild state")
            
            state.update_last_activity()
            
            # Fire events for changes
            for change_event in changes:
                self._fire_state_change_event(change_event)
            
            logger.debug(f"Updated state for guild {guild_id}: {list(updates.keys())}")
            return state
    
    def set_guild_state_field(self, guild_id: int, field: str, value: Any) -> GuildState:
        """
        Set a specific field in guild state.
        
        Args:
            guild_id: Discord guild ID
            field: Field name to set
            value: Value to set
            
        Returns:
            Updated guild state
        """
        return self.update_guild_state(guild_id, {field: value})
    
    def get_guild_state_field(self, guild_id: int, field: str, default: Any = None) -> Any:
        """
        Get a specific field from guild state.
        
        Args:
            guild_id: Discord guild ID
            field: Field name to get
            default: Default value if field not found
            
        Returns:
            Field value or default
        """
        state = self.get_guild_state(guild_id, create_if_missing=False)
        if state is None:
            return default
        
        return getattr(state, field, default)
    
    def clear_guild_state(self, guild_id: int, preserve_custom: bool = False) -> bool:
        """
        Clear all state for a guild.
        
        Args:
            guild_id: Discord guild ID
            preserve_custom: Whether to preserve custom_data
            
        Returns:
            True if state was cleared, False if no state existed
        """
        with self._get_guild_lock(guild_id):
            if guild_id not in self._guild_states:
                return False
            
            old_state = self._guild_states[guild_id]
            
            # Preserve custom data if requested
            custom_data = old_state.custom_data.copy() if preserve_custom else {}
            
            # Create fresh state
            self._guild_states[guild_id] = GuildState(
                guild_id=guild_id,
                custom_data=custom_data
            )
            
            # Fire cleanup event
            self._fire_state_change_event(
                StateChangeEvent(guild_id, "state_cleared", old_state, self._guild_states[guild_id])
            )
            
            logger.info(f"Cleared state for guild {guild_id}")
            return True
    
    def remove_guild_state(self, guild_id: int) -> bool:
        """
        Completely remove state for a guild.
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            True if state was removed, False if no state existed
        """
        with self._global_lock:
            if guild_id in self._guild_states:
                old_state = self._guild_states.pop(guild_id)
                
                # Remove guild lock
                if guild_id in self._locks:
                    del self._locks[guild_id]
                
                # Fire removal event
                self._fire_state_change_event(
                    StateChangeEvent(guild_id, "state_removed", old_state, None)
                )
                
                logger.info(f"Removed state for guild {guild_id}")
                return True
            return False
    
    def get_active_guilds(self) -> List[int]:
        """
        Get list of guilds with active state.
        
        Returns:
            List of guild IDs with active streams or connections
        """
        active_guilds = []
        
        with self._global_lock:
            for guild_id, state in self._guild_states.items():
                if state.is_active():
                    active_guilds.append(guild_id)
        
        return active_guilds
    
    def get_streaming_guilds(self) -> List[int]:
        """
        Get list of guilds currently streaming.
        
        Returns:
            List of guild IDs currently streaming
        """
        streaming_guilds = []
        
        with self._global_lock:
            for guild_id, state in self._guild_states.items():
                if state.is_streaming():
                    streaming_guilds.append(guild_id)
        
        return streaming_guilds
    
    def get_all_guild_ids(self) -> List[int]:
        """
        Get list of all guilds with any state.
        
        Returns:
            List of all guild IDs with state
        """
        with self._global_lock:
            return list(self._guild_states.keys())
    
    def get_state_summary(self) -> Dict[str, Any]:
        """
        Get summary of all state.
        
        Returns:
            Summary dictionary with state statistics
        """
        with self._global_lock:
            total_guilds = len(self._guild_states)
            active_guilds = len([s for s in self._guild_states.values() if s.is_active()])
            streaming_guilds = len([s for s in self._guild_states.values() if s.is_streaming()])
            
            return {
                'total_guilds': total_guilds,
                'active_guilds': active_guilds,
                'streaming_guilds': streaming_guilds,
                'guild_ids': list(self._guild_states.keys())
            }
    
    def cleanup_stale_state(self, max_age_hours: float = 24.0) -> int:
        """
        Clean up stale guild state.
        
        Args:
            max_age_hours: Maximum age of inactive state before cleanup
            
        Returns:
            Number of states cleaned up
        """
        cleaned_count = 0
        cutoff_time = datetime.now(timezone.utc).timestamp() - (max_age_hours * 3600)
        
        guilds_to_remove = []
        
        with self._global_lock:
            for guild_id, state in self._guild_states.items():
                # Don't clean up active states
                if state.is_active():
                    continue
                
                # Check if state is stale
                if state.last_updated.timestamp() < cutoff_time:
                    guilds_to_remove.append(guild_id)
        
        # Remove stale states
        for guild_id in guilds_to_remove:
            if self.remove_guild_state(guild_id):
                cleaned_count += 1
        
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} stale guild states")
        
        return cleaned_count
    
    def start_background_cleanup(self, cleanup_interval_minutes: float = 60.0):
        """
        Start background cleanup task.
        
        Args:
            cleanup_interval_minutes: How often to run cleanup
        """
        if self._cleanup_task and not self._cleanup_task.done():
            logger.warning("Background cleanup already running")
            return
        
        async def cleanup_loop():
            while True:
                try:
                    await asyncio.sleep(cleanup_interval_minutes * 60)
                    self.cleanup_stale_state()
                except asyncio.CancelledError:
                    logger.info("Background cleanup task cancelled")
                    break
                except Exception as e:
                    logger.error(f"Error in background cleanup: {e}")
        
        self._cleanup_task = asyncio.create_task(cleanup_loop())
        logger.info(f"Started background cleanup (interval: {cleanup_interval_minutes} minutes)")
    
    def stop_background_cleanup(self):
        """Stop background cleanup task."""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            logger.info("Stopped background cleanup task")
    
    def add_state_change_listener(self, listener: Any):
        """
        Add a listener for state change events.
        
        Args:
            listener: Callable that accepts StateChangeEvent
        """
        self._event_listeners.append(listener)
    
    def remove_state_change_listener(self, listener: Any):
        """
        Remove a state change listener.
        
        Args:
            listener: Listener to remove
        """
        if listener in self._event_listeners:
            self._event_listeners.remove(listener)
    
    def _get_guild_lock(self, guild_id: int) -> Lock:
        """Get or create a lock for a specific guild"""
        with self._global_lock:
            if guild_id not in self._locks:
                self._locks[guild_id] = Lock()
            return self._locks[guild_id]
    
    def _fire_state_change_event(self, event: StateChangeEvent):
        """Fire state change event to all listeners"""
        for listener in self._event_listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    # Schedule async listeners
                    asyncio.create_task(listener(event))
                else:
                    # Call sync listeners directly
                    listener(event)
            except Exception as e:
                logger.error(f"Error in state change listener: {e}")
    
    def __len__(self) -> int:
        """Return number of managed guild states"""
        return len(self._guild_states)
    
    def __contains__(self, guild_id: int) -> bool:
        """Check if guild state exists"""
        return guild_id in self._guild_states


# Global state manager instance
_global_state_manager: Optional[StateManager] = None

def get_state_manager() -> StateManager:
    """Get the global state manager instance"""
    global _global_state_manager
    if _global_state_manager is None:
        _global_state_manager = StateManager()
    return _global_state_manager

def get_guild_state(guild_id: int, create_if_missing: bool = True) -> Optional[GuildState]:
    """Convenience function to get guild state"""
    return get_state_manager().get_guild_state(guild_id, create_if_missing)

def update_guild_state(guild_id: int, updates: Dict[str, Any]) -> GuildState:
    """Convenience function to update guild state"""
    return get_state_manager().update_guild_state(guild_id, updates)

def clear_guild_state(guild_id: int) -> bool:
    """Convenience function to clear guild state"""
    return get_state_manager().clear_guild_state(guild_id)
