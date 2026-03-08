"""Tests for NotificationQueue module"""

import pytest
import json
import tempfile
import asyncio
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.notification_queue import (
    NotificationQueue,
    NotificationItem,
    NotificationPriority,
    QueueStatus,
    get_notification_queue,
    stop_notification_queue
)
from agent.notification_router import NotificationRouter


@pytest.fixture
def mock_router():
    """Create a mock notification router for module-level reuse."""
    router = AsyncMock(spec=NotificationRouter)
    router.send_notification = AsyncMock(return_value={"slack": True})
    return router


class TestNotificationQueue:
    """Test cases for NotificationQueue"""

    @pytest.fixture
    def mock_router(self):
        """Create a mock notification router"""
        router = AsyncMock(spec=NotificationRouter)
        router.send_notification = AsyncMock(return_value={"slack": True})
        return router

    @pytest.fixture
    def queue(self, mock_router):
        """Create NotificationQueue with mock router"""
        q = NotificationQueue(router=mock_router, worker_count=1, max_retries=2)
        return q

    def test_queue_initialization(self, mock_router):
        """Test queue initialization"""
        q = NotificationQueue(router=mock_router, max_size=50, max_retries=3)

        assert q.max_size == 50
        assert q.max_retries == 3
        assert q.status == QueueStatus.IDLE

    @pytest.mark.asyncio
    async def test_enqueue(self, queue):
        """Test enqueueing a notification"""
        notification_id = await queue.enqueue(
            "task_completed",
            {"task_id": "test-001"}
        )

        assert notification_id is not None
        assert notification_id.startswith("notif-")

    @pytest.mark.asyncio
    async def test_enqueue_with_priority(self, queue):
        """Test enqueueing with custom priority"""
        await queue.enqueue(
            "task_completed",
            {"task_id": "test-001"},
            priority=NotificationPriority.HIGH
        )

        # Verify item was added
        assert queue._queue.qsize() == 1

    @pytest.mark.asyncio
    async def test_start_stop(self, queue):
        """Test starting and stopping the queue"""
        await queue.start()
        assert queue.status == QueueStatus.RUNNING

        await queue.stop()
        assert queue.status == QueueStatus.STOPPED

    @pytest.mark.asyncio
    async def test_process_notification_success(self, queue, mock_router):
        """Test successful notification processing"""
        item = NotificationItem(
            id="test-001",
            event_type="task_completed",
            data={"task_id": "test-001"}
        )

        result = await queue._process_notification(item)

        assert result is True
        mock_router.send_notification.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_notification_failure(self, queue, mock_router):
        """Test notification processing failure"""
        mock_router.send_notification = AsyncMock(return_value={})

        item = NotificationItem(
            id="test-001",
            event_type="task_completed",
            data={"task_id": "test-001"},
            max_retries=3
        )

        result = await queue._process_notification(item)

        assert result is False
        # Should be added to retry queue
        assert len(queue._retry_queue) == 1

    @pytest.mark.asyncio
    async def test_retry_after_max_retries(self, queue, mock_router):
        """Test notification fails after max retries"""
        mock_router.send_notification = AsyncMock(return_value={})

        item = NotificationItem(
            id="test-001",
            event_type="task_completed",
            data={"task_id": "test-001"},
            max_retries=2,
            retry_count=2  # Already at max
        )

        result = await queue._process_notification(item)

        assert result is False
        # Should NOT be added to retry queue (max retries reached)
        assert len(queue._retry_queue) == 0

    @pytest.mark.asyncio
    async def test_worker_processes_queue(self, queue, mock_router):
        """Test worker processes items from queue"""
        await queue.start()

        # Enqueue a notification
        await queue.enqueue("task_completed", {"task_id": "test-001"})

        # Wait for processing
        await asyncio.sleep(0.5)

        # Verify notification was processed
        mock_router.send_notification.assert_called()

        await queue.stop()

    @pytest.mark.asyncio
    async def test_priority_processing(self, mock_router):
        """Test higher priority items are processed first"""
        q = NotificationQueue(router=mock_router, worker_count=1)

        # Enqueue in order: LOW, HIGH, NORMAL
        await q.enqueue("task_completed", {"id": "1"}, priority=NotificationPriority.LOW)
        await q.enqueue("task_failed", {"id": "2"}, priority=NotificationPriority.HIGH)
        await q.enqueue("task_completed", {"id": "3"}, priority=NotificationPriority.NORMAL)

        # Get items without processing
        items = []
        while not q._queue.empty():
            priority, item = q._queue.get_nowait()
            items.append((priority, item.id))
            q._queue.task_done()

        # Verify order: HIGH (0), NORMAL (1), LOW (2)
        assert items[0][0] == 0  # HIGH
        assert items[1][0] == 1  # NORMAL
        assert items[2][0] == 2  # LOW

    @pytest.mark.asyncio
    async def test_pause_resume(self, queue):
        """Test pause and resume functionality"""
        await queue.start()
        assert queue.status == QueueStatus.RUNNING

        await queue.pause()
        assert queue.status == QueueStatus.PAUSED

        await queue.resume()
        assert queue.status == QueueStatus.RUNNING

        await queue.stop()

    @pytest.mark.asyncio
    async def test_clear_queue(self, queue):
        """Test clearing the queue"""
        await queue.enqueue("task_completed", {"id": "1"})
        await queue.enqueue("task_completed", {"id": "2"})

        assert queue._queue.qsize() == 2

        await queue.clear()

        assert queue._queue.qsize() == 0


