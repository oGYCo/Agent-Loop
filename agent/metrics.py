"""Metrics Module - Prometheus metrics collection for Agent-Loop

Exposes metrics in Prometheus format including:
- Task completion and error counts
- Session duration
- API call counts
- Agent status
"""

import time
import threading
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST


# ========== Task Metrics ==========

TASKS_COMPLETED = Counter(
    "agent_tasks_completed_total",
    "Total number of tasks completed",
    ["status"]  # "success" or "error"
)

TASKS_PENDING = Gauge(
    "agent_tasks_pending",
    "Number of pending tasks"
)

TASKS_TOTAL = Gauge(
    "agent_tasks_total",
    "Total number of tasks"
)


# ========== Session Metrics ==========

SESSION_DURATION = Histogram(
    "agent_session_duration_seconds",
    "Session duration in seconds",
    buckets=[1, 5, 10, 30, 60, 300, 600, 1800, 3600]
)

SESSIONS_ACTIVE = Gauge(
    "agent_sessions_active",
    "Number of currently active sessions"
)

SESSIONS_TOTAL = Counter(
    "agent_sessions_total",
    "Total number of sessions started"
)


# ========== Error Metrics ==========

ERROR_COUNT = Counter(
    "agent_errors_total",
    "Total number of errors",
    ["type"]  # error type/category
)


# ========== API Metrics ==========

API_CALLS = Counter(
    "agent_api_calls_total",
    "Total number of API calls",
    ["endpoint"]  # endpoint name
)

API_DURATION = Histogram(
    "agent_api_duration_seconds",
    "API request duration in seconds",
    ["endpoint"],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1, 5]
)


# ========== Agent Status Metrics ==========

AGENT_STATUS = Gauge(
    "agent_status",
    "Current agent status (0=idle, 1=running, 2=error)"
)

ITERATION_COUNT = Counter(
    "agent_iterations_total",
    "Total number of agent iterations"
)


# ========== Performance Metrics ==========

TASK_DURATION = Histogram(
    "agent_task_duration_seconds",
    "Task execution duration in seconds",
    buckets=[0.1, 0.5, 1, 5, 10, 30, 60, 300, 600]
)


# ========== Metrics Collector ==========

class MetricsCollector:
    """Central metrics collector with thread-safe operations"""

    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self._session_start_times: dict[str, float] = {}
        self._task_start_times: dict[str, float] = {}

    @classmethod
    def get_instance(cls) -> "MetricsCollector":
        """Get singleton instance"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # Task methods
    def increment_task_completed(self, success: bool = True):
        """Increment task completion counter"""
        status = "success" if success else "error"
        TASKS_COMPLETED.labels(status=status).inc()

    def set_tasks_pending(self, count: int):
        """Set pending tasks gauge"""
        TASKS_PENDING.set(count)

    def set_tasks_total(self, count: int):
        """Set total tasks gauge"""
        TASKS_TOTAL.set(count)

    # Session methods
    def start_session(self, session_id: str):
        """Record session start time"""
        self._session_start_times[session_id] = time.time()
        SESSIONS_ACTIVE.inc()
        SESSIONS_TOTAL.inc()

    def end_session(self, session_id: str):
        """Record session end time and update duration histogram"""
        start_time = self._session_start_times.pop(session_id, None)
        if start_time:
            duration = time.time() - start_time
            SESSION_DURATION.observe(duration)
        SESSIONS_ACTIVE.dec()

    # Error methods
    def increment_error(self, error_type: str = "unknown"):
        """Increment error counter"""
        ERROR_COUNT.labels(type=error_type).inc()

    # API methods
    def increment_api_call(self, endpoint: str):
        """Increment API call counter"""
        API_CALLS.labels(endpoint=endpoint).inc()

    def observe_api_duration(self, endpoint: str, duration: float):
        """Record API request duration"""
        API_DURATION.labels(endpoint=endpoint).observe(duration)

    # Agent status methods
    def set_agent_status(self, status: str):
        """Set agent status (idle, running, error)"""
        status_map = {"idle": 0, "running": 1, "error": 2}
        AGENT_STATUS.set(status_map.get(status, 0))

    def increment_iteration(self):
        """Increment iteration counter"""
        ITERATION_COUNT.inc()

    # Task duration methods
    def start_task(self, task_id: str):
        """Record task start time"""
        self._task_start_times[task_id] = time.time()

    def end_task(self, task_id: str):
        """Record task end time and update duration histogram"""
        start_time = self._task_start_times.pop(task_id, None)
        if start_time:
            duration = time.time() - start_time
            TASK_DURATION.observe(duration)


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance"""
    return MetricsCollector.get_instance()


def get_prometheus_metrics() -> bytes:
    """Generate Prometheus metrics output"""
    return generate_latest()


def get_metrics_content_type() -> str:
    """Get Prometheus content type"""
    return CONTENT_TYPE_LATEST
