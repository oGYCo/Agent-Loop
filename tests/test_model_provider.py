"""Tests for ModelProvider module"""

import os
import pytest
from pathlib import Path
from unittest.mock import patch

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.model_provider import (
    ProviderType,
    ProviderConfig,
    ModelProviderManager,
    create_provider_manager,
    mask_api_key,
    DEFAULT_BASE_URLS,
    DEFAULT_MODELS,
)


class TestProviderType:
    """Test cases for ProviderType enum"""

    def test_provider_types(self):
        """Test that all expected provider types exist"""
        assert ProviderType.OPENAI.value == "openai"
        assert ProviderType.ANTHROPIC.value == "anthropic"
        assert ProviderType.MINIMAX.value == "minimax"


class TestProviderConfig:
    """Test cases for ProviderConfig dataclass"""

    def test_default_model(self):
        """Test that default models are set correctly"""
        config = ProviderConfig(provider="openai")
        assert config.get_model() == DEFAULT_MODELS[ProviderType.OPENAI]

        config = ProviderConfig(provider="anthropic")
        assert config.get_model() == DEFAULT_MODELS[ProviderType.ANTHROPIC]

        config = ProviderConfig(provider="minimax")
        assert config.get_model() == DEFAULT_MODELS[ProviderType.MINIMAX]

    def test_custom_model(self):
        """Test that custom model overrides default"""
        config = ProviderConfig(provider="openai", model="gpt-4.1")
        assert config.get_model() == "gpt-4.1"

    def test_default_base_url(self):
        """Test that default base URLs are set correctly"""
        config = ProviderConfig(provider="openai")
        # Without env var, should use default
        assert config.get_base_url() == DEFAULT_BASE_URLS[ProviderType.OPENAI]

        config = ProviderConfig(provider="anthropic")
        # Without env var override, should use default
        # Note: This may be affected by ANTHROPIC_BASE_URL env var in test environment
        base_url = config.get_base_url()
        assert base_url in [DEFAULT_BASE_URLS[ProviderType.ANTHROPIC], "https://api.minimaxi.com/anthropic"]

    def test_custom_base_url(self):
        """Test that custom base URL overrides default"""
        config = ProviderConfig(
            provider="openai",
            base_url="https://custom.proxy.com/v1"
        )
        assert config.get_base_url() == "https://custom.proxy.com/v1"

    def test_api_key_from_env(self):
        """Test that API key can be loaded from environment variable"""
        config = ProviderConfig(
            provider="openai",
            api_key_env="TEST_OPENAI_API_KEY"
        )

        with patch.dict(os.environ, {"TEST_OPENAI_API_KEY": "test-key-123"}):
            assert config.get_api_key() == "test-key-123"

    def test_api_key_direct(self):
        """Test that direct API key is used"""
        config = ProviderConfig(
            provider="openai",
            api_key="direct-key-456"
        )
        assert config.get_api_key() == "direct-key-456"

    def test_api_key_env_priority(self):
        """Test that env var takes priority over direct key"""
        config = ProviderConfig(
            provider="openai",
            api_key="direct-key",
            api_key_env="TEST_OPENAI_API_KEY"
        )

        with patch.dict(os.environ, {"TEST_OPENAI_API_KEY": "env-key"}):
            # env var should take priority
            assert config.get_api_key() == "env-key"

    def test_get_env_vars_openai(self):
        """Test environment variables for OpenAI provider"""
        config = ProviderConfig(
            provider="openai",
            model="gpt-4.1",
            api_key="test-key",
            base_url="https://custom.proxy.com"
        )
        env_vars = config.get_env_vars()

        assert "OPENAI_API_KEY" in env_vars
        assert env_vars["OPENAI_API_KEY"] == "test-key"
        assert "OPENAI_BASE_URL" in env_vars
        assert env_vars["OPENAI_BASE_URL"] == "https://custom.proxy.com"

    def test_get_env_vars_anthropic(self):
        """Test environment variables for Anthropic provider"""
        config = ProviderConfig(
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            api_key="test-key",
            base_url="https://custom.proxy.com"
        )
        env_vars = config.get_env_vars()

        assert "ANTHROPIC_AUTH_TOKEN" in env_vars
        assert env_vars["ANTHROPIC_AUTH_TOKEN"] == "test-key"
        assert "ANTHROPIC_BASE_URL" in env_vars
        assert env_vars["ANTHROPIC_BASE_URL"] == "https://custom.proxy.com"


