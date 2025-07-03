"""
FastAPI Bridge Server for Second Life Integration

Provides a comprehensive REST API server that enables Second Life objects
to control BunBot with full feature parity to Discord commands.

Key Features:
- RESTful API with comprehensive endpoints
- Real-time WebSocket communication
- JWT-based authentication system
- Rate limiting and security middleware
- Integration with all Phase 1-4 systems
- Cross-platform state synchronization
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import uvicorn
from contextlib import asynccontextmanager

# Phase 1 Infrastructure
from core.service_registry import ServiceRegistry
from core.state_manager import StateManager
from core.event_bus import EventBus
from core.config_manager import ConfigurationManager

# Phase 2 Monitoring
from monitoring.health_monitor import HealthMonitor
from monitoring.metrics_collector import MetricsCollector

# Phase 3 Audio
from audio import IAudioProcessor, IVolumeManager, IEffectsChain

# SL Bridge Components
from .middleware.auth_middleware import verify_token, SLAuthMiddleware
from .middleware.rate_limiter import RateLimitMiddleware
from .routes import audio_routes, favorites_routes, stream_routes, status_routes, settings_routes
from .models.response_models import SLResponse, ErrorResponse
from .security.token_manager import TokenManager
from .ui.response_formatter import ResponseFormatter

logger = logging.getLogger('sl_bridge.server')

class SLBridgeServer:
    """
    Main FastAPI server for Second Life integration.
    
    Provides comprehensive REST API and WebSocket interfaces for
    cross-platform bot control and synchronization.
    """
    
    def __init__(self, service_registry: ServiceRegistry):
        self.service_registry = service_registry
        self.state_manager = service_registry.get(StateManager)
        self.event_bus = service_registry.get(EventBus)
        self.config_manager = service_registry.get(ConfigurationManager)
        self.health_monitor = service_registry.get_optional(HealthMonitor)
        self.metrics_collector = service_registry.get_optional(MetricsCollector)
        
        # Audio services
        self.audio_processor = service_registry.get_optional(IAudioProcessor)
        self.volume_manager = service_registry.get_optional(IVolumeManager)
        self.effects_chain = service_registry.get_optional(IEffectsChain)
        
        # SL Bridge services
        self.token_manager = TokenManager(service_registry)
        self.response_formatter = ResponseFormatter()
        
        # Server configuration
        self.host = "0.0.0.0"
        self.port = 8080
        self.app: Optional[FastAPI] = None
        self.server_task: Optional[asyncio.Task] = None
        
        # WebSocket management
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_metadata: Dict[str, Dict[str, Any]] = {}
        
        # Server state
        self.is_running = False
        self.start_time: Optional[datetime] = None
        
        logger.info("SL Bridge Server initialized")
    
    async def initialize(self) -> None:
        """Initialize the FastAPI server and configure middleware"""
        try:
            # Create FastAPI app with lifespan management
            @asynccontextmanager
            async def lifespan(app: FastAPI):
                # Startup
                await self._startup()
                yield
                # Shutdown
                await self._shutdown()
            
            self.app = FastAPI(
                title="BunBot Second Life Bridge",
                description="REST API for Second Life integration with BunBot Discord radio bot",
                version="1.0.0",
                docs_url="/docs",
                redoc_url="/redoc",
                lifespan=lifespan
            )
            
            # Configure CORS
            self.app.add_middleware(
                CORSMiddleware,
                allow_origins=["*"],  # Configure appropriately for production
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )
            
            # Add custom middleware
            self.app.add_middleware(SLAuthMiddleware, token_manager=self.token_manager)
            self.app.add_middleware(RateLimitMiddleware, service_registry=self.service_registry)
            
            # Include API routes
            self.app.include_router(audio_routes.router, prefix="/api/v1/audio", tags=["audio"])
            self.app.include_router(favorites_routes.router, prefix="/api/v1/favorites", tags=["favorites"])
            self.app.include_router(stream_routes.router, prefix="/api/v1/streams", tags=["streams"])
            self.app.include_router(status_routes.router, prefix="/api/v1/status", tags=["status"])
            self.app.include_router(settings_routes.router, prefix="/api/v1/settings", tags=["settings"])
            
            # Add WebSocket endpoint
            self.app.websocket("/ws/{token}")(self.websocket_endpoint)
            
            # Add health check endpoint
            @self.app.get("/health")
            async def health_check():
                return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}
            
            # Add root endpoint
            @self.app.get("/")
            async def root():
                return {
                    "service": "BunBot Second Life Bridge",
                    "version": "1.0.0",
                    "status": "running" if self.is_running else "stopped",
                    "uptime_seconds": (datetime.now(timezone.utc) - self.start_time).total_seconds() if self.start_time else 0
                }
            
            logger.info("FastAPI app initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing FastAPI server: {e}")
            raise
    
    async def start(self) -> None:
        """Start the FastAPI server"""
        try:
            if self.is_running:
                logger.warning("SL Bridge Server is already running")
                return
            
            await self.initialize()
            
            # Configure uvicorn server
            config = uvicorn.Config(
                app=self.app,
                host=self.host,
                port=self.port,
                log_level="info",
                access_log=True
            )
            
            server = uvicorn.Server(config)
            
            # Start server in background task
            self.server_task = asyncio.create_task(server.serve())
            
            self.is_running = True
            self.start_time = datetime.now(timezone.utc)
            
            # Register with health monitor
            await self.health_monitor.register_component(
                "sl_bridge_server",
                self._health_check_callback
            )
            
            # Emit startup event
            await self.event_bus.emit("sl_bridge_started", {
                "timestamp": self.start_time.isoformat(),
                "host": self.host,
                "port": self.port
            })
            
            logger.info(f"SL Bridge Server started on {self.host}:{self.port}")
            
        except Exception as e:
            logger.error(f"Error starting SL Bridge Server: {e}")
            self.is_running = False
            raise
    
    async def stop(self) -> None:
        """Stop the FastAPI server"""
        try:
            if not self.is_running:
                logger.warning("SL Bridge Server is not running")
                return
            
            # Close all WebSocket connections
            for connection_id, websocket in self.active_connections.items():
                try:
                    await websocket.close(code=1001, reason="Server shutting down")
                except Exception as e:
                    logger.warning(f"Error closing WebSocket connection {connection_id}: {e}")
            
            self.active_connections.clear()
            self.connection_metadata.clear()
            
            # Stop server task
            if self.server_task:
                self.server_task.cancel()
                try:
                    await self.server_task
                except asyncio.CancelledError:
                    pass
            
            # Unregister from health monitor
            await self.health_monitor.unregister_component("sl_bridge_server")
            
            # Emit shutdown event
            await self.event_bus.emit("sl_bridge_stopped", {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "uptime_seconds": (datetime.now(timezone.utc) - self.start_time).total_seconds() if self.start_time else 0
            })
            
            self.is_running = False
            self.start_time = None
            
            logger.info("SL Bridge Server stopped")
            
        except Exception as e:
            logger.error(f"Error stopping SL Bridge Server: {e}")
            raise
    
    async def websocket_endpoint(self, websocket: WebSocket, token: str):
        """Handle WebSocket connections for real-time communication"""
        connection_id = None
        try:
            # Verify token
            token_data = await self.token_manager.verify_token(token)
            if not token_data:
                await websocket.close(code=4001, reason="Invalid token")
                return
            
            # Accept connection
            await websocket.accept()
            connection_id = f"ws_{len(self.active_connections)}_{datetime.now().timestamp()}"
            
            # Store connection
            self.active_connections[connection_id] = websocket
            self.connection_metadata[connection_id] = {
                "guild_id": token_data.get("guild_id"),
                "permissions": token_data.get("permissions", []),
                "connected_at": datetime.now(timezone.utc).isoformat(),
                "last_activity": datetime.now(timezone.utc).isoformat()
            }
            
            logger.info(f"WebSocket connection established: {connection_id}")
            
            # Send welcome message
            await websocket.send_json({
                "type": "connection_established",
                "connection_id": connection_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            
            # Listen for messages
            while True:
                data = await websocket.receive_json()
                await self._handle_websocket_message(connection_id, data)
                
                # Update last activity
                self.connection_metadata[connection_id]["last_activity"] = datetime.now(timezone.utc).isoformat()
        
        except WebSocketDisconnect:
            logger.info(f"WebSocket connection disconnected: {connection_id}")
        except Exception as e:
            logger.error(f"Error in WebSocket connection {connection_id}: {e}")
        finally:
            # Clean up connection
            if connection_id:
                self.active_connections.pop(connection_id, None)
                self.connection_metadata.pop(connection_id, None)
    
    async def _handle_websocket_message(self, connection_id: str, data: Dict[str, Any]) -> None:
        """Handle incoming WebSocket messages"""
        try:
            message_type = data.get("type")
            
            if message_type == "ping":
                # Respond to ping with pong
                await self.active_connections[connection_id].send_json({
                    "type": "pong",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
            
            elif message_type == "subscribe_events":
                # Subscribe to specific events
                events = data.get("events", [])
                metadata = self.connection_metadata[connection_id]
                metadata["subscribed_events"] = events
                
                await self.active_connections[connection_id].send_json({
                    "type": "subscription_confirmed",
                    "events": events,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
            
            else:
                logger.warning(f"Unknown WebSocket message type: {message_type}")
        
        except Exception as e:
            logger.error(f"Error handling WebSocket message from {connection_id}: {e}")
    
    async def broadcast_event(self, event_type: str, data: Dict[str, Any], guild_id: Optional[int] = None) -> None:
        """Broadcast event to subscribed WebSocket connections"""
        try:
            message = {
                "type": "event",
                "event_type": event_type,
                "data": data,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            # Send to relevant connections
            for connection_id, websocket in self.active_connections.items():
                try:
                    metadata = self.connection_metadata.get(connection_id, {})
                    
                    # Check if connection should receive this event
                    if guild_id and metadata.get("guild_id") != guild_id:
                        continue
                    
                    subscribed_events = metadata.get("subscribed_events", [])
                    if subscribed_events and event_type not in subscribed_events:
                        continue
                    
                    await websocket.send_json(message)
                    
                except Exception as e:
                    logger.warning(f"Error sending event to WebSocket {connection_id}: {e}")
        
        except Exception as e:
            logger.error(f"Error broadcasting event {event_type}: {e}")
    
    async def _startup(self) -> None:
        """Server startup tasks"""
        try:
            # Register event listeners for broadcasting
            await self.event_bus.subscribe("audio_*", self._on_audio_event)
            await self.event_bus.subscribe("stream_*", self._on_stream_event)
            await self.event_bus.subscribe("favorites_*", self._on_favorites_event)
            
            logger.info("SL Bridge Server startup completed")
            
        except Exception as e:
            logger.error(f"Error during server startup: {e}")
            raise
    
    async def _shutdown(self) -> None:
        """Server shutdown tasks"""
        try:
            # Unsubscribe from events
            await self.event_bus.unsubscribe("audio_*", self._on_audio_event)
            await self.event_bus.unsubscribe("stream_*", self._on_stream_event)
            await self.event_bus.unsubscribe("favorites_*", self._on_favorites_event)
            
            logger.info("SL Bridge Server shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during server shutdown: {e}")
    
    async def _on_audio_event(self, event: str, data: Dict[str, Any]) -> None:
        """Handle audio events for WebSocket broadcasting"""
        guild_id = data.get("guild_id")
        await self.broadcast_event(event, data, guild_id)
    
    async def _on_stream_event(self, event: str, data: Dict[str, Any]) -> None:
        """Handle stream events for WebSocket broadcasting"""
        guild_id = data.get("guild_id")
        await self.broadcast_event(event, data, guild_id)
    
    async def _on_favorites_event(self, event: str, data: Dict[str, Any]) -> None:
        """Handle favorites events for WebSocket broadcasting"""
        guild_id = data.get("guild_id")
        await self.broadcast_event(event, data, guild_id)
    
    async def _health_check_callback(self) -> Dict[str, Any]:
        """Health check callback for Phase 2 monitoring"""
        try:
            return {
                "status": "healthy" if self.is_running else "unhealthy",
                "uptime_seconds": (datetime.now(timezone.utc) - self.start_time).total_seconds() if self.start_time else 0,
                "active_connections": len(self.active_connections),
                "host": self.host,
                "port": self.port
            }
        except Exception as e:
            logger.error(f"Error in health check: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    def get_server_info(self) -> Dict[str, Any]:
        """Get current server information"""
        return {
            "status": "running" if self.is_running else "stopped",
            "host": self.host,
            "port": self.port,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "uptime_seconds": (datetime.now(timezone.utc) - self.start_time).total_seconds() if self.start_time else 0,
            "active_connections": len(self.active_connections),
            "total_connections": len(self.connection_metadata)
        }
