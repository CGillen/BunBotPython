"""
Alert Management System for BunBot
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta

from core import StateManager, EventBus, ConfigurationManager
from .interfaces import (
    IAlertManager, AlertMessage, AlertSeverity, HealthCheck, RecoveryResult
)

logger = logging.getLogger('discord.monitoring.alert_manager')

class AlertManager(IAlertManager):
    """
    Alert management service for BunBot notifications.
    
    Sends notifications about health issues, recovery attempts,
    and system status to appropriate Discord channels.
    """
    
    def __init__(self, state_manager: StateManager, event_bus: EventBus, 
                 config_manager: ConfigurationManager, service_registry=None):
        self.state_manager = state_manager
        self.event_bus = event_bus
        self.config_manager = config_manager
        self.service_registry = service_registry
        
        # Alert throttling to prevent spam
        self._alert_history: Dict[str, datetime] = {}  # alert_key -> last_sent_time
        self._throttle_duration = timedelta(minutes=5)  # Minimum time between duplicate alerts
        
        # Subscribe to events that should trigger alerts
        self.event_bus.subscribe(['guild_health_checked'], self.handle_health_check_event,
                                handler_id='alert_manager_health')
        self.event_bus.subscribe(['recovery_successful', 'recovery_failed'], self.handle_recovery_event,
                                handler_id='alert_manager_recovery')
        self.event_bus.subscribe(['threshold_exceeded'], self.handle_threshold_event,
                                handler_id='alert_manager_threshold')
        
        logger.info("AlertManager initialized")
    
    async def send_alert(self, alert: AlertMessage) -> bool:
        """
        Send an alert message to appropriate channels.
        
        Args:
            alert: Alert message to send
            
        Returns:
            True if alert was sent successfully
        """
        try:
            # Check if this alert should be throttled
            alert_key = self._generate_alert_key(alert)
            if self._should_throttle_alert(alert_key):
                logger.debug(f"Throttling duplicate alert: {alert.title}")
                return False
            
            # Get target channel
            if alert.guild_id:
                channel = await self._get_announcement_channel(alert.guild_id)
                if not channel:
                    logger.warning(f"No announcement channel available for guild {alert.guild_id}")
                    return False
            else:
                # System-wide alerts - would need a different approach
                logger.info(f"System-wide alert: {alert.title}")
                return True
            
            # Create Discord embed
            embed_dict = alert.to_embed_dict()
            
            # Send the message
            try:
                import discord
                embed = discord.Embed.from_dict(embed_dict)
                await channel.send(embed=embed)
                
                # Record successful send
                self._alert_history[alert_key] = datetime.now(timezone.utc)
                
                logger.info(f"Sent alert to guild {alert.guild_id}: {alert.title}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to send alert message: {e}")
                return False
                
        except Exception as e:
            logger.error(f"Error in send_alert: {e}")
            return False
    
    async def send_health_alert(self, guild_id: int, health_check: HealthCheck) -> bool:
        """
        Send health-related alert based on health check results.
        
        Args:
            guild_id: Discord guild ID
            health_check: Health check result
            
        Returns:
            True if alert was sent
        """
        try:
            # Only send alerts for concerning health states
            if health_check.status.value in ['healthy', 'unknown']:
                return False
            
            # Determine alert severity based on health status
            if health_check.status.value == 'critical':
                severity = AlertSeverity.CRITICAL
            elif health_check.status.value == 'warning':
                severity = AlertSeverity.WARNING
            else:
                severity = AlertSeverity.INFO
            
            # Create alert message
            alert = AlertMessage(
                guild_id=guild_id,
                severity=severity,
                title=f"Health Issue Detected - {health_check.component.title()}",
                message=health_check.message,
                metadata={'health_check': health_check.metrics}
            )
            
            return await self.send_alert(alert)
            
        except Exception as e:
            logger.error(f"Error sending health alert: {e}")
            return False
    
    async def send_recovery_notification(self, guild_id: int, recovery_result: RecoveryResult) -> bool:
        """
        Send recovery attempt notification.
        
        Args:
            guild_id: Discord guild ID
            recovery_result: Recovery attempt result
            
        Returns:
            True if notification was sent
        """
        try:
            # Determine severity and message based on result
            if recovery_result.success:
                severity = AlertSeverity.INFO
                title = f"🔧 Auto-Recovery Successful"
                message = f"Successfully recovered from {recovery_result.issue_type.value}: {recovery_result.message}"
            else:
                severity = AlertSeverity.WARNING
                title = f"🚨 Auto-Recovery Failed"
                message = f"Failed to recover from {recovery_result.issue_type.value}: {recovery_result.message}"
                
                # If this was the final attempt, make it critical
                if recovery_result.attempt_number >= 3:
                    severity = AlertSeverity.CRITICAL
                    title = f"🆘 Auto-Recovery Exhausted"
                    message += f" (Final attempt {recovery_result.attempt_number})"
            
            alert = AlertMessage(
                guild_id=guild_id,
                severity=severity,
                title=title,
                message=message,
                metadata={
                    'recovery_result': recovery_result.to_dict()
                }
            )
            
            return await self.send_alert(alert)
            
        except Exception as e:
            logger.error(f"Error sending recovery notification: {e}")
            return False
    
    async def send_maintenance_announcement(self, message: str, guilds: Optional[List[int]] = None) -> int:
        """
        Send maintenance announcement to specified guilds or all active guilds.
        
        Args:
            message: Maintenance message to send
            guilds: Optional list of guild IDs (None for all active guilds)
            
        Returns:
            Number of guilds that received the announcement
        """
        try:
            # Get target guilds
            if guilds is None:
                target_guilds = self.state_manager.get_active_guilds()
            else:
                target_guilds = guilds
            
            sent_count = 0
            
            for guild_id in target_guilds:
                try:
                    alert = AlertMessage(
                        guild_id=guild_id,
                        severity=AlertSeverity.INFO,
                        title="🔧 Maintenance Announcement",
                        message=message
                    )
                    
                    if await self.send_alert(alert):
                        sent_count += 1
                        
                except Exception as e:
                    logger.error(f"Failed to send maintenance announcement to guild {guild_id}: {e}")
            
            logger.info(f"Sent maintenance announcement to {sent_count}/{len(target_guilds)} guilds")
            return sent_count
            
        except Exception as e:
            logger.error(f"Error sending maintenance announcements: {e}")
            return 0
    
    async def handle_health_check_event(self, event) -> None:
        """Handle health check events and send alerts if needed"""
        try:
            guild_id = event.get_event_data('guild_id')
            status = event.get_event_data('status')
            issues = event.get_event_data('issues', [])
            
            if not guild_id or not status:
                return
            
            # Only alert on concerning health states with issues
            if status in ['warning', 'critical'] and issues:
                # Create a mock health check for the alert
                from .interfaces import HealthCheck, HealthStatus
                
                health_check = HealthCheck(
                    component="guild",
                    status=HealthStatus(status),
                    message=f"Detected {len(issues)} issue(s): {', '.join(issues[:3])}",
                    metrics=event.get_event_data('metrics', {})
                )
                
                await self.send_health_alert(guild_id, health_check)
                
        except Exception as e:
            logger.error(f"Error handling health check event: {e}")
    
    async def handle_recovery_event(self, event) -> None:
        """Handle recovery events and send notifications"""
        try:
            guild_id = event.get_event_data('guild_id')
            issue_type_str = event.get_event_data('issue_type')
            attempt_number = event.get_event_data('attempt_number', 1)
            
            if not guild_id or not issue_type_str:
                return
            
            # Create a mock recovery result for notification
            from .interfaces import RecoveryResult, IssueType
            
            try:
                issue_type = IssueType(issue_type_str)
            except ValueError:
                issue_type = IssueType.UNKNOWN_ERROR
            
            success = event.event_type == 'recovery_successful'
            message = event.get_event_data('error', 'Recovery completed') if not success else 'Recovery successful'
            
            recovery_result = RecoveryResult(
                guild_id=guild_id,
                issue_type=issue_type,
                success=success,
                message=message,
                attempt_number=attempt_number,
                recovery_time_seconds=0.0
            )
            
            await self.send_recovery_notification(guild_id, recovery_result)
            
        except Exception as e:
            logger.error(f"Error handling recovery event: {e}")
    
    async def handle_threshold_event(self, event) -> None:
        """Handle threshold exceeded events"""
        try:
            metric_type = event.get_event_data('metric_type')
            value = event.get_event_data('value')
            threshold = event.get_event_data('threshold')
            severity = event.get_event_data('severity', 'warning')
            
            if not metric_type or value is None:
                return
            
            # System-wide threshold alerts
            alert_severity = AlertSeverity.WARNING if severity == 'warning' else AlertSeverity.CRITICAL
            
            alert = AlertMessage(
                guild_id=None,  # System-wide alert
                severity=alert_severity,
                title=f"System Threshold Exceeded - {metric_type.title()}",
                message=f"{metric_type.replace('_', ' ').title()}: {value:.1f}% (threshold: {threshold:.1f}%)",
                metadata={
                    'metric_type': metric_type,
                    'value': value,
                    'threshold': threshold
                }
            )
            
            # For now, just log system-wide alerts
            # In the future, could send to admin channels
            logger.warning(f"System alert: {alert.title} - {alert.message}")
            
        except Exception as e:
            logger.error(f"Error handling threshold event: {e}")
    
    async def _get_announcement_channel(self, guild_id: int):
        """Get announcement channel for a guild with fallback logic"""
        try:
            # Get bot instance from service registry
            if not self.service_registry:
                logger.warning("No service registry available for getting bot instance")
                return None
                
            from discord.ext import commands
            bot_instance = self.service_registry.get_optional(commands.AutoShardedBot)
            if not bot_instance:
                logger.warning("Bot instance not available in service registry")
                return None
            
            guild = bot_instance.get_guild(guild_id)
            if not guild:
                return None
            
            # Get guild state to find last active channel
            state = self.state_manager.get_guild_state(guild_id, create_if_missing=False)
            if state and state.text_channel:
                # Check if bot still has permissions
                channel = state.text_channel
                if channel.permissions_for(guild.me).send_messages:
                    return channel
            
            # Fallback to first channel with send permissions
            for channel in guild.text_channels:
                if channel.permissions_for(guild.me).send_messages:
                    return channel
            
            return None
            
        except Exception as e:
            logger.debug(f"Could not get announcement channel for guild {guild_id}: {e}")
            return None
    
    def _generate_alert_key(self, alert: AlertMessage) -> str:
        """Generate a unique key for alert throttling"""
        return f"{alert.guild_id}:{alert.severity.value}:{alert.title}"
    
    def _should_throttle_alert(self, alert_key: str) -> bool:
        """Check if an alert should be throttled"""
        last_sent = self._alert_history.get(alert_key)
        if last_sent:
            time_since_last = datetime.now(timezone.utc) - last_sent
            return time_since_last < self._throttle_duration
        return False
    
    def get_alert_stats(self) -> Dict[str, Any]:
        """Get alert statistics"""
        return {
            'total_alerts_sent': len(self._alert_history),
            'active_throttles': sum(
                1 for last_sent in self._alert_history.values()
                if datetime.now(timezone.utc) - last_sent < self._throttle_duration
            ),
            'throttle_duration_minutes': self._throttle_duration.total_seconds() / 60
        }
