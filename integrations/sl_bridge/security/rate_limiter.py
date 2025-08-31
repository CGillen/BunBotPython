"""
Rate Limiting for SL Bridge

Provides rate limiting functionality to prevent API abuse
Based on token bucket algorithm with Redis-like interface (in-memory for now)
"""

import time
import logging
import asyncio
from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
from collections import defaultdict

from core import ServiceRegistry

logger = logging.getLogger('sl_bridge.security.rate_limiter')


@dataclass
class RateLimitRule:
    """Rate limiting rule configuration"""
    requests: int  # Number of requests allowed
    period: int    # Time period in seconds
    burst: Optional[int] = None  # Burst allowance (defaults to requests)
    
    def __post_init__(self):
        if self.burst is None:
            self.burst = self.requests


@dataclass
class TokenBucket:
    """Token bucket for rate limiting"""
    capacity: int
    tokens: float
    refill_rate: float  # tokens per second
    last_refill: float = field(default_factory=time.time)
    
    def consume(self, tokens: int = 1) -> bool:
        """
        Try to consume tokens from bucket.
        
        Args:
            tokens: Number of tokens to consume
            
        Returns:
            True if tokens were consumed, False if rate limited
        """
        current_time = time.time()
        
        # Refill tokens based on elapsed time
        elapsed = current_time - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = current_time
        
        # Try to consume tokens
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        
        return False
    
    def time_until_available(self, tokens: int = 1) -> float:
        """
        Calculate time until requested tokens are available.
        
        Args:
            tokens: Number of tokens needed
            
        Returns:
            Time in seconds until tokens are available
        """
        if self.tokens >= tokens:
            return 0.0
        
        needed_tokens = tokens - self.tokens
        return needed_tokens / self.refill_rate


