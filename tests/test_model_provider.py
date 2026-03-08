"""Tests for ModelProvider module"""

import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.model_provider import (
    ProviderType,
    ProviderConfig,
    ProviderStats,
    ProviderHealthStatus,
    ModelProviderManager,
    create_provider_manager,
    mask_api_key,
    DEFAULT_BASE_URLS,
    DEFAULT_MODELS,
    ErrorCategory,
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


class TestProviderStats:
    """Test cases for ProviderStats"""

    def test_default_values(self):
        """Test default values for ProviderStats"""
        stats = ProviderStats()
        assert stats.total_calls == 0
        assert stats.successful_calls == 0
        assert stats.failed_calls == 0
        assert stats.total_response_time == 0.0
        assert stats.last_used_at is None
        assert stats.last_error is None
        assert stats.consecutive_failures == 0

    def test_success_rate(self):
        """Test success rate calculation"""
        stats = ProviderStats()
        stats.total_calls = 10
        stats.successful_calls = 7
        assert stats.success_rate == 0.7

        # Zero calls
        stats2 = ProviderStats()
        assert stats2.success_rate == 0.0

    def test_average_response_time(self):
        """Test average response time calculation"""
        stats = ProviderStats()
        stats.successful_calls = 5
        stats.total_response_time = 10.0
        assert stats.average_response_time == 2.0

        # Zero successful calls
        stats2 = ProviderStats()
        assert stats2.average_response_time == 0.0


class TestProviderConfigExtended:
    """Extended test cases for ProviderConfig with new features"""

    def test_fallback_provider(self):
        """Test fallback provider configuration"""
        config = ProviderConfig(
            provider="openai",
            fallback_provider="anthropic"
        )
        assert config.fallback_provider == "anthropic"

    def test_api_keys_list(self):
        """Test multiple API keys configuration"""
        config = ProviderConfig(
            provider="openai",
            api_keys=["key1", "key2", "key3"]
        )
        assert len(config.get_all_api_keys()) == 3

    def test_get_api_key_with_rotation(self):
        """Test API key rotation"""
        config = ProviderConfig(
            provider="openai",
            api_keys=["key1", "key2"]
        )
        # First key
        key1 = config.get_api_key(0)
        assert key1 == "key1"

    def test_get_all_api_keys(self):
        """Test getting all API keys"""
        config = ProviderConfig(
            provider="openai",
            api_key="direct-key",
            api_key_env="TEST_API_KEY",
            api_keys=["list-key1", "list-key2"]
        )

        with patch.dict(os.environ, {"TEST_API_KEY": "env-key"}):
            keys = config.get_all_api_keys()
            assert "list-key1" in keys
            assert "list-key2" in keys
            assert "direct-key" in keys
            assert "env-key" in keys

    def test_has_multiple_keys(self):
        """Test checking if multiple keys are available"""
        config1 = ProviderConfig(provider="openai", api_keys=["key1", "key2"])
        assert config1.has_multiple_keys() is True

        config2 = ProviderConfig(provider="openai", api_key="single-key")
        assert config2.has_multiple_keys() is False


class TestErrorCategory:
    """Test cases for error classification"""

    def test_timeout_error(self):
        """Test timeout error classification"""
        error = TimeoutError("Request timed out")
        category = ModelProviderManager.classify_error(error)
        assert category == ErrorCategory.TIMEOUT

    def test_rate_limit_error(self):
        """Test rate limit error classification"""
        error = Exception("Rate limit exceeded")
        category = ModelProviderManager.classify_error(error)
        assert category == ErrorCategory.RATE_LIMIT

    def test_auth_error_401(self):
        """Test authentication error classification from status code"""
        error = Exception("Unauthorized")
        category = ModelProviderManager.classify_error(error, response_status=401)
        assert category == ErrorCategory.AUTH_ERROR

    def test_not_found_error(self):
        """Test not found error classification"""
        error = Exception("Not found")
        category = ModelProviderManager.classify_error(error, response_status=404)
        assert category == ErrorCategory.NOT_FOUND

    def test_server_error(self):
        """Test server error classification"""
        error = Exception("Internal server error")
        category = ModelProviderManager.classify_error(error, response_status=500)
        assert category == ErrorCategory.SERVER_ERROR


class TestModelProviderManagerExtended:
    """Extended test cases for ModelProviderManager with new features"""

    def test_provider_stats_tracking(self):
        """Test provider statistics tracking"""
        config = {
            "providers": {
                "test_provider": {
                    "provider": "openai",
                    "model": "gpt-4.1"
                }
            },
            "active_provider": "test_provider"
        }

        manager = ModelProviderManager(config)

        # Record a successful call
        manager.record_call_start("test_provider")
        manager.record_call_success("test_provider", 1.5)

        stats = manager.get_provider_stats("test_provider")
        assert stats is not None
        assert stats.total_calls == 1
        assert stats.successful_calls == 1
        assert stats.failed_calls == 0
        assert stats.average_response_time == 1.5

    def test_provider_failure_tracking(self):
        """Test provider failure tracking"""
        config = {
            "providers": {
                "test_provider": {
                    "provider": "openai",
                    "model": "gpt-4.1"
                }
            },
            "active_provider": "test_provider"
        }

        manager = ModelProviderManager(config)

        # Record a failed call
        manager.record_call_failure("test_provider", "Rate limit exceeded")

        stats = manager.get_provider_stats("test_provider")
        assert stats is not None
        assert stats.failed_calls == 1
        assert stats.consecutive_failures == 1
        assert stats.last_error == "Rate limit exceeded"

    def test_health_status(self):
        """Test provider health status"""
        config = {
            "providers": {
                "test_provider": {
                    "provider": "openai",
                    "model": "gpt-4.1"
                }
            },
            "active_provider": "test_provider"
        }

        manager = ModelProviderManager(config)

        # Default should be unknown
        health = manager.get_health_status("test_provider")
        assert health == ProviderHealthStatus.UNKNOWN

        # Set health status
        manager.set_health_status("test_provider", ProviderHealthStatus.HEALTHY)
        health = manager.get_health_status("test_provider")
        assert health == ProviderHealthStatus.HEALTHY

    def test_fallback_provider_chain(self):
        """Test fallback provider configuration"""
        config = {
            "providers": {
                "primary": {
                    "provider": "openai",
                    "model": "gpt-4.1",
                    "fallback_provider": "secondary"
                },
                "secondary": {
                    "provider": "anthropic",
                    "model": "claude-sonnet-4-20250514"
                }
            },
            "active_provider": "primary"
        }

        manager = ModelProviderManager(config)

        fallback = manager.get_fallback_provider("primary")
        assert fallback == "secondary"

        # Non-existent fallback
        fallback2 = manager.get_fallback_provider("secondary")
        assert fallback2 is None

    def test_failover(self):
        """Test provider failover"""
        config = {
            "providers": {
                "primary": {
                    "provider": "openai",
                    "model": "gpt-4.1",
                    "fallback_provider": "secondary"
                },
                "secondary": {
                    "provider": "anthropic",
                    "model": "claude-sonnet-4-20250514"
                }
            },
            "active_provider": "primary"
        }

        manager = ModelProviderManager(config)

        # Set health for fallback to healthy
        manager.set_health_status("secondary", ProviderHealthStatus.HEALTHY)

        # Failover
        success = manager.failover("primary")
        assert success is True

        # Verify we switched
        active = manager.get_active_provider()
        assert active is not None
        assert active.config.provider == "anthropic"

    def test_failover_to_unhealthy_fails(self):
        """Test failover to unhealthy provider fails"""
        config = {
            "providers": {
                "primary": {
                    "provider": "openai",
                    "model": "gpt-4.1",
                    "fallback_provider": "secondary"
                },
                "secondary": {
                    "provider": "anthropic",
                    "model": "claude-sonnet-4-20250514"
                }
            },
            "active_provider": "primary"
        }

        manager = ModelProviderManager(config)

        # Set health for fallback to unhealthy
        manager.set_health_status("secondary", ProviderHealthStatus.UNHEALTHY)

        # Failover should fail
        success = manager.failover("primary")
        assert success is False

    def test_validate_providers(self):
        """Test provider validation"""
        config = {
            "providers": {
                "valid_provider": {
                    "provider": "openai",
                    "api_key": "test-key",
                    "model": "gpt-4.1"
                },
                "no_key_provider": {
                    "provider": "anthropic",
                    "model": "claude-sonnet-4-20250514"
                },
                "missing_fallback": {
                    "provider": "minimax",
                    "model": "MiniMax-M2.5-highspeed",
                    "fallback_provider": "nonexistent"
                }
            },
            "active_provider": "valid_provider"
        }

        manager = ModelProviderManager(config)

        warnings = manager.validate_providers()

        assert "valid_provider" not in warnings  # Should have no warnings
        assert "no_key_provider" in warnings  # Should have warning about no API key
        assert "missing_fallback" in warnings  # Should have warning about missing fallback

    def test_validate_providers_with_env_key(self):
        """Test provider validation with env var API key"""
        config = {
            "providers": {
                "env_provider": {
                    "provider": "openai",
                    "api_key_env": "TEST_PROVIDER_KEY",
                    "model": "gpt-4.1"
                }
            },
            "active_provider": "env_provider"
        }

        with patch.dict(os.environ, {"TEST_PROVIDER_KEY": "test-key"}):
            manager = ModelProviderManager(config)
            warnings = manager.validate_providers()
            assert "env_provider" not in warnings  # Should have no warnings

    def test_is_error_retryable(self):
        """Test error retryability check"""
        config = {}
        manager = ModelProviderManager(config)

        # Transient errors should be retryable
        assert manager.is_error_retryable(TimeoutError("timeout")) is True
        assert manager.is_error_retryable(Exception("rate limit"), 429) is True
        assert manager.is_error_retryable(Exception("server error"), 500) is True

        # Permanent errors should not be retryable
        assert manager.is_error_retryable(Exception("unauthorized"), 401) is False
        assert manager.is_error_retryable(Exception("not found"), 404) is False
        assert manager.is_error_retryable(Exception("invalid request"), 400) is False

    def test_get_next_api_key_index(self):
        """Test API key rotation index"""
        config = {
            "providers": {
                "multi_key": {
                    "provider": "openai",
                    "api_keys": ["key1", "key2", "key3"]
                }
            },
            "active_provider": "multi_key"
        }

        manager = ModelProviderManager(config)

        # Initialize stats first by recording a call
        manager.record_call_start("multi_key")

        # First call should return 1 (after incrementing from 0), then 2, then 0, then 1
        idx1 = manager.get_next_api_key_index("multi_key")
        assert idx1 == 1

        idx2 = manager.get_next_api_key_index("multi_key")
        assert idx2 == 2

        idx3 = manager.get_next_api_key_index("multi_key")
        assert idx3 == 0  # Back to start

        idx4 = manager.get_next_api_key_index("multi_key")
        assert idx4 == 1

    def test_load_providers_with_new_fields(self):
        """Test loading providers with new configuration fields"""
        config = {
            "providers": {
                "test_provider": {
                    "provider": "openai",
                    "model": "gpt-4.1",
                    "fallback_provider": "backup",
                    "api_keys": ["key1", "key2"],
                    "health_check_enabled": True,
                    "health_check_interval": 600
                }
            },
            "active_provider": "test_provider"
        }

        manager = ModelProviderManager(config)
        provider = manager.get_provider("test_provider")

        assert provider is not None
        assert provider.fallback_provider == "backup"
        assert provider.api_keys == ["key1", "key2"]
        assert provider.health_check_enabled is True
        assert provider.health_check_interval == 600
