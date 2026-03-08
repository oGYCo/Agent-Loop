"""Model Provider Module - Extensible Model Provider System

This module provides a unified interface for configuring different model providers
including OpenAI, Anthropic, and MiniMax. Users can configure multiple providers
and switch between them as needed.

Provider Configuration:
- Provider type (openai, anthropic, minimax)
- API key (can be from env var or direct config)
- Model name
- Base URL (for proxy/custom endpoints)
- Additional provider-specific settings

Privacy:
- API keys should be stored in environment variables when possible
- If stored in config, they will be masked in logs and UI
"""

import os
import logging
from typing import Dict, Any, Optional, Literal
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ProviderType(Enum):
    """Supported model provider types"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    MINIMAX = "minimax"


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
class ProviderConfig:
    """Configuration for a single model provider"""
    provider: str
    api_key: Optional[str] = None
    api_key_env: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    additional_config: Dict[str, Any] = field(default_factory=dict)

    def get_api_key(self) -> Optional[str]:
        """Get API key from env var or direct config"""
        if self.api_key_env:
            return os.environ.get(self.api_key_env)
        return self.api_key

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

    def __init__(self, config: Dict[str, Any]):
        """Initialize with project config dict

        Args:
            config: Project configuration dictionary containing provider settings
        """
        self._config = config
        self._active_provider: Optional[ActiveProvider] = None
        self._providers: Dict[str, ProviderConfig] = {}
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
                    additional_config=provider_data.get("additional_config", {}),
                )

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


def create_provider_manager(config: Dict[str, Any]) -> ModelProviderManager:
    """Create a ModelProviderManager from config

    Args:
        config: Project configuration dictionary

    Returns:
        ModelProviderManager instance
    """
    return ModelProviderManager(config)


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
