"""Model Provider Module - Extensible Model Provider System with Failover Support

This module provides a unified interface for configuring different model providers
including OpenAI, Anthropic, and MiniMax. Users can configure multiple providers
and switch between them as needed.

Features:
- Provider failover chain with automatic switching on failures
- Health check for provider availability monitoring
- Smart retry with transient vs permanent error detection
- Usage statistics and Prometheus metrics
- API key rotation across multiple keys per provider

Provider Configuration:
- Provider type (openai, anthropic, minimax)
- API key (can be from env var or direct config)
- Multiple API keys for rotation
- Model name
- Base URL (for proxy/custom endpoints)
- Fallback provider chain
- Health check settings

Privacy:
- API keys should be stored in environment variables when possible
- If stored in config, they will be masked in logs and UI
"""

import os
import time
import logging
import threading
from typing import Dict, Any, Optional, List, Literal
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent.metrics import MetricsCollector

logger = logging.getLogger(__name__)


class ProviderType(Enum):
    """Supported model provider types"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    MINIMAX = "minimax"


class ProviderHealthStatus(Enum):
    """Provider health status"""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ErrorCategory(Enum):
    """Error category for retry decisions"""
    # Transient errors - retryable
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    SERVER_ERROR = "server_error"  # 5xx errors
    CONNECTION_ERROR = "connection_error"

    # Permanent errors - not retryable
    AUTH_ERROR = "auth_error"  # 401, 403
    NOT_FOUND = "not_found"  # 404
    INVALID_REQUEST = "invalid_request"  # 400
    QUOTA_EXCEEDED = "quota_exceeded"

    # Unknown
    UNKNOWN = "unknown"


# Default base URLs for each provider
DEFAULT_BASE_URLS: Dict[ProviderType, str] = {
    ProviderType.OPENAI: "https://api.openai.com/v1",
    ProviderType.ANTHROPIC: "https://api.anthropic.com",
    ProviderType.MINIMAX: "https://api.minimaxi.com/anthropic",
}

# Environment variable names for each provider
ENV_VAR_NAMES: Dict[ProviderType, Dict[str, str]] = {
    ProviderType.OPENAI: {
        "api_key": "OPENAI_API_KEY",
        "base_url": "OPENAI_BASE_URL",
    },
    ProviderType.ANTHROPIC: {
        "api_key": "ANTHROPIC_AUTH_TOKEN",
        "base_url": "ANTHROPIC_BASE_URL",
    },
    ProviderType.MINIMAX: {
        "api_key": "ANTHROPIC_AUTH_TOKEN",
        "base_url": "ANTHROPIC_BASE_URL",
    },
}

# Default models for each provider
DEFAULT_MODELS: Dict[ProviderType, str] = {
    ProviderType.OPENAI: "gpt-4.1",
    ProviderType.ANTHROPIC: "claude-sonnet-4-20250514",
    ProviderType.MINIMAX: "MiniMax-M2.5-highspeed",
}


@dataclass
class ProviderStats:
    """Usage statistics for a provider"""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_response_time: float = 0.0  # in seconds
    last_used_at: Optional[datetime] = None
    last_error: Optional[str] = None
    consecutive_failures: int = 0
    current_api_key_index: int = 0

    @property
    def success_rate(self) -> float:
        """Calculate success rate"""
        if self.total_calls == 0:
            return 0.0
        return self.successful_calls / self.total_calls

    @property
    def average_response_time(self) -> float:
        """Calculate average response time"""
        if self.successful_calls == 0:
            return 0.0
        return self.total_response_time / self.successful_calls


@dataclass
class ProviderConfig:
    """Configuration for a single model provider"""
    provider: str
    api_key: Optional[str] = None
    api_key_env: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    fallback_provider: Optional[str] = None  # Fallback provider name
    api_keys: List[str] = field(default_factory=list)  # Multiple API keys for rotation
    health_check_enabled: bool = True
    health_check_interval: int = 300  # seconds
    additional_config: Dict[str, Any] = field(default_factory=dict)

    def get_api_key(self, key_index: Optional[int] = None) -> Optional[str]:
        """Get API key from env var, direct config, or from API keys list

        Args:
            key_index: Optional index to get a specific key from the api_keys list

        Returns:
            The API key string
        """
        # If api_keys list has keys, use round-robin rotation
        if self.api_keys:
            if key_index is not None and 0 <= key_index < len(self.api_keys):
                return self.api_keys[key_index]
            # Return first key by default
            return self.api_keys[0] if self.api_keys else None

        # Fall back to env var or direct config
        if self.api_key_env:
            return os.environ.get(self.api_key_env)
        return self.api_key

    def get_all_api_keys(self) -> List[str]:
        """Get all available API keys for this provider"""
        keys = []
        # Add keys from api_keys list
        keys.extend(self.api_keys)
        # Add direct api_key if present
        if self.api_key and self.api_key not in keys:
            keys.append(self.api_key)
        # Try to get from env var
        if self.api_key_env:
            env_key = os.environ.get(self.api_key_env)
            if env_key and env_key not in keys:
                keys.append(env_key)
        return keys

    def has_multiple_keys(self) -> bool:
        """Check if provider has multiple API keys configured"""
        return len(self.get_all_api_keys()) > 1

    def get_base_url(self) -> str:
        """Get base URL from config or env, with provider default as fallback"""
        if self.base_url:
            return self.base_url
        # Try env var first
        provider_type = ProviderType(self.provider)
        env_vars = ENV_VAR_NAMES.get(provider_type, {})
        base_url_env = env_vars.get("base_url")
        if base_url_env:
            env_value = os.environ.get(base_url_env)
            if env_value:
                return env_value
        # Fall back to default
        return DEFAULT_BASE_URLS.get(provider_type, "")

    def get_model(self) -> str:
        """Get model name from config or use provider default"""
        if self.model:
            return self.model
        provider_type = ProviderType(self.provider)
        return DEFAULT_MODELS.get(provider_type, "")

    def get_env_vars(self) -> Dict[str, str]:
        """Get environment variables for SDK"""
        api_key = self.get_api_key()
        base_url = self.get_base_url()
        model = self.get_model()

        provider_type = ProviderType(self.provider)

        # Build env var dict based on provider type
        if provider_type == ProviderType.OPENAI:
            return {
                "OPENAI_API_KEY": api_key or "",
                "OPENAI_BASE_URL": base_url,
                "OPENAI_MODEL": model,
            }
        else:
            # Anthropic and MiniMax use ANTHROPIC_* vars
            return {
                "ANTHROPIC_AUTH_TOKEN": api_key or "",
                "ANTHROPIC_BASE_URL": base_url,
            }


@dataclass
class ActiveProvider:
    """Currently active provider configuration"""
    config: ProviderConfig
    provider_type: ProviderType


class ModelProviderManager:
    """Manages model provider configurations and switching"""

    def __init__(self, config: Dict[str, Any], metrics_collector: Optional["MetricsCollector"] = None):
        """Initialize with project config dict

        Args:
            config: Project configuration dictionary containing provider settings
            metrics_collector: Optional metrics collector for Prometheus metrics
        """
        self._config = config
        self._active_provider: Optional[ActiveProvider] = None
        self._providers: Dict[str, ProviderConfig] = {}
        self._metrics_collector = metrics_collector
        self._load_providers()

    def _load_providers(self) -> None:
        """Load provider configurations from config"""
        provider_config = self._config.get("providers", {})

        # If no providers configured, create default from legacy config
        if not provider_config:
            self._create_default_provider()
            return

        # Load each provider
        for name, provider_data in provider_config.items():
            if isinstance(provider_data, dict):
                self._providers[name] = ProviderConfig(
                    provider=provider_data.get("provider", ""),
                    api_key=provider_data.get("api_key"),
                    api_key_env=provider_data.get("api_key_env"),
                    model=provider_data.get("model"),
                    base_url=provider_data.get("base_url"),
                    fallback_provider=provider_data.get("fallback_provider"),
                    api_keys=provider_data.get("api_keys", []),
                    health_check_enabled=provider_data.get("health_check_enabled", True),
                    health_check_interval=provider_data.get("health_check_interval", 300),
                    additional_config=provider_data.get("additional_config", {}),
                )

        # Initialize stats for each provider
        self._provider_stats: Dict[str, ProviderStats] = {
            name: ProviderStats() for name in self._providers
        }

        # Initialize health status
        self._provider_health: Dict[str, ProviderHealthStatus] = {
            name: ProviderHealthStatus.UNKNOWN for name in self._providers
        }

        # Set active provider
        active_name = self._config.get("active_provider")
        if active_name and active_name in self._providers:
            self._set_active_provider(active_name)
        elif self._providers:
            # Default to first provider
            first_name = next(iter(self._providers))
            self._set_active_provider(first_name)

    def _create_default_provider(self) -> None:
        """Create default provider from legacy config (model, api_key settings)"""
        # Get legacy config
        model = self._config.get("model", "MiniMax-M2.5-highspeed")

        # Determine provider type from model or base_url
        base_url = os.environ.get("ANTHROPIC_BASE_URL", "")
        if "openai.com" in base_url.lower():
            provider_type = ProviderType.OPENAI
        elif "minimax" in base_url.lower():
            provider_type = ProviderType.MINIMAX
        else:
            # Default to minimax for backward compatibility
            provider_type = ProviderType.MINIMAX

        # Create default provider config
        default_provider = ProviderConfig(
            provider=provider_type.value,
            model=model,
            # API key from env
            api_key_env=ENV_VAR_NAMES[provider_type]["api_key"],
        )

        self._providers["default"] = default_provider
        self._active_provider = ActiveProvider(
            config=default_provider,
            provider_type=provider_type,
        )

    def _set_active_provider(self, name: str) -> None:
        """Set the active provider by name"""
        provider_config = self._providers.get(name)
        if provider_config:
            self._active_provider = ActiveProvider(
                config=provider_config,
                provider_type=ProviderType(provider_config.provider),
            )
            logger.info(f"Active provider set to: {name} ({provider_config.provider})")
        else:
            logger.warning(f"Provider '{name}' not found")

    def get_active_provider(self) -> Optional[ActiveProvider]:
        """Get currently active provider"""
        return self._active_provider

    def get_provider(self, name: str) -> Optional[ProviderConfig]:
        """Get provider config by name"""
        return self._providers.get(name)

    def list_providers(self) -> Dict[str, ProviderConfig]:
        """List all configured providers"""
        return self._providers.copy()

    def switch_provider(self, name: str) -> bool:
        """Switch to a different provider

        Args:
            name: Provider name to switch to

        Returns:
            True if successful, False otherwise
        """
        if name not in self._providers:
            logger.error(f"Provider '{name}' not found")
            return False

        self._set_active_provider(name)
        return True

    def get_sdk_env_vars(self) -> Dict[str, str]:
        """Get environment variables for the active provider's SDK"""
        if self._active_provider:
            return self._active_provider.config.get_env_vars()
        return {}

    def get_model(self) -> str:
        """Get model name from active provider"""
        if self._active_provider:
            return self._active_provider.config.get_model()
        return ""

    def get_base_url(self) -> str:
        """Get base URL from active provider"""
        if self._active_provider:
            return self._active_provider.config.get_base_url()
        return ""

    def get_provider_type(self) -> Optional[ProviderType]:
        """Get provider type from active provider"""
        if self._active_provider:
            return self._active_provider.provider_type
        return None

    def set_metrics_collector(self, metrics_collector: "MetricsCollector") -> None:
        """Set the metrics collector for Prometheus metrics"""
        self._metrics_collector = metrics_collector

    def _update_metrics(self) -> None:
        """Update Prometheus metrics for the active provider"""
        if self._metrics_collector and self._active_provider:
            self._metrics_collector.set_active_provider(self._active_provider.config.provider)

    # ========== Provider Statistics ==========

    def get_provider_stats(self, name: str) -> Optional[ProviderStats]:
        """Get usage statistics for a provider"""
        return getattr(self, '_provider_stats', {}).get(name)

    def get_all_stats(self) -> Dict[str, ProviderStats]:
        """Get statistics for all providers"""
        return getattr(self, '_provider_stats', {})

    def record_call_start(self, provider_name: str) -> None:
        """Record the start of a provider call"""
        if not hasattr(self, '_provider_stats'):
            self._provider_stats = {}
        if provider_name not in self._provider_stats:
            self._provider_stats[provider_name] = ProviderStats()
        self._provider_stats[provider_name].total_calls += 1
        self._provider_stats[provider_name].last_used_at = datetime.now()

    def record_call_success(self, provider_name: str, response_time: float) -> None:
        """Record a successful provider call"""
        if hasattr(self, '_provider_stats') and provider_name in self._provider_stats:
            stats = self._provider_stats[provider_name]
            stats.successful_calls += 1
            stats.total_response_time += response_time
            stats.consecutive_failures = 0

        # Update Prometheus metrics
        if self._metrics_collector:
            self._metrics_collector.record_provider_call(provider_name, success=True)
            if response_time > 0:
                self._metrics_collector.record_provider_response_time(provider_name, response_time)

    def record_call_failure(self, provider_name: str, error: str) -> None:
        """Record a failed provider call"""
        if hasattr(self, '_provider_stats') and provider_name in self._provider_stats:
            stats = self._provider_stats[provider_name]
            stats.failed_calls += 1
            stats.last_error = error
            stats.consecutive_failures += 1

        # Update Prometheus metrics
        if self._metrics_collector:
            self._metrics_collector.record_provider_call(provider_name, success=False)

    def get_next_api_key_index(self, provider_name: str) -> int:
        """Get the next API key index for round-robin rotation"""
        if hasattr(self, '_provider_stats') and provider_name in self._provider_stats:
            stats = self._provider_stats[provider_name]
            provider = self._providers.get(provider_name)
            if provider:
                num_keys = len(provider.get_all_api_keys())
                if num_keys > 1:
                    stats.current_api_key_index = (stats.current_api_key_index + 1) % num_keys
                    return stats.current_api_key_index
        return 0

    # ========== Provider Health ==========

    def get_health_status(self, name: str) -> ProviderHealthStatus:
        """Get health status for a provider"""
        return getattr(self, '_provider_health', {}).get(name, ProviderHealthStatus.UNKNOWN)

    def set_health_status(self, name: str, status: ProviderHealthStatus) -> None:
        """Set health status for a provider"""
        if not hasattr(self, '_provider_health'):
            self._provider_health = {}
        self._provider_health[name] = status
        logger.info(f"Provider '{name}' health status: {status.value}")

        # Update Prometheus metrics
        if self._metrics_collector:
            self._metrics_collector.set_provider_health(name, status.value)

    async def provider_health_check(self, name: str) -> bool:
        """Check if a provider is healthy by making a simple API request

        Args:
            name: Provider name to check

        Returns:
            True if provider is healthy, False otherwise
        """
        provider = self._providers.get(name)
        if not provider:
            logger.warning(f"Provider '{name}' not found for health check")
            return False

        if not provider.health_check_enabled:
            logger.debug(f"Health check disabled for provider '{name}'")
            return True

        # Check if we have valid credentials
        api_key = provider.get_api_key()
        if not api_key:
            logger.warning(f"No API key available for provider '{name}'")
            self.set_health_status(name, ProviderHealthStatus.UNHEALTHY)
            return False

        # For now, we'll do a simple connectivity check
        # In production, this would make an actual API call to list models
        try:
            import httpx
            base_url = provider.get_base_url()
            headers = {}

            # Set appropriate headers based on provider type
            provider_type = ProviderType(provider.provider)
            if provider_type == ProviderType.OPENAI:
                headers["Authorization"] = f"Bearer {api_key}"
            else:
                headers["x-api-key"] = api_key

            # Make a simple request
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Try models list endpoint
                models_url = f"{base_url}/models"
                response = await client.get(models_url, headers=headers)

                if response.status_code == 200:
                    self.set_health_status(name, ProviderHealthStatus.HEALTHY)
                    return True
                elif response.status_code == 401:
                    logger.warning(f"Provider '{name}' authentication failed during health check")
                    self.set_health_status(name, ProviderHealthStatus.UNHEALTHY)
                    return False
                else:
                    logger.warning(f"Provider '{name}' health check failed: {response.status_code}")
                    self.set_health_status(name, ProviderHealthStatus.UNHEALTHY)
                    return False
        except Exception as e:
            logger.warning(f"Provider '{name}' health check error: {e}")
            self.set_health_status(name, ProviderHealthStatus.UNHEALTHY)
            return False

    # ========== Smart Retry & Error Classification ==========

    @staticmethod
    def classify_error(error: Exception, response_status: Optional[int] = None) -> ErrorCategory:
        """Classify an error to determine if it's retryable

        Args:
            error: The exception that occurred
            response_status: Optional HTTP status code from the response

        Returns:
            ErrorCategory indicating if the error is retryable
        """
        error_message = str(error).lower()
        error_type = type(error).__name__.lower()

        # Check HTTP status code first
        if response_status:
            if response_status == 401 or response_status == 403:
                return ErrorCategory.AUTH_ERROR
            elif response_status == 404:
                return ErrorCategory.NOT_FOUND
            elif response_status == 400:
                return ErrorCategory.INVALID_REQUEST
            elif response_status == 429:
                return ErrorCategory.RATE_LIMIT
            elif 500 <= response_status < 600:
                return ErrorCategory.SERVER_ERROR

        # Check error type/message
        if any(keyword in error_message for keyword in ["timeout", "timed out"]):
            return ErrorCategory.TIMEOUT
        elif any(keyword in error_message for keyword in ["rate limit", "rate_limit", "too many requests"]):
            return ErrorCategory.RATE_LIMIT
        elif any(keyword in error_message for keyword in ["connection", "connect", "network"]):
            return ErrorCategory.CONNECTION_ERROR
        elif any(keyword in error_message for keyword in ["401", "unauthorized", "authentication", "auth"]):
            return ErrorCategory.AUTH_ERROR
        elif any(keyword in error_message for keyword in ["403", "forbidden"]):
            return ErrorCategory.AUTH_ERROR
        elif any(keyword in error_message for keyword in ["404", "not found"]):
            return ErrorCategory.NOT_FOUND
        elif any(keyword in error_message for keyword in ["400", "bad request", "invalid"]):
            return ErrorCategory.INVALID_REQUEST
        elif any(keyword in error_message for keyword in ["quota", "exceeded"]):
            return ErrorCategory.QUOTA_EXCEEDED

        return ErrorCategory.UNKNOWN

    def is_error_retryable(self, error: Exception, response_status: Optional[int] = None) -> bool:
        """Determine if an error is retryable

        Args:
            error: The exception that occurred
            response_status: Optional HTTP status code

        Returns:
            True if the error is retryable, False otherwise
        """
        category = self.classify_error(error, response_status)

        # Transient errors are retryable
        retryable_categories = {
            ErrorCategory.TIMEOUT,
            ErrorCategory.RATE_LIMIT,
            ErrorCategory.SERVER_ERROR,
            ErrorCategory.CONNECTION_ERROR,
        }

        return category in retryable_categories

    # ========== Failover ==========

    def get_fallback_provider(self, provider_name: str) -> Optional[str]:
        """Get the fallback provider for a given provider

        Args:
            provider_name: The name of the provider

        Returns:
            The name of the fallback provider, or None if not configured
        """
        provider = self._providers.get(provider_name)
        if provider and provider.fallback_provider:
            fallback = provider.fallback_provider
            # Verify fallback exists
            if fallback in self._providers:
                return fallback
            else:
                logger.warning(f"Fallback provider '{fallback}' not found for '{provider_name}'")
        return None

    def failover(self, from_provider: str) -> bool:
        """Failover to the fallback provider

        Args:
            from_provider: The provider that failed

        Returns:
            True if failover succeeded, False otherwise
        """
        fallback = self.get_fallback_provider(from_provider)
        if fallback:
            # Check if fallback is healthy
            health = self.get_health_status(fallback)
            if health == ProviderHealthStatus.UNHEALTHY:
                logger.warning(f"Fallback provider '{fallback}' is unhealthy")
                # Try cascading failover
                return self.failover(fallback)

            logger.info(f"Failing over from '{from_provider}' to '{fallback}'")

            # Record failover in metrics
            if self._metrics_collector:
                self._metrics_collector.record_provider_failover(from_provider, fallback)

            return self.switch_provider(fallback)

        logger.error(f"No fallback provider available for '{from_provider}'")
        return False

    def handle_failure(self, provider_name: str, error: Exception, response_status: Optional[int] = None) -> bool:
        """Handle a provider failure with smart failover

        Args:
            provider_name: The provider that failed
            error: The exception that occurred
            response_status: Optional HTTP status code

        Returns:
            True if failover was successful, False otherwise
        """
        # Record the failure
        self.record_call_failure(provider_name, str(error))

        # Check if error is retryable
        if self.is_error_retryable(error, response_status):
            logger.info(f"Provider '{provider_name}' error is retryable: {error}")
            return False  # Let the caller handle retry

        # Permanent error - try failover
        logger.warning(f"Provider '{provider_name}' encountered permanent error: {error}")
        return self.failover(provider_name)

    # ========== Validation ==========

    def validate_providers(self) -> Dict[str, List[str]]:
        """Validate all configured provider credentials

        Returns:
            Dictionary mapping provider names to list of validation warnings
        """
        warnings = {}

        for name, provider in self._providers.items():
            provider_warnings = []

            # Check if API key is available
            api_keys = provider.get_all_api_keys()
            if not api_keys:
                provider_warnings.append(f"No API key configured (tried env var '{provider.api_key_env}')")
            else:
                logger.info(f"Provider '{name}' has {len(api_keys)} API key(s) configured")

            # Check if model is configured
            if not provider.model:
                provider_warnings.append(f"No model specified, using default")

            # Check fallback provider exists
            if provider.fallback_provider:
                if provider.fallback_provider not in self._providers:
                    provider_warnings.append(
                        f"Fallback provider '{provider.fallback_provider}' not found"
                    )

            if provider_warnings:
                warnings[name] = provider_warnings
                for warning in provider_warnings:
                    logger.warning(f"Provider '{name}' validation warning: {warning}")

        return warnings


def create_provider_manager(config: Dict[str, Any], metrics_collector: Optional["MetricsCollector"] = None) -> ModelProviderManager:
    """Create a ModelProviderManager from config

    Args:
        config: Project configuration dictionary
        metrics_collector: Optional metrics collector for Prometheus metrics

    Returns:
        ModelProviderManager instance
    """
    return ModelProviderManager(config, metrics_collector)


def mask_api_key(api_key: Optional[str], visible_chars: int = 4) -> str:
    """Mask an API key for privacy

    Args:
        api_key: The API key to mask
        visible_chars: Number of characters to show at the end

    Returns:
        Masked API key string
    """
    if not api_key:
        return ""

    if len(api_key) <= visible_chars:
        return "*" * len(api_key)

    return "*" * (len(api_key) - visible_chars) + api_key[-visible_chars:]
