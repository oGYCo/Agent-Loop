"""Agent-Loop package.

Exports top-level symbols lazily so lightweight modules such as
``agent.console`` can be imported without pulling in the full runtime stack.
"""

from importlib import import_module
from typing import Any

__version__ = "0.1.0"

_EXPORTS = {
    "AgentCore": (".agent_core", "AgentCore"),
    "StateManager": (".state_manager", "StateManager"),
    "TaskSelector": (".task_selector", "TaskSelector"),
    "SessionManager": (".session_manager", "SessionManager"),
    "HumanIntervention": (".human_intervention", "HumanIntervention"),
    "GitHelper": (".git_helper", "GitHelper"),
    "AgentTestRunner": (".test_runner", "AgentTestRunner"),
    "PromptManager": (".prompt_manager", "PromptManager"),
    "PerformanceMonitor": (".performance_monitor", "PerformanceMonitor"),
    "ConfigReloader": (".config_reloader", "ConfigReloader"),
    "EmailNotifier": (".email_notifier", "EmailNotifier"),
    "get_email_notifier": (".email_notifier", "get_email_notifier"),
    "reset_email_notifier": (".email_notifier", "reset_email_notifier"),
    "WebhookNotifier": (".webhook", "WebhookNotifier"),
    "get_webhook_notifier": (".webhook", "get_webhook_notifier"),
    "reset_webhook_notifier": (".webhook", "reset_webhook_notifier"),
    "SlackNotifier": (".slack_notifier", "SlackNotifier"),
    "get_slack_notifier": (".slack_notifier", "get_slack_notifier"),
    "reset_slack_notifier": (".slack_notifier", "reset_slack_notifier"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    """Lazily import package exports on first access."""
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attr_name = _EXPORTS[name]
    module = import_module(module_name, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Expose lazy exports to dir() and IDE completion."""
    return sorted(list(globals().keys()) + __all__)
