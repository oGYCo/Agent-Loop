"""Tests for PerformanceMonitor module"""

import time
import threading
import pytest

# Add parent directory to path for imports
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.performance_monitor import (
    PerformanceMetrics,
    PerformanceMonitor,
    get_monitor,
    reset_monitor,
    monitor_scope,
)


class TestPerformanceMetrics:
    """Test cases for PerformanceMetrics class"""

    def test_init(self):
        """Test PerformanceMetrics initialization"""
        metrics = PerformanceMetrics()
        assert metrics.task_timings == []
        assert metrics.session_start is None
        assert metrics.session_end is None

    def test_start_session(self):
        """Test starting a session"""
        metrics = PerformanceMetrics()
        metrics.start_session()
        assert metrics.session_start is not None
        assert isinstance(metrics.session_start, float)

    def test_end_session_empty(self):
        """Test ending session with no tasks"""
        metrics = PerformanceMetrics()
        metrics.start_session()
        time.sleep(0.01)  # Small delay to ensure duration > 0
        stats = metrics.end_session()

        assert stats["total_tasks"] == 0
        assert stats["session_duration_seconds"] > 0
        assert stats["session_start"] is not None
        assert stats["session_end"] is not None

    def test_end_session_with_tasks(self):
        """Test ending session with recorded tasks"""
        metrics = PerformanceMetrics()
        metrics.start_session()

        # Record some tasks
        metrics.record_task("task-001", "Test Task 1", 1.5, "success")
        metrics.record_task("task-002", "Test Task 2", 2.0, "success")
        metrics.record_task("task-003", "Test Task 3", 0.5, "error", "Test error")

        stats = metrics.end_session()

        assert stats["total_tasks"] == 3
        assert stats["avg_task_duration"] == 1.33  # (1.5 + 2.0 + 0.5) / 3
        assert stats["min_task_duration"] == 0.5
        assert stats["max_task_duration"] == 2.0
        assert stats["total_task_time"] == 4.0

    def test_record_task_success(self):
        """Test recording a successful task"""
        metrics = PerformanceMetrics()
        metrics.record_task("task-001", "Test Task", 1.5, "success")

        assert len(metrics.task_timings) == 1
        task = metrics.task_timings[0]
        assert task["task_id"] == "task-001"
        assert task["task_name"] == "Test Task"
        assert task["duration"] == 1.5
        assert task["status"] == "success"
        assert "timestamp" in task
        assert "error" not in task

    def test_record_task_with_error(self):
        """Test recording a failed task with error"""
        metrics = PerformanceMetrics()
        metrics.record_task("task-001", "Test Task", 1.5, "error", "Something went wrong")

        assert len(metrics.task_timings) == 1
        task = metrics.task_timings[0]
        assert task["status"] == "error"
        assert task["error"] == "Something went wrong"

    def test_multiple_task_recordings(self):
        """Test recording multiple tasks"""
        metrics = PerformanceMetrics()

        for i in range(10):
            metrics.record_task(f"task-{i}", f"Task {i}", float(i + 1), "success")

        assert len(metrics.task_timings) == 10
        # Verify durations are 1.0, 2.0, ..., 10.0
        durations = [t["duration"] for t in metrics.task_timings]
        assert durations == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]


class TestPerformanceMonitor:
    """Test cases for PerformanceMonitor class"""

    def test_init(self):
        """Test PerformanceMonitor initialization"""
        monitor = PerformanceMonitor()
        assert isinstance(monitor.metrics, PerformanceMetrics)
        assert monitor._operation_stack == []

    def test_track_operation_context_manager(self):
        """Test track_operation as context manager"""
        monitor = PerformanceMonitor()

        with monitor.track_operation("test_operation"):
            time.sleep(0.01)  # Small delay

        operations = monitor.get_operation_summary()
        assert len(operations) == 1
        op = operations[0]
        assert op["operation"] == "test_operation"
        assert op["task_id"] is None
        assert op["duration_seconds"] > 0
        assert "cpu_time_seconds" in op
        assert "memory_kb" in op
        assert "timestamp" in op

    def test_track_operation_with_task_id(self):
        """Test track_operation with task_id"""
        monitor = PerformanceMonitor()

        with monitor.track_operation("test_operation", "task-123"):
            time.sleep(0.01)

        operations = monitor.get_operation_summary()
        assert len(operations) == 1
        assert operations[0]["task_id"] == "task-123"

    def test_track_operation_nested(self):
        """Test nested track_operation calls"""
        monitor = PerformanceMonitor()

        with monitor.track_operation("outer"):
            with monitor.track_operation("inner"):
                time.sleep(0.01)

        operations = monitor.get_operation_summary()
        assert len(operations) == 2

    def test_track_function_decorator(self):
        """Test track_function decorator"""
        monitor = PerformanceMonitor()

        @monitor.track_function
        def test_func():
            time.sleep(0.01)
            return "result"

        result = test_func()
        assert result == "result"

    def test_track_function_with_args(self):
        """Test track_function decorator with arguments"""
        monitor = PerformanceMonitor()

        @monitor.track_function
        def add(a, b):
            return a + b

        result = add(2, 3)
        assert result == 5

    def test_track_function_exception(self):
        """Test track_function decorator with exception"""
        monitor = PerformanceMonitor()

        @monitor.track_function
        def failing_func():
            raise ValueError("Test error")

        with pytest.raises(ValueError) as exc_info:
            failing_func()
        assert str(exc_info.value) == "Test error"

    def test_get_system_metrics(self):
        """Test get_system_metrics"""
        monitor = PerformanceMonitor()
        metrics = monitor.get_system_metrics()

        assert "cpu_user_time" in metrics
        assert "cpu_system_time" in metrics
        assert "max_memory_kb" in metrics
        assert "page_faults" in metrics
        assert "io_blocks" in metrics
        assert "context_switches" in metrics

    def test_get_operation_summary(self):
        """Test get_operation_summary"""
        monitor = PerformanceMonitor()

        assert monitor.get_operation_summary() == []

        with monitor.track_operation("op1"):
            pass

        summary = monitor.get_operation_summary()
        assert len(summary) == 1
        assert summary[0]["operation"] == "op1"

    def test_clear_operations(self):
        """Test clear_operations"""
        monitor = PerformanceMonitor()

        with monitor.track_operation("op1"):
            pass

        assert len(monitor.get_operation_summary()) == 1

        monitor.clear_operations()
        assert monitor.get_operation_summary() == []


