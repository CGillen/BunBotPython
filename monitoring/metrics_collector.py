"""
Metrics Collection System for BunBot Monitoring
"""

import logging
import asyncio
import time
import psutil
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timezone, timedelta

from core import StateManager, EventBus, ConfigurationManager
from .interfaces import (
    IMetricsCollector, SystemMetrics, StreamMetrics, MetricType,
    HealthStatus
)

logger = logging.getLogger('discord.monitoring.metrics_collector')

class MetricsCollector(IMetricsCollector):
    """
    Comprehensive metrics collection service for BunBot.
    
    Collects performance data from system resources and individual
    guild streams, stores historical data, and emits events when
    thresholds are exceeded.
    """
    
    def __init__(self, state_manager: StateManager, event_bus: EventBus, 
                 config_manager: ConfigurationManager, service_registry=None, database_connection=None):
        self.state_manager = state_manager
        self.event_bus = event_bus
        self.config_manager = config_manager
        self.service_registry = service_registry
        self.db = database_connection
        
        # Track startup time for uptime calculation
        self.startup_time = time.time()
        
        # Cache for expensive operations
        self._last_system_metrics: Optional[SystemMetrics] = None
        self._system_metrics_cache_time: float = 0
        self._cache_duration = 5  # seconds
        
        logger.info("MetricsCollector initialized")
    
    async def collect_system_metrics(self) -> SystemMetrics:
        """
        Collect comprehensive system performance metrics.
        
        Returns:
            SystemMetrics object with current system performance data
        """
        try:
            # Check cache first to avoid expensive operations
            current_time = time.time()
            if (self._last_system_metrics and 
                current_time - self._system_metrics_cache_time < self._cache_duration):
                return self._last_system_metrics
            
            # Collect CPU and memory statistics
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            
            # Get guild statistics from StateManager
            all_guild_ids = self.state_manager.get_all_guild_ids()
            active_guild_ids = self.state_manager.get_active_guilds()
            
            # Calculate uptime
            uptime_seconds = current_time - self.startup_time
            
            # Create metrics object
            metrics = SystemMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_used_mb=memory.used / (1024 * 1024),
                memory_total_mb=memory.total / (1024 * 1024),
                active_guilds=len(active_guild_ids),
                total_guilds=len(all_guild_ids),
                uptime_seconds=uptime_seconds
            )
            
            # Cache the results
            self._last_system_metrics = metrics
            self._system_metrics_cache_time = current_time
            
            # Check thresholds and emit events if needed
            await self._check_system_thresholds(metrics)
            
            # Store metrics if database is available
            if self.db:
                await self.store_metrics(metrics)
            
            logger.debug(f"Collected system metrics: CPU {cpu_percent}%, Memory {memory.percent}%")
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}")
            # Return minimal metrics on error
            return SystemMetrics(
                cpu_percent=0.0,
                memory_percent=0.0,
                memory_used_mb=0.0,
                memory_total_mb=0.0,
                active_guilds=0,
                total_guilds=0,
                uptime_seconds=0.0
            )
    
    async def collect_stream_metrics(self, guild_id: int) -> StreamMetrics:
        """
        Collect metrics for a specific guild's stream.
        
        Args:
            guild_id: Discord guild ID to collect metrics for
            
        Returns:
            StreamMetrics object with current stream health data
        """
        try:
            # Get guild state
            state = self.state_manager.get_guild_state(guild_id, create_if_missing=False)
            
            # Initialize default metrics
            stream_url = None
            is_connected = False
            is_playing = False
            connection_quality = "unknown"
            response_time_ms = None
            last_metadata_update = None
            error_count = 0
            uptime_seconds = 0.0
            
            if state:
                stream_url = state.current_stream_url
                last_metadata_update = state.last_updated
                
                # Calculate uptime if stream is active
                if state.start_time:
                    uptime_seconds = (datetime.now(timezone.utc) - state.start_time).total_seconds()
                
                # Check voice client status (requires bot instance access)
                try:
                    # Get bot instance from service registry
                    if self.service_registry:
                        from discord.ext import commands
                        bot_instance = self.service_registry.get_optional(commands.AutoShardedBot)
                        if bot_instance:
                            guild = bot_instance.get_guild(guild_id)
                            if guild and guild.voice_client:
                                voice_client = guild.voice_client
                                # Use proper Discord.py VoiceClient methods
                                is_connected = getattr(voice_client, 'is_connected', lambda: False)()
                                is_playing = getattr(voice_client, 'is_playing', lambda: False)()
                except Exception as e:
                    logger.debug(f"Could not check voice client for guild {guild_id}: {e}")
                
                # Test stream response time if URL is available
                if stream_url:
                    response_time_ms = await self._test_stream_response_time(stream_url)
                    connection_quality = self._determine_connection_quality(response_time_ms, is_connected, is_playing)
            
            # Create metrics object
            metrics = StreamMetrics(
                guild_id=guild_id,
                stream_url=stream_url,
                is_connected=is_connected,
                is_playing=is_playing,
                connection_quality=connection_quality,
                response_time_ms=response_time_ms,
                last_metadata_update=last_metadata_update,
                error_count=error_count,
                uptime_seconds=uptime_seconds
            )
            
            # Store metrics if database is available
            if self.db:
                await self.store_metrics(metrics)
            
            # Emit stream health event
            await self.event_bus.emit_async('stream_metrics_collected',
                                          guild_id=guild_id,
                                          metrics=metrics.to_dict())
            
            logger.debug(f"Collected stream metrics for guild {guild_id}: {connection_quality}")
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to collect stream metrics for guild {guild_id}: {e}")
            # Return minimal metrics on error
            return StreamMetrics(
                guild_id=guild_id,
                stream_url=None,
                is_connected=False,
                is_playing=False,
                connection_quality="failed",
                response_time_ms=None,
                last_metadata_update=None
            )
    
    async def get_metric_history(self, metric_type: MetricType, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get historical metrics data from storage.
        
        Args:
            metric_type: Type of metrics to retrieve
            hours: Number of hours of history to retrieve
            
        Returns:
            List of metric data dictionaries
        """
        if not self.db:
            logger.warning("No database connection available for metric history")
            return []
        
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
            
            cursor = await self.db.execute(
                "SELECT * FROM health_metrics WHERE metric_type = ? AND timestamp >= ? ORDER BY timestamp DESC",
                (metric_type.value, cutoff_time.isoformat())
            )
            
            rows = await cursor.fetchall()
            
            # Convert rows to dictionaries
            metrics_history = []
            for row in rows:
                metric_data = {
                    'id': row[0],
                    'guild_id': row[1],
                    'metric_type': row[2],
                    'metric_value': row[3],
                    'threshold_breached': bool(row[4]),
                    'timestamp': row[5],
                    'details': row[6]  # JSON field
                }
                metrics_history.append(metric_data)
            
            logger.debug(f"Retrieved {len(metrics_history)} historical metrics for {metric_type.value}")
            return metrics_history
            
        except Exception as e:
            logger.error(f"Failed to retrieve metric history: {e}")
            return []
    
    async def store_metrics(self, metrics: Union[SystemMetrics, StreamMetrics]) -> bool:
        """
        Store metrics to persistent storage.
        
        Args:
            metrics: Metrics object to store
            
        Returns:
            True if stored successfully, False otherwise
        """
        if not self.db:
            return False
        
        try:
            if isinstance(metrics, SystemMetrics):
                await self._store_system_metrics(metrics)
            elif isinstance(metrics, StreamMetrics):
                await self._store_stream_metrics(metrics)
            else:
                logger.warning(f"Unknown metrics type: {type(metrics)}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to store metrics: {e}")
            return False
    
    async def _store_system_metrics(self, metrics: SystemMetrics) -> None:
        """Store system metrics to database"""
        # Store CPU metrics
        await self.db.execute(
            "INSERT INTO health_metrics (guild_id, metric_type, metric_value, threshold_breached, timestamp, details) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (None, MetricType.SYSTEM_CPU.value, metrics.cpu_percent, 
             metrics.cpu_percent > 80, metrics.timestamp.isoformat(), 
             '{"uptime_seconds": ' + str(metrics.uptime_seconds) + '}')
        )
        
        # Store memory metrics
        await self.db.execute(
            "INSERT INTO health_metrics (guild_id, metric_type, metric_value, threshold_breached, timestamp, details) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (None, MetricType.SYSTEM_MEMORY.value, metrics.memory_percent,
             metrics.memory_percent > 85, metrics.timestamp.isoformat(),
             '{"used_mb": ' + str(metrics.memory_used_mb) + ', "total_mb": ' + str(metrics.memory_total_mb) + '}')
        )
        
        # Store active streams count
        await self.db.execute(
            "INSERT INTO health_metrics (guild_id, metric_type, metric_value, threshold_breached, timestamp, details) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (None, MetricType.ACTIVE_STREAMS.value, metrics.active_guilds,
             False, metrics.timestamp.isoformat(),
             '{"total_guilds": ' + str(metrics.total_guilds) + '}')
        )
        
        await self.db.commit()
    
    async def _store_stream_metrics(self, metrics: StreamMetrics) -> None:
        """Store stream metrics to database"""
        # Store response time if available
        if metrics.response_time_ms is not None:
            await self.db.execute(
                "INSERT INTO health_metrics (guild_id, metric_type, metric_value, threshold_breached, timestamp, details) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (metrics.guild_id, MetricType.RESPONSE_TIME.value, metrics.response_time_ms,
                 metrics.response_time_ms > 2000, metrics.timestamp.isoformat(),
                 '{"connection_quality": "' + metrics.connection_quality + '"}')
            )
        
        # Store stream health status
        health_score = self._calculate_stream_health_score(metrics)
        await self.db.execute(
            "INSERT INTO health_metrics (guild_id, metric_type, metric_value, threshold_breached, timestamp, details) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (metrics.guild_id, MetricType.STREAM_HEALTH.value, health_score,
             health_score < 0.7, metrics.timestamp.isoformat(),
             '{"is_playing": ' + str(metrics.is_playing).lower() + ', "uptime_seconds": ' + str(metrics.uptime_seconds) + '}')
        )
        
        await self.db.commit()
    
    async def _test_stream_response_time(self, stream_url: str) -> Optional[float]:
        """Test response time for a stream URL"""
        try:
            import urllib.request
            import time
            
            start_time = time.time()
            
            # Create a quick HEAD request to test response time
            request = urllib.request.Request(stream_url, method='HEAD')
            response = urllib.request.urlopen(request, timeout=5)
            
            end_time = time.time()
            response_time_ms = (end_time - start_time) * 1000
            
            response.close()
            return response_time_ms
            
        except Exception as e:
            logger.debug(f"Could not test response time for {stream_url}: {e}")
            return None
    
    def _determine_connection_quality(self, response_time_ms: Optional[float], 
                                    is_connected: bool, is_playing: bool) -> str:
        """Determine connection quality based on metrics"""
        if not is_connected:
            return "offline"
        
        if not is_playing:
            return "connected_not_playing"
        
        if response_time_ms is None:
            return "unknown"
        
        if response_time_ms < 500:
            return "excellent"
        elif response_time_ms < 1000:
            return "good"
        elif response_time_ms < 2000:
            return "fair"
        else:
            return "poor"
    
    def _calculate_stream_health_score(self, metrics: StreamMetrics) -> float:
        """Calculate overall health score for a stream (0.0 to 1.0)"""
        score = 0.0
        
        # Base score for being connected and playing
        if metrics.is_connected:
            score += 0.3
        if metrics.is_playing:
            score += 0.3
        
        # Response time score
        if metrics.response_time_ms is not None:
            if metrics.response_time_ms < 500:
                score += 0.4
            elif metrics.response_time_ms < 1000:
                score += 0.3
            elif metrics.response_time_ms < 2000:
                score += 0.2
            else:
                score += 0.1
        
        return min(score, 1.0)
    
    async def _check_system_thresholds(self, metrics: SystemMetrics) -> None:
        """Check system metrics against thresholds and emit events"""
        config = self.config_manager.get_configuration()
        thresholds = config.alert_thresholds
        
        # Check CPU threshold
        cpu_threshold = thresholds.get('cpu_usage', 80.0)
        if metrics.cpu_percent > cpu_threshold:
            await self.event_bus.emit_async('threshold_exceeded',
                                          metric_type='cpu_usage',
                                          value=metrics.cpu_percent,
                                          threshold=cpu_threshold,
                                          severity='warning' if metrics.cpu_percent < 90 else 'critical')
        
        # Check memory threshold  
        memory_threshold = thresholds.get('memory_usage', 85.0)
        if metrics.memory_percent > memory_threshold:
            await self.event_bus.emit_async('threshold_exceeded',
                                          metric_type='memory_usage',
                                          value=metrics.memory_percent,
                                          threshold=memory_threshold,
                                          severity='warning' if metrics.memory_percent < 95 else 'critical')
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of current metrics status"""
        try:
            summary = {
                'cache_enabled': True,
                'cache_duration_seconds': self._cache_duration,
                'has_database': self.db is not None,
                'startup_time': self.startup_time,
                'uptime_hours': (time.time() - self.startup_time) / 3600
            }
            
            if self._last_system_metrics:
                summary.update({
                    'latest_cpu_percent': self._last_system_metrics.cpu_percent,
                    'latest_memory_percent': self._last_system_metrics.memory_percent,
                    'latest_active_guilds': self._last_system_metrics.active_guilds,
                    'latest_total_guilds': self._last_system_metrics.total_guilds
                })
            
            return summary
            
        except Exception as e:
            logger.error(f"Failed to get metrics summary: {e}")
            return {'error': str(e)}
