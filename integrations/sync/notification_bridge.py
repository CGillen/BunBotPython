"""
NotificationBridge for Cross-Platform Notifications

Sends synchronized notifications and updates to all connected platforms
including Discord channels and Second Life objects.
"""

import logging
from typing import Dict, Any, List, Optional, Set
import asyncio
from datetime import datetime

from core import ServiceRegistry, EventBus

logger = logging.getLogger('integrations.sync.notification_bridge')


class NotificationBridge:
    """
    Manages cross-platform notifications and updates.
    
    Ensures that important events and status changes are communicated
    to all connected platforms in a consistent and timely manner.
    """
    
    def __init__(self, service_registry: ServiceRegistry):
        self.service_registry = service_registry
        self.event_bus = service_registry.get(EventBus)
        
        # Platform notification handlers
        self.notification_handlers: Dict[str, Dict[str, Any]] = {}
        self.platform_subscriptions: Dict[str, Set[str]] = {}  # platform -> notification types
        
        # Notification configuration
        self.batch_notifications = True
        self.batch_delay = 0.5  # seconds
        self.max_batch_size = 20
        
        # Notification queue for batching
        self.notification_queue: asyncio.Queue = asyncio.Queue()
        self.processing_task: Optional[asyncio.Task] = None
        self.is_running = False
        
        logger.info("NotificationBridge initialized")
    
    async def start(self) -> None:
        """Start the notification processing"""
        if not self.is_running:
            self.is_running = True
            if self.batch_notifications:
                self.processing_task = asyncio.create_task(self._process_notification_queue())
            logger.info("NotificationBridge started")
    
    async def stop(self) -> None:
        """Stop the notification processing"""
        if self.is_running:
            self.is_running = False
            if self.processing_task:
                self.processing_task.cancel()
                try:
                    await self.processing_task
                except asyncio.CancelledError:
                    pass
            logger.info("NotificationBridge stopped")
    
    def register_platform_handler(self, platform_id: str, handler: callable,
                                 notification_types: List[str]) -> None:
        """
        Register a notification handler for a platform.
        
        Args:
            platform_id: Platform identifier
            handler: Async callable to handle notifications
            notification_types: List of notification types this handler supports
        """
        self.notification_handlers[platform_id] = {
            'handler': handler,
            'notification_types': set(notification_types),
            'registered_at': datetime.now(),
            'active': True
        }
        
        self.platform_subscriptions[platform_id] = set(notification_types)
        
        logger.info(f"Registered notification handler for {platform_id}: {notification_types}")
    
    def unregister_platform_handler(self, platform_id: str) -> None:
        """Unregister a platform notification handler"""
        if platform_id in self.notification_handlers:
            del self.notification_handlers[platform_id]
        
        if platform_id in self.platform_subscriptions:
            del self.platform_subscriptions[platform_id]
        
        logger.info(f"Unregistered notification handler for {platform_id}")
    
    async def notify_all_platforms(self, guild_id: int, notification_type: str, 
                                 data: Dict[str, Any], exclude_platforms: Optional[List[str]] = None) -> None:
        """
        Send a notification to all connected platforms.
        
        Args:
            guild_id: Discord guild ID
            notification_type: Type of notification
            data: Notification data
            exclude_platforms: Platforms to exclude from notification
        """
        try:
            notification = {
                'guild_id': guild_id,
                'type': notification_type,
                'data': data,
                'timestamp': datetime.now().isoformat(),
                'exclude_platforms': exclude_platforms or []
            }
            
            if self.batch_notifications:
                await self.notification_queue.put(notification)
            else:
                await self._send_notification(notification)
            
        except Exception as e:
            logger.error(f"Error sending notification {notification_type}: {e}")
    
    async def notify_specific_platforms(self, guild_id: int, notification_type: str,
                                      data: Dict[str, Any], platforms: List[str]) -> None:
        """
        Send a notification to specific platforms only.
        
        Args:
            guild_id: Discord guild ID
            notification_type: Type of notification
            data: Notification data
            platforms: List of platforms to notify
        """
        try:
            notification = {
                'guild_id': guild_id,
                'type': notification_type,
                'data': data,
                'timestamp': datetime.now().isoformat(),
                'target_platforms': platforms
            }
            
            await self._send_notification(notification)
            
        except Exception as e:
            logger.error(f"Error sending specific notification {notification_type}: {e}")
    
    async def _process_notification_queue(self) -> None:
        """Process queued notifications in batches"""
        while self.is_running:
            try:
                notifications_batch = []
                
                # Collect notifications for batch processing
                for _ in range(self.max_batch_size):
                    try:
                        notification = await asyncio.wait_for(
                            self.notification_queue.get(),
                            timeout=self.batch_delay
                        )
                        notifications_batch.append(notification)
                    except asyncio.TimeoutError:
                        break
                
                # Process collected notifications
                if notifications_batch:
                    await self._process_notifications_batch(notifications_batch)
                
                # Brief pause if no notifications
                if not notifications_batch:
                    await asyncio.sleep(self.batch_delay)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in notification queue processing: {e}")
                await asyncio.sleep(1)
    
    async def _process_notifications_batch(self, notifications: List[Dict[str, Any]]) -> None:
        """Process a batch of notifications"""
        for notification in notifications:
            try:
                await self._send_notification(notification)
            except Exception as e:
                logger.error(f"Error processing notification: {e}")
    
    async def _send_notification(self, notification: Dict[str, Any]) -> None:
        """Send a notification to appropriate platform handlers"""
        try:
            notification_type = notification['type']
            exclude_platforms = notification.get('exclude_platforms', [])
            target_platforms = notification.get('target_platforms')
            
            # Determine which platforms to notify
            platforms_to_notify = []
            
            if target_platforms:
                # Specific platforms only
                platforms_to_notify = target_platforms
            else:
                # All platforms except excluded ones
                for platform_id, subscriptions in self.platform_subscriptions.items():
                    if platform_id not in exclude_platforms:
                        if notification_type in subscriptions or '*' in subscriptions:
                            platforms_to_notify.append(platform_id)
            
            # Send to each platform
            for platform_id in platforms_to_notify:
                await self._notify_platform(platform_id, notification)
            
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
    
    async def _notify_platform(self, platform_id: str, notification: Dict[str, Any]) -> None:
        """Send notification to a specific platform"""
        try:
            if platform_id not in self.notification_handlers:
                return
            
            handler_info = self.notification_handlers[platform_id]
            
            if not handler_info['active']:
                return
            
            # Check if platform supports this notification type
            notification_type = notification['type']
            supported_types = handler_info['notification_types']
            
            if notification_type not in supported_types and '*' not in supported_types:
                return
            
            # Call platform handler
            handler = handler_info['handler']
            await handler(notification)
            
        except Exception as e:
            logger.error(f"Error notifying platform {platform_id}: {e}")
            # Mark platform as inactive on repeated failures
            if platform_id in self.notification_handlers:
                handler_info = self.notification_handlers[platform_id]
                handler_info['active'] = False
                logger.warning(f"Marked platform {platform_id} as inactive due to errors")
    
    async def send_stream_notification(self, guild_id: int, event_type: str,
                                     stream_data: Dict[str, Any]) -> None:
        """Send stream-related notifications"""
        await self.notify_all_platforms(
            guild_id=guild_id,
            notification_type=f"stream_{event_type}",
            data={
                'event_type': event_type,
                'stream_info': stream_data,
                'category': 'stream'
            }
        )
    
    async def send_audio_notification(self, guild_id: int, event_type: str,
                                    audio_data: Dict[str, Any]) -> None:
        """Send audio-related notifications"""
        await self.notify_all_platforms(
            guild_id=guild_id,
            notification_type=f"audio_{event_type}",
            data={
                'event_type': event_type,
                'audio_info': audio_data,
                'category': 'audio'
            }
        )
    
    async def send_favorites_notification(self, guild_id: int, event_type: str,
                                        favorites_data: Dict[str, Any]) -> None:
        """Send favorites-related notifications"""
        await self.notify_all_platforms(
            guild_id=guild_id,
            notification_type=f"favorites_{event_type}",
            data={
                'event_type': event_type,
                'favorites_info': favorites_data,
                'category': 'favorites'
            }
        )
    
    async def send_system_notification(self, notification_type: str,
                                     system_data: Dict[str, Any],
                                     guild_id: Optional[int] = None) -> None:
        """Send system-wide notifications"""
        await self.notify_all_platforms(
            guild_id=guild_id or 0,  # Use 0 for system-wide notifications
            notification_type=f"system_{notification_type}",
            data={
                'system_info': system_data,
                'category': 'system',
                'system_wide': guild_id is None
            }
        )
    
    def get_platform_status(self) -> Dict[str, Any]:
        """Get status of all registered platforms"""
        platform_status = {}
        
        for platform_id, handler_info in self.notification_handlers.items():
            platform_status[platform_id] = {
                'active': handler_info['active'],
                'notification_types': list(handler_info['notification_types']),
                'registered_at': handler_info['registered_at'].isoformat()
            }
        
        return platform_status
    
    def get_notification_stats(self) -> Dict[str, Any]:
        """Get notification bridge statistics"""
        return {
            'is_running': self.is_running,
            'registered_platforms': len(self.notification_handlers),
            'active_platforms': sum(1 for h in self.notification_handlers.values() if h['active']),
            'batch_notifications': self.batch_notifications,
            'queue_size': self.notification_queue.qsize(),
            'platform_subscriptions': {
                platform: list(types) for platform, types in self.platform_subscriptions.items()
            }
        }
    
    async def test_platform_notification(self, platform_id: str) -> bool:
        """Test notification delivery to a specific platform"""
        try:
            test_notification = {
                'guild_id': 0,
                'type': 'test',
                'data': {
                    'message': 'Test notification',
                    'timestamp': datetime.now().isoformat()
                },
                'timestamp': datetime.now().isoformat()
            }
            
            await self._notify_platform(platform_id, test_notification)
            return True
            
        except Exception as e:
            logger.error(f"Test notification failed for {platform_id}: {e}")
            return False
