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


# ========== Provider Metrics ==========

PROVIDER_CALLS = Counter(
    "agent_provider_calls_total",
    "Total number of provider API calls",
    ["provider", "status"]  # provider name, "success" or "failure"
)

PROVIDER_RESPONSE_TIME = Histogram(
    "agent_provider_response_time_seconds",
    "Provider response time in seconds",
    ["provider"],
    buckets=[0.1, 0.5, 1, 5, 10, 30, 60, 120]
)

PROVIDER_HEALTH = Gauge(
    "agent_provider_health",
    "Provider health status (0=unknown, 1=healthy, 2=unhealthy)",
    ["provider"]
)

PROVIDER_FAILOVER = Counter(
    "agent_provider_failover_total",
    "Total number of provider failovers",
    ["from_provider", "to_provider"]
)

PROVIDER_ACTIVE = Gauge(
    "agent_provider_active",
    "Currently active provider",
    ["provider"]
)


# ========== Metrics Collector ==========

class MetricsCollector:
    """Central metrics collector with thread-safe operations"""

    _instance = None
    _lock = threading.Lock()
    # Maximum tracked concurrent sessions/tasks to prevent memory leaks
    _MAX_TRACKED_ENTRIES = 100

    def __init__(self):
        self._session_start_times: dict[str, float] = {}
        self._task_start_times: dict[str, float] = {}
        self._providers_set: set[str] = set()

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
        # Prevent unbounded growth: evict oldest entries if over limit
        if len(self._session_start_times) >= self._MAX_TRACKED_ENTRIES:
            oldest_key = min(self._session_start_times, key=self._session_start_times.get)  # type: ignore[arg-type]
            self._session_start_times.pop(oldest_key, None)
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
        # Prevent unbounded growth: evict oldest entries if over limit
        if len(self._task_start_times) >= self._MAX_TRACKED_ENTRIES:
            oldest_key = min(self._task_start_times, key=self._task_start_times.get)  # type: ignore[arg-type]
            self._task_start_times.pop(oldest_key, None)
        self._task_start_times[task_id] = time.time()

    def end_task(self, task_id: str):
        """Record task end time and update duration histogram"""
        start_time = self._task_start_times.pop(task_id, None)
        if start_time:
            duration = time.time() - start_time
            TASK_DURATION.observe(duration)

    # Provider methods
    def record_provider_call(self, provider: str, success: bool = True):
        """Record a provider API call"""
        status = "success" if success else "failure"
        PROVIDER_CALLS.labels(provider=provider, status=status).inc()

    def record_provider_response_time(self, provider: str, duration: float):
        """Record provider response time"""
        PROVIDER_RESPONSE_TIME.labels(provider=provider).observe(duration)

    def set_provider_health(self, provider: str, status: str):
        """Set provider health status (healthy, unhealthy, unknown)"""
        status_map = {"healthy": 1, "unhealthy": 2, "unknown": 0}
        PROVIDER_HEALTH.labels(provider=provider).set(status_map.get(status, 0))

    def record_provider_failover(self, from_provider: str, to_provider: str):
        """Record a provider failover event"""
        PROVIDER_FAILOVER.labels(from_provider=from_provider, to_provider=to_provider).inc()

    def set_active_provider(self, provider: str):
        """Set the currently active provider"""
        # Reset all providers first
        for p in self._providers_set:
            PROVIDER_ACTIVE.labels(provider=p).set(0)
        # Set active provider
        PROVIDER_ACTIVE.labels(provider=provider).set(1)
        self._providers_set.add(provider)


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance"""
    return MetricsCollector.get_instance()


def get_prometheus_metrics() -> bytes:
    """Generate Prometheus metrics output"""
    return generate_latest()


def get_metrics_content_type() -> str:
    """Get Prometheus content type"""
    return CONTENT_TYPE_LATEST
