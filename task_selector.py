"""Task Selector - 任务选择模块

从功能列表选取下一任务
"""

from typing import Optional, Any

from state_manager import StateManager


class TaskSelector:
    """任务选择器"""

    def __init__(self, state_manager: Optional[StateManager] = None) -> None:
        self.state_manager = state_manager or StateManager()

    def select_next_task(self) -> Optional[dict[str, Any]]:
        """选择下一个要执行的任务

        优先级规则：
        1. 首先选择状态为 pending 且 passes 为 false 的任务
        2. 按 priority 字段升序排列（数字越小优先级越高）
        3. 返回优先级最高的任务
        """
        data = self.state_manager.load_feature_list()
        features = data.get("features", [])

        # 过滤出 pending 且未通过的任务
        pending_tasks = [
            f for f in features
            if f.get("status") == "pending" and not f.get("passes", False)
        ]

        if not pending_tasks:
            return None

        # 按优先级排序
        pending_tasks.sort(key=lambda x: x.get("priority", 999))

        return pending_tasks[0]

    def get_pending_count(self) -> int:
        """获取待完成任务数量"""
        data = self.state_manager.load_feature_list()
        features = data.get("features", [])
        return sum(
            1 for f in features
            if f.get("status") == "pending" and not f.get("passes", False)
        )

    def get_completed_count(self) -> int:
        """获取已完成任务数量"""
        data = self.state_manager.load_feature_list()
        features = data.get("features", [])
        return sum(
            1 for f in features
            if f.get("status") == "completed" or f.get("passes", False)
        )

    def get_total_count(self) -> int:
        """获取总任务数量"""
        data = self.state_manager.load_feature_list()
        return len(data.get("features", []))

    def mark_task_completed(self, task_id: str) -> bool:
        """标记任务为完成"""
        return self.state_manager.update_feature(
            task_id,
            {"status": "completed", "passes": True}
        )

    def mark_task_failed(self, task_id: str) -> bool:
        """标记任务为失败"""
        return self.state_manager.update_feature(
            task_id,
            {"status": "failed"}
        )
