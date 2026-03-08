"""Shared test fixtures for test isolation."""

import pytest


@pytest.fixture(autouse=True)
def _reset_performance_monitor_singleton():
    """Reset the PerformanceMonitor global singleton before each test.

    This prevents stale singleton instances after importlib.reload()
    in hot-reload tests.
    """
    from agent.performance_monitor import reset_monitor
    reset_monitor()
    yield
    reset_monitor()
