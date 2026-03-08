"""Config Model - Pydantic配置模型模块

使用Pydantic BaseModel定义完整的配置数据模型，支持：
- 类型检查和默认值
- 环境变量覆盖
- 配置迁移
- 配置验证
"""

import os
import json
import logging
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, cast

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger("config_model")

# 配置schema版本
CURRENT_SCHEMA_VERSION = "1.2"


class SessionType(str, Enum):
    """会话类型枚举"""
    DEFAULT = "default"
    CODER = "coder"
    RESEARCHER = "researcher"
    REVIEWER = "reviewer"
    AUTO = "auto"  # Backward compatibility


class ProjectType(str, Enum):
    """项目类型枚举"""
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    RUST = "rust"
    GO = "go"
    JAVA = "java"
    UNKNOWN = "unknown"


class ProviderType(str, Enum):
    """模型提供商类型"""
    MINIMAX = "minimax"
    ANTHROPIC = "anthropic"
    OPENAI = "openai"


# ============== 子配置模型 ==============


class ProviderConfig(BaseModel):
    """单个模型提供商配置"""
    provider: ProviderType = ProviderType.MINIMAX
    model: str = "MiniMax-M2.5-highspeed"
    api_key_env: str = "ANTHROPIC_AUTH_TOKEN"
    base_url_env: str = "ANTHROPIC_BASE_URL"

    model_config = {"use_enum_values": True}


class ProvidersConfig(BaseModel):
    """提供商配置映射"""
    default: ProviderConfig = Field(default_factory=ProviderConfig)


class RateLimitEndpointConfig(BaseModel):
    """单个端点的速率限制配置"""
    limit: str = "100/minute"


class RateLimitConfig(BaseModel):
    """速率限制配置"""
    enabled: bool = True
    default_limit: str = "100/minute"
    endpoints: Dict[str, str] = Field(default_factory=dict)


class CORSConfig(BaseModel):
    """CORS跨域配置"""
    enabled: bool = True
    allow_origins: List[str] = Field(default_factory=list)
    allow_credentials: bool = False
    allow_methods: List[str] = Field(default_factory=lambda: ["GET", "POST", "PATCH", "DELETE"])
    allow_headers: List[str] = Field(default_factory=lambda: ["*"])


class RetryConfig(BaseModel):
    """重试配置"""
    max_retries: int = 3
    retry_interval: int = 5
    retry_on_errors: List[str] = Field(default_factory=lambda: ["connection_error", "timeout", "process_error"])


class WebhookConfig(BaseModel):
    """Webhook通知配置"""
    enabled: bool = False
    url: str = ""
    secret: str = ""
    timeout: int = 10
    events: List[str] = Field(default_factory=lambda: ["task_completed", "task_failed", "human_intervention"])
    retry_count: int = 3
    retry_interval: int = 2


class EmailConfig(BaseModel):
    """邮件通知配置"""
    enabled: bool = False
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    use_tls: bool = True
    from_name: str = "Agent-Loop"
    from_email: str = "agent-loop@example.com"
    to_emails: List[str] = Field(default_factory=list)
    events: List[str] = Field(default_factory=lambda: ["task_completed", "task_failed", "human_intervention"])
    timeout: int = 30


class SlackConfig(BaseModel):
    """Slack通知配置"""
    enabled: bool = False
    webhook_url: str = ""
    channel: str = ""
    username: str = "Agent-Loop"
    icon_emoji: str = ":robot_face:"
    events: List[str] = Field(default_factory=lambda: ["task_completed", "task_failed", "human_intervention"])
    timeout: int = 10
    retry_count: int = 3
    retry_interval: int = 2


class DocumentationURLsConfig(BaseModel):
    """文档URL配置"""
    sdk_overview: str = "https://platform.claude.com/docs/en/agent-sdk/overview"
    python_sdk: str = "https://platform.claude.com/docs/en/agent-sdk/python"


# ============== 主配置模型 ==============