class TestModelProviderManager:
    """Test cases for ModelProviderManager"""

    def test_empty_config_creates_default(self):
        """Test that empty config creates default provider"""
        manager = ModelProviderManager({})

        assert manager.get_active_provider() is not None
        provider = manager.get_active_provider()
        assert provider is not None
        assert provider.provider_type == ProviderType.MINIMAX

    def test_load_provider_from_config(self):
        """Test loading provider from config dict"""
        config = {
            "providers": {
                "my_openai": {
                    "provider": "openai",
                    "model": "gpt-4.1",
                    "api_key_env": "MY_OPENAI_KEY",
                }
            },
            "active_provider": "my_openai"
        }

        manager = ModelProviderManager(config)
        provider = manager.get_active_provider()

        assert provider is not None
        assert provider.provider_type == ProviderType.OPENAI
        assert provider.config.get_model() == "gpt-4.1"

    def test_list_providers(self):
        """Test listing all configured providers"""
        config = {
            "providers": {
                "openai_provider": {
                    "provider": "openai",
                    "model": "gpt-4.1"
                },
                "anthropic_provider": {
                    "provider": "anthropic",
                    "model": "claude-sonnet-4-20250514"
                }
            }
        }

        manager = ModelProviderManager(config)
        providers = manager.list_providers()

        assert "openai_provider" in providers
        assert "anthropic_provider" in providers

    def test_switch_provider(self):
        """Test switching between providers"""
        config = {
            "providers": {
                "provider1": {
                    "provider": "openai",
                    "model": "gpt-4.1"
                },
                "provider2": {
                    "provider": "anthropic",
                    "model": "claude-sonnet-4-20250514"
                }
            },
            "active_provider": "provider1"
        }

        manager = ModelProviderManager(config)

        # Initial provider
        provider = manager.get_active_provider()
        assert provider is not None
        assert provider.config.get_model() == "gpt-4.1"

        # Switch to provider2
        success = manager.switch_provider("provider2")
        assert success is True

        provider = manager.get_active_provider()
        assert provider is not None
        assert provider.config.get_model() == "claude-sonnet-4-20250514"

    def test_switch_provider_failure(self):
        """Test switching to non-existent provider"""
        config = {
            "providers": {
                "provider1": {
                    "provider": "openai",
                    "model": "gpt-4.1"
                }
            },
            "active_provider": "provider1"
        }

        manager = ModelProviderManager(config)
        success = manager.switch_provider("nonexistent")

        assert success is False

    def test_get_sdk_env_vars(self):
        """Test getting SDK environment variables"""
        config = {
            "providers": {
                "my_provider": {
                    "provider": "openai",
                    "model": "gpt-4.1",
                    "api_key": "test-key",
                    "base_url": "https://custom.proxy.com"
                }
            },
            "active_provider": "my_provider"
        }

        manager = ModelProviderManager(config)
        env_vars = manager.get_sdk_env_vars()

        assert "OPENAI_API_KEY" in env_vars
        assert env_vars["OPENAI_API_KEY"] == "test-key"

    def test_get_model(self):
        """Test getting model from active provider"""
        config = {
            "providers": {
                "my_provider": {
                    "provider": "openai",
                    "model": "gpt-4.1"
                }
            },
            "active_provider": "my_provider"
        }

        manager = ModelProviderManager(config)
        assert manager.get_model() == "gpt-4.1"

    def test_get_base_url(self):
        """Test getting base URL from active provider"""
        config = {
            "providers": {
                "my_provider": {
                    "provider": "openai",
                    "base_url": "https://custom.proxy.com"
                }
            },
            "active_provider": "my_provider"
        }

        manager = ModelProviderManager(config)
        assert manager.get_base_url() == "https://custom.proxy.com"

    def test_get_provider_type(self):
        """Test getting provider type"""
        config = {
            "providers": {
                "my_provider": {
                    "provider": "anthropic"
                }
            },
            "active_provider": "my_provider"
        }

        manager = ModelProviderManager(config)
        assert manager.get_provider_type() == ProviderType.ANTHROPIC

    def test_legacy_config_compatibility(self):
        """Test backward compatibility with legacy config (model field)"""
        # Old config format without providers
        config = {
            "model": "MiniMax-M2.5-highspeed",
            "active_provider": "default"
        }

        # Set environment variable for backward compatibility
        with patch.dict(os.environ, {"ANTHROPIC_BASE_URL": "https://api.minimaxi.com/anthropic"}):
            manager = ModelProviderManager(config)
            assert manager.get_model() == "MiniMax-M2.5-highspeed"
            assert manager.get_provider_type() == ProviderType.MINIMAX


class TestMaskApiKey:
    """Test cases for mask_api_key function"""

    def test_mask_empty(self):
        """Test masking empty string"""
        assert mask_api_key(None) == ""
        assert mask_api_key("") == ""

    def test_mask_short_key(self):
        """Test masking short API key"""
        assert mask_api_key("abc") == "***"

    def test_mask_long_key(self):
        """Test masking long API key"""
        masked = mask_api_key("sk-1234567890abcdef")
        assert masked.startswith("***")
        assert masked.endswith("cdef")
        assert len(masked) == len("sk-1234567890abcdef")

    def test_mask_custom_visible_chars(self):
        """Test masking with custom visible characters"""
        masked = mask_api_key("sk-1234567890abcdef", visible_chars=8)
        assert masked.startswith("********")
        assert masked.endswith("abcdef")
