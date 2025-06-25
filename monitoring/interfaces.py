"""
Abstract Interfaces and Data Structures for BunBot Monitoring System
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone, timedelta

logger = logging.getLogger('discord.monitoring.interfaces')

class HealthStatus(Enum):
    """Health status levels for components and systems"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical" 
    OFFLINE = "offline"
    UNKNOWN = "unknown"

class MetricType(Enum):
    """Types of metrics that can be collected"""
    STREAM_HEALTH = "stream_health"
    VOICE_CLIENT_STATUS = "voice_client_status"
    SYSTEM_CPU = "system_cpu"
    SYSTEM_MEMORY = "system_memory"
    RESPONSE_TIME = "response_time"
    ACTIVE_STREAMS = "active_streams"
    ERROR_RATE = "error_rate"
    RECOVERY_SUCCESS_RATE = "recovery_success_rate"

class IssueType(Enum):
    """Types of issues that can be recovered from"""
    STREAM_DISCONNECT = "stream_disconnect"
    STATE_DESYNC = "state_desync"
    VOICE_CLIENT_LOST = "voice_client_lost"
    STREAM_UNAVAILABLE = "stream_unavailable"
    PERMISSION_ERROR = "permission_error"
    UNKNOWN_ERROR = "unknown_error"

class AlertSeverity(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"

@dataclass
class HealthCheck:
    """Result of a health check operation"""
    component: str
    status: HealthStatus
    message: str
    metrics: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    details: Optional[Dict[str, Any]] = None
    
    def is_healthy(self) -> bool:
        """Check if the component is in a healthy state"""
        return self.status == HealthStatus.HEALTHY
    
    def requires_attention(self) -> bool:
        """Check if the component requires attention"""
        return self.status in [HealthStatus.WARNING, HealthStatus.CRITICAL, HealthStatus.OFFLINE]

@dataclass
class SystemMetrics:
    """System performance metrics"""
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_total_mb: float
    active_guilds: int
    total_guilds: int
    uptime_seconds: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'cpu_percent': self.cpu_percent,
            'memory_percent': self.memory_percent,
            'memory_used_mb': self.memory_used_mb,
            'memory_total_mb': self.memory_total_mb,
            'active_guilds': self.active_guilds,
            'total_guilds': self.total_guilds,
            'uptime_seconds': self.uptime_seconds,
            'timestamp': self.timestamp.isoformat()
        }

@dataclass
class StreamMetrics:
    """Stream-specific metrics"""
    guild_id: int
    stream_url: Optional[str]
    is_connected: bool
    is_playing: bool
    connection_quality: str  # "excellent", "good", "poor", "failed"
    response_time_ms: Optional[float]
    last_metadata_update: Optional[datetime]
    error_count: int = 0
    uptime_seconds: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'guild_id': self.guild_id,
            'stream_url': self.stream_url,
            'is_connected': self.is_connected,
            'is_playing': self.is_playing,
            'connection_quality': self.connection_quality,
            'response_time_ms': self.response_time_ms,
            'last_metadata_update': self.last_metadata_update.isoformat() if self.last_metadata_update else None,
            'error_count': self.error_count,
            'uptime_seconds': self.uptime_seconds,
            'timestamp': self.timestamp.isoformat()
        }

@dataclass
class RecoveryResult:
    """Result of a recovery operation"""
    guild_id: int
    issue_type: IssueType
    success: bool
    message: str
    attempt_number: int
    recovery_time_seconds: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error_details: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/storage"""
        return {
            'guild_id': self.guild_id,
            'issue_type': self.issue_type.value,
            'success': self.success,
            'message': self.message,
            'attempt_number': self.attempt_number,
            'recovery_time_seconds': self.recovery_time_seconds,
            'timestamp': self.timestamp.isoformat(),
            'error_details': self.error_details
        }

@dataclass
class AlertMessage:
    """Alert message structure"""
    guild_id: Optional[int]  # None for system-wide alerts
    severity: AlertSeverity
    title: str
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_embed_dict(self) -> Dict[str, Any]:
        """Convert to Discord embed dictionary"""
        color_map = {
            AlertSeverity.INFO: 0x3498db,      # Blue
            AlertSeverity.WARNING: 0xf39c12,   # Orange
            AlertSeverity.CRITICAL: 0xe74c3c,  # Red
            AlertSeverity.EMERGENCY: 0x8e44ad  # Purple
        }
        
        return {
            'title': f"{self._get_severity_emoji()} {self.title}",
            'description': self.message,
            'color': color_map.get(self.severity, 0x95a5a6),
            'timestamp': self.timestamp.isoformat(),
            'fields': [
                {
                    'name': 'Severity',
                    'value': self.severity.value.title(),
                    'inline': True
                },
                {
                    'name': 'Time',
                    'value': self.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC'),
                    'inline': True
                }
            ]
        }
    
    def _get_severity_emoji(self) -> str:
        """Get emoji for severity level"""
        emoji_map = {
            AlertSeverity.INFO: "ℹ️",
            AlertSeverity.WARNING: "⚠️", 
            AlertSeverity.CRITICAL: "🚨",
            AlertSeverity.EMERGENCY: "🆘"
        }
        return emoji_map.get(self.severity, "📢")

class IHealthMonitor(ABC):
    """Abstract interface for health monitoring"""
    
    @abstractmethod
    async def check_guild_health(self, guild_id: int) -> HealthCheck:
        """Check health of a specific guild"""
        pass
    
    @abstractmethod
    async def check_system_health(self) -> HealthCheck:
        """Check overall system health"""
        pass
    
    @abstractmethod
    async def start_monitoring(self, check_interval_seconds: int = 30) -> None:
        """Start continuous health monitoring"""
        pass
    
    @abstractmethod
    async def stop_monitoring(self) -> None:
        """Stop health monitoring"""
        pass

class IMetricsCollector(ABC):
    """Abstract interface for metrics collection"""
    
    @abstractmethod
    async def collect_system_metrics(self) -> SystemMetrics:
        """Collect system-wide performance metrics"""
        pass
    
    @abstractmethod
    async def collect_stream_metrics(self, guild_id: int) -> StreamMetrics:
        """Collect metrics for a specific guild's stream"""
        pass
    
    @abstractmethod
    async def get_metric_history(self, metric_type: MetricType, hours: int = 24) -> List[Dict[str, Any]]:
        """Get historical metrics data"""
        pass
    
    @abstractmethod
    async def store_metrics(self, metrics: Union[SystemMetrics, StreamMetrics]) -> bool:
        """Store metrics to persistent storage"""
        pass

