"""
Health Monitoring System for BunBot
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta

from core import StateManager, EventBus, ConfigurationManager
from .interfaces import (
    IHealthMonitor, IMetricsCollector, HealthCheck, HealthStatus,
    SystemMetrics, StreamMetrics, IssueType
)

logger = logging.getLogger('discord.monitoring.health_monitor')

class HealthMonitor(IHealthMonitor):
    """
    Comprehensive health monitoring service for BunBot.
    
    Monitors both system-wide health and individual guild stream health,
    detecting issues and emitting events for automated recovery and alerting.
    """
    
    def __init__(self, state_manager: StateManager, event_bus: EventBus, 
                 config_manager: ConfigurationManager, metrics_collector: IMetricsCollector):
        self.state_manager = state_manager
        self.event_bus = event_bus
        self.config_manager = config_manager
        self.metrics_collector = metrics_collector
        
        # Health monitoring control
        self._monitoring_active = False
        self._monitoring_task: Optional[asyncio.Task] = None
        self._check_interval = 30  # seconds
        
        # Health history tracking
        self._guild_health_history: Dict[int, List[HealthCheck]] = {}
        self._system_health_history: List[HealthCheck] = []
        self._max_history_items = 100
        
        logger.info("HealthMonitor initialized")
    
    async def check_guild_health(self, guild_id: int) -> HealthCheck:
        """
        Perform comprehensive health check for a specific guild.
        
        Args:
            guild_id: Discord guild ID to check
            
        Returns:
            HealthCheck result with current guild health status
        """
        try:
            logger.debug(f"Checking health for guild {guild_id}")
            
            # Get current state and metrics
            state = self.state_manager.get_guild_state(guild_id, create_if_missing=False)
            stream_metrics = await self.metrics_collector.collect_stream_metrics(guild_id)
            
            # Initialize health assessment
            health_issues = []
            overall_status = HealthStatus.HEALTHY
            health_metrics = {}
            
            # 1. Check if guild has any state
            if not state:
                return HealthCheck(
                    component="guild",
                    status=HealthStatus.OFFLINE,
                    message="No active state - guild is offline",
                    metrics={"guild_id": guild_id}
                )
            
            # 2. Check for state desynchronization issues
            state_issues = await self._check_state_consistency(guild_id, state)
            if state_issues:
                health_issues.extend(state_issues)
                overall_status = HealthStatus.CRITICAL
            
            # 3. Check stream connectivity and performance
            stream_issues = await self._check_stream_health(guild_id, stream_metrics)
            if stream_issues:
                health_issues.extend(stream_issues)
                if overall_status == HealthStatus.HEALTHY:
                    overall_status = HealthStatus.WARNING if len(stream_issues) == 1 else HealthStatus.CRITICAL
            
            # 4. Check for cleanup issues
            cleanup_issues = await self._check_cleanup_state(guild_id, state)
            if cleanup_issues:
                health_issues.extend(cleanup_issues)
                overall_status = HealthStatus.CRITICAL
            
            # 5. Check voice client health
            voice_issues = await self._check_voice_client_health(guild_id)
            if voice_issues:
                health_issues.extend(voice_issues)
                if overall_status == HealthStatus.HEALTHY:
                    overall_status = HealthStatus.WARNING
            
            # Compile health metrics
            health_metrics.update({
                'guild_id': guild_id,
                'stream_url': stream_metrics.stream_url,
                'is_connected': stream_metrics.is_connected,
                'is_playing': stream_metrics.is_playing,
                'connection_quality': stream_metrics.connection_quality,
                'response_time_ms': stream_metrics.response_time_ms,
                'uptime_seconds': stream_metrics.uptime_seconds,
                'issues_detected': len(health_issues)
            })
            
            # Generate health message
            if overall_status == HealthStatus.HEALTHY:
                message = "Guild is healthy and operating normally"
            elif overall_status == HealthStatus.WARNING:
                message = f"Guild has {len(health_issues)} minor issue(s) detected"
            elif overall_status == HealthStatus.CRITICAL:
                message = f"Guild has {len(health_issues)} critical issue(s) requiring attention"
            else:
                message = "Guild health status unknown"
            
            # Create health check result
            health_check = HealthCheck(
                component="guild",
                status=overall_status,
                message=message,
                metrics=health_metrics,
                details={'issues': health_issues}
            )
            
            # Store in history
            self._add_to_guild_history(guild_id, health_check)
            
            # Emit health check event
            await self.event_bus.emit_async('guild_health_checked',
                                          guild_id=guild_id,
                                          status=overall_status.value,
                                          issues=health_issues,
                                          metrics=health_metrics)
            
            logger.debug(f"Guild {guild_id} health check complete: {overall_status.value}")
            return health_check
            
        except Exception as e:
            logger.error(f"Failed to check guild health for {guild_id}: {e}")
            return HealthCheck(
                component="guild",
                status=HealthStatus.UNKNOWN,
                message=f"Health check failed: {e}",
                metrics={'guild_id': guild_id, 'error': str(e)}
            )
    
    async def check_system_health(self) -> HealthCheck:
        """
        Perform comprehensive system-wide health check.
        
        Returns:
            HealthCheck result with current system health status
        """
        try:
            logger.debug("Checking system health")
            
            # Get system metrics
            system_metrics = await self.metrics_collector.collect_system_metrics()
            
            # Initialize health assessment
            health_issues = []
            overall_status = HealthStatus.HEALTHY
            
            # 1. Check system resource usage
            resource_issues = await self._check_system_resources(system_metrics)
            if resource_issues:
                health_issues.extend(resource_issues)
                overall_status = HealthStatus.WARNING
            
            # 2. Check critical resource thresholds
            critical_issues = await self._check_critical_thresholds(system_metrics)
            if critical_issues:
                health_issues.extend(critical_issues)
                overall_status = HealthStatus.CRITICAL
            
            # 3. Check guild health aggregate
            guild_issues = await self._check_guild_health_aggregate()
            if guild_issues:
                health_issues.extend(guild_issues)
                if overall_status == HealthStatus.HEALTHY:
                    overall_status = HealthStatus.WARNING
            
            # 4. Check system connectivity and responsiveness
            connectivity_issues = await self._check_system_connectivity()
            if connectivity_issues:
                health_issues.extend(connectivity_issues)
                overall_status = HealthStatus.CRITICAL
            
            # Generate system health message
            if overall_status == HealthStatus.HEALTHY:
                message = f"System healthy: {system_metrics.active_guilds} active guilds, CPU {system_metrics.cpu_percent:.1f}%, Memory {system_metrics.memory_percent:.1f}%"
            elif overall_status == HealthStatus.WARNING:
                message = f"System has {len(health_issues)} warning(s): elevated resource usage detected"
            elif overall_status == HealthStatus.CRITICAL:
                message = f"System has {len(health_issues)} critical issue(s): immediate attention required"
            else:
                message = "System health status unknown"
            
            # Create health check result
            health_check = HealthCheck(
                component="system",
                status=overall_status,
                message=message,
                metrics=system_metrics.to_dict(),
                details={'issues': health_issues}
            )
            
            # Store in history
            self._system_health_history.append(health_check)
            if len(self._system_health_history) > self._max_history_items:
                self._system_health_history = self._system_health_history[-self._max_history_items:]
            
            # Emit system health event
            await self.event_bus.emit_async('system_health_checked',
                                          status=overall_status.value,
                                          issues=health_issues,
                                          metrics=system_metrics.to_dict())
            
            logger.debug(f"System health check complete: {overall_status.value}")
            return health_check
            
        except Exception as e:
            logger.error(f"Failed to check system health: {e}")
            return HealthCheck(
                component="system",
                status=HealthStatus.UNKNOWN,
                message=f"System health check failed: {e}",
                metrics={'error': str(e)}
            )
    
    async def start_monitoring(self, check_interval_seconds: int = 30) -> None:
        """
        Start continuous health monitoring.
        
        Args:
            check_interval_seconds: How often to perform health checks
        """
        if self._monitoring_active:
            logger.warning("Health monitoring is already running")
            return
        
        self._check_interval = check_interval_seconds
        self._monitoring_active = True
        
        # Start monitoring task
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        
        logger.info(f"Started health monitoring (interval: {check_interval_seconds}s)")
    
    async def stop_monitoring(self) -> None:
        """Stop continuous health monitoring."""
        if not self._monitoring_active:
            return
        
        self._monitoring_active = False
        
        if self._monitoring_task and not self._monitoring_task.done():
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Stopped health monitoring")
    
    async def _monitoring_loop(self) -> None:
        """Main monitoring loop that runs continuously"""
        while self._monitoring_active:
            try:
                # Perform system health check
                await self.check_system_health()
                
                # Perform guild health checks for active guilds
                active_guilds = self.state_manager.get_active_guilds()
                for guild_id in active_guilds:
                    if not self._monitoring_active:  # Check if monitoring was stopped
                        break
                    
                    await self.check_guild_health(guild_id)
                    
                    # Small delay between guild checks to avoid overwhelming
                    await asyncio.sleep(0.1)
                
                # Wait for next check interval
                await asyncio.sleep(self._check_interval)
                
            except asyncio.CancelledError:
                logger.info("Health monitoring loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in health monitoring loop: {e}")
                await asyncio.sleep(5)  # Wait before retrying
    
    async def _check_state_consistency(self, guild_id: int, state) -> List[str]:
        """Check for state desynchronization issues"""
        issues = []
        
        try:
            # Import bot to check actual Discord state
            import bot
            guild = bot.bot.get_guild(guild_id)
            
            if not guild:
                issues.append("Guild not found in bot's guild list")
                return issues
            
            voice_client = guild.voice_client
            
            # Check for state/voice client mismatches
            if state.current_stream_url and not voice_client:
                issues.append("Stream URL set but no voice client connected")
                # Emit recovery event
                await self.event_bus.emit_async('issue_detected',
                                              guild_id=guild_id,
                                              issue_type=IssueType.STATE_DESYNC.value,
                                              description="Stream URL without voice client")
            
            if voice_client and not state.current_stream_url:
                issues.append("Voice client connected but no stream URL set")
                await self.event_bus.emit_async('issue_detected',
                                              guild_id=guild_id,
                                              issue_type=IssueType.STATE_DESYNC.value,
                                              description="Voice client without stream URL")
            
            # Check if voice client is in wrong state
            if voice_client and state.current_stream_url:
                is_connected = getattr(voice_client, 'is_connected', lambda: False)()
                if not is_connected:
                    issues.append("Voice client disconnected but state indicates active stream")
                    await self.event_bus.emit_async('issue_detected',
                                                  guild_id=guild_id,
                                                  issue_type=IssueType.VOICE_CLIENT_LOST.value,
                                                  description="Voice client disconnected unexpectedly")
                
        except Exception as e:
            logger.debug(f"Could not check state consistency for guild {guild_id}: {e}")
            # This is not necessarily an error, bot module might not be available
        
        return issues
    
    async def _check_stream_health(self, guild_id: int, metrics: StreamMetrics) -> List[str]:
        """Check stream connectivity and performance"""
        issues = []
        
        # Check response time issues
        if metrics.response_time_ms and metrics.response_time_ms > 3000:
            issues.append(f"High stream response time: {metrics.response_time_ms:.0f}ms")
            await self.event_bus.emit_async('issue_detected',
                                          guild_id=guild_id,
                                          issue_type=IssueType.STREAM_UNAVAILABLE.value,
                                          description=f"High response time: {metrics.response_time_ms:.0f}ms")
        
        # Check connection quality
        if metrics.connection_quality in ['poor', 'failed']:
            issues.append(f"Poor stream connection quality: {metrics.connection_quality}")
            await self.event_bus.emit_async('issue_detected',
                                          guild_id=guild_id,
                                          issue_type=IssueType.STREAM_UNAVAILABLE.value,
                                          description=f"Poor connection quality: {metrics.connection_quality}")
        
        # Check for stream URL without connection
        if metrics.stream_url and not metrics.is_connected:
            issues.append("Stream URL configured but not connected")
            await self.event_bus.emit_async('issue_detected',
                                          guild_id=guild_id,
                                          issue_type=IssueType.STREAM_DISCONNECT.value,
                                          description="Stream not connected despite URL configuration")
        
        return issues
    
    async def _check_cleanup_state(self, guild_id: int, state) -> List[str]:
        """Check for stuck cleanup operations"""
        issues = []
        
        if getattr(state, 'cleaning_up', False):
            # Check how long cleanup has been running
            if state.last_updated:
                cleanup_duration = datetime.now(timezone.utc) - state.last_updated
                if cleanup_duration > timedelta(minutes=5):
                    issues.append(f"Cleanup stuck for {cleanup_duration.total_seconds():.0f}s")
                    await self.event_bus.emit_async('issue_detected',
                                                  guild_id=guild_id,
                                                  issue_type=IssueType.STATE_DESYNC.value,
                                                  description=f"Cleanup operation stuck for {cleanup_duration}")
        
        return issues
    
    async def _check_voice_client_health(self, guild_id: int) -> List[str]:
        """Check voice client specific issues"""
        issues = []
        
        try:
            import bot
            guild = bot.bot.get_guild(guild_id)
            
            if guild and guild.voice_client:
                voice_client = guild.voice_client
                
                # Check if voice client is in error state
                is_connected_func = getattr(voice_client, 'is_connected', lambda: True)
                if hasattr(voice_client, 'is_connected') and not is_connected_func():
                    issues.append("Voice client exists but is not connected")
                
                # Check for permission issues (would require checking channel permissions)
                # This is a placeholder for future permission checking
                
        except Exception as e:
            logger.debug(f"Could not check voice client health for guild {guild_id}: {e}")
        
        return issues
    
    async def _check_system_resources(self, metrics: SystemMetrics) -> List[str]:
        """Check system resource usage against warning thresholds"""
        issues = []
        config = self.config_manager.get_configuration()
        thresholds = config.alert_thresholds
        
        # Check CPU usage
        cpu_warning = thresholds.get('cpu_usage', 80.0) - 10  # Warning 10% below critical
        if metrics.cpu_percent > cpu_warning:
            issues.append(f"Elevated CPU usage: {metrics.cpu_percent:.1f}%")
        
        # Check memory usage
        memory_warning = thresholds.get('memory_usage', 85.0) - 10  # Warning 10% below critical
        if metrics.memory_percent > memory_warning:
            issues.append(f"Elevated memory usage: {metrics.memory_percent:.1f}%")
        
        return issues
    
    async def _check_critical_thresholds(self, metrics: SystemMetrics) -> List[str]:
        """Check system resource usage against critical thresholds"""
        issues = []
        config = self.config_manager.get_configuration()
        thresholds = config.alert_thresholds
        
        # Check critical CPU usage
        cpu_critical = thresholds.get('cpu_usage', 80.0)
        if metrics.cpu_percent > cpu_critical:
            issues.append(f"Critical CPU usage: {metrics.cpu_percent:.1f}%")
        
        # Check critical memory usage
        memory_critical = thresholds.get('memory_usage', 85.0)
        if metrics.memory_percent > memory_critical:
            issues.append(f"Critical memory usage: {metrics.memory_percent:.1f}%")
        
        return issues
    
    async def _check_guild_health_aggregate(self) -> List[str]:
        """Check overall guild health statistics"""
        issues = []
        
        # Get guild statistics
        total_guilds = len(self.state_manager.get_all_guild_ids())
        active_guilds = len(self.state_manager.get_active_guilds())
        
        # Check if too many guilds are inactive (might indicate connectivity issues)
        if total_guilds > 0:
            inactive_ratio = (total_guilds - active_guilds) / total_guilds
            if inactive_ratio > 0.5:  # More than 50% inactive
                issues.append(f"High guild inactivity: {inactive_ratio*100:.1f}% of guilds are inactive")
        
        return issues
    
    async def _check_system_connectivity(self) -> List[str]:
        """Check system connectivity and responsiveness"""
        issues = []
        
        # This is a placeholder for future connectivity checks
        # Could include Discord API connectivity, database connectivity, etc.
        
        return issues
    
    def _add_to_guild_history(self, guild_id: int, health_check: HealthCheck) -> None:
        """Add health check to guild history"""
        if guild_id not in self._guild_health_history:
            self._guild_health_history[guild_id] = []
        
        self._guild_health_history[guild_id].append(health_check)
        
        # Limit history size
        if len(self._guild_health_history[guild_id]) > self._max_history_items:
            self._guild_health_history[guild_id] = self._guild_health_history[guild_id][-self._max_history_items:]
    
    def get_guild_health_history(self, guild_id: int, limit: int = 10) -> List[HealthCheck]:
        """Get recent health check history for a guild"""
        history = self._guild_health_history.get(guild_id, [])
        return history[-limit:] if limit else history
    
    def get_system_health_history(self, limit: int = 10) -> List[HealthCheck]:
        """Get recent system health check history"""
        return self._system_health_history[-limit:] if limit else self._system_health_history
