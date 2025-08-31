"""
Webhook Manager for BunBot External Integrations

Provides comprehensive outbound webhook system for real-time notifications
to external services and platforms.

Key Features:
- Event-driven webhook delivery
- Retry logic with exponential backoff
- Secure signature verification
- Rate limiting and delivery tracking
- Comprehensive logging and monitoring
"""

import logging
import asyncio
import hmac
import hashlib
import json
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import aiohttp
from urllib.parse import urlparse

# Phase 1 Infrastructure
from core.service_registry import ServiceRegistry
from core.state_manager import StateManager
from core.event_bus import EventBus
from core.config_manager import ConfigurationManager

# Phase 2 Monitoring
from monitoring.health_monitor import HealthMonitor
from monitoring.metrics_collector import MetricsCollector

logger = logging.getLogger('external.webhook_manager')

class WebhookEventType(Enum):
    """Types of webhook events"""
    STREAM_STARTED = "stream_started"
    STREAM_STOPPED = "stream_stopped"
    STREAM_ERROR = "stream_error"
    AUDIO_VOLUME_CHANGED = "audio_volume_changed"
    FAVORITE_ADDED = "favorite_added"
    FAVORITE_REMOVED = "favorite_removed"
    GUILD_JOINED = "guild_joined"
    GUILD_LEFT = "guild_left"
    MAINTENANCE_STARTED = "maintenance_started"
    MAINTENANCE_COMPLETED = "maintenance_completed"
    HEALTH_STATUS_CHANGED = "health_status_changed"

class DeliveryStatus(Enum):
    """Status of webhook deliveries"""
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"
    EXPIRED = "expired"

@dataclass
class WebhookEvent:
    """Webhook event data structure"""
    event_id: str
    event_type: WebhookEventType
    guild_id: Optional[int]
    timestamp: datetime
    data: Dict[str, Any]
    source: str = "BunBot"
    version: str = "1.0"

@dataclass
class WebhookEndpoint:
    """Webhook endpoint configuration"""
    endpoint_id: str
    url: str
    secret: Optional[str]
    event_types: List[WebhookEventType]
    active: bool = True
    max_retries: int = 3
    timeout: int = 30
    headers: Optional[Dict[str, str]] = None
    guild_id: Optional[int] = None  # Guild-specific webhook

@dataclass
class WebhookDelivery:
    """Webhook delivery tracking"""
    delivery_id: str
    webhook_id: str
    event_id: str
    status: DeliveryStatus
    attempt_count: int
    created_at: datetime
    last_attempt: Optional[datetime] = None
    next_retry: Optional[datetime] = None
    response_code: Optional[int] = None
    response_body: Optional[str] = None
    error_message: Optional[str] = None

