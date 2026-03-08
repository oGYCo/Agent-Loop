"""Constants Module - Centralized constants for Agent-Loop

This module provides centralized constants to avoid magic numbers and strings
scattered throughout the codebase.
"""

from enum import Enum


# ============== Task/Feature Constants ==============

DEFAULT_PRIORITY = 999  # Default priority when task has no priority specified
MIN_PRIORITY = 1  # Highest priority (lower number = higher priority)
MAX_PRIORITY = 1000  # Lowest priority


# ============== Retry Constants ==============

MAX_RETRY_COUNT = 3  # Maximum number of retry attempts
RETRY_BASE_DELAY = 5  # Base delay in seconds for exponential backoff
RETRY_MAX_DELAY = 60  # Maximum delay cap in seconds


# ============== Configuration Keys ==============

class ConfigKeys(str, Enum):
    """Configuration keys used in config.json"""
    WEBHOOK = "webhook"
    EMAIL = "email"
    SLACK = "slack"
    API_KEYS = "api_keys"
    RETRY = "retry"
    MAX_ERRORS_BEFORE_INTERVENTION = "max_errors_before_intervention"
    PROJECT_NAME = "project_name"
    PROJECT_TYPE = "project_type"
    TEST_COMMAND = "test_command"
    TEST_PATTERN = "test_pattern"
    CONTEXT_WINDOW_LIMIT = "context_window_limit"
    MODEL = "model"
    SESSION_TYPE = "session_type"
    CONTEXT_FILES = "context_files"
    VERIFY_COMMAND = "verify_command"
    ALLOWED_TOOLS = "allowed_tools"
    MCP_SERVERS = "mcp_servers"


# ============== File Names ==============

class FileNames(str, Enum):
    """File names used in .agent/ directory"""
    CONFIG = "config.json"
    FEATURE_LIST = "feature_list.json"
    STATE = "state.json"
    PROMPTS = "prompts.json"
    SESSION_HISTORY = "session_history.json"
    MEMORY = "MEMORY.md"
    PROMPT_TEMPLATES_DIR = "prompt_templates"


# ============== API Paths ==============

class ApiPaths(str, Enum):
    """API endpoint paths"""
    HEALTH = "/health"
    STATUS = "/status"
    TASKS = "/tasks"
    TASK_BY_ID = "/tasks/{task_id}"
    SESSIONS = "/sessions"
    SESSION_BY_ID = "/sessions/{session_id}"
    METRICS = "/metrics"


# ============== Event Types ==============

class EventTypes(str, Enum):
    """Event types for notifications"""
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    HUMAN_INTERVENTION = "human_intervention"
    SESSION_STARTED = "session_started"
    SESSION_ENDED = "session_ended"
    TASK_STARTED = "task_started"
    TEST = "test"


# ============== Status Values ==============

class StatusValues(str, Enum):
    """Task/Feature status values"""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"


# ============== Log Levels ==============

class LogLevels(str, Enum):
    """Logging levels"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


# ============== Notification Channels ==============

class NotificationChannel(str, Enum):
    """Notification channel identifiers"""
    WEBHOOK = "webhook"
    EMAIL = "email"
    SLACK = "slack"


# ============== Default Configuration Values ==============

DEFAULT_TIMEOUT = 10  # Default HTTP timeout in seconds
DEFAULT_RETRY_COUNT = 3  # Default retry count for notifications
DEFAULT_RETRY_INTERVAL = 2  # Default retry interval in seconds
DEFAULT_CONTEXT_WINDOW_LIMIT = 100000  # Default context window limit
DEFAULT_MAX_ERRORS = 3  # Default max errors before human intervention

# ============== Notification Severity ==============

class NotificationSeverity(str, Enum):
    """Notification severity levels"""
    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    DEBUG = "debug"


# ============== HTTP Constants ==============

HTTP_TIMEOUT_DEFAULT = 10  # Default timeout for HTTP requests in seconds
HTTP_USER_AGENT = "Agent-Loop/1.0"
CONTENT_TYPE_JSON = "application/json"


# ============== Misc Constants ==============

MAX_FIELD_LENGTH = 4000  # Max length for text fields in notifications
MAX_FIELD_PREVIEW_LENGTH = 300  # Max preview length for long fields