class ProjectConfig(BaseSettings):
    """主配置模型 - 支持环境变量覆盖

    环境变量覆盖规则:
    - 前缀: AGENT_LOOP_
    - 例如: project_name -> AGENT_LOOP_PROJECT_NAME
    - 嵌套字段使用双下划线: providers__default__model -> AGENT_LOOP_PROVIDERS__DEFAULT__MODEL

    默认值根据选择的model自动调整context_window_limit:
    - GPT-4系列: 128000
    - Claude系列: 200000
    - MiniMax系列: 100000
    """

    # 基础配置
    project_name: str = "Agent-Loop"
    project_type: str = "python"
    model: str = "MiniMax-M2.5-highspeed"
    session_type: SessionType = SessionType.CODER

    # 提供商配置
    active_provider: str = "default"
    providers: ProvidersConfig = Field(default_factory=ProvidersConfig)

    # 执行配置
    test_command: str = "pytest tests/ -v"
    test_pattern: str = "test_*.py"
    max_errors_before_intervention: int = 3
    context_window_limit: int = 100000

    # API配置
    api_keys: Dict[str, Any] = Field(default_factory=lambda: {"enabled": False, "keys": []})

    # 网络配置
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)
    cors: CORSConfig = Field(default_factory=CORSConfig)
    retry: RetryConfig = Field(default_factory=RetryConfig)

    # 通知配置
    webhook: WebhookConfig = Field(default_factory=WebhookConfig)
    email: EmailConfig = Field(default_factory=EmailConfig)
    slack: SlackConfig = Field(default_factory=SlackConfig)

    # 文档配置
    documentation_urls: DocumentationURLsConfig = Field(default_factory=DocumentationURLsConfig)

    # 上下文配置
    context_files: List[str] = Field(default_factory=lambda: ["README.md", "CLAUDE.md"])
    verify_command: str = "pytest tests/ -x -q"
    allowed_tools: List[str] = Field(default_factory=lambda: [
        "Read", "Write", "Edit", "Bash", "Glob", "Grep", "MultiEdit", "WebSearch", "WebFetch"
    ])
    mcp_servers: List[str] = Field(default_factory=list)

    # Schema版本（用于迁移）
    schema_version: str = CURRENT_SCHEMA_VERSION

    model_config = SettingsConfigDict(
        env_prefix="AGENT_LOOP_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    @field_validator("context_window_limit", mode="before")
    @classmethod
    def adjust_context_window(cls, v: Any, info) -> int:
        """根据model自动调整context_window_limit"""
        # 如果context_window_limit已明确设置，保留该值
        if v is not None and v != 100000:  # 不是默认值
            return v

        # 从info.data获取model
        model = info.data.get("model", "").lower() if info.data else ""

        # 根据model自动调整
        if "gpt-4" in model or "gpt4" in model:
            return 128000
        elif "claude" in model:
            return 200000
        elif "mini" in model and "max" in model:
            return 100000
        elif "o1" in model or "o3" in model:
            return 200000

        # 默认值
        return 100000

    def get_effective_model(self) -> str:
        """获取实际使用的模型名称"""
        if self.active_provider in self.providers.model_dump():
            provider = self.providers.model_dump()[self.active_provider]
            return provider.get("model", self.model)
        return self.model

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于保存）"""
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectConfig":
        """从字典创建配置"""
        return cls(**data)


# ============== 配置迁移引擎 ==============


class ConfigMigration:
    """配置迁移引擎

    支持从旧版本迁移到新版本，输出迁移日志。
    """

    def __init__(self) -> None:
        self.migrations: Dict[str, callable] = {}
        self._register_migrations()

    def _register_migrations(self) -> None:
        """注册所有迁移函数"""
        self.migrations["1.0"] = self._migrate_v1_0_to_v1_1
        self.migrations["1.1"] = self._migrate_v1_1_to_v1_2

    def _migrate_v1_0_to_v1_1(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """迁移 v1.0 -> v1.1"""
        logger.info("Running migration: v1.0 -> v1.1")
        # v1.1: 添加schema_version字段
        config["schema_version"] = "1.1"
        return config

    def _migrate_v1_1_to_v1_2(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """迁移 v1.1 -> v1.2"""
        logger.info("Running migration: v1.1 -> v1.2")
        # v1.2: 添加新的通知配置默认值
        if "documentation_urls" not in config:
            config["documentation_urls"] = {
                "sdk_overview": "https://platform.claude.com/docs/en/agent-sdk/overview",
                "python_sdk": "https://platform.claude.com/docs/en/agent-sdk/python"
            }
        return config

    def migrate(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """执行迁移

        Args:
            config: 原始配置字典

        Returns:
            迁移后的配置字典
        """
        # 获取当前schema版本（兼容旧配置）
        current_version = config.get("schema_version", "1.0")
        logger.info(f"Current config schema version: {current_version}")

        # 如果已经是最新版本，无需迁移
        if current_version == CURRENT_SCHEMA_VERSION:
            return config

        # 按顺序执行迁移
        migration_order = ["1.0", "1.1"]
        for version in migration_order:
            if version == current_version:
                break
            if version in self.migrations:
                config = self.migrations[version](config)

        # 确保最终版本正确
        config["schema_version"] = CURRENT_SCHEMA_VERSION
        logger.info(f"Migration complete. Final schema version: {CURRENT_SCHEMA_VERSION}")

        return config


# ============== 配置加载器 ==============


class ConfigLoader:
    """配置加载器

    负责：
    - 从config.json加载配置
    - 应用环境变量覆盖
    - 执行配置迁移
    - 验证配置有效性
    """

    def __init__(self, agent_dir: Optional[str] = None) -> None:
        if agent_dir is None:
            agent_dir = str(Path(__file__).parent.parent / ".agent")
        self.agent_dir = Path(agent_dir)
        self.config_path = self.agent_dir / "config.json"
        self.migration_engine = ConfigMigration()

    def load(self) -> ProjectConfig:
        """加载并返回配置"""
        # 1. 尝试从文件加载
        if self.config_path.exists():
            config_dict = self._load_from_file()
        else:
            config_dict = {}

        # 2. 应用环境变量覆盖
        config_dict = self._apply_env_overrides(config_dict)

        # 3. 执行迁移
        config_dict = self.migration_engine.migrate(config_dict)

        # 4. 创建Pydantic模型（会自动验证和调整默认值）
        return ProjectConfig(**config_dict)

    def _load_from_file(self) -> Dict[str, Any]:
        """从配置文件加载"""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return cast(Dict[str, Any], json.load(f))
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse config.json: {e}, using defaults")
            return {}
        except Exception as e:
            logger.warning(f"Failed to load config.json: {e}, using defaults")
            return {}

    def _apply_env_overrides(self, config_dict: Dict[str, Any]) -> Dict[str, Any]:
        """应用环境变量覆盖

        通过检查环境变量来覆盖配置值。
        环境变量使用 AGENT_LOOP_ 前缀，嵌套使用双下划线。
        """
        # 扁平化配置以便查找对应的环境变量
        def get_nested_value(d: Dict[str, Any], path: str) -> Any:
            keys = path.split(".")
            value = d
            for key in keys:
                if isinstance(value, dict):
                    value = value.get(key)
                else:
                    return None
            return value

        def set_nested_value(d: Dict[str, Any], path: str, value: Any) -> None:
            keys = path.split(".")
            current = d
            for key in keys[:-1]:
                if key not in current:
                    current[key] = {}
                current = current[key]
            current[keys[-1]] = value

        # 检查所有可能的配置键
        for key in ["project_name", "project_type", "model", "session_type",
                    "active_provider", "test_command", "test_pattern",
                    "max_errors_before_intervention", "context_window_limit"]:
            env_key = f"AGENT_LOOP_{key.upper()}"
            if env_key in os.environ:
                value = os.environ[env_key]
                # 类型转换
                if key == "max_errors_before_intervention":
                    value = int(value)
                elif key == "context_window_limit":
                    value = int(value)
                set_nested_value(config_dict, key, value)

        # 检查嵌套配置
        for provider_name in ["default"]:
            for field in ["model", "provider"]:
                env_key = f"AGENT_LOOP_PROVIDERS__{provider_name}__{field.upper()}"
                if env_key in os.environ:
                    value = os.environ[env_key]
                    if "providers" not in config_dict:
                        config_dict["providers"] = {}
                    if provider_name not in config_dict["providers"]:
                        config_dict["providers"][provider_name] = {}
                    config_dict["providers"][provider_name][field] = value

        return config_dict

    def save(self, config: ProjectConfig) -> None:
        """保存配置到文件"""
        config_dict = config.to_dict()
        # 确保schema_version存在
        config_dict["schema_version"] = CURRENT_SCHEMA_VERSION

        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(config_dict, f, indent=2, ensure_ascii=False)


# ============== 配置导出/导入 ==============


def export_config(agent_dir: Optional[str] = None, include_sensitive: bool = False) -> Dict[str, Any]:
    """导出配置（脱敏版）

    Args:
        agent_dir: Agent目录路径
        include_sensitive: 是否包含敏感信息

    Returns:
        导出配置字典
    """
    loader = ConfigLoader(agent_dir)
    config = loader.load()
    config_dict = config.to_dict()

    if not include_sensitive:
        # 脱敏处理
        if "api_keys" in config_dict:
            config_dict["api_keys"]["keys"] = ["***REDACTED***"]
            config_dict["api_keys"]["enabled"] = False

        if "email" in config_dict:
            config_dict["email"]["smtp_password"] = "***REDACTED***"

        if "webhook" in config_dict:
            config_dict["webhook"]["secret"] = "***REDACTED***"

        if "slack" in config_dict:
            config_dict["slack"]["webhook_url"] = "***REDACTED***"

        # 隐藏api_key_env引用的实际值
        for provider_name, provider_config in config_dict.get("providers", {}).items():
            if isinstance(provider_config, dict):
                # 标记环境变量但不显示实际值
                provider_config["api_key_env"] = "***REDACTED***"

    return config_dict


def import_config(config_dict: Dict[str, Any], agent_dir: Optional[str] = None) -> ProjectConfig:
    """导入配置

    Args:
        config_dict: 配置字典
        agent_dir: Agent目录路径

    Returns:
        验证后的ProjectConfig对象
    """
    # 迁移配置
    migration_engine = ConfigMigration()
    config_dict = migration_engine.migrate(config_dict)

    # 创建并验证配置
    return ProjectConfig(**config_dict)


# ============== 便捷函数 ==============


def load_config(agent_dir: Optional[str] = None) -> ProjectConfig:
    """便捷函数：加载配置"""
    return ConfigLoader(agent_dir).load()


def save_config(config: ProjectConfig, agent_dir: Optional[str] = None) -> None:
    """便捷函数：保存配置"""
    ConfigLoader(agent_dir).save(config)
