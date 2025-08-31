"""
SLBridgeService - Service wrapper for SLBridgeServer integration

Provides service-oriented integration of the SL Bridge server into the
BunBot application architecture with proper lifecycle management.
"""

import logging
import asyncio
from typing import Dict, Any, Optional, List
import os

from core import ServiceRegistry
from .server import SLBridgeServer
from .state_sync import StateSynchronizer
from .commands import SLCommandProcessor

logger = logging.getLogger('integrations.sl_bridge.service')


class SLBridgeService:
    """
    Service wrapper for SL Bridge integration.
    
    Manages the FastAPI server, state synchronization, and command processing
    as an integrated service within the BunBot application.
    """
    
    def __init__(self, service_registry: ServiceRegistry):
        self.service_registry = service_registry
        self.server: Optional[SLBridgeServer] = None
        self.state_synchronizer: Optional[StateSynchronizer] = None
        self.command_processor: Optional[SLCommandProcessor] = None
        
        self.is_running = False
        self.is_enabled = self._check_if_enabled()
        
        # Configuration from environment
        self.host = os.getenv('SL_BRIDGE_HOST', '0.0.0.0')
        self.port = int(os.getenv('SL_BRIDGE_PORT', '8080'))
        self.jwt_secret = os.getenv('SL_BRIDGE_JWT_SECRET', 'dev_secret_change_in_production')
        self.api_keys = os.getenv('SL_BRIDGE_API_KEYS', 'dev_key_123').split(',')
        
        logger.info(f"SLBridgeService initialized - Enabled: {self.is_enabled}")
    
    def _check_if_enabled(self) -> bool:
        """Check if SL Bridge is enabled via environment variables"""
        enabled = os.getenv('SL_BRIDGE_ENABLED', 'false').lower() == 'true'
        
        # Also check if required dependencies are available
        try:
            import fastapi
            import uvicorn
            return enabled
        except ImportError:
            if enabled:
                logger.warning("SL Bridge enabled but FastAPI/Uvicorn not installed")
            return False
    
    async def start(self) -> None:
        """Start the SL Bridge service"""
        try:
            if not self.is_enabled:
                logger.info("SL Bridge is disabled - skipping startup")
                return
            
            if self.is_running:
                logger.warning("SL Bridge service is already running")
                return
            
            logger.info("Starting SL Bridge service...")
            
            # Initialize components
            await self._initialize_components()
            
            # Start the FastAPI server
            await self._start_server()
            
            self.is_running = True
            logger.info(f"SL Bridge service started on {self.host}:{self.port}")
            
        except Exception as e:
            logger.error(f"Failed to start SL Bridge service: {e}")
            raise
    
    async def stop(self) -> None:
        """Stop the SL Bridge service"""
        try:
            if not self.is_running:
                return
            
            logger.info("Stopping SL Bridge service...")
            
            # Stop components in reverse order
            if self.state_synchronizer:
                await self.state_synchronizer.shutdown()
            
            if self.server:
                await self.server.stop()
            
            self.is_running = False
            logger.info("SL Bridge service stopped")
            
        except Exception as e:
            logger.error(f"Error stopping SL Bridge service: {e}")
    
    async def _initialize_components(self) -> None:
        """Initialize SL Bridge components"""
        try:
            # Initialize state synchronizer
            self.state_synchronizer = StateSynchronizer(self.service_registry)
            await self.state_synchronizer.initialize()
            
            # Initialize command processor
            self.command_processor = SLCommandProcessor(self.service_registry)
            
            # Initialize server with configuration
            server_config = {
                'host': self.host,
                'port': self.port,
                'jwt_secret': self.jwt_secret,
                'api_keys': self.api_keys,
                'command_processor': self.command_processor,
                'state_synchronizer': self.state_synchronizer
            }
            
            self.server = SLBridgeServer(self.service_registry, server_config)
            
            logger.info("SL Bridge components initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize SL Bridge components: {e}")
            raise
    
    async def _start_server(self) -> None:
        """Start the FastAPI server"""
        try:
            if self.server:
                # Start server in background task to avoid blocking
                asyncio.create_task(self.server.start())
                
                # Give server time to start
                await asyncio.sleep(1)
                
                logger.info("FastAPI server started in background")
            
        except Exception as e:
            logger.error(f"Failed to start FastAPI server: {e}")
            raise
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get comprehensive status of the SL Bridge service"""
        try:
            status = {
                'enabled': self.is_enabled,
                'running': self.is_running,
                'host': self.host,
                'port': self.port,
                'components': {
                    'server': self.server is not None,
                    'state_synchronizer': self.state_synchronizer is not None,
                    'command_processor': self.command_processor is not None
                }
            }
            
            # Add component-specific status
            if self.server:
                status['server_status'] = self.server.get_server_status()
            
            if self.state_synchronizer:
                status['sync_stats'] = self.state_synchronizer.get_sync_stats()
            
            if self.command_processor:
                status['command_stats'] = self.command_processor.get_command_stats()
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting service status: {e}")
            return {
                'enabled': self.is_enabled,
                'running': False,
                'error': str(e)
            }
    
    async def process_sl_command(self, command: str, parameters: Dict[str, Any],
                               guild_id: int, **kwargs) -> Dict[str, Any]:
        """
        Process a command from Second Life.
        
        Args:
            command: Command to execute
            parameters: Command parameters
            guild_id: Discord guild ID
            **kwargs: Additional command context
            
        Returns:
            Command execution result
        """
        try:
            if not self.command_processor:
                return {
                    'success': False,
                    'error': 'Command processor not available',
                    'error_code': 'SERVICE_UNAVAILABLE'
                }
            
            from .commands import SLCommand
            sl_command = SLCommand(
                command=command,
                parameters=parameters,
                guild_id=guild_id,
                **kwargs
            )
            
            return await self.command_processor.process_command(sl_command)
            
        except Exception as e:
            logger.error(f"Error processing SL command {command}: {e}")
            return {
                'success': False,
                'error': f'Internal error: {str(e)}',
                'error_code': 'INTERNAL_ERROR'
            }
    
    async def sync_state_to_sl(self, guild_id: int, state_type: str,
                             state_data: Dict[str, Any]) -> None:
        """Sync state changes to Second Life"""
        try:
            if self.state_synchronizer:
                await self.state_synchronizer.sync_state_to_sl(
                    guild_id, state_type, state_data
                )
            
        except Exception as e:
            logger.error(f"Error syncing state to SL: {e}")
    
    async def register_sl_connection(self, guild_id: int, connection_id: str,
                                   metadata: Dict[str, Any] = None) -> None:
        """Register a new SL connection"""
        try:
            if self.state_synchronizer:
                self.state_synchronizer.register_sl_connection(
                    guild_id, connection_id, metadata
                )
            
        except Exception as e:
            logger.error(f"Error registering SL connection: {e}")
    
    async def unregister_sl_connection(self, guild_id: int, connection_id: str) -> None:
        """Unregister an SL connection"""
        try:
            if self.state_synchronizer:
                self.state_synchronizer.unregister_sl_connection(guild_id, connection_id)
            
        except Exception as e:
            logger.error(f"Error unregistering SL connection: {e}")
    
    def get_api_endpoints(self) -> List[Dict[str, Any]]:
        """Get list of available API endpoints"""
        try:
            if self.server and hasattr(self.server, 'get_api_endpoints'):
                return self.server.get_api_endpoints()
            
            # Fallback endpoint list
            return [
                {'path': '/api/v1/streams/play', 'method': 'POST', 'description': 'Play a stream'},
                {'path': '/api/v1/streams/stop', 'method': 'POST', 'description': 'Stop current stream'},
                {'path': '/api/v1/audio/volume', 'method': 'POST', 'description': 'Set volume'},
                {'path': '/api/v1/favorites/list', 'method': 'GET', 'description': 'List favorites'},
                {'path': '/api/v1/status/health', 'method': 'GET', 'description': 'Health check'},
                {'path': '/api/v1/settings/bridge', 'method': 'GET', 'description': 'Bridge settings'}
            ]
            
        except Exception as e:
            logger.error(f"Error getting API endpoints: {e}")
            return []
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check of the SL Bridge service"""
        try:
            health_status = {
                'service': 'healthy' if self.is_running else 'stopped',
                'enabled': self.is_enabled,
                'timestamp': asyncio.get_event_loop().time()
            }
            
            # Check server health
            if self.server:
                try:
                    server_health = await self.server.health_check()
                    health_status['server'] = server_health
                except Exception as e:
                    health_status['server'] = {'status': 'error', 'error': str(e)}
            
            # Check state synchronizer health
            if self.state_synchronizer:
                sync_stats = self.state_synchronizer.get_sync_stats()
                health_status['state_sync'] = {
                    'status': 'healthy' if sync_stats.get('sync_enabled') else 'disabled',
                    'active_guilds': sync_stats.get('active_guilds', 0),
                    'total_connections': sync_stats.get('total_connections', 0)
                }
            
            return health_status
            
        except Exception as e:
            logger.error(f"Error in health check: {e}")
            return {
                'service': 'error',
                'error': str(e),
                'timestamp': asyncio.get_event_loop().time()
            }