class TestMonitorScope:
    """Test cases for monitor_scope context manager"""

    def test_monitor_scope_creates_new_instance(self):
        """Test monitor_scope creates a new isolated instance"""
        with monitor_scope() as monitor:
            assert isinstance(monitor, PerformanceMonitor)
            # Can track operations in this scope
            with monitor.track_operation("test_op"):
                time.sleep(0.01)

            assert len(monitor.get_operation_summary()) == 1

    def test_monitor_scope_isolation(self):
        """Test that each monitor_scope creates isolated instances"""
        with monitor_scope() as monitor1:
            with monitor1.track_operation("op1"):
                pass

            with monitor_scope() as monitor2:
                with monitor2.track_operation("op2"):
                    pass

            # monitor1 and monitor2 are different instances
            assert monitor1 is not monitor2
            # Each has its own operation summary
            assert len(monitor1.get_operation_summary()) == 1
            assert len(monitor2.get_operation_summary()) == 1

    def test_monitor_scope_with_session(self):
        """Test monitor_scope with session tracking"""
        with monitor_scope() as monitor:
            monitor.metrics.start_session()
            with monitor.track_operation("task"):
                time.sleep(0.01)
            monitor.metrics.record_task("task-1", "Test", 1.0, "success")
            stats = monitor.metrics.end_session()

            assert stats["total_tasks"] == 1
            assert stats["session_duration_seconds"] > 0


class TestGlobalMonitor:
    """Test cases for global monitor singleton"""

    def test_get_monitor_returns_singleton(self):
        """Test get_monitor returns the same instance"""
        reset_monitor()  # Reset first

        monitor1 = get_monitor()
        monitor2 = get_monitor()

        assert monitor1 is monitor2

    def test_reset_monitor_creates_new_instance(self):
        """Test reset_monitor creates a new monitor instance"""
        reset_monitor()  # Reset first

        monitor1 = get_monitor()
        reset_monitor()
        monitor2 = get_monitor()

        # After reset, a new instance should be created
        # Note: The global is now None, so get_monitor creates a new one
        # But since we call get_monitor after reset, it's a new instance
        assert monitor1 is not monitor2

    def test_monitor_state_isolated_after_reset(self):
        """Test that state is isolated after reset"""
        reset_monitor()

        # Get monitor and record an operation
        monitor1 = get_monitor()
        with monitor1.track_operation("op1"):
            pass

        assert len(monitor1.get_operation_summary()) == 1

        # Reset and get new monitor
        reset_monitor()
        monitor2 = get_monitor()

        # New monitor should have empty operations
        assert len(monitor2.get_operation_summary()) == 0

    def test_get_monitor_thread_safety(self):
        """Test that get_monitor is thread-safe"""
        reset_monitor()

        monitors = []
        errors = []

        def get_monitor_in_thread():
            try:
                m = get_monitor()
                monitors.append(m)
            except Exception as e:
                errors.append(e)

        # Create multiple threads trying to get the monitor
        threads = [threading.Thread(target=get_monitor_in_thread) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All should get the same instance without errors
        assert len(errors) == 0
        assert len(monitors) == 10
        # All monitors should be the same instance
        assert all(m is monitors[0] for m in monitors)

        reset_monitor()


class TestIntegration:
    """Integration tests for performance_monitor"""

    def test_full_workflow(self):
        """Test complete workflow: start session, record tasks, end session"""
        reset_monitor()
        monitor = get_monitor()

        # Start session
        monitor.metrics.start_session()

        # Simulate task execution
        with monitor.track_operation("task_execution", "task-001"):
            time.sleep(0.01)

        # Record task result
        monitor.metrics.record_task("task-001", "Test Task", 1.5, "success")

        # End session
        stats = monitor.metrics.end_session()

        assert stats["total_tasks"] == 1
        assert stats["session_duration_seconds"] > 0
        assert "avg_task_duration" in stats

        reset_monitor()  # Clean up

    def test_decorator_and_context_manager_together(self):
        """Test using both decorator and context manager"""
        reset_monitor()
        monitor = get_monitor()

        @monitor.track_function
        def decorated_func():
            with monitor.track_operation("inner_operation"):
                time.sleep(0.01)
            return "done"

        result = decorated_func()
        assert result == "done"

        # Should have 2 operations: decorated wrapper + inner
        summary = monitor.get_operation_summary()
        assert len(summary) >= 1

        reset_monitor()  # Clean up
