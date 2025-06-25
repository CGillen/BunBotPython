"""
Service Registry - Dependency Injection Container for BunBot
"""

import logging
import inspect
from abc import ABC, ABCMeta
from typing import TypeVar, Type, Dict, Any, Optional, Callable, Union, Set
from enum import Enum
from dataclasses import dataclass
from threading import Lock

logger = logging.getLogger('discord.core.service_registry')

T = TypeVar('T')

class ServiceLifetime(Enum):
    """Service lifetime management options"""
    SINGLETON = "singleton"
    TRANSIENT = "transient"
    SCOPED = "scoped"  # For future web request scoping

class ServiceNotFound(Exception):
    """Raised when a requested service is not registered"""
    pass

class CircularDependencyError(Exception):
    """Raised when circular dependencies are detected"""
    pass

class ServiceConfigurationError(Exception):
    """Raised when service configuration is invalid"""
    pass

@dataclass
class ServiceDefinition:
    """Metadata for a registered service"""
    interface_type: Type
    implementation_type: Optional[Type]
    lifetime: ServiceLifetime
    factory: Optional[Callable] = None
    instance: Optional[Any] = None
    configuration: Optional[Dict[str, Any]] = None
    dependencies: Optional[Set[Type]] = None
    
    def __post_init__(self):
        if self.configuration is None:
            self.configuration = {}