class IRecoveryManager(ABC):
    """Abstract interface for automated recovery"""
    
    @abstractmethod
    async def attempt_recovery(self, guild_id: int, issue_type: IssueType) -> RecoveryResult:
        """Attempt to recover from a specific issue"""
        pass
    
    @abstractmethod
    async def can_attempt_recovery(self, guild_id: int, issue_type: IssueType) -> bool:
        """Check if recovery can be attempted (not exceeded retry limits)"""
        pass
    
    @abstractmethod
    async def reset_recovery_attempts(self, guild_id: int, issue_type: IssueType) -> None:
        """Reset recovery attempt counter for successful recovery"""
        pass
    
    @abstractmethod
    async def get_recovery_history(self, guild_id: int, hours: int = 24) -> List[RecoveryResult]:
        """Get recovery attempt history"""
        pass

class IAlertManager(ABC):
    """Abstract interface for alert management"""
    
    @abstractmethod
    async def send_alert(self, alert: AlertMessage) -> bool:
        """Send an alert message"""
        pass
    
    @abstractmethod
    async def send_health_alert(self, guild_id: int, health_check: HealthCheck) -> bool:
        """Send health-related alert"""
        pass
    
    @abstractmethod
    async def send_recovery_notification(self, guild_id: int, recovery_result: RecoveryResult) -> bool:
        """Send recovery notification"""
        pass
    
    @abstractmethod
    async def send_maintenance_announcement(self, message: str, guilds: Optional[List[int]] = None) -> int:
        """Send maintenance announcement to guilds"""
        pass

class IChannelManager(ABC):
    """Abstract interface for announcement channel management"""
    
    @abstractmethod
    async def set_announcement_channel(self, guild_id: int, channel_id: int) -> bool:
        """Set custom announcement channel for guild"""
        pass
    
    @abstractmethod
    async def get_announcement_channel(self, guild_id: int):
        """Get announcement channel with fallback logic"""
        pass
    
    @abstractmethod
    async def clear_announcement_channel(self, guild_id: int) -> bool:
        """Clear custom announcement channel setting"""
        pass

class IMaintenanceManager(ABC):
    """Abstract interface for maintenance management"""
    
    @abstractmethod
    async def schedule_maintenance(self, message: str, duration: timedelta, start_time: Optional[datetime] = None) -> int:
        """Schedule a maintenance window"""
        pass
    
    @abstractmethod
    async def start_maintenance(self, maintenance_id: int) -> bool:
        """Start a scheduled maintenance"""
        pass
    
    @abstractmethod
    async def end_maintenance(self, maintenance_id: int, completion_message: Optional[str] = None) -> bool:
        """End a maintenance window"""
        pass
    
    @abstractmethod
    async def get_active_maintenance(self) -> Optional[Dict[str, Any]]:
        """Get currently active maintenance window"""
        pass

class IDashboardManager(ABC):
    """Abstract interface for dashboard management"""
    
    @abstractmethod
    async def create_health_dashboard_embed(self, guild_id: int):
        """Create health dashboard embed"""
        pass
    
    @abstractmethod
    def create_health_dashboard_view(self, guild_id: int):
        """Create interactive dashboard view"""
        pass
    
    @abstractmethod
    async def update_dashboard(self, guild_id: int, message_id: int) -> bool:
        """Update existing dashboard message"""
        pass
