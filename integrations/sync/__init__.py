"""
Cross-Platform Synchronization System for BunBot

Provides real-time state synchronization between Discord and Second Life
platforms, ensuring consistent bot state and functionality across both interfaces.

Key Components:
- StateSynchronizer: Real-time state sync between platforms
- EventBridge: Bridge Phase 1 EventBus events to external platforms
- ConflictResolver: Handle simultaneous commands from multiple platforms
- NotificationBridge: Send updates to all connected platforms
"""

from .state_synchronizer import StateSynchronizer
from .event_bridge import EventBridge
from .conflict_resolver import ConflictResolver
from .notification_bridge import NotificationBridge

__all__ = [
    'StateSynchronizer',
    'EventBridge', 
    'ConflictResolver',
    'NotificationBridge'
]
