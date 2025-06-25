"""
BunBot Application
"""

import logging
import logging.handlers
import os
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional
import discord
from discord.ext import commands, tasks

from core import ServiceRegistry, ServiceLifetime, StateManager, EventBus, ConfigurationManager
from .error_service import ErrorService
from .ui_service import UIService
from .stream_service import StreamService
from .favorites_service import FavoritesService
from .command_service import CommandService
from .monitoring_service import MonitoringService
from audio import IAudioProcessor, IVolumeManager, IEffectsChain, IAudioMixer
from monitoring.interfaces import IHealthMonitor, IMetricsCollector, IAlertManager

# Import existing modules we need to integrate
import urllib_hack
from dotenv import load_dotenv

logger = logging.getLogger('services.bunbot_application')

class BunBotApplication:
    """
    Main BunBot application that orchestrates all services.
    
    Provides clean separation between Discord.py bot management
    and business logic while maintaining the existing functionality.
    """
    
    def __init__(self, service_registry: Optional[ServiceRegistry] = None):
        self.service_registry = service_registry or ServiceRegistry()
        self.bot: Optional[commands.AutoShardedBot] = None
        self._startup_complete = False
        
        # Load environment variables
        load_dotenv()
        
        # Configuration from environment
        self.bot_token = os.getenv('BOT_TOKEN')
        self.log_file_path = Path(os.getenv('LOG_FILE_PATH', './')).joinpath('log.txt')
        self.log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
        self.tls_verify = bool(os.environ.get('TLS_VERIFY', True))
        self.demo_mode = os.getenv('DEMO_MODE', 'False').lower() == 'true'
        
        # Clustering configuration
        self.cluster_id = int(os.environ.get('CLUSTER_ID', 0))
        self.total_clusters = int(os.environ.get('TOTAL_CLUSTERS', 1))
        self.total_shards = int(os.environ.get('TOTAL_SHARDS', 1))
        
        logger.info("BunBotApplication initialized")
    
    async def initialize(self) -> None:
        """Initialize all services and register them with the service registry"""
        try:
            logger.info("Initializing BunBotApplication services...")
            
            # Register core services
            await self._register_core_services()
            
            # Register business logic services
            await self._register_business_services()
            
            # Initialize Discord bot
            await self._initialize_discord_bot()
            
            # Register monitoring services if available
            await self._register_monitoring_services()
            
            logger.info("BunBotApplication services initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize BunBotApplication: {e}")
            raise
    
    async def run(self) -> None:
        """Run the bot application"""
        try:
            if not self.bot_token:
                raise ValueError("BOT_TOKEN environment variable is required")
            
            # Initialize services
            await self.initialize()
            
            # Start the Discord bot
            logger.info("Starting Discord bot...")
            await self.bot.start(self.bot_token)
            
        except Exception as e:
            logger.error(f"Failed to run BunBotApplication: {e}")
            raise
    
    def run_sync(self) -> None:
        """Run the bot application synchronously (for main entry point)"""
        try:
            asyncio.run(self.run())
        except KeyboardInterrupt:
            logger.info("Bot shutdown requested")
        except Exception as e:
            logger.error(f"Bot application error: {e}")
            raise
    
    async def shutdown(self) -> None:
        """Gracefully shutdown the application"""
        try:
            logger.info("Shutting down BunBotApplication...")
            
            # Stop monitoring tasks
            monitoring_service = self.service_registry.get_optional(MonitoringService)
            if monitoring_service and hasattr(monitoring_service, 'stop_monitoring'):
                await monitoring_service.stop_monitoring()
            
            # Close Discord bot
            if self.bot:
                await self.bot.close()
            
            logger.info("BunBotApplication shutdown complete")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
    
    async def _register_core_services(self) -> None:
        """Register core infrastructure services"""
        try:
            # Register ServiceRegistry itself so it can be retrieved by other services
            self.service_registry.register_instance(ServiceRegistry, self.service_registry)
            
            # Register core services
            self.service_registry.register(ConfigurationManager, lifetime=ServiceLifetime.SINGLETON)
            self.service_registry.register(StateManager, lifetime=ServiceLifetime.SINGLETON)
            self.service_registry.register(EventBus, lifetime=ServiceLifetime.SINGLETON)
            
            logger.debug("Core services registered")
            
        except Exception as e:
            logger.error(f"Failed to register core services: {e}")
            raise
    
    async def _register_business_services(self) -> None:
        """Register business logic services"""
        try:
            # Register business services with proper dependencies
            self.service_registry.register(ErrorService, lifetime=ServiceLifetime.SINGLETON)
            self.service_registry.register(UIService, lifetime=ServiceLifetime.SINGLETON)
            self.service_registry.register(StreamService, lifetime=ServiceLifetime.SINGLETON)
            self.service_registry.register(FavoritesService, lifetime=ServiceLifetime.SINGLETON)
            
            # Register audio processing services
            await self._register_audio_services()
            
            # Register CommandService before sync
            self.service_registry.register(CommandService, lifetime=ServiceLifetime.SINGLETON)
            
            # Register SL Bridge service if available
            await self._register_sl_bridge_service()
            
            logger.debug("Business services registered")
            
        except Exception as e:
            logger.error(f"Failed to register business services: {e}")
            raise
    
    async def _register_monitoring_services(self) -> None:
        """Register monitoring services if available"""
        try:
            # Try to register monitoring services
            try:
                from monitoring.metrics_collector import MetricsCollector
                from monitoring.alert_manager import AlertManager
                from monitoring.health_monitor import HealthMonitor
                
                # Register MetricsCollector with custom factory to pass service_registry
                def create_metrics_collector(state_manager, event_bus, config_manager):
                    return MetricsCollector(state_manager, event_bus, config_manager, 
                                          service_registry=self.service_registry)
                
                self.service_registry.register(
                    IMetricsCollector, 
                    factory=create_metrics_collector,
                    lifetime=ServiceLifetime.SINGLETON
                )
                
                # Register AlertManager with custom factory to pass service_registry  
                def create_alert_manager(state_manager, event_bus, config_manager):
                    return AlertManager(state_manager, event_bus, config_manager,
                                      service_registry=self.service_registry)
                
                self.service_registry.register(
                    IAlertManager,
                    factory=create_alert_manager, 
                    lifetime=ServiceLifetime.SINGLETON
                )
                
                # Register HealthMonitor 
                self.service_registry.register(
                    IHealthMonitor, 
                    HealthMonitor, 
                    lifetime=ServiceLifetime.SINGLETON
                )
                
                logger.debug("Monitoring services registered")
                
            except ImportError as e:
                logger.warning(f"Monitoring services not available - running without monitoring: {e}")
            
        except Exception as e:
            logger.error(f"Failed to register monitoring services: {e}")
            # Don't raise - monitoring is optional
    
    async def _register_audio_services(self) -> None:
        """Register audio processing services if available"""
        try:
            # Check for required dependencies first
            missing_deps = []
            try:
                import numpy
            except ImportError:
                missing_deps.append("numpy")
            
            try:
                import scipy
                import scipy.signal  # Specifically check for signal processing
            except ImportError:
                missing_deps.append("scipy")
            
            if missing_deps:
                logger.warning(f"Audio processing disabled - missing dependencies: {', '.join(missing_deps)}")
                logger.info("Install missing dependencies with: pip install numpy scipy")
                return
            
            # Try to register audio services
            try:
                from audio.audio_processor import AudioProcessor
                from audio.volume_manager import VolumeManager
                from audio.effects_chain import EffectsChain
                from audio.mixer import AudioMixer
                
                # Test that services can be imported and instantiated
                logger.info("Registering audio processing services...")
                
                # Register audio services with proper interface-to-implementation mapping
                self.service_registry.register(
                    IAudioProcessor, 
                    AudioProcessor, 
                    lifetime=ServiceLifetime.SINGLETON
                )
                
                # Register VolumeManager with custom factory to pass service_registry
                def create_volume_manager(state_manager: StateManager, event_bus: EventBus, 
                                        config_manager: ConfigurationManager):
                    # Capture service_registry in closure to fix scope issue
                    service_registry = self.service_registry
                    return VolumeManager(state_manager, event_bus, config_manager, service_registry)
                
                self.service_registry.register(
                    IVolumeManager, 
                    factory=create_volume_manager,
                    lifetime=ServiceLifetime.SINGLETON
                )
                
                self.service_registry.register(
                    IEffectsChain, 
                    EffectsChain, 
                    lifetime=ServiceLifetime.SINGLETON
                )
                
                self.service_registry.register(
                    IAudioMixer, 
                    AudioMixer, 
                    lifetime=ServiceLifetime.SINGLETON
                )
                
                # Test that services can be resolved
                try:
                    volume_manager = self.service_registry.get(IVolumeManager)
                    effects_chain = self.service_registry.get(IEffectsChain)
                    audio_processor = self.service_registry.get(IAudioProcessor)
                    logger.info("✅ Audio processing services registered and validated successfully")
                except Exception as resolve_error:
                    logger.error(f"❌ Audio services registered but failed validation: {resolve_error}")
                    raise resolve_error
                
            except ImportError as e:
                logger.warning(f"Audio processing services not available - missing audio modules: {e}")
                logger.info("Audio commands will show 'not available' message")
            except Exception as e:
                logger.error(f"Failed to register audio services: {e}")
                logger.info("Audio commands will show 'not available' message")
            
        except Exception as e:
            logger.error(f"Critical error in audio service registration: {e}")
            # Don't raise - audio enhancement is optional
    
    async def _register_sl_bridge_service(self) -> None:
        """Register SL Bridge service if available"""
        try:
            # Try to register SL Bridge service
            try:
                from integrations.sl_bridge.sl_bridge_service import SLBridgeService
                self.service_registry.register(SLBridgeService, lifetime=ServiceLifetime.SINGLETON)
                logger.debug("SL Bridge service registered")
            except ImportError as e:
                logger.info(f"SL Bridge not available - running without Second Life integration: {e}")
            
        except Exception as e:
            logger.error(f"Failed to register SL Bridge service: {e}")
            # Don't raise - SL Bridge is optional
    
    async def _initialize_discord_bot(self) -> None:
        """Initialize Discord bot with proper configuration"""
        try:
            # Calculate shard IDs for clustering
            shards_per_cluster = int(self.total_shards / self.total_clusters)
            shard_ids = [
                i for i in range(
                    self.cluster_id * shards_per_cluster,
                    (self.cluster_id * shards_per_cluster) + shards_per_cluster
                ) if i < self.total_shards
            ]
            
            # Set up Discord intents
            intents = discord.Intents.default()
            intents.message_content = True
            
            # Create bot instance
            self.bot = commands.AutoShardedBot(
                command_prefix='/',
                case_insensitive=True,
                intents=intents,
                shard_ids=shard_ids,
                shard_count=self.total_shards
            )
            
            # Add cluster information as custom attributes
            setattr(self.bot, 'cluster_id', self.cluster_id)
            setattr(self.bot, 'total_shards', self.total_shards)
            
            # Register bot instance with service registry
            self.service_registry.register_instance(commands.AutoShardedBot, self.bot)
            
            # Set up bot event handlers
            await self._setup_bot_events()
            
            # Initialize logging for Discord.py
            await self._setup_logging()
            
            logger.info(f"Discord bot initialized - Cluster {self.cluster_id}, Shards: {shard_ids}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Discord bot: {e}")
            raise
    
    async def _setup_bot_events(self) -> None:
        """Set up Discord bot event handlers"""
        if not self.bot:
            raise ValueError("Bot instance not initialized")
            
        @self.bot.event
        async def on_ready():
            """Handle bot ready event"""
            try:
                if not self.bot:
                    logger.error("Bot instance is None in on_ready")
                    return
                    
                # Initialize urllib hack for ICY streams
                urllib_hack.init_urllib_hack(self.tls_verify)
                
                # Register commands BEFORE syncing with Discord
                logger.info("Registering slash commands...")
                command_service = self.service_registry.get(CommandService)
                await command_service.register_commands(self.bot)
                
                # Sync slash commands with Discord (now that they're registered)
                logger.info("Syncing slash commands with Discord...")
                try:
                    synced = await self.bot.tree.sync()
                    logger.info(f"Successfully synced {len(synced)} slash commands")
                except Exception as sync_error:
                    logger.error(f"Failed to sync commands: {sync_error}")
                    # Continue anyway - prefix commands will still work
                
                # Start monitoring if available
                monitoring_service = self.service_registry.get_optional(MonitoringService)
                if monitoring_service and hasattr(monitoring_service, 'start_monitoring'):
                    await monitoring_service.start_monitoring()
                
                self._startup_complete = True
                
                logger.info(f"Bot ready: {self.bot.user}")
                logger.info(f"Shard IDs: {self.bot.shard_ids}")
                logger.info(f"Cluster ID: {self.cluster_id}")
                
            except Exception as e:
                logger.error(f"Error in on_ready: {e}")
        
        @self.bot.tree.error
        async def on_command_error(interaction: discord.Interaction, error: Exception):
            """Handle command errors through ErrorService"""
            try:
                error_service = self.service_registry.get(ErrorService)
                await error_service.handle_command_error(interaction, error)
            except Exception as e:
                logger.error(f"Error in command error handler: {e}")
                # Fallback error handling
                try:
                    if not interaction.response.is_done():
                        await interaction.response.send_message(
                            "An unexpected error occurred. Please try again later.",
                            ephemeral=True
                        )
                except:
                    pass
    
    async def _setup_logging(self) -> None:
        """Set up logging configuration"""
        try:
            # Configure Discord.py logging
            discord_logger = logging.getLogger('discord')
            discord_logger.setLevel(self.log_level)
            
            # Set specific loggers to INFO to reduce noise
            logging.getLogger('discord.http').setLevel(logging.INFO)
            logging.getLogger('discord.client').setLevel(logging.INFO)
            logging.getLogger('discord.gateway').setLevel(logging.INFO)
            
            # Create formatters
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            
            # Console handler
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            discord_logger.addHandler(console_handler)
            
            # File handler with rotation
            if self.log_file_path:
                file_handler = logging.handlers.RotatingFileHandler(
                    filename=self.log_file_path,
                    encoding='utf-8',
                    maxBytes=32 * 1024 * 1024,  # 32 MiB
                    backupCount=5
                )
                file_handler.setFormatter(formatter)
                discord_logger.addHandler(file_handler)
            
            logger.debug("Logging configured")
            
        except Exception as e:
            logger.error(f"Failed to setup logging: {e}")
            # Don't raise - logging setup failure shouldn't stop the bot
    
    def get_service_stats(self) -> Dict[str, Any]:
        """Get statistics about all registered services"""
        try:
            registered_services = self.service_registry.get_registered_services()
            
            service_stats = {}
            for service_type, service_def in registered_services.items():
                service_name = service_type.__name__
                service_stats[service_name] = {
                    'lifetime': service_def.lifetime.value,
                    'has_instance': service_def.instance is not None,
                    'has_configuration': bool(service_def.configuration)
                }
            
            return {
                'total_services': len(registered_services),
                'startup_complete': self._startup_complete,
                'bot_ready': self.bot is not None and self.bot.is_ready() if self.bot else False,
                'cluster_id': self.cluster_id,
                'total_shards': self.total_shards,
                'services': service_stats
            }
            
        except Exception as e:
            logger.error(f"Failed to get service stats: {e}")
            return {
                'total_services': 0,
                'startup_complete': False,
                'bot_ready': False,
                'error': str(e)
            }


# Factory function for creating the application
def create_application() -> BunBotApplication:
    """Create and configure a new BunBotApplication instance"""
    service_registry = ServiceRegistry()
    return BunBotApplication(service_registry)
