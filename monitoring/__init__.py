"""
Monitoring & Maintenance Systems for BunBot

Provides comprehensive health monitoring, metrics collection, automated recovery,
and maintenance announcement capabilities built on the core infrastructure.

Key Components:
- Health monitoring for streams and system performance
- Automated error recovery and stream restart capabilities
- Maintenance announcement system with channel configuration
- Interactive Discord dashboard with real-time updates
- Metrics collection and alerting system

Architecture:
- Built on core ServiceRegistry, StateManager, EventBus, and ConfigurationManager
- Event-driven monitoring with automatic recovery
- Configurable announcement channels with intelligent fallbacks
- Discord embed UI with interactive buttons
"""

from .interfaces import (
    HealthStatus, HealthCheck, SystemMetrics, RecoveryResult,
    IHealthMonitor, IMetricsCollector, IRecoveryManager, IAlertManager
)
from .health_monitor import HealthMonitor
from .metrics_collector import MetricsCollector
from .recovery_manager import RecoveryManager
from .alert_manager import AlertManager
from .maintenance_manager import MaintenanceManager
from .channel_manager import ChannelManager
from .dashboard_manager import DashboardManager

__all__ = [
    # Enums and Data Classes
    'HealthStatus',
    'HealthCheck', 
    'SystemMetrics',
    'RecoveryResult',
    
    # Interfaces
    'IHealthMonitor',
    'IMetricsCollector', 
    'IRecoveryManager',
    'IAlertManager',
    
    # Implementations
    'HealthMonitor',
    'MetricsCollector',
    'RecoveryManager', 
    'AlertManager',
    'MaintenanceManager',
    'ChannelManager',
    'DashboardManager'
]