class RateLimiter:
    """
    Rate limiter with multiple algorithms and key-based limiting.
    
    Provides token bucket rate limiting with configurable rules
    and integration with SL Bridge authentication system.
    """
    
    def __init__(self, service_registry: ServiceRegistry):
        self.service_registry = service_registry
        
        # Rate limit rules by endpoint/permission
        self.rules: Dict[str, RateLimitRule] = self._define_rate_limit_rules()
        
        # Token buckets by key (user_id, ip, etc.)
        self.buckets: Dict[str, TokenBucket] = {}
        
        # Global rate limiting
        self.global_bucket = TokenBucket(
            capacity=1000,  # 1000 requests
            tokens=1000,
            refill_rate=100  # 100 requests per second
        )
        
        # Cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
        
        logger.info("RateLimiter initialized")
    
    def _define_rate_limit_rules(self) -> Dict[str, RateLimitRule]:
        """Define rate limiting rules for different endpoints"""
        return {
            # Authentication endpoints
            "auth.token_create": RateLimitRule(requests=10, period=300),  # 10 per 5 min
            "auth.token_refresh": RateLimitRule(requests=20, period=300),  # 20 per 5 min
            
            # Stream control endpoints  
            "stream.play": RateLimitRule(requests=30, period=60),   # 30 per minute
            "stream.stop": RateLimitRule(requests=60, period=60),   # 60 per minute
            "stream.status": RateLimitRule(requests=120, period=60), # 120 per minute
            
            # Favorites endpoints
            "favorites.read": RateLimitRule(requests=100, period=60),  # 100 per minute
            "favorites.write": RateLimitRule(requests=20, period=60),  # 20 per minute
            "favorites.delete": RateLimitRule(requests=10, period=60), # 10 per minute
            
            # Audio endpoints
            "audio.volume": RateLimitRule(requests=60, period=60),   # 60 per minute
            "audio.eq": RateLimitRule(requests=30, period=60),       # 30 per minute
            "audio.info": RateLimitRule(requests=120, period=60),    # 120 per minute
            
            # WebSocket endpoints
            "websocket.connect": RateLimitRule(requests=10, period=60), # 10 per minute
            "websocket.message": RateLimitRule(requests=300, period=60), # 300 per minute
            
            # Default rule
            "default": RateLimitRule(requests=60, period=60)  # 60 per minute
        }
    
    async def check_rate_limit(self, key: str, rule_name: str = "default", 
                             tokens: int = 1) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if request is within rate limits.
        
        Args:
            key: Rate limiting key (user_id, IP, etc.)
            rule_name: Name of the rate limiting rule to apply
            tokens: Number of tokens to consume
            
        Returns:
            Tuple of (allowed, metadata)
        """
        try:
            # Check global rate limit first
            if not self.global_bucket.consume(tokens):
                return False, {
                    "reason": "global_rate_limit",
                    "retry_after": self.global_bucket.time_until_available(tokens),
                    "limit_type": "global"
                }
            
            # Get or create bucket for key
            bucket = await self._get_or_create_bucket(key, rule_name)
            
            # Check rate limit
            if bucket.consume(tokens):
                return True, {
                    "remaining": int(bucket.tokens),
                    "limit": bucket.capacity,
                    "reset_time": time.time() + (bucket.capacity - bucket.tokens) / bucket.refill_rate
                }
            else:
                # Rate limited
                retry_after = bucket.time_until_available(tokens)
                
                logger.warning(f"Rate limit exceeded for key {key} on rule {rule_name}")
                
                return False, {
                    "reason": "rate_limit_exceeded",
                    "retry_after": retry_after,
                    "limit_type": "user",
                    "rule": rule_name,
                    "key": key
                }
            
        except Exception as e:
            logger.error(f"Error checking rate limit for {key}: {e}")
            # Allow request on error (fail open)
            return True, {"error": "rate_limit_check_failed"}
    
    async def _get_or_create_bucket(self, key: str, rule_name: str) -> TokenBucket:
        """
        Get existing bucket or create new one for key.
        
        Args:
            key: Rate limiting key
            rule_name: Rule name to apply
            
        Returns:
            TokenBucket for the key
        """
        bucket_key = f"{rule_name}:{key}"
        
        if bucket_key not in self.buckets:
            rule = self.rules.get(rule_name, self.rules["default"])
            
            self.buckets[bucket_key] = TokenBucket(
                capacity=rule.burst or rule.requests,
                tokens=rule.burst or rule.requests,
                refill_rate=rule.requests / rule.period
            )
        
        return self.buckets[bucket_key]
    
    async def reset_rate_limit(self, key: str, rule_name: Optional[str] = None) -> bool:
        """
        Reset rate limit for a key.
        
        Args:
            key: Rate limiting key
            rule_name: Specific rule to reset (None for all)
            
        Returns:
            True if reset successfully
        """
        try:
            if rule_name:
                bucket_key = f"{rule_name}:{key}"
                if bucket_key in self.buckets:
                    bucket = self.buckets[bucket_key]
                    bucket.tokens = bucket.capacity
                    bucket.last_refill = time.time()
                    logger.info(f"Reset rate limit for {bucket_key}")
            else:
                # Reset all buckets for key
                keys_to_reset = [k for k in self.buckets.keys() if k.endswith(f":{key}")]
                for bucket_key in keys_to_reset:
                    bucket = self.buckets[bucket_key]
                    bucket.tokens = bucket.capacity
                    bucket.last_refill = time.time()
                
                logger.info(f"Reset all rate limits for key {key}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error resetting rate limit for {key}: {e}")
            return False
    
    async def get_rate_limit_status(self, key: str, rule_name: str = "default") -> Dict[str, Any]:
        """
        Get current rate limit status for a key.
        
        Args:
            key: Rate limiting key
            rule_name: Rule name to check
            
        Returns:
            Dict with rate limit status
        """
        try:
            bucket_key = f"{rule_name}:{key}"
            
            if bucket_key not in self.buckets:
                rule = self.rules.get(rule_name, self.rules["default"])
                return {
                    "limit": rule.requests,
                    "remaining": rule.requests,
                    "reset_time": time.time() + rule.period,
                    "period": rule.period
                }
            
            bucket = self.buckets[bucket_key]
            
            # Trigger refill calculation
            bucket.consume(0)
            
            return {
                "limit": bucket.capacity,
                "remaining": int(bucket.tokens),
                "reset_time": time.time() + (bucket.capacity - bucket.tokens) / bucket.refill_rate,
                "period": self.rules.get(rule_name, self.rules["default"]).period
            }
            
        except Exception as e:
            logger.error(f"Error getting rate limit status for {key}: {e}")
            return {"error": "failed_to_get_status"}
    
    async def start_cleanup_task(self) -> None:
        """Start background cleanup task for expired buckets"""
        if self._cleanup_task and not self._cleanup_task.done():
            return
        
        self._cleanup_task = asyncio.create_task(self._cleanup_expired_buckets())
        logger.info("Started rate limiter cleanup task")
    
    async def stop_cleanup_task(self) -> None:
        """Stop background cleanup task"""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Stopped rate limiter cleanup task")
    
    async def _cleanup_expired_buckets(self) -> None:
        """Background task to clean up expired buckets"""
        try:
            while True:
                current_time = time.time()
                
                # Remove buckets that haven't been used for 1 hour
                expired_keys = []
                for key, bucket in self.buckets.items():
                    if current_time - bucket.last_refill > 3600:  # 1 hour
                        expired_keys.append(key)
                
                for key in expired_keys:
                    del self.buckets[key]
                
                if expired_keys:
                    logger.debug(f"Cleaned up {len(expired_keys)} expired rate limit buckets")
                
                # Sleep for 10 minutes before next cleanup
                await asyncio.sleep(600)
                
        except asyncio.CancelledError:
            logger.info("Rate limiter cleanup task cancelled")
        except Exception as e:
            logger.error(f"Error in rate limiter cleanup task: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get rate limiter statistics.
        
        Returns:
            Dict with statistics
        """
        try:
            return {
                "total_buckets": len(self.buckets),
                "global_bucket_tokens": int(self.global_bucket.tokens),
                "global_bucket_capacity": self.global_bucket.capacity,
                "rules_configured": len(self.rules),
                "cleanup_task_running": self._cleanup_task and not self._cleanup_task.done()
            }
        except Exception as e:
            logger.error(f"Error getting rate limiter statistics: {e}")
            return {"error": "failed_to_get_statistics"}
    
    async def add_rule(self, name: str, rule: RateLimitRule) -> bool:
        """
        Add or update a rate limiting rule.
        
        Args:
            name: Rule name
            rule: Rate limiting rule
            
        Returns:
            True if added successfully
        """
        try:
            self.rules[name] = rule
            logger.info(f"Added rate limiting rule {name}: {rule.requests}/{rule.period}s")
            return True
        except Exception as e:
            logger.error(f"Error adding rate limiting rule {name}: {e}")
            return False
    
    async def remove_rule(self, name: str) -> bool:
        """
        Remove a rate limiting rule.
        
        Args:
            name: Rule name to remove
            
        Returns:
            True if removed successfully
        """
        try:
            if name in self.rules and name != "default":
                del self.rules[name]
                
                # Remove associated buckets
                keys_to_remove = [k for k in self.buckets.keys() if k.startswith(f"{name}:")]
                for key in keys_to_remove:
                    del self.buckets[key]
                
                logger.info(f"Removed rate limiting rule {name}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error removing rate limiting rule {name}: {e}")
            return False