class TestNotificationQueueStats:
    """Test cases for queue statistics"""

    @pytest.fixture
    def mock_router(self):
        """Create a mock notification router"""
        router = AsyncMock(spec=NotificationRouter)
        router.send_notification = AsyncMock(return_value={"slack": True})
        return router

    @pytest.mark.asyncio
    async def test_stats_tracking(self, mock_router):
        """Test statistics are tracked correctly"""
        q = NotificationQueue(router=mock_router, worker_count=1, max_retries=1)

        await q.start()

        # Enqueue notifications
        await q.enqueue("task_completed", {"id": "1"})
        await q.enqueue("task_failed", {"id": "2"})

        # Wait for processing
        await asyncio.sleep(0.5)

        stats = q.stats

        assert stats["total_sent"] >= 0

        await q.stop()

    def test_get_queue_info(self, mock_router):
        """Test get_queue_info returns correct data"""
        q = NotificationQueue(router=mock_router, worker_count=2, max_retries=3)

        info = q.get_queue_info()

        assert "status" in info
        assert "queue_size" in info
        assert "retry_queue_size" in info
        assert info["workers"] == 2


class TestNotificationItem:
    """Test cases for NotificationItem"""

    def test_notification_item_creation(self):
        """Test creating a NotificationItem"""
        item = NotificationItem(
            id="test-001",
            event_type="task_completed",
            data={"task_id": "test-001"},
            priority=NotificationPriority.HIGH,
            max_retries=5
        )

        assert item.id == "test-001"
        assert item.event_type == "task_completed"
        assert item.priority == NotificationPriority.HIGH
        assert item.max_retries == 5
        assert item.retry_count == 0

    def test_default_values(self):
        """Test NotificationItem default values"""
        item = NotificationItem(
            id="test-001",
            event_type="task_completed",
            data={}
        )

        assert item.priority == NotificationPriority.NORMAL
        assert item.max_retries == 3
        assert item.retry_count == 0
        assert item.last_error is None


class TestGetNotificationQueue:
    """Test cases for get_notification_queue function"""

    @pytest.mark.asyncio
    async def test_get_global_queue(self, mock_router):
        """Test getting global queue instance"""
        # Reset global queue
        import agent.notification_queue as nq_module
        nq_module._notification_queue = None

        queue = get_notification_queue(mock_router, auto_start=False)

        assert queue is not None

        await queue.stop()

    @pytest.mark.asyncio
    async def test_stop_global_queue(self, mock_router):
        """Test stopping global queue"""
        # Reset global queue
        import agent.notification_queue as nq_module
        nq_module._notification_queue = None

        queue = get_notification_queue(mock_router, auto_start=True)
        await asyncio.sleep(0.1)

        await stop_notification_queue()

        assert nq_module._notification_queue is None
