"""Performance Monitor - 性能监控模块

跟踪任务执行时间、会话时长、系统资源使用等指标。
"""

import time
import logging
import resource
import threading
from datetime import datetime
from typing import Dict, Any, List
from contextlib import contextmanager
from functools import wraps

# 配置性能日志记录器
perf_logger = logging.getLogger("agent_core.performance")


class PerformanceMetrics:
    """性能指标收集器"""

    def __init__(self) -> None:
        self.task_timings: List[Dict[str, Any]] = []
        self.session_start: float | None = None
        self.session_end: float | None = None

    def start_session(self) -> None:
        """开始会话计时"""
        self.session_start = time.time()
        perf_logger.info("Session performance tracking started")

    def end_session(self) -> Dict[str, Any]:
        """结束会话并返回性能统计"""
        self.session_end = time.time()
        duration = self.session_end - self.session_start if self.session_start else 0

        stats = {
            "session_duration_seconds": round(duration, 2),
            "total_tasks": len(self.task_timings),
            "session_start": datetime.fromtimestamp(self.session_start).isoformat() if self.session_start else None,
            "session_end": datetime.fromtimestamp(self.session_end).isoformat() if self.session_end else None,
        }

        # 计算任务统计
        if self.task_timings:
            task_durations = [t.get("duration", 0) for t in self.task_timings]
            stats["avg_task_duration"] = round(sum(task_durations) / len(task_durations), 2)
            stats["min_task_duration"] = round(min(task_durations), 2)
            stats["max_task_duration"] = round(max(task_durations), 2)
            stats["total_task_time"] = round(sum(task_durations), 2)

        perf_logger.info(f"Session completed: {stats}")
        return stats

    def record_task(self, task_id: str, task_name: str, duration: float, status: str, error: str | None = None) -> None:
        """记录任务执行信息"""
        task_info = {
            "task_id": task_id,
            "task_name": task_name,
            "duration": round(duration, 2),
            "status": status,
            "timestamp": datetime.now().isoformat(),
        }
        if error:
            task_info["error"] = error

        self.task_timings.append(task_info)
        perf_logger.info(
            f"Task performance: {task_name} ({task_id}) - {duration:.2f}s - Status: {status}"
        )


class PerformanceMonitor:
    """性能监控器 - 提供上下文管理器和装饰器"""

    def __init__(self) -> None:
        self.metrics = PerformanceMetrics()
        self._operation_stack: List[Dict[str, Any]] = []

    @contextmanager
    def track_operation(self, operation_name: str, task_id: str | None = None):
        """上下文管理器：跟踪操作性能

        Args:
            operation_name: 操作名称
            task_id: 可选的任务ID

        Usage:
            with monitor.track_operation("execute_task", "task-123"):
                # 执行操作
                pass
        """
        start_time = time.time()
        start_resources = resource.getrusage(resource.RUSAGE_SELF)

        try:
            yield
        finally:
            end_time = time.time()
            end_resources = resource.getrusage(resource.RUSAGE_SELF)
            duration = end_time - start_time

            # 计算资源使用
            cpu_time = (end_resources.ru_utime - start_resources.ru_utime) + \
                       (end_resources.ru_stime - start_resources.ru_stime)
            memory_kb = end_resources.ru_maxrss

            operation_info = {
                "operation": operation_name,
                "task_id": task_id,
                "duration_seconds": round(duration, 4),
                "cpu_time_seconds": round(cpu_time, 4),
                "memory_kb": memory_kb,
                "timestamp": datetime.now().isoformat(),
            }

            self._operation_stack.append(operation_info)

            perf_logger.info(
                f"Performance: {operation_name} - Duration: {duration:.4f}s, "
                f"CPU: {cpu_time:.4f}s, Memory: {memory_kb}KB"
            )

    def track_function(self, func):
        """装饰器：跟踪函数性能

        Usage:
            @monitor.track_function
            def my_function():
                pass
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            start_resources = resource.getrusage(resource.RUSAGE_SELF)
            status = "success"
            error = None

            try:
                return func(*args, **kwargs)
            except Exception as e:
                status = "error"
                error = str(e)
                raise
            finally:
                end_time = time.time()
                end_resources = resource.getrusage(resource.RUSAGE_SELF)
                duration = end_time - start_time

                cpu_time = (end_resources.ru_utime - start_resources.ru_utime) + \
                           (end_resources.ru_stime - start_resources.ru_stime)
                memory_kb = end_resources.ru_maxrss

                perf_logger.info(
                    f"Function performance: {func.__name__} - Duration: {duration:.4f}s, "
                    f"CPU: {cpu_time:.4f}s, Memory: {memory_kb}KB, Status: {status}"
                )

        return wrapper

    def get_system_metrics(self) -> Dict[str, Any]:
        """获取当前系统资源使用情况"""
        resources = resource.getrusage(resource.RUSAGE_SELF)

        return {
            "cpu_user_time": resources.ru_utime,
            "cpu_system_time": resources.ru_stime,
            "max_memory_kb": resources.ru_maxrss,
            "page_faults": resources.ru_minflt + resources.ru_majflt,
            "io_blocks": resources.ru_inblock + resources.ru_oublock,
            "context_switches": resources.ru_nvcsw + resources.ru_nivcsw,
        }

    def get_operation_summary(self) -> List[Dict[str, Any]]:
        """获取操作摘要"""
        return self._operation_stack.copy()

    def clear_operations(self) -> None:
        """清除操作记录"""
        self._operation_stack.clear()


# 全局性能监控器实例（线程安全）
_global_monitor: PerformanceMonitor | None = None
_global_monitor_lock = threading.Lock()


def get_monitor() -> PerformanceMonitor:
    """获取全局性能监控器实例（线程安全）"""
    global _global_monitor
    if _global_monitor is None:
        with _global_monitor_lock:
            # Double-check locking pattern
            if _global_monitor is None:
                _global_monitor = PerformanceMonitor()
    return _global_monitor


def reset_monitor() -> None:
    """重置全局性能监控器（线程安全）"""
    global _global_monitor
    with _global_monitor_lock:
        _global_monitor = None


@contextmanager
def monitor_scope() -> "PerformanceMonitor":
    """上下文管理器：创建作用域内的性能监控器实例

    推荐使用此方法代替全局 get_monitor() 以避免多线程/异步环境中的竞态条件。

    Usage:
        with monitor_scope() as monitor:
            with monitor.track_operation("operation_name"):
                # 执行操作
                pass

    Yields:
        PerformanceMonitor: 新的监控器实例
    """
    monitor = PerformanceMonitor()
    try:
        yield monitor
    finally:
        # 作用域结束时自动清理
        pass
