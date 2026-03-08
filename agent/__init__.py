"""Agent-Loop - Autonomous AI Agent System

A production-ready autonomous AI agent system built on Claude Agent SDK.
"""

__version__ = "1.0.0"

from .agent_core import AgentCore
from .state_manager import StateManager
from .task_selector import TaskSelector
from .session_manager import SessionManager
from .human_intervention import HumanIntervention
from .git_helper import GitHelper
from .test_runner import AgentTestRunner
from .prompt_manager import PromptManager
from .performance_monitor import PerformanceMonitor
from .config_reloader import ConfigReloader
from .email_notifier import EmailNotifier, get_email_notifier, reset_email_notifier
from .webhook import WebhookNotifier, get_webhook_notifier, reset_webhook_notifier
from .slack_notifier import SlackNotifier, get_slack_notifier, reset_slack_notifier

__all__ = [
    "AgentCore",
    "StateManager",
    "TaskSelector",
    "SessionManager",
    "HumanIntervention",
    "GitHelper",
    "AgentTestRunner",
    "PromptManager",
    "PerformanceMonitor",
    "ConfigReloader",
    "EmailNotifier",
    "get_email_notifier",
    "reset_email_notifier",
    "WebhookNotifier",
    "get_webhook_notifier",
    "reset_webhook_notifier",
    "SlackNotifier",
    "get_slack_notifier",
    "reset_slack_notifier",
]
