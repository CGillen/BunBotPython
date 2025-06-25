"""
ConflictResolver for Cross-Platform Command Conflicts

Handles simultaneous commands from multiple platforms (Discord, Second Life)
to prevent conflicts and ensure consistent bot state.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import asyncio

from core import ServiceRegistry, StateManager

logger = logging.getLogger('integrations.sync.conflict_resolver')


class ConflictResolver:
    """
    Resolves command conflicts between different platforms.
    
    Ensures that simultaneous commands from Discord and Second Life
    don't interfere with each other and maintains consistent bot state.
    """
    
    def __init__(self, service_registry: ServiceRegistry):
        self.service_registry = service_registry
        self.state_manager = service_registry.get(StateManager)
        
        # Command tracking
        self.active_commands: Dict[int, Dict[str, Any]] = {}  # guild_id -> command info
        self.command_history: Dict[int, List[Dict[str, Any]]] = {}  # guild_id -> command list
        
        # Conflict resolution settings
        self.command_timeout = 30.0  # seconds
        self.priority_order = ['discord', 'second_life', 'api']
        self.max_history_length = 100
        
        logger.info("ConflictResolver initialized")
    
    async def request_command_execution(self, guild_id: int, command: str, 
                                      source: str, user_id: Optional[str] = None,
                                      parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Request execution of a command, handling conflicts.
        
        Args:
            guild_id: Discord guild ID
            command: Command to execute
            source: Platform source ('discord', 'second_life', 'api')
            user_id: User identifier
            parameters: Command parameters
            
        Returns:
            Dictionary with execution result and conflict resolution info
        """
        try:
            command_request = {
                'command': command,
                'source': source,
                'user_id': user_id,
                'parameters': parameters or {},
                'timestamp': datetime.now(),
                'request_id': f"{guild_id}_{command}_{datetime.now().timestamp()}"
            }
            
            logger.info(f"Command request: {command} from {source} for guild {guild_id}")
            
            # Check for active conflicting commands
            conflict_result = await self._check_for_conflicts(guild_id, command_request)
            
            if conflict_result['has_conflict']:
                logger.warning(f"Command conflict detected: {conflict_result['reason']}")
                return {
                    'success': False,
                    'conflict': True,
                    'reason': conflict_result['reason'],
                    'conflicting_command': conflict_result.get('conflicting_command'),
                    'resolution': conflict_result.get('resolution')
                }
            
            # No conflict - approve execution
            await self._register_active_command(guild_id, command_request)
            
            return {
                'success': True,
                'conflict': False,
                'approved': True,
                'request_id': command_request['request_id']
            }
            
        except Exception as e:
            logger.error(f"Error in command conflict resolution: {e}")
            return {
                'success': False,
                'conflict': False,
                'error': str(e)
            }
    
    async def command_completed(self, guild_id: int, request_id: str, 
                              success: bool, result: Optional[Dict[str, Any]] = None) -> None:
        """
        Mark a command as completed and remove from active tracking.
        
        Args:
            guild_id: Discord guild ID
            request_id: Command request ID
            success: Whether command completed successfully
            result: Command execution result
        """
        try:
            if guild_id in self.active_commands:
                active_cmd = self.active_commands[guild_id]
                if active_cmd.get('request_id') == request_id:
                    # Add to history
                    completion_record = {
                        **active_cmd,
                        'completed_at': datetime.now(),
                        'success': success,
                        'result': result
                    }
                    
                    await self._add_to_history(guild_id, completion_record)
                    
                    # Remove from active commands
                    del self.active_commands[guild_id]
                    
                    logger.info(f"Command {active_cmd['command']} completed for guild {guild_id}")
            
        except Exception as e:
            logger.error(f"Error marking command as completed: {e}")
    
    async def _check_for_conflicts(self, guild_id: int, command_request: Dict[str, Any]) -> Dict[str, Any]:
        """Check if the command request conflicts with active commands"""
        try:
            command = command_request['command']
            source = command_request['source']
            
            # Check for active command in this guild
            if guild_id in self.active_commands:
                active_cmd = self.active_commands[guild_id]
                
                # Check if active command has timed out
                elapsed = (datetime.now() - active_cmd['timestamp']).total_seconds()
                if elapsed > self.command_timeout:
                    # Active command timed out - remove it
                    logger.warning(f"Active command {active_cmd['command']} timed out for guild {guild_id}")
                    del self.active_commands[guild_id]
                else:
                    # Active command still valid - check for conflicts
                    conflict_type = self._get_conflict_type(command, active_cmd['command'])
                    
                    if conflict_type != 'none':
                        resolution = self._resolve_conflict(command_request, active_cmd)
                        
                        return {
                            'has_conflict': True,
                            'conflict_type': conflict_type,
                            'reason': f"Active {active_cmd['command']} from {active_cmd['source']}",
                            'conflicting_command': active_cmd,
                            'resolution': resolution
                        }
            
            return {'has_conflict': False}
            
        except Exception as e:
            logger.error(f"Error checking for conflicts: {e}")
            return {
                'has_conflict': True,
                'reason': f"Error during conflict check: {e}"
            }
    
    def _get_conflict_type(self, new_command: str, active_command: str) -> str:
        """Determine the type of conflict between commands"""
        
        # Streaming commands that conflict with each other
        streaming_commands = ['play', 'stop', 'pause', 'resume', 'skip']
        audio_commands = ['volume', 'eq', 'bass', 'treble']
        favorites_commands = ['favorite_add', 'favorite_remove', 'favorite_play']
        
        if new_command in streaming_commands and active_command in streaming_commands:
            if new_command == active_command:
                return 'duplicate'  # Same command
            else:
                return 'streaming'  # Different streaming commands
        
        if new_command in audio_commands and active_command in audio_commands:
            return 'audio'  # Audio setting conflicts
        
        if new_command in favorites_commands and active_command in favorites_commands:
            return 'favorites'  # Favorites management conflicts
        
        return 'none'  # No conflict
    
    def _resolve_conflict(self, new_request: Dict[str, Any], active_command: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve conflict based on priority rules"""
        
        new_source = new_request['source']
        active_source = active_command['source']
        
        # Check source priority
        try:
            new_priority = self.priority_order.index(new_source)
            active_priority = self.priority_order.index(active_source)
            
            if new_priority < active_priority:
                return {
                    'action': 'override',
                    'reason': f'{new_source} has higher priority than {active_source}'
                }
            elif new_priority > active_priority:
                return {
                    'action': 'reject',
                    'reason': f'{active_source} has higher priority than {new_source}'
                }
            else:
                # Same priority - use time-based resolution
                time_diff = (new_request['timestamp'] - active_command['timestamp']).total_seconds()
                
                if time_diff > 5.0:  # Allow override after 5 seconds
                    return {
                        'action': 'override',
                        'reason': 'Active command is old enough to override'
                    }
                else:
                    return {
                        'action': 'reject',
                        'reason': 'Active command is too recent to override'
                    }
        except ValueError:
            # Unknown source priority
            return {
                'action': 'reject',
                'reason': 'Unknown source priority'
            }
    
    async def _register_active_command(self, guild_id: int, command_request: Dict[str, Any]) -> None:
        """Register a command as active"""
        self.active_commands[guild_id] = command_request
        logger.debug(f"Registered active command: {command_request['command']} for guild {guild_id}")
    
    async def _add_to_history(self, guild_id: int, completion_record: Dict[str, Any]) -> None:
        """Add completed command to history"""
        if guild_id not in self.command_history:
            self.command_history[guild_id] = []
        
        history = self.command_history[guild_id]
        history.append(completion_record)
        
        # Trim history if too long
        if len(history) > self.max_history_length:
            history.pop(0)
    
    def get_active_commands(self) -> Dict[int, Dict[str, Any]]:
        """Get all currently active commands"""
        return dict(self.active_commands)
    
    def get_command_history(self, guild_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Get command history for a guild"""
        if guild_id in self.command_history:
            history = self.command_history[guild_id]
            return history[-limit:] if len(history) > limit else history
        return []
    
    def get_conflict_stats(self) -> Dict[str, Any]:
        """Get conflict resolution statistics"""
        total_active = len(self.active_commands)
        total_history = sum(len(hist) for hist in self.command_history.values())
        
        return {
            'active_commands': total_active,
            'guilds_with_active_commands': len(self.active_commands),
            'total_completed_commands': total_history,
            'guilds_with_history': len(self.command_history),
            'command_timeout_seconds': self.command_timeout,
            'priority_order': self.priority_order
        }
    
    async def cleanup_expired_commands(self) -> int:
        """Clean up expired active commands and return count removed"""
        try:
            expired_count = 0
            current_time = datetime.now()
            expired_guilds = []
            
            for guild_id, active_cmd in self.active_commands.items():
                elapsed = (current_time - active_cmd['timestamp']).total_seconds()
                if elapsed > self.command_timeout:
                    expired_guilds.append(guild_id)
                    expired_count += 1
            
            # Remove expired commands
            for guild_id in expired_guilds:
                expired_cmd = self.active_commands[guild_id]
                logger.warning(f"Cleaning up expired command: {expired_cmd['command']} for guild {guild_id}")
                del self.active_commands[guild_id]
            
            return expired_count
            
        except Exception as e:
            logger.error(f"Error cleaning up expired commands: {e}")
            return 0
