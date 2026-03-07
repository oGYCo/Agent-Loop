"""Tests for the metrics module"""

import pytest
from agent.metrics import (
    get_metrics_collector,
    get_prometheus_metrics,
    get_metrics_content_type,
)


def test_metrics_collector_singleton():
    """Test that get_metrics_collector returns a singleton"""
    collector1 = get_metrics_collector()
    collector2 = get_metrics_collector()
    assert collector1 is collector2


def test_prometheus_metrics_output():
    """Test that get_prometheus_metrics returns valid Prometheus format"""
    metrics = get_prometheus_metrics()
    assert isinstance(metrics, bytes)
    # Should contain some expected metrics
    content = metrics.decode("utf-8")
    assert "agent_tasks_pending" in content
    assert "agent_tasks_total" in content


def test_metrics_content_type():
    """Test that content type is correct"""
    content_type = get_metrics_content_type()
    assert "text/plain" in content_type


def test_collector_task_metrics():
    """Test task-related metrics methods"""
    collector = get_metrics_collector()

    # Test increment completed
    collector.increment_task_completed(success=True)
    collector.increment_task_completed(success=False)

    # Test set gauge values
    collector.set_tasks_pending(5)
    collector.set_tasks_total(10)


def test_collector_session_metrics():
    """Test session-related metrics methods"""
    collector = get_metrics_collector()

    # Test session tracking
    collector.start_session("test-session-1")
    collector.end_session("test-session-1")


def test_collector_error_metrics():
    """Test error metrics"""
    collector = get_metrics_collector()
    collector.increment_error("test_error")


def test_collector_api_metrics():
    """Test API metrics"""
    collector = get_metrics_collector()
    collector.increment_api_call("/test")
    collector.observe_api_duration("/test", 0.1)


def test_collector_status_metrics():
    """Test agent status metrics"""
    collector = get_metrics_collector()
    collector.set_agent_status("running")
    collector.increment_iteration()


def test_collector_task_duration():
    """Test task duration tracking"""
    collector = get_metrics_collector()
    collector.start_task("task-1")
    collector.end_task("task-1")
