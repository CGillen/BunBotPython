"""
Command Processor for SL Bridge

Handles command processing and routing for Second Life integration
"""

import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from core import ServiceRegistry

logger = logging.getLogger('sl_bridge.commands')


@dataclass
class SLCommand:
    """
    Represents a command from Second Life.
    """
    command: str
    parameters: Dict[str, Any]
    guild_id: int
    object_key: Optional[str] = None
    avatar_key: Optional[str] = None
    avatar_name: Optional[str] = None
    timestamp: Optional[datetime] = None


class SLCommandProcessor:
    """
    Processes commands from Second Life objects and routes them
    to appropriate BunBot services.
    
    This provides a command-based interface that mirrors Discord
    slash commands but adapted for Second Life's HTTP request model.
    """
    
    def __init__(self, service_registry: ServiceRegistry):
        self.service_registry = service_registry
        
        # Command routing table
        self.command_handlers = {
            'play': self._handle_play_command,
            'stop': self._handle_stop_command,
            'volume': self._handle_volume_command,
            'favorites': self._handle_favorites_command,
            'status': self._handle_status_command,
            'help': self._handle_help_command
        }
        
        logger.info("SL Command Processor initialized")
    
    async def process_command(self, command: SLCommand) -> Dict[str, Any]:
        """
        Process a command from Second Life.
        
        Args:
            command: SL command to process
            
        Returns:
            Command result dictionary
        """
        try:
            logger.info(f"Processing SL command: {command.command} from guild {command.guild_id}")
            
            # Validate command
            if not command.command:
                return {
                    'success': False,
                    'error': 'No command specified',
                    'error_code': 'INVALID_COMMAND'
                }
            
            # Look up command handler
            handler = self.command_handlers.get(command.command.lower())
            if not handler:
                return {
                    'success': False,
                    'error': f'Unknown command: {command.command}',
                    'error_code': 'UNKNOWN_COMMAND',
                    'available_commands': list(self.command_handlers.keys())
                }
            
            # Execute command
            result = await handler(command)
            
            logger.info(f"SL command {command.command} completed with success: {result.get('success', False)}")
            return result
            
        except Exception as e:
            logger.error(f"Error processing SL command {command.command}: {e}")
            return {
                'success': False,
                'error': f'Internal error processing command: {str(e)}',
                'error_code': 'INTERNAL_ERROR'
            }
    
    async def _handle_play_command(self, command: SLCommand) -> Dict[str, Any]:
        """Handle play command from SL"""
        try:
            url = command.parameters.get('url')
            if not url:
                return {
                    'success': False,
                    'error': 'URL parameter is required for play command',
                    'error_code': 'MISSING_PARAMETER'
                }
            
            # Use stream adapter to play
            from .adapters import StreamAdapter
            stream_adapter = StreamAdapter(self.service_registry)
            
            result = await stream_adapter.play_stream(
                url=url,
                guild_id=command.guild_id
            )
            
            return {
                'success': result.get('success', False),
                'message': result.get('message', 'Stream started'),
                'data': result
            }
            
        except Exception as e:
            logger.error(f"Error in play command: {e}")
            return {
                'success': False,
                'error': f'Failed to start stream: {str(e)}',
                'error_code': 'PLAY_FAILED'
            }
    
    async def _handle_stop_command(self, command: SLCommand) -> Dict[str, Any]:
        """Handle stop command from SL"""
        try:
            from .adapters import StreamAdapter
            stream_adapter = StreamAdapter(self.service_registry)
            
            result = await stream_adapter.stop_stream(command.guild_id)
            
            return {
                'success': result.get('success', False),
                'message': result.get('message', 'Stream stopped'),
                'data': result
            }
            
        except Exception as e:
            logger.error(f"Error in stop command: {e}")
            return {
                'success': False,
                'error': f'Failed to stop stream: {str(e)}',
                'error_code': 'STOP_FAILED'
            }
    
    async def _handle_volume_command(self, command: SLCommand) -> Dict[str, Any]:
        """Handle volume command from SL"""
        try:
            volume = command.parameters.get('volume')
            if volume is None:
                return {
                    'success': False,
                    'error': 'Volume parameter is required',
                    'error_code': 'MISSING_PARAMETER'
                }
            
            try:
                volume = float(volume)
                if not 0.0 <= volume <= 1.0:
                    return {
                        'success': False,
                        'error': 'Volume must be between 0.0 and 1.0',
                        'error_code': 'INVALID_PARAMETER'
                    }
            except (ValueError, TypeError):
                return {
                    'success': False,
                    'error': 'Volume must be a number',
                    'error_code': 'INVALID_PARAMETER'
                }
            
            from .adapters import AudioAdapter
            audio_adapter = AudioAdapter(self.service_registry)
            
            result = await audio_adapter.set_volume(
                guild_id=command.guild_id,
                volume=volume
            )
            
            return {
                'success': result.get('success', False),
                'message': f'Volume set to {volume:.1%}',
                'data': result
            }
            
        except Exception as e:
            logger.error(f"Error in volume command: {e}")
            return {
                'success': False,
                'error': f'Failed to set volume: {str(e)}',
                'error_code': 'VOLUME_FAILED'
            }
    
    async def _handle_favorites_command(self, command: SLCommand) -> Dict[str, Any]:
        """Handle favorites command from SL"""
        try:
            action = command.parameters.get('action', 'list')
            
            if action == 'list':
                # Get favorites service
                from services.favorites_service import FavoritesService
                favorites_service = self.service_registry.get(FavoritesService)
                
                favorites = favorites_service.get_all_favorites(command.guild_id)
                
                return {
                    'success': True,
                    'message': f'Found {len(favorites)} favorites',
                    'data': {
                        'favorites': favorites[:20],  # Limit to 20
                        'total_count': len(favorites)
                    }
                }
            
            elif action == 'play':
                number = command.parameters.get('number')
                if number is None:
                    return {
                        'success': False,
                        'error': 'Favorite number is required for play action',
                        'error_code': 'MISSING_PARAMETER'
                    }
                
                from services.favorites_service import FavoritesService
                favorites_service = self.service_registry.get(FavoritesService)
                
                favorite = favorites_service.get_favorite_by_number(
                    guild_id=command.guild_id,
                    number=int(number)
                )
                
                if not favorite:
                    return {
                        'success': False,
                        'error': f'Favorite #{number} not found',
                        'error_code': 'FAVORITE_NOT_FOUND'
                    }
                
                # Play the favorite
                from .adapters import StreamAdapter
                stream_adapter = StreamAdapter(self.service_registry)
                
                result = await stream_adapter.play_stream(
                    url=favorite['stream_url'],
                    guild_id=command.guild_id
                )
                
                return {
                    'success': result.get('success', False),
                    'message': f"Playing favorite #{number}: {favorite['station_name']}",
                    'data': result
                }
            
            else:
                return {
                    'success': False,
                    'error': f'Unknown favorites action: {action}',
                    'error_code': 'INVALID_ACTION',
                    'available_actions': ['list', 'play']
                }
                
        except Exception as e:
            logger.error(f"Error in favorites command: {e}")
            return {
                'success': False,
                'error': f'Failed to process favorites command: {str(e)}',
                'error_code': 'FAVORITES_FAILED'
            }
    
    async def _handle_status_command(self, command: SLCommand) -> Dict[str, Any]:
        """Handle status command from SL"""
        try:
            from .adapters import StreamAdapter, AudioAdapter
            
            stream_adapter = StreamAdapter(self.service_registry)
            audio_adapter = AudioAdapter(self.service_registry)
            
            # Get stream status
            stream_status = await stream_adapter.get_stream_status(command.guild_id)
            
            # Get audio info
            audio_info = await audio_adapter.get_audio_info(command.guild_id)
            
            status = {
                'guild_id': command.guild_id,
                'stream': {
                    'is_playing': stream_status.get('is_playing', False),
                    'current_song': stream_status.get('current_song'),
                    'station_name': stream_status.get('station_name')
                },
                'audio': {
                    'volume': audio_info.get('volume', 0.8)
                },
                'timestamp': datetime.now().isoformat()
            }
            
            return {
                'success': True,
                'message': 'Status retrieved',
                'data': status
            }
            
        except Exception as e:
            logger.error(f"Error in status command: {e}")
            return {
                'success': False,
                'error': f'Failed to get status: {str(e)}',
                'error_code': 'STATUS_FAILED'
            }
    
    async def _handle_help_command(self, command: SLCommand) -> Dict[str, Any]:
        """Handle help command from SL"""
        try:
            help_info = {
                'available_commands': {
                    'play': {
                        'description': 'Play a stream',
                        'parameters': {'url': 'Stream URL to play'},
                        'example': 'play?url=http://stream.example.com'
                    },
                    'stop': {
                        'description': 'Stop current stream',
                        'parameters': {},
                        'example': 'stop'
                    },
                    'volume': {
                        'description': 'Set volume level',
                        'parameters': {'volume': 'Volume level (0.0 to 1.0)'},
                        'example': 'volume?volume=0.8'
                    },
                    'favorites': {
                        'description': 'Manage favorites',
                        'parameters': {
                            'action': 'list or play',
                            'number': 'Favorite number (for play action)'
                        },
                        'example': 'favorites?action=list'
                    },
                    'status': {
                        'description': 'Get current status',
                        'parameters': {},
                        'example': 'status'
                    },
                    'help': {
                        'description': 'Show this help',
                        'parameters': {},
                        'example': 'help'
                    }
                },
                'api_info': {
                    'base_url': '/api/v1',
                    'authentication': 'Bearer token required',
                    'response_format': 'JSON'
                }
            }
            
            return {
                'success': True,
                'message': 'Help information',
                'data': help_info
            }
            
        except Exception as e:
            logger.error(f"Error in help command: {e}")
            return {
                'success': False,
                'error': f'Failed to get help: {str(e)}',
                'error_code': 'HELP_FAILED'
            }
    
    def get_command_stats(self) -> Dict[str, Any]:
        """Get command processor statistics"""
        return {
            'available_commands': len(self.command_handlers),
            'command_list': list(self.command_handlers.keys()),
            'processor_status': 'active'
        }
