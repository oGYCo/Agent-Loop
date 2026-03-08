"""Notification Queue - 异步通知队列

提供异步通知队列，支持：
- 非阻塞通知发送
- 失败通知自动重试
- 重试队列管理
- 队列状态监控
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from collections import deque

from .notification_router import NotificationRouter

logger = logging.getLogger(__name__)


class QueueStatus(Enum):
    """队列状态"""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"


class NotificationPriority(Enum):
    """通知优先级"""
    HIGH = 0    # 高优先级，如 human_intervention
    NORMAL = 1  # 普通优先级，如 task_failed
    LOW = 2     # 低优先级，如 task_completed


@dataclass(order=True)
class NotificationItem:
    """通知队列项"""
    sort_index: tuple[float, str] = field(init=False, repr=False, compare=True)
    id: str = field(compare=False)
    event_type: str = field(compare=False)
    data: Dict[str, Any] = field(compare=False)
    priority: NotificationPriority = field(default=NotificationPriority.NORMAL, compare=False)
    created_at: float = field(default_factory=time.time, compare=False)
    retry_count: int = field(default=0, compare=False)
    max_retries: int = field(default=3, compare=False)
    last_error: Optional[str] = field(default=None, compare=False)

    def __post_init__(self) -> None:
        """Provide a deterministic tie-breaker for heap comparisons."""
        self.sort_index = (self.created_at, self.id)


class NotificationQueue:
    """通知队列

    异步通知队列，实现：
    - 优先级队列
    - 失败重试
    - 非阻塞发送

    配置示例:
    ```python
    queue = NotificationQueue(
        max_size=100,
        max_retries=3,
        retry_interval=5,
        worker_count=2
    )
    await queue.start()
    ```
    """

    def __init__(
        self,
        router: Optional[NotificationRouter] = None,
        max_size: int = 100,
        max_retries: int = 3,
        retry_interval: float = 5.0,
        worker_count: int = 2,
        enable_retry_queue: bool = True
    ) -> None:
        """初始化通知队列

        Args:
            router: 通知路由器实例
            max_size: 队列最大长度
            max_retries: 最大重试次数
            retry_interval: 重试间隔（秒）
            worker_count: 工作线程数
            enable_retry_queue: 是否启用重试队列
        """
        self.router = router or NotificationRouter()
        self.max_size = max_size
        self.max_retries = max_retries
        self.retry_interval = retry_interval
        self.worker_count = worker_count
        self.enable_retry_queue = enable_retry_queue

        # 队列
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue(maxsize=max_size)
        self._retry_queue: deque = deque()
        self._processing_queue: Dict[str, NotificationItem] = {}

        # 状态
        self._status = QueueStatus.IDLE
        self._workers: List[asyncio.Task] = []
        self._retry_worker: Optional[asyncio.Task] = None
        self._running = False

        # 统计
        self._stats = {
            "total_sent": 0,
            "total_failed": 0,
            "total_retried": 0,
            "current_queue_size": 0,
            "current_retry_size": 0
        }

        # 通知ID生成器
        self._notification_id = 0

    @property
    def status(self) -> QueueStatus:
        """获取队列状态"""
        return self._status

    @property
    def stats(self) -> Dict[str, Any]:
        """获取队列统计"""
        return {
            **self._stats,
            "queue_size": self._queue.qsize(),
            "retry_queue_size": len(self._retry_queue),
            "processing_count": len(self._processing_queue),
            "status": self._status.value
        }

    def _generate_id(self) -> str:
        """生成唯一通知ID"""
        self._notification_id += 1
        return f"notif-{int(time.time() * 1000)}-{self._notification_id}"

    def _get_priority_for_event(self, event_type: str) -> NotificationPriority:
        """根据事件类型获取优先级"""
        priority_map = {
            "human_intervention": NotificationPriority.HIGH,
            "task_failed": NotificationPriority.NORMAL,
            "task_completed": NotificationPriority.LOW,
        }
        return priority_map.get(event_type, NotificationPriority.NORMAL)

    async def enqueue(
        self,
        event_type: str,
        data: Dict[str, Any],
        priority: Optional[NotificationPriority] = None,
        max_retries: Optional[int] = None
    ) -> str:
        """将通知加入队列

        Args:
            event_type: 事件类型
            data: 通知数据
            priority: 优先级，默认根据事件类型自动确定
            max_retries: 最大重试次数

        Returns:
            通知ID
        """
        if self._status == QueueStatus.STOPPED:
            raise RuntimeError("Queue is stopped")

        if priority is None:
            priority = self._get_priority_for_event(event_type)

        if max_retries is None:
            max_retries = self.max_retries

        notification = NotificationItem(
            id=self._generate_id(),
            event_type=event_type,
            data=data,
            priority=priority,
            max_retries=max_retries
        )

        # 使用优先级队列，(priority, notification) 元组
        # asyncio.PriorityQueue 使用最小堆，priority 越小越先处理
        await self._queue.put((priority.value, notification))

        logger.debug(f"Enqueued notification {notification.id} for event {event_type}")
        return notification.id

    async def _process_notification(self, item: NotificationItem) -> bool:
        """处理单个通知

        Args:
            item: 通知项

        Returns:
            是否处理成功
        """
        self._processing_queue[item.id] = item

        try:
            logger.debug(f"Processing notification {item.id}")

            results = await self.router.send_notification(
                item.event_type,
                item.data
            )

            # 检查是否有任何渠道发送成功
            success = any(results.values()) if results else False

            if success:
                self._stats["total_sent"] += 1
                logger.info(f"Notification {item.id} sent successfully")
                return True
            else:
                raise Exception("All channels failed to send")

        except Exception as e:
            item.last_error = str(e)
            item.retry_count += 1

            logger.warning(
                f"Notification {item.id} failed (attempt {item.retry_count}/{item.max_retries}): {e}"
            )

            if self.enable_retry_queue and item.retry_count < item.max_retries:
                # 加入重试队列
                self._retry_queue.append(item)
                self._stats["total_retried"] += 1
                logger.info(f"Notification {item.id} added to retry queue")
            else:
                self._stats["total_failed"] += 1
                logger.error(f"Notification {item.id} failed permanently after {item.retry_count} attempts")

            return False

        finally:
            self._processing_queue.pop(item.id, None)

    async def _worker(self, worker_id: int) -> None:
        """工作线程

        Args:
            worker_id: 工作线程ID
        """
        logger.debug(f"Worker {worker_id} started")

        while self._running:
            try:
                # 从队列获取通知
                try:
                    priority, item = await asyncio.wait_for(
                        self._queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue

                # 处理通知
                await self._process_notification(item)

                # 标记任务完成
                self._queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")

        logger.debug(f"Worker {worker_id} stopped")

    async def _retry_worker_func(self) -> None:
        """重试工作线程"""
        logger.debug("Retry worker started")

        while self._running:
            try:
                if not self._retry_queue:
                    await asyncio.sleep(self.retry_interval)
                    continue

                # 从重试队列获取通知
                item = self._retry_queue.popleft()

                logger.debug(f"Retrying notification {item.id}")

                # 重新处理
                await self._process_notification(item)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Retry worker error: {e}")
                await asyncio.sleep(1)

        logger.debug("Retry worker stopped")

    async def start(self) -> None:
        """启动队列"""
        if self._status == QueueStatus.RUNNING:
            logger.warning("Queue is already running")
            return

        self._running = True
        self._status = QueueStatus.RUNNING

        # 启动工作线程
        for i in range(self.worker_count):
            worker = asyncio.create_task(self._worker(i))
            self._workers.append(worker)

        # 启动重试工作线程
        if self.enable_retry_queue:
            self._retry_worker = asyncio.create_task(self._retry_worker_func())

        logger.info(f"Notification queue started with {self.worker_count} workers")

    async def stop(self) -> None:
        """停止队列"""
        self._running = False
        self._status = QueueStatus.STOPPED

        # 取消所有工作线程
        for worker in self._workers:
            worker.cancel()

        if self._retry_worker:
            self._retry_worker.cancel()

        # 等待所有工作线程结束
        await asyncio.gather(*self._workers, return_exceptions=True)
        if self._retry_worker:
            await asyncio.gather(self._retry_worker, return_exceptions=True)

        self._workers.clear()
        self._retry_worker = None

        logger.info("Notification queue stopped")

    async def pause(self) -> None:
        """暂停队列"""
        if self._status != QueueStatus.RUNNING:
            return

        self._status = QueueStatus.PAUSED
        logger.info("Notification queue paused")

    async def resume(self) -> None:
        """恢复队列"""
        if self._status != QueueStatus.PAUSED:
            return

        self._status = QueueStatus.RUNNING
        logger.info("Notification queue resumed")

    async def clear(self) -> None:
        """清空队列"""
        # 清空主队列
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except asyncio.QueueEmpty:
                break

        # 清空重试队列
        self._retry_queue.clear()

        logger.info("Notification queue cleared")

    def get_queue_info(self) -> Dict[str, Any]:
        """获取队列信息

        Returns:
            队列信息字典
        """
        return {
            "status": self._status.value,
            "queue_size": self._queue.qsize(),
            "retry_queue_size": len(self._retry_queue),
            "processing_count": len(self._processing_queue),
            "workers": self.worker_count,
            "stats": self._stats
        }

    def get_pending_notifications(self) -> List[Dict[str, Any]]:
        """获取待处理的通知列表

        Returns:
            通知信息列表
        """
        pending = []

        # 从队列中获取
        temp_list = list(self._queue.queue)
        for priority, item in temp_list:
            pending.append({
                "id": item.id,
                "event_type": item.event_type,
                "priority": item.priority.value,
                "created_at": item.created_at,
                "retry_count": item.retry_count,
                "location": "queue"
            })

        # 从重试队列中获取
        for item in self._retry_queue:
            pending.append({
                "id": item.id,
                "event_type": item.event_type,
                "priority": item.priority.value,
                "created_at": item.created_at,
                "retry_count": item.retry_count,
                "last_error": item.last_error,
                "location": "retry_queue"
            })

        # 从处理中字典获取
        for item in self._processing_queue.values():
            pending.append({
                "id": item.id,
                "event_type": item.event_type,
                "priority": item.priority.value,
                "created_at": item.created_at,
                "retry_count": item.retry_count,
                "location": "processing"
            })

        return pending


# 全局通知队列实例
_notification_queue: Optional[NotificationQueue] = None


def get_notification_queue(
    router: Optional[NotificationRouter] = None,
    auto_start: bool = True
) -> NotificationQueue:
    """获取全局通知队列实例

    Args:
        router: 通知路由器实例
        auto_start: 是否自动启动队列

    Returns:
        NotificationQueue 实例
    """
    global _notification_queue
    if _notification_queue is None:
        _notification_queue = NotificationQueue(router)
        if auto_start:
            asyncio.create_task(_notification_queue.start())
    return _notification_queue


async def stop_notification_queue() -> None:
    """停止全局通知队列"""
    global _notification_queue
    if _notification_queue is not None:
        await _notification_queue.stop()
        _notification_queue = None