class ServiceRegistry:
    """
    Dependency injection container for managing service instances.
    
    Provides type-safe service registration, resolution, and lifecycle management
    with support for complex dependency graphs and configuration injection.
    
    Usage:
        registry = ServiceRegistry()
        registry.register(IService, ConcreteService, ServiceLifetime.SINGLETON)
        service = registry.get(IService)
    """
    
    def __init__(self):
        self._services: Dict[Type, ServiceDefinition] = {}
        self._resolving: Set[Type] = set()  # Circular dependency detection
        self._lock = Lock()  # Thread safety
        logger.info("ServiceRegistry initialized")
    
    def register(
        self, 
        interface_type: Type[T], 
        implementation_type: Optional[Type[T]] = None,
        lifetime: ServiceLifetime = ServiceLifetime.SINGLETON,
        factory: Optional[Callable[..., T]] = None,
        configuration: Optional[Dict[str, Any]] = None
    ) -> 'ServiceRegistry':

        """
        Register a service with the container.
        
        Args:
            interface_type: The interface/abstract type to register
            implementation_type: The concrete implementation (if not using factory)
            lifetime: Service lifetime management
            factory: Optional factory function for complex construction
            configuration: Optional configuration dictionary
            
        Returns:
            Self for method chaining
            
        Raises:
            ServiceConfigurationError: If registration parameters are invalid
        """
        with self._lock:
            # Validation
            if implementation_type is None and factory is None:
                # Allow self-registration for concrete classes
                if not self._is_abstract(interface_type):
                    implementation_type = interface_type
                else:
                    raise ServiceConfigurationError(
                        f"Must provide implementation_type or factory for abstract type {interface_type}"
                    )
            
            if implementation_type and factory:
                raise ServiceConfigurationError(
                    "Cannot specify both implementation_type and factory"
                )
            
            # Validate implementation implements interface
            if implementation_type and interface_type != implementation_type:
                if not issubclass(implementation_type, interface_type):
                    raise ServiceConfigurationError(
                        f"{implementation_type} does not implement {interface_type}"
                    )
            
            # Analyze dependencies for the implementation
            target_for_analysis = implementation_type or factory
            dependencies = self._analyze_dependencies(target_for_analysis) if target_for_analysis else set()
            
            service_def = ServiceDefinition(
                interface_type=interface_type,
                implementation_type=implementation_type,
                lifetime=lifetime,
                factory=factory,
                configuration=configuration or {},
                dependencies=dependencies
            )
            
            self._services[interface_type] = service_def
            
            # Safe logging with proper None handling
            target_name = "factory" if factory else (implementation_type.__name__ if implementation_type else "unknown")
            logger.info(
                f"Registered service: {interface_type.__name__} -> "
                f"{target_name} ({lifetime.value})"
            )
            
            return self
    
    def register_instance(self, interface_type: Type[T], instance: T) -> 'ServiceRegistry':
        """
        Register a pre-created instance as a singleton service.
        
        Args:
            interface_type: The interface type
            instance: The pre-created instance
            
        Returns:
            Self for method chaining
        """
        with self._lock:
            service_def = ServiceDefinition(
                interface_type=interface_type,
                implementation_type=type(instance),
                lifetime=ServiceLifetime.SINGLETON,
                instance=instance
            )
            
            self._services[interface_type] = service_def
            
            logger.info(f"Registered instance: {interface_type.__name__}")
            return self
    
    def get(self, interface_type: Type[T]) -> T:
        """
        Resolve a service instance from the container.
        
        Args:
            interface_type: The interface type to resolve
            
        Returns:
            Service instance
            
        Raises:
            ServiceNotFound: If service is not registered
            CircularDependencyError: If circular dependencies detected
        """
        return self._resolve_service(interface_type)
    
    def get_optional(self, interface_type: Type[T]) -> Optional[T]:
        """
        Resolve a service instance, returning None if not registered.
        
        Args:
            interface_type: The interface type to resolve
            
        Returns:
            Service instance or None
        """
        try:
            return self.get(interface_type)
        except ServiceNotFound:
            return None
    
    def is_registered(self, interface_type: Type[T]) -> bool:
        """
        Check if a service is registered.
        
        Args:
            interface_type: The interface type to check
            
        Returns:
            True if registered, False otherwise
        """
        return interface_type in self._services
    
    def configure_service(self, interface_type: Type[T], configuration: Dict[str, Any]):
        """
        Update configuration for a registered service.
        
        Args:
            interface_type: The interface type
            configuration: Configuration dictionary
            
        Raises:
            ServiceNotFound: If service is not registered
        """
        with self._lock:
            if interface_type not in self._services:
                raise ServiceNotFound(f"Service {interface_type} is not registered")
            
            service_def = self._services[interface_type]
            if service_def.configuration is None:
                service_def.configuration = {}
            service_def.configuration.update(configuration)
            
            # If it's a singleton with an existing instance, we may need to reconfigure
            if (service_def.lifetime == ServiceLifetime.SINGLETON and 
                service_def.instance is not None and
                hasattr(service_def.instance, 'configure')):
                service_def.instance.configure(configuration)
            
            logger.info(f"Updated configuration for {interface_type.__name__}")
    
    def get_registered_services(self) -> Dict[Type, ServiceDefinition]:
        """Get all registered services (for debugging/monitoring)"""
        return self._services.copy()
    
    def _resolve_service(self, interface_type: Type[T]) -> T:
        """Internal service resolution with circular dependency detection"""
        
        # Check for circular dependencies
        if interface_type in self._resolving:
            dependency_chain = " -> ".join([t.__name__ for t in self._resolving])
            raise CircularDependencyError(
                f"Circular dependency detected: {dependency_chain} -> {interface_type.__name__}"
            )
        
        # Check if service is registered
        if interface_type not in self._services:
            raise ServiceNotFound(f"Service {interface_type.__name__} is not registered")
        
        service_def = self._services[interface_type]
        
        # Return existing singleton instance
        if (service_def.lifetime == ServiceLifetime.SINGLETON and 
            service_def.instance is not None):
            return service_def.instance
        
        # Mark as resolving for circular dependency detection
        self._resolving.add(interface_type)
        
        try:
            # Create new instance
            if service_def.factory:
                instance = self._create_from_factory(service_def)
            else:
                instance = self._create_from_type(service_def)
            
            # Configure instance if it supports configuration
            if service_def.configuration and hasattr(instance, 'configure'):
                instance.configure(service_def.configuration)
            
            # Store singleton instance
            if service_def.lifetime == ServiceLifetime.SINGLETON:
                service_def.instance = instance
            
            logger.debug(f"Resolved service: {interface_type.__name__}")
            return instance
            
        finally:
            # Remove from resolving set
            self._resolving.discard(interface_type)
    
    def _create_from_factory(self, service_def: ServiceDefinition):
        """Create instance using factory function"""
        if service_def.factory is None:
            raise ServiceConfigurationError("Factory is None")
            
        factory_sig = inspect.signature(service_def.factory)
        kwargs = {}
        
        # Resolve factory dependencies
        for param_name, param in factory_sig.parameters.items():
            if param.annotation != inspect.Parameter.empty:
                dependency = self._resolve_service(param.annotation)
                kwargs[param_name] = dependency
        
        return service_def.factory(**kwargs)
    
    def _create_from_type(self, service_def: ServiceDefinition):
        """Create instance from implementation type"""
        if service_def.implementation_type is None:
            raise ServiceConfigurationError("Implementation type is None")
            
        constructor = service_def.implementation_type.__init__
        constructor_sig = inspect.signature(constructor)
        kwargs = {}
        
        # Resolve constructor dependencies (skip 'self' parameter)
        for param_name, param in constructor_sig.parameters.items():
            if param_name == 'self':
                continue
                
            if param.annotation != inspect.Parameter.empty:
                # Handle optional dependencies
                if param.default != inspect.Parameter.empty:
                    try:
                        dependency = self._resolve_service(param.annotation)
                        kwargs[param_name] = dependency
                    except ServiceNotFound:
                        # Use default value for optional dependencies
                        pass
                else:
                    dependency = self._resolve_service(param.annotation)
                    kwargs[param_name] = dependency
        
        return service_def.implementation_type(**kwargs)
    
    def _analyze_dependencies(self, target: Union[Type, Callable]) -> Set[Type]:
        """Analyze dependencies from constructor or factory signature"""
        dependencies = set()
        
        if target is None:
            return dependencies
        
        try:
            if inspect.isclass(target):
                sig = inspect.signature(target.__init__)
            else:
                sig = inspect.signature(target)
            
            for param_name, param in sig.parameters.items():
                if param_name == 'self':
                    continue
                    
                if param.annotation != inspect.Parameter.empty:
                    dependencies.add(param.annotation)
                    
        except (ValueError, TypeError) as e:
            logger.warning(f"Could not analyze dependencies for {target}: {e}")
        
        return dependencies
    
    def _is_abstract(self, cls: Type) -> bool:
        """Check if a class is abstract"""
        return (inspect.isabstract(cls) or 
                isinstance(cls, ABCMeta) or 
                issubclass(cls, ABC))


# Global service registry instance
_global_registry: Optional[ServiceRegistry] = None

def get_service_registry() -> ServiceRegistry:
    """Get the global service registry instance"""
    global _global_registry
    if _global_registry is None:
        _global_registry = ServiceRegistry()
    return _global_registry

def configure_services_from_dict(config: Dict[str, Any]) -> ServiceRegistry:
    """
    Configure services from a configuration dictionary.
    
    Expected format:
    {
        "services": {
            "service_name": {
                "implementation": "module.path.ClassName",
                "lifetime": "singleton|transient",
                "configuration": {...}
            }
        }
    }
    """
    registry = get_service_registry()
    
    services_config = config.get('services', {})
    for service_name, service_config in services_config.items():
        # This would need import resolution - placeholder for now
        logger.info(f"Service configuration loaded for: {service_name}")
    
    return registry
