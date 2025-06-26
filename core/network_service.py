"""
Network Service for BunBot
Provides centralized HTTP/ICY operations with resilience patterns
"""

import asyncio
import logging
import time
import urllib.request
import urllib.error
from typing import Dict, Any, Optional, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta

from .config_manager import get_config

logger = logging.getLogger('core.network_service')

class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered

@dataclass
class NetworkMetrics:
    """Network operation metrics"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    timeout_requests: int = 0
    average_response_time: float = 0.0
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None

@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration"""
    failure_threshold: int = 5
    timeout_seconds: int = 60
    half_open_max_calls: int = 3
    success_threshold: int = 2

class CircuitBreaker:
    """
    Circuit breaker implementation for network resilience.
    
    Prevents cascading failures by failing fast when a service
    is consistently unavailable.
    """
    
    def __init__(self, name: str, config: CircuitBreakerConfig):
        self.name = name
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.half_open_calls = 0
        
        logger.debug(f"Circuit breaker '{name}' initialized")
    
    def can_execute(self) -> bool:
        """Check if request can be executed"""
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            # Check if timeout period has passed
            if (self.last_failure_time and 
                datetime.now() - self.last_failure_time > timedelta(seconds=self.config.timeout_seconds)):
                self.state = CircuitState.HALF_OPEN
                self.half_open_calls = 0
                logger.info(f"Circuit breaker '{self.name}' transitioning to HALF_OPEN")
                return True
            return False
        
        if self.state == CircuitState.HALF_OPEN:
            return self.half_open_calls < self.config.half_open_max_calls
        
        return False
    
    def record_success(self):
        """Record successful operation"""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
                logger.info(f"Circuit breaker '{self.name}' closed after recovery")
        else:
            self.failure_count = 0
    
    def record_failure(self):
        """Record failed operation"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.state == CircuitState.CLOSED:
            if self.failure_count >= self.config.failure_threshold:
                self.state = CircuitState.OPEN
                logger.warning(f"Circuit breaker '{self.name}' opened after {self.failure_count} failures")
        
        elif self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            self.success_count = 0
            logger.warning(f"Circuit breaker '{self.name}' reopened during half-open test")
        
        if self.state == CircuitState.HALF_OPEN:
            self.half_open_calls += 1

class NetworkService:
    """
    Network service with resilience patterns.
    
    Provides centralized HTTP/ICY operations with:
    - Circuit breaker pattern
    - Exponential backoff retry logic
    - Configurable timeouts
    - Connection health monitoring
    - Metrics collection
    """
    
    def __init__(self):
        self.config = get_config()
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.metrics: Dict[str, NetworkMetrics] = {}
        self._session_cache: Dict[str, Any] = {}
        
        # Initialize urllib_hack
        try:
            import urllib_hack
            urllib_hack.init_urllib_hack(self.config.tls_verify)
            logger.info("urllib_hack initialized for ICY protocol support")
        except ImportError:
            logger.warning("urllib_hack not available, ICY protocol may not work")
        
        logger.info("NetworkService initialized")
    
    def get_circuit_breaker(self, service_name: str) -> CircuitBreaker:
        """Get or create circuit breaker for service"""
        if service_name not in self.circuit_breakers:
            config = CircuitBreakerConfig(
                failure_threshold=self.config.circuit_breaker_threshold,
                timeout_seconds=self.config.circuit_breaker_timeout
            )
            self.circuit_breakers[service_name] = CircuitBreaker(service_name, config)
        
        return self.circuit_breakers[service_name]
    
    def get_metrics(self, service_name: str) -> NetworkMetrics:
        """Get or create metrics for service"""
        if service_name not in self.metrics:
            self.metrics[service_name] = NetworkMetrics()
        return self.metrics[service_name]
    
    async def get_with_resilience(
        self, 
        url: str, 
        timeout: Optional[int] = None,
        service_name: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Perform HTTP GET with full resilience patterns.
        
        Args:
            url: URL to fetch
            timeout: Request timeout (uses config default if None)
            service_name: Service name for circuit breaker (derived from URL if None)
            headers: Optional HTTP headers
            
        Returns:
            Response data with metadata
            
        Raises:
            NetworkTimeoutError: On timeout
            CircuitBreakerOpenError: When circuit breaker is open
            NetworkError: On other network errors
        """
        # Determine service name and timeout
        service_name = service_name or self._extract_service_name(url)
        timeout = timeout or self.config.network_timeout
        
        # Get circuit breaker and metrics
        circuit_breaker = self.get_circuit_breaker(service_name)
        metrics = self.get_metrics(service_name)
        
        # Check circuit breaker
        if not circuit_breaker.can_execute():
            metrics.failed_requests += 1
            raise CircuitBreakerOpenError(f"Circuit breaker open for {service_name}")
        
        # Perform request with retry logic
        return await self._execute_with_retry(
            url, timeout, service_name, headers, circuit_breaker, metrics
        )
    
    async def _execute_with_retry(
        self,
        url: str,
        timeout: int,
        service_name: str,
        headers: Optional[Dict[str, str]],
        circuit_breaker: CircuitBreaker,
        metrics: NetworkMetrics
    ) -> Dict[str, Any]:
        """Execute request with exponential backoff retry"""
        
        last_exception = None
        retry_delays = [1, 2, 4]  # Exponential backoff
        
        for attempt in range(self.config.retry_attempts):
            try:
                start_time = time.time()
                
                # Create request
                request = urllib.request.Request(url)
                if headers:
                    for key, value in headers.items():
                        request.add_header(key, value)
                
                # Execute request with timeout
                response = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None, 
                        lambda: urllib.request.urlopen(request, timeout=timeout)
                    ),
                    timeout=timeout + 1  # Add buffer for asyncio timeout
                )
                
                # Calculate response time
                response_time = time.time() - start_time
                
                # Read response data
                data = response.read()
                
                # Update metrics
                metrics.total_requests += 1
                metrics.successful_requests += 1
                metrics.last_success = datetime.now()
                
                # Update average response time
                if metrics.average_response_time == 0:
                    metrics.average_response_time = response_time
                else:
                    metrics.average_response_time = (
                        metrics.average_response_time * 0.8 + response_time * 0.2
                    )
                
                # Record success in circuit breaker
                circuit_breaker.record_success()
                
                logger.debug(f"Request to {service_name} succeeded in {response_time:.3f}s")
                
                return {
                    'status_code': response.getcode(),
                    'headers': dict(response.headers),
                    'data': data,
                    'response_time': response_time,
                    'url': url,
                    'attempt': attempt + 1
                }
                
            except asyncio.TimeoutError as e:
                last_exception = e
                metrics.total_requests += 1
                metrics.timeout_requests += 1
                metrics.last_failure = datetime.now()
                
                logger.warning(f"Timeout on attempt {attempt + 1} for {service_name}: {e}")
                
            except urllib.error.URLError as e:
                last_exception = e
                metrics.total_requests += 1
                metrics.failed_requests += 1
                metrics.last_failure = datetime.now()
                
                logger.warning(f"URL error on attempt {attempt + 1} for {service_name}: {e}")
                
            except Exception as e:
                last_exception = e
                metrics.total_requests += 1
                metrics.failed_requests += 1
                metrics.last_failure = datetime.now()
                
                logger.error(f"Unexpected error on attempt {attempt + 1} for {service_name}: {e}")
            
            # Wait before retry (except on last attempt)
            if attempt < self.config.retry_attempts - 1:
                delay = retry_delays[min(attempt, len(retry_delays) - 1)]
                logger.debug(f"Retrying {service_name} in {delay}s (attempt {attempt + 1})")
                await asyncio.sleep(delay)
        
        # All retries failed
        circuit_breaker.record_failure()
        
        if isinstance(last_exception, asyncio.TimeoutError):
            raise NetworkTimeoutError(f"Request to {service_name} timed out after {self.config.retry_attempts} attempts")
        else:
            raise NetworkError(f"Request to {service_name} failed after {self.config.retry_attempts} attempts: {last_exception}")
    
    def _extract_service_name(self, url: str) -> str:
        """Extract service name from URL for circuit breaker identification"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return f"{parsed.netloc}:{parsed.port}" if parsed.port else parsed.netloc
        except Exception:
            return "unknown_service"
    
    def get_service_health(self, service_name: str) -> Dict[str, Any]:
        """Get health status for a service"""
        circuit_breaker = self.circuit_breakers.get(service_name)
        metrics = self.metrics.get(service_name)
        
        if not circuit_breaker or not metrics:
            return {
                'service_name': service_name,
                'status': 'unknown',
                'circuit_state': 'unknown',
                'metrics': {}
            }
        
        success_rate = 0.0
        if metrics.total_requests > 0:
            success_rate = metrics.successful_requests / metrics.total_requests
        
        return {
            'service_name': service_name,
            'status': 'healthy' if circuit_breaker.state == CircuitState.CLOSED else 'unhealthy',
            'circuit_state': circuit_breaker.state.value,
            'metrics': {
                'total_requests': metrics.total_requests,
                'success_rate': success_rate,
                'average_response_time': metrics.average_response_time,
                'last_success': metrics.last_success.isoformat() if metrics.last_success else None,
                'last_failure': metrics.last_failure.isoformat() if metrics.last_failure else None
            }
        }
    
    def get_all_service_health(self) -> Dict[str, Dict[str, Any]]:
        """Get health status for all services"""
        return {
            service_name: self.get_service_health(service_name)
            for service_name in self.circuit_breakers.keys()
        }

# Custom exceptions
class NetworkError(Exception):
    """Base network error"""
    pass

class NetworkTimeoutError(NetworkError):
    """Network timeout error"""
    pass

class CircuitBreakerOpenError(NetworkError):
    """Circuit breaker is open"""
    pass

# Global network service instance
_global_network_service: Optional[NetworkService] = None

def get_network_service() -> NetworkService:
    """Get the global network service instance"""
    global _global_network_service
    if _global_network_service is None:
        _global_network_service = NetworkService()
    return _global_network_service