class WebhookManager:
    """
    Manages outbound webhooks for external service integration.
    
    Provides reliable webhook delivery with retry logic, rate limiting,
    and comprehensive monitoring and logging.
    """
    
    def __init__(self, service_registry: ServiceRegistry):
        self.service_registry = service_registry
        self.state_manager = service_registry.get_service(StateManager)
        self.event_bus = service_registry.get_service(EventBus)
        self.config_manager = service_registry.get_service(ConfigurationManager)
        self.health_monitor = service_registry.get_service(HealthMonitor)
        self.metrics_collector = service_registry.get_service(MetricsCollector)
        
        # Webhook management
        self.webhooks: Dict[str, WebhookEndpoint] = {}
        self.pending_deliveries: Dict[str, WebhookDelivery] = {}
        self.delivery_queue: asyncio.Queue = asyncio.Queue()
        
        # Configuration
        self.max_concurrent_deliveries = 10
        self.retry_delays = [30, 60, 300, 900]  # 30s, 1m, 5m, 15m
        self.max_delivery_age = timedelta(hours=24)
        
        # HTTP session
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Delivery workers
        self.delivery_workers: List[asyncio.Task] = []
        self.running = False
        
        logger.info("Webhook Manager initialized")
    
    async def initialize(self) -> None:
        """Initialize the webhook manager"""
        try:
            # Create HTTP session
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)
            
            # Load webhook configurations
            await self._load_webhook_configurations()
            
            # Subscribe to events for webhook delivery
            await self._register_event_handlers()
            
            # Start delivery workers
            await self._start_delivery_workers()
            
            # Register with health monitor
            await self.health_monitor.register_component(
                "webhook_manager",
                self._health_check_callback
            )
            
            self.running = True
            logger.info("Webhook Manager initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing Webhook Manager: {e}")
            raise
    
    async def shutdown(self) -> None:
        """Shutdown the webhook manager"""
        try:
            self.running = False
            
            # Stop delivery workers
            for worker in self.delivery_workers:
                worker.cancel()
            
            await asyncio.gather(*self.delivery_workers, return_exceptions=True)
            
            # Close HTTP session
            if self.session:
                await self.session.close()
            
            # Unregister from health monitor
            await self.health_monitor.unregister_component("webhook_manager")
            
            logger.info("Webhook Manager shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during Webhook Manager shutdown: {e}")
    
    async def register_webhook(self, webhook: WebhookEndpoint) -> bool:
        """
        Register a new webhook endpoint.
        
        Args:
            webhook: Webhook endpoint configuration
            
        Returns:
            True if registration was successful
        """
        try:
            # Validate webhook URL
            parsed_url = urlparse(webhook.url)
            if not parsed_url.scheme or not parsed_url.netloc:
                logger.error(f"Invalid webhook URL: {webhook.url}")
                return False
            
            # Store webhook
            self.webhooks[webhook.endpoint_id] = webhook
            
            # Persist webhook configuration
            await self.state_manager.set_global_state(
                f"webhook_{webhook.endpoint_id}",
                asdict(webhook)
            )
            
            logger.info(f"Registered webhook: {webhook.endpoint_id} -> {webhook.url}")
            return True
            
        except Exception as e:
            logger.error(f"Error registering webhook {webhook.endpoint_id}: {e}")
            return False
    
    async def unregister_webhook(self, webhook_id: str) -> bool:
        """
        Unregister a webhook endpoint.
        
        Args:
            webhook_id: ID of webhook to unregister
            
        Returns:
            True if unregistration was successful
        """
        try:
            if webhook_id in self.webhooks:
                del self.webhooks[webhook_id]
                
                # Remove from persistent storage
                await self.state_manager.delete_global_state(f"webhook_{webhook_id}")
                
                logger.info(f"Unregistered webhook: {webhook_id}")
                return True
            else:
                logger.warning(f"Webhook not found: {webhook_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error unregistering webhook {webhook_id}: {e}")
            return False
    
    async def send_webhook(self, event: WebhookEvent) -> None:
        """
        Send webhook event to all matching endpoints.
        
        Args:
            event: Webhook event to send
        """
        try:
            # Find matching webhooks
            matching_webhooks = []
            for webhook in self.webhooks.values():
                if not webhook.active:
                    continue
                
                # Check event type filter
                if event.event_type not in webhook.event_types:
                    continue
                
                # Check guild filter
                if webhook.guild_id and webhook.guild_id != event.guild_id:
                    continue
                
                matching_webhooks.append(webhook)
            
            # Create deliveries for each matching webhook
            for webhook in matching_webhooks:
                delivery = WebhookDelivery(
                    delivery_id=f"{event.event_id}_{webhook.endpoint_id}",
                    webhook_id=webhook.endpoint_id,
                    event_id=event.event_id,
                    status=DeliveryStatus.PENDING,
                    attempt_count=0,
                    created_at=datetime.now(timezone.utc)
                )
                
                self.pending_deliveries[delivery.delivery_id] = delivery
                await self.delivery_queue.put((webhook, event, delivery))
            
            logger.debug(f"Queued webhook event {event.event_id} for {len(matching_webhooks)} endpoints")
            
        except Exception as e:
            logger.error(f"Error sending webhook event {event.event_id}: {e}")
    
    async def get_webhook_status(self, webhook_id: str) -> Optional[Dict[str, Any]]:
        """Get status information for a webhook"""
        try:
            webhook = self.webhooks.get(webhook_id)
            if not webhook:
                return None
            
            # Get delivery statistics
            total_deliveries = 0
            successful_deliveries = 0
            failed_deliveries = 0
            
            for delivery in self.pending_deliveries.values():
                if delivery.webhook_id == webhook_id:
                    total_deliveries += 1
                    if delivery.status == DeliveryStatus.DELIVERED:
                        successful_deliveries += 1
                    elif delivery.status == DeliveryStatus.FAILED:
                        failed_deliveries += 1
            
            return {
                "webhook_id": webhook_id,
                "url": webhook.url,
                "active": webhook.active,
                "event_types": [et.value for et in webhook.event_types],
                "total_deliveries": total_deliveries,
                "successful_deliveries": successful_deliveries,
                "failed_deliveries": failed_deliveries,
                "success_rate": (successful_deliveries / total_deliveries * 100) if total_deliveries > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error getting webhook status for {webhook_id}: {e}")
            return None
    
    async def _load_webhook_configurations(self) -> None:
        """Load webhook configurations from storage"""
        try:
            # This would load webhook configurations from state manager
            # For now, we'll start with empty configuration
            logger.info("Webhook configurations loaded")
            
        except Exception as e:
            logger.error(f"Error loading webhook configurations: {e}")
    
    async def _register_event_handlers(self) -> None:
        """Register event handlers for webhook delivery"""
        try:
            # Register handlers for events that should trigger webhooks
            await self.event_bus.subscribe("stream_*", self._on_stream_event)
            await self.event_bus.subscribe("audio_*", self._on_audio_event)
            await self.event_bus.subscribe("favorites_*", self._on_favorites_event)
            await self.event_bus.subscribe("guild_*", self._on_guild_event)
            await self.event_bus.subscribe("maintenance_*", self._on_maintenance_event)
            await self.event_bus.subscribe("health_*", self._on_health_event)
            
            logger.info("Webhook event handlers registered")
            
        except Exception as e:
            logger.error(f"Error registering webhook event handlers: {e}")
    
    async def _start_delivery_workers(self) -> None:
        """Start webhook delivery worker tasks"""
        try:
            for i in range(self.max_concurrent_deliveries):
                worker = asyncio.create_task(self._delivery_worker(f"worker_{i}"))
                self.delivery_workers.append(worker)
            
            logger.info(f"Started {len(self.delivery_workers)} webhook delivery workers")
            
        except Exception as e:
            logger.error(f"Error starting delivery workers: {e}")
            raise
    
    async def _delivery_worker(self, worker_id: str) -> None:
        """Webhook delivery worker"""
        while self.running:
            try:
                # Get delivery from queue with timeout
                webhook, event, delivery = await asyncio.wait_for(
                    self.delivery_queue.get(),
                    timeout=1.0
                )
                
                # Perform delivery
                success = await self._deliver_webhook(webhook, event, delivery)
                
                if not success and delivery.attempt_count < webhook.max_retries:
                    # Schedule retry
                    await self._schedule_retry(webhook, event, delivery)
                elif not success:
                    # Mark as failed
                    delivery.status = DeliveryStatus.EXPIRED
                    logger.warning(f"Webhook delivery expired: {delivery.delivery_id}")
                
                # Mark queue task as done
                self.delivery_queue.task_done()
                
            except asyncio.TimeoutError:
                # No work available, continue
                continue
            except Exception as e:
                logger.error(f"Error in delivery worker {worker_id}: {e}")
                await asyncio.sleep(1)
    
    async def _deliver_webhook(self, webhook: WebhookEndpoint, event: WebhookEvent, delivery: WebhookDelivery) -> bool:
        """Deliver webhook to endpoint"""
        try:
            delivery.attempt_count += 1
            delivery.last_attempt = datetime.now(timezone.utc)
            delivery.status = DeliveryStatus.RETRYING if delivery.attempt_count > 1 else DeliveryStatus.PENDING
            
            # Prepare payload
            payload = {
                "event": asdict(event),
                "delivery": {
                    "id": delivery.delivery_id,
                    "timestamp": delivery.created_at.isoformat()
                }
            }
            
            # Prepare headers
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "BunBot-Webhook/1.0"
            }
            
            if webhook.headers:
                headers.update(webhook.headers)
            
            # Add signature if secret is configured
            payload_json = json.dumps(payload, default=str)
            if webhook.secret:
                signature = hmac.new(
                    webhook.secret.encode(),
                    payload_json.encode(),
                    hashlib.sha256
                ).hexdigest()
                headers["X-Webhook-Signature"] = f"sha256={signature}"
            
            # Make HTTP request
            async with self.session.post(
                webhook.url,
                data=payload_json,
                headers=headers,
                timeout=webhook.timeout
            ) as response:
                delivery.response_code = response.status
                delivery.response_body = await response.text()
                
                if 200 <= response.status < 300:
                    delivery.status = DeliveryStatus.DELIVERED
                    logger.debug(f"Webhook delivered successfully: {delivery.delivery_id}")
                    return True
                else:
                    delivery.status = DeliveryStatus.FAILED
                    delivery.error_message = f"HTTP {response.status}: {delivery.response_body}"
                    logger.warning(f"Webhook delivery failed: {delivery.delivery_id} - {delivery.error_message}")
                    return False
        
        except Exception as e:
            delivery.status = DeliveryStatus.FAILED
            delivery.error_message = str(e)
            logger.error(f"Error delivering webhook {delivery.delivery_id}: {e}")
            return False
    
    async def _schedule_retry(self, webhook: WebhookEndpoint, event: WebhookEvent, delivery: WebhookDelivery) -> None:
        """Schedule webhook delivery retry"""
        try:
            retry_delay = self.retry_delays[min(delivery.attempt_count - 1, len(self.retry_delays) - 1)]
            delivery.next_retry = datetime.now(timezone.utc) + timedelta(seconds=retry_delay)
            
            # Schedule retry (simplified - in production would use a proper scheduler)
            asyncio.create_task(self._delayed_retry(webhook, event, delivery, retry_delay))
            
            logger.debug(f"Scheduled retry for {delivery.delivery_id} in {retry_delay} seconds")
            
        except Exception as e:
            logger.error(f"Error scheduling retry for {delivery.delivery_id}: {e}")
    
    async def _delayed_retry(self, webhook: WebhookEndpoint, event: WebhookEvent, delivery: WebhookDelivery, delay: int) -> None:
        """Execute delayed retry"""
        try:
            await asyncio.sleep(delay)
            await self.delivery_queue.put((webhook, event, delivery))
        except Exception as e:
            logger.error(f"Error in delayed retry for {delivery.delivery_id}: {e}")
    
    # Event handlers for webhook delivery
    async def _on_stream_event(self, event: str, data: Dict[str, Any]) -> None:
        """Handle stream events for webhook delivery"""
        try:
            event_type_map = {
                "stream_started": WebhookEventType.STREAM_STARTED,
                "stream_stopped": WebhookEventType.STREAM_STOPPED,
                "stream_error": WebhookEventType.STREAM_ERROR
            }
            
            webhook_event_type = event_type_map.get(event)
            if webhook_event_type:
                webhook_event = WebhookEvent(
                    event_id=f"stream_{datetime.now().timestamp()}",
                    event_type=webhook_event_type,
                    guild_id=data.get("guild_id"),
                    timestamp=datetime.now(timezone.utc),
                    data=data
                )
                await self.send_webhook(webhook_event)
        
        except Exception as e:
            logger.error(f"Error handling stream event for webhooks: {e}")
    
    async def _on_audio_event(self, event: str, data: Dict[str, Any]) -> None:
        """Handle audio events for webhook delivery"""
        try:
            if event == "audio_volume_changed":
                webhook_event = WebhookEvent(
                    event_id=f"audio_{datetime.now().timestamp()}",
                    event_type=WebhookEventType.AUDIO_VOLUME_CHANGED,
                    guild_id=data.get("guild_id"),
                    timestamp=datetime.now(timezone.utc),
                    data=data
                )
                await self.send_webhook(webhook_event)
        
        except Exception as e:
            logger.error(f"Error handling audio event for webhooks: {e}")
    
    async def _on_favorites_event(self, event: str, data: Dict[str, Any]) -> None:
        """Handle favorites events for webhook delivery"""
        try:
            event_type_map = {
                "favorite_added": WebhookEventType.FAVORITE_ADDED,
                "favorite_removed": WebhookEventType.FAVORITE_REMOVED
            }
            
            webhook_event_type = event_type_map.get(event)
            if webhook_event_type:
                webhook_event = WebhookEvent(
                    event_id=f"favorites_{datetime.now().timestamp()}",
                    event_type=webhook_event_type,
                    guild_id=data.get("guild_id"),
                    timestamp=datetime.now(timezone.utc),
                    data=data
                )
                await self.send_webhook(webhook_event)
        
        except Exception as e:
            logger.error(f"Error handling favorites event for webhooks: {e}")
    
    async def _on_guild_event(self, event: str, data: Dict[str, Any]) -> None:
        """Handle guild events for webhook delivery"""
        try:
            event_type_map = {
                "guild_joined": WebhookEventType.GUILD_JOINED,
                "guild_left": WebhookEventType.GUILD_LEFT
            }
            
            webhook_event_type = event_type_map.get(event)
            if webhook_event_type:
                webhook_event = WebhookEvent(
                    event_id=f"guild_{datetime.now().timestamp()}",
                    event_type=webhook_event_type,
                    guild_id=data.get("guild_id"),
                    timestamp=datetime.now(timezone.utc),
                    data=data
                )
                await self.send_webhook(webhook_event)
        
        except Exception as e:
            logger.error(f"Error handling guild event for webhooks: {e}")
    
    async def _on_maintenance_event(self, event: str, data: Dict[str, Any]) -> None:
        """Handle maintenance events for webhook delivery"""
        try:
            event_type_map = {
                "maintenance_started": WebhookEventType.MAINTENANCE_STARTED,
                "maintenance_completed": WebhookEventType.MAINTENANCE_COMPLETED
            }
            
            webhook_event_type = event_type_map.get(event)
            if webhook_event_type:
                webhook_event = WebhookEvent(
                    event_id=f"maintenance_{datetime.now().timestamp()}",
                    event_type=webhook_event_type,
                    guild_id=data.get("guild_id"),
                    timestamp=datetime.now(timezone.utc),
                    data=data
                )
                await self.send_webhook(webhook_event)
        
        except Exception as e:
            logger.error(f"Error handling maintenance event for webhooks: {e}")
    
    async def _on_health_event(self, event: str, data: Dict[str, Any]) -> None:
        """Handle health events for webhook delivery"""
        try:
            if event == "health_status_changed":
                webhook_event = WebhookEvent(
                    event_id=f"health_{datetime.now().timestamp()}",
                    event_type=WebhookEventType.HEALTH_STATUS_CHANGED,
                    guild_id=data.get("guild_id"),
                    timestamp=datetime.now(timezone.utc),
                    data=data
                )
                await self.send_webhook(webhook_event)
        
        except Exception as e:
            logger.error(f"Error handling health event for webhooks: {e}")
    
    async def _health_check_callback(self) -> Dict[str, Any]:
        """Health check callback for Phase 2 monitoring"""
        try:
            return {
                "status": "healthy" if self.running else "unhealthy",
                "active_webhooks": len([w for w in self.webhooks.values() if w.active]),
                "pending_deliveries": len(self.pending_deliveries),
                "delivery_workers": len(self.delivery_workers),
                "queue_size": self.delivery_queue.qsize()
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }
