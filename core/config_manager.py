"""
Configuration Management System for BunBot
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Type, TypeVar, Union
from dataclasses import dataclass, field
from enum import Enum

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    yaml = None

try:
    from pydantic import BaseModel, validator, ValidationError
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False
    ValidationError = Exception

logger = logging.getLogger('discord.core.config_manager')

T = TypeVar('T')

class Environment(Enum):
    """Supported deployment environments"""
    DEVELOPMENT = "development"
    STAGING = "staging"  
    PRODUCTION = "production"
    TESTING = "testing"

class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing"""
    pass

@dataclass
class ConfigurationSource:
    """Configuration source metadata"""
    name: str
    path: Optional[Path] = None
    priority: int = 0
    environment_specific: bool = False
    required: bool = True

if PYDANTIC_AVAILABLE:
    class BotConfiguration(BaseModel):  # type: ignore
        """Main bot configuration model with Pydantic validation"""
        
        # Discord Configuration
        bot_token: str
        command_prefix: str = "/"
        case_insensitive: bool = True
        
        # Clustering Configuration  
        cluster_id: int = 0
        total_clusters: int = 1
        total_shards: int = 1
        
        # Logging Configuration
        log_level: str = "INFO"
        log_file_path: str = "./log.txt"
        log_max_bytes: int = 32 * 1024 * 1024  # 32MB
        log_backup_count: int = 5
        
        # Database Configuration
        database_path: str = "bunbot.db"
        database_url: Optional[str] = None  # For future cloud DB support
        
        # TLS Configuration
        tls_verify: bool = True
        
        # Audio Configuration
        volume_normalization: bool = True
        default_volume: float = 1.0
        audio_effects_enabled: bool = True
        crossfade_duration: float = 3.0
        
        # Monitoring Configuration
        health_check_interval: int = 30
        metrics_retention_days: int = 30
        alert_thresholds: Dict[str, float] = field(default_factory=lambda: {
            "cpu_usage": 80.0,
            "memory_usage": 85.0,
            "response_time": 2.0
        })
        
        # Second Life Integration
        sl_bridge_enabled: bool = False
        sl_bridge_port: int = 8080
        sl_bridge_host: str = "localhost"
        sl_api_key_length: int = 32
        
        # Integration Configuration
        webhook_timeout: int = 10
        webhook_retry_attempts: int = 3
        
        @validator('log_level')
        def validate_log_level(cls, v):
            valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
            if v.upper() not in valid_levels:
                raise ValueError(f'log_level must be one of {valid_levels}')
            return v.upper()
        
        @validator('default_volume')
        def validate_volume(cls, v):
            if not 0.0 <= v <= 2.0:
                raise ValueError('default_volume must be between 0.0 and 2.0')
            return v
        
        @validator('bot_token')
        def validate_bot_token(cls, v):
            if not v or len(v) < 50:  # Discord bot tokens are typically much longer
                raise ValueError('bot_token must be a valid Discord bot token')
            return v

else:
    class BotConfiguration:
        """Main bot configuration model without Pydantic (fallback)"""
        
        def __init__(self, **kwargs):
            # Discord Configuration
            self.bot_token = kwargs.get('bot_token', '')
            self.command_prefix = kwargs.get('command_prefix', '/')
            self.case_insensitive = kwargs.get('case_insensitive', True)
            
            # Clustering Configuration  
            self.cluster_id = kwargs.get('cluster_id', 0)
            self.total_clusters = kwargs.get('total_clusters', 1)
            self.total_shards = kwargs.get('total_shards', 1)
            
            # Logging Configuration
            self.log_level = kwargs.get('log_level', 'INFO').upper()
            self.log_file_path = kwargs.get('log_file_path', './log.txt')
            self.log_max_bytes = kwargs.get('log_max_bytes', 32 * 1024 * 1024)
            self.log_backup_count = kwargs.get('log_backup_count', 5)
            
            # Database Configuration
            self.database_path = kwargs.get('database_path', 'bunbot.db')
            self.database_url = kwargs.get('database_url')
            
            # TLS Configuration
            self.tls_verify = kwargs.get('tls_verify', True)
            
            # Audio Configuration
            self.volume_normalization = kwargs.get('volume_normalization', True)
            self.default_volume = kwargs.get('default_volume', 1.0)
            self.audio_effects_enabled = kwargs.get('audio_effects_enabled', True)
            self.crossfade_duration = kwargs.get('crossfade_duration', 3.0)
            
            # Monitoring Configuration
            self.health_check_interval = kwargs.get('health_check_interval', 30)
            self.metrics_retention_days = kwargs.get('metrics_retention_days', 30)
            self.alert_thresholds = kwargs.get('alert_thresholds', {
                "cpu_usage": 80.0,
                "memory_usage": 85.0,
                "response_time": 2.0
            })
            
            # Second Life Integration
            self.sl_bridge_enabled = kwargs.get('sl_bridge_enabled', False)
            self.sl_bridge_port = kwargs.get('sl_bridge_port', 8080)
            self.sl_bridge_host = kwargs.get('sl_bridge_host', 'localhost')
            self.sl_api_key_length = kwargs.get('sl_api_key_length', 32)
            
            # Integration Configuration
            self.webhook_timeout = kwargs.get('webhook_timeout', 10)
            self.webhook_retry_attempts = kwargs.get('webhook_retry_attempts', 3)
            
            # Basic validation
            self._validate()
        
        def _validate(self):
            """Basic validation for fallback configuration"""
            if not self.bot_token:
                raise ConfigurationError("bot_token is required")
            
            valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
            if self.log_level.upper() not in valid_levels:
                raise ConfigurationError(f'log_level must be one of {valid_levels}')
            
            if not 0.0 <= self.default_volume <= 2.0:
                raise ConfigurationError('default_volume must be between 0.0 and 2.0')

class ConfigurationManager:
    """
    Centralized configuration management system.
    
    Handles loading, validation, and management of application configuration
    from multiple sources with environment-specific overrides.
    """
    
    def __init__(self, base_path: Optional[Path] = None):
        self.base_path = base_path or Path.cwd()
        self.config_dir = self.base_path / "config"
        self.environment = self._detect_environment()
        self._configuration: Optional[BotConfiguration] = None
        self._sources: Dict[str, ConfigurationSource] = {}
        
        logger.info(f"ConfigurationManager initialized for environment: {self.environment.value}")
    
    def load_configuration(self) -> BotConfiguration:
        """
        Load and validate configuration from all sources.
        
        Returns:
            Validated configuration object
            
        Raises:
            ConfigurationError: If configuration is invalid or missing
        """
        try:
            # Load base configuration
            config_data = self._load_base_configuration()
            
            # Apply environment-specific overrides
            config_data = self._apply_environment_overrides(config_data)
            
            # Apply environment variable overrides
            config_data = self._apply_environment_variables(config_data)
            
            # Validate and create configuration object
            if PYDANTIC_AVAILABLE:
                self._configuration = BotConfiguration(**config_data)
            else:
                # Fallback for systems without Pydantic
                self._configuration = self._create_config_object(config_data)
            
            logger.info("Configuration loaded successfully")
            return self._configuration
            
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise ConfigurationError(f"Configuration loading failed: {e}")
    
    def get_configuration(self) -> BotConfiguration:
        """Get current configuration, loading if necessary"""
        if self._configuration is None:
            return self.load_configuration()
        return self._configuration
    
    def reload_configuration(self) -> BotConfiguration:
        """Reload configuration from sources"""
        self._configuration = None
        return self.load_configuration()
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """
        Get a specific configuration value with dot notation support.
        
        Args:
            key: Configuration key (supports dot notation like 'audio.volume')
            default: Default value if key not found
            
        Returns:
            Configuration value
        """
        config = self.get_configuration()
        
        # Support dot notation
        keys = key.split('.')
        value = config
        
        try:
            for k in keys:
                if hasattr(value, k):
                    value = getattr(value, k)
                elif isinstance(value, dict):
                    value = value[k]
                else:
                    return default
            return value
        except (KeyError, AttributeError):
            return default
    
    def validate_configuration(self, config_data: Dict[str, Any]) -> bool:
        """
        Validate configuration data without loading.
        
        Args:
            config_data: Configuration dictionary to validate
            
        Returns:
            True if valid, False otherwise
        """
        try:
            if PYDANTIC_AVAILABLE:
                BotConfiguration(**config_data)
            else:
                # Basic validation for required fields
                required_fields = ['bot_token']
                for field in required_fields:
                    if field not in config_data:
                        return False
            return True
        except (ValidationError, Exception):
            return False
    
    def _detect_environment(self) -> Environment:
        """Detect current environment from various sources"""
        
        # Check environment variable first
        env_var = os.getenv('BUNBOT_ENVIRONMENT', '').lower()
        if env_var:
            try:
                return Environment(env_var)
            except ValueError:
                pass
        
        # Check for development indicators
        if (self.base_path / '.git').exists() or os.getenv('DEBUG'):
            return Environment.DEVELOPMENT
        
        # Check for production indicators
        if os.getenv('PRODUCTION') or os.getenv('HEROKU'):
            return Environment.PRODUCTION
        
        # Default to development
        return Environment.DEVELOPMENT
    
    def _load_base_configuration(self) -> Dict[str, Any]:
        """Load base configuration from default sources"""
        config_data = {}
        
        # Load from default.yaml if it exists
        default_config_path = self.config_dir / "default.yaml"
        if default_config_path.exists():
            config_data.update(self._load_yaml_file(default_config_path))
            logger.debug(f"Loaded base configuration from {default_config_path}")
        
        # Load from existing .env patterns for backward compatibility
        self._load_from_env_file(config_data)
        
        return config_data
    
    def _apply_environment_overrides(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply environment-specific configuration overrides"""
        
        env_config_path = self.config_dir / f"{self.environment.value}.yaml"
        if env_config_path.exists():
            env_config = self._load_yaml_file(env_config_path)
            config_data = self._deep_merge(config_data, env_config)
            logger.debug(f"Applied environment overrides from {env_config_path}")
        
        return config_data
    
    def _apply_environment_variables(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply environment variable overrides"""
        
        # Map environment variables to configuration keys
        env_mappings = {
            'BOT_TOKEN': 'bot_token',
            'LOG_LEVEL': 'log_level',
            'LOG_FILE_PATH': 'log_file_path',
            'DATABASE_PATH': 'database_path',
            'DATABASE_URL': 'database_url',
            'TLS_VERIFY': 'tls_verify',
            'CLUSTER_ID': 'cluster_id',
            'TOTAL_CLUSTERS': 'total_clusters',
            'TOTAL_SHARDS': 'total_shards',
            'SL_BRIDGE_ENABLED': 'sl_bridge_enabled',
            'SL_BRIDGE_PORT': 'sl_bridge_port',
        }
        
        for env_var, config_key in env_mappings.items():
            env_value = os.getenv(env_var)
            if env_value is not None:
                # Type conversion based on expected type
                if config_key in ['cluster_id', 'total_clusters', 'total_shards', 'sl_bridge_port']:
                    try:
                        config_data[config_key] = int(env_value)
                    except ValueError:
                        logger.warning(f"Invalid integer value for {env_var}: {env_value}")
                elif config_key in ['tls_verify', 'sl_bridge_enabled']:
                    config_data[config_key] = env_value.lower() in ('true', '1', 'yes', 'on')
                else:
                    config_data[config_key] = env_value
                
                logger.debug(f"Applied environment variable {env_var} -> {config_key}")
        
        return config_data
    
    def _load_yaml_file(self, path: Path) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        if not YAML_AVAILABLE:
            logger.warning(f"YAML not available, skipping {path}")
            return {}
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}  # type: ignore
        except Exception as e:
            logger.error(f"Failed to load YAML file {path}: {e}")
            return {}
    
    def _load_from_env_file(self, config_data: Dict[str, Any]):
        """Load from .env file for backward compatibility"""
        env_file = self.base_path / '.env'
        if env_file.exists():
            try:
                with open(env_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            key = key.strip()
                            value = value.strip().strip('"\'')
                            
                            # Map common .env keys to config keys
                            if key == 'BOT_TOKEN':
                                config_data['bot_token'] = value
                            elif key == 'LOG_LEVEL':
                                config_data['log_level'] = value
                            elif key == 'LOG_FILE_PATH':
                                config_data['log_file_path'] = value
                            # Add more mappings as needed
                            
                logger.debug(f"Loaded configuration from .env file")
            except Exception as e:
                logger.error(f"Failed to load .env file: {e}")
    
    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries"""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _create_config_object(self, config_data: Dict[str, Any]) -> 'BotConfiguration':
        """Create configuration object without Pydantic (fallback)"""
        
        class SimpleBotConfiguration:
            def __init__(self, **kwargs):
                # Set defaults
                self.bot_token = kwargs.get('bot_token', '')
                self.command_prefix = kwargs.get('command_prefix', '/')
                self.case_insensitive = kwargs.get('case_insensitive', True)
                self.cluster_id = kwargs.get('cluster_id', 0)
                self.total_clusters = kwargs.get('total_clusters', 1)
                self.total_shards = kwargs.get('total_shards', 1)
                self.log_level = kwargs.get('log_level', 'INFO').upper()
                self.log_file_path = kwargs.get('log_file_path', './log.txt')
                self.log_max_bytes = kwargs.get('log_max_bytes', 32 * 1024 * 1024)
                self.log_backup_count = kwargs.get('log_backup_count', 5)
                self.database_path = kwargs.get('database_path', 'bunbot.db')
                self.database_url = kwargs.get('database_url')
                self.tls_verify = kwargs.get('tls_verify', True)
                self.volume_normalization = kwargs.get('volume_normalization', True)
                self.default_volume = kwargs.get('default_volume', 1.0)
                self.audio_effects_enabled = kwargs.get('audio_effects_enabled', True)
                self.crossfade_duration = kwargs.get('crossfade_duration', 3.0)
                self.health_check_interval = kwargs.get('health_check_interval', 30)
                self.metrics_retention_days = kwargs.get('metrics_retention_days', 30)
                self.alert_thresholds = kwargs.get('alert_thresholds', {
                    "cpu_usage": 80.0,
                    "memory_usage": 85.0,
                    "response_time": 2.0
                })
                self.sl_bridge_enabled = kwargs.get('sl_bridge_enabled', False)
                self.sl_bridge_port = kwargs.get('sl_bridge_port', 8080)
                self.sl_bridge_host = kwargs.get('sl_bridge_host', 'localhost')
                self.sl_api_key_length = kwargs.get('sl_api_key_length', 32)
                self.webhook_timeout = kwargs.get('webhook_timeout', 10)
                self.webhook_retry_attempts = kwargs.get('webhook_retry_attempts', 3)
                
                # Basic validation
                if not self.bot_token:
                    raise ConfigurationError("bot_token is required")
        
        return SimpleBotConfiguration(**config_data)


# Global configuration manager instance
_global_config_manager: Optional[ConfigurationManager] = None

def get_config_manager() -> ConfigurationManager:
    """Get the global configuration manager instance"""
    global _global_config_manager
    if _global_config_manager is None:
        _global_config_manager = ConfigurationManager()
    return _global_config_manager

def get_config() -> BotConfiguration:
    """Get the current bot configuration"""
    return get_config_manager().get_configuration()

def reload_config() -> BotConfiguration:
    """Reload the bot configuration from sources"""
    return get_config_manager().reload_configuration()
