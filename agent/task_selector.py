"""Task Selector - 任务选择模块

从功能列表选取下一任务，支持任务依赖关系管理。
"""

from typing import Any, cast

from .state_manager import StateManager

# 默认优先级 - 当任务未指定优先级时使用
DEFAULT_PRIORITY = 1000


class CircularDependencyError(Exception):
    """Raised when circular dependencies are detected in task list"""
    pass


class TaskSelector:
    """任务选择器"""

    # 任务特征类型定义
    FeatureType = dict[str, Any]
    FeatureListType = dict[str, Any]

    def __init__(self, state_manager: StateManager | None = None) -> None:
        self.state_manager = state_manager or StateManager()

    def select_next_task(self) -> dict[str, Any] | None:
        """选择下一个要执行的任务

        依赖规则：
        1. 优先选择依赖已满足的任务
        2. 按 priority 字段升序排列（数字越小优先级越高）
        3. 返回优先级最高且依赖已满足的任务
        4. 如果有依赖未满足的任务，跳过这些任务

        Returns:
            下一个要执行的任务，如果所有任务都完成或被阻塞则返回None
        """
        data: dict[str, Any] = self.state_manager.load_feature_list()
        features: list[dict[str, Any]] = cast(list[dict[str, Any]], data.get("features", []))

        # 过滤出 pending 且未通过的任务
        pending_tasks: list[dict[str, Any]] = [
            f for f in features
            if f.get("status") == "pending" and not f.get("passes", False)
        ]

        if not pending_tasks:
            return None

        # 过滤出依赖已满足的任务
        ready_tasks = [
            f for f in pending_tasks
            if self.is_dependency_satisfied(f.get("id", ""))
        ]

        if not ready_tasks:
            # 所有pending任务都有未满足的依赖
            return None

        # 按优先级排序
        ready_tasks.sort(key=lambda x: x.get("priority", DEFAULT_PRIORITY))

        return ready_tasks[0]

    def get_pending_count(self) -> int:
        """获取待完成任务数量"""
        data: dict[str, Any] = self.state_manager.load_feature_list()
        features: list[dict[str, Any]] = cast(list[dict[str, Any]], data.get("features", []))
        return sum(
            1 for f in features
            if f.get("status") == "pending" and not f.get("passes", False)
        )

    def get_completed_count(self) -> int:
        """Get completed task count.

        A task is considered completed if status is 'completed' OR passes is True.
        """
        data: dict[str, Any] = self.state_manager.load_feature_list()
        features: list[dict[str, Any]] = cast(list[dict[str, Any]], data.get("features", []))
        return sum(
            1 for f in features
            if f.get("status") == "completed" or f.get("passes") is True
        )

    def get_total_count(self) -> int:
        """获取总任务数量"""
        data: dict[str, Any] = self.state_manager.load_feature_list()
        features: list[dict[str, Any]] = cast(list[dict[str, Any]], data.get("features", []))
        return len(features)

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

    def get_dependencies(self, task_id: str) -> list[str]:
        """获取任务的依赖列表

        Args:
            task_id: 任务ID

        Returns:
            依赖的任务ID列表
        """
        feature = self.state_manager.get_feature(task_id)
        if feature is None:
            return []
        return feature.get("depends_on", [])

    def get_task_by_id(self, task_id: str) -> dict[str, Any] | None:
        """根据ID获取任务"""
        return self.state_manager.get_feature(task_id)

    def is_dependency_satisfied(self, task_id: str) -> bool:
        """检查任务的依赖是否已满足

        依赖满足条件：
        1. 所有依赖任务都已完成 (status=completed 或 passes=True)

        Args:
            task_id: 任务ID

        Returns:
            True 如果所有依赖都已满足
        """
        deps = self.get_dependencies(task_id)
        if not deps:
            return True

        for dep_id in deps:
            dep_task = self.get_task_by_id(dep_id)
            if dep_task is None:
                # 依赖的任务不存在，视为不满足
                return False
            # 检查依赖任务是否完成
            if not (dep_task.get("status") == "completed" or dep_task.get("passes") is True):
                return False
        return True

    def get_blocked_tasks(self) -> list[dict[str, Any]]:
        """获取被阻塞的任务列表

        被阻塞的任务：有未完成的依赖任务

        Returns:
            被阻塞的任务列表
        """
        data: dict[str, Any] = self.state_manager.load_feature_list()
        features: list[dict[str, Any]] = cast(list[dict[str, Any]], data.get("features", []))

        blocked = []
        for f in features:
            task_id = f.get("id", "")
            status = f.get("status", "pending")
            passes = f.get("passes", False)

            # 只检查未完成的任务
            if status == "completed" or passes is True:
                continue

            # 检查依赖是否满足
            if not self.is_dependency_satisfied(task_id):
                blocked.append(f)

        return blocked

    def _topological_sort(self) -> list[dict[str, Any]]:
        """执行拓扑排序返回所有任务的执行顺序

        使用Kahn算法实现拓扑排序

        Returns:
            按依赖顺序排列的任务列表

        Raises:
            CircularDependencyError: 当检测到循环依赖时
        """
        data: dict[str, Any] = self.state_manager.load_feature_list()
        features: list[dict[str, Any]] = cast(list[dict[str, Any]], data.get("features", []))

        # 构建依赖图
        task_map: dict[str, dict[str, Any]] = {}
        in_degree: dict[str, int] = {}
        depends_on: dict[str, list[str]] = {}

        for f in features:
            task_id = f.get("id", "")
            task_map[task_id] = f
            in_degree[task_id] = 0
            deps = f.get("depends_on", [])
            if not isinstance(deps, list):
                deps = []
            depends_on[task_id] = deps

        # 计算入度
        for task_id, deps in depends_on.items():
            for dep_id in deps:
                if dep_id in in_degree:
                    # 这里不增加入度，因为我们按依赖关系反向构建
                    pass

        # 构建正向图并计算入度
        graph: dict[str, list[str]] = {tid: [] for tid in task_map}
        in_degree = {tid: 0 for tid in task_map}

        for task_id, deps in depends_on.items():
            in_degree[task_id] = len(deps)
            for dep_id in deps:
                if dep_id in graph:
                    graph[dep_id].append(task_id)

        # Kahn算法
        queue = [tid for tid, degree in in_degree.items() if degree == 0]
        result = []

        while queue:
            # 按优先级排序
            queue.sort(key=lambda tid: task_map[tid].get("priority", DEFAULT_PRIORITY))
            current = queue.pop(0)
            result.append(task_map[current])

            for neighbor in graph[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # 检查是否有循环依赖
        if len(result) != len(features):
            # 找出循环依赖的任务
            remaining = set(task_map.keys()) - set(r.get("id") for r in result)
            cycle_tasks = [task_map[tid].get("name", tid) for tid in remaining]
            raise CircularDependencyError(
                f"Circular dependency detected involving: {', '.join(cycle_tasks)}"
            )

        return result

    def get_resolved_order(self) -> list[dict[str, Any]]:
        """获取解析后的任务执行顺序（考虑依赖关系）

        Returns:
            按依赖顺序排列的任务列表
        """
        try:
            return self._topological_sort()
        except CircularDependencyError:
            # 如果有循环依赖，返回空列表
            return []

    def validate_dependencies(self) -> tuple[bool, str]:
        """验证所有任务的依赖关系

        Returns:
            (is_valid, error_message) - 如果有效返回(True, "")
        """
        try:
            self._topological_sort()
            return True, ""
        except CircularDependencyError as e:
            return False, str(e)
