"""Human Intervention - 人工干预机制

当遇到特定情况时，暂停并通知人类
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

from state_manager import StateManager


class HumanIntervention:
    """人工干预处理器"""

    def __init__(self, state_manager: Optional[StateManager] = None) -> None:
        self.state_manager = state_manager or StateManager()
        self.config = self.state_manager.load_config()
        self.max_errors = self.config.get("max_errors_before_intervention", 3)

    def should_intervene(
        self,
        error_count: int,
        error_type: Optional[str] = None,
        task_id: Optional[str] = None
    ) -> bool:
        """判断是否需要人工干预

        触发条件：
        1. 错误次数超过阈值
        2. 遇到不可逆操作
        3. 遇到无法解决的错误
        """
        # 检查错误次数
        if error_count >= self.max_errors:
            return True

        # 检查特定错误类型
        irreversible_operations = [
            "delete",
            "drop",
            "remove",
            "destroy"
        ]

        if error_type and any(op in error_type.lower() for op in irreversible_operations):
            return True

        return False

    def request_intervention(
        self,
        reason: str,
        context: Optional[Dict[str, Any]] = None,
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """请求人工干预

        Returns:
            包含干预请求详情的字典
        """
        request = {
            "timestamp": datetime.now().isoformat(),
            "reason": reason,
            "context": context or {},
            "task_id": task_id,
            "status": "pending"
        }

        # 保存干预请求
        self._save_intervention_request(request)

        return request

    def _save_intervention_request(self, request: Dict[str, Any]) -> None:
        """保存干预请求到文件"""
        request_file = self.state_manager.agent_dir / "intervention_requests.json"

        requests = []
        if request_file.exists():
            with open(request_file, "r") as f:
                try:
                    requests = json.load(f)
                except json.JSONDecodeError:
                    requests = []

        requests.append(request)

        with open(request_file, "w") as f:
            json.dump(requests, f, indent=2)

    def check_and_notify(self, state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """检查状态并发送通知

        Returns:
            如果需要干预返回干预请求，否则返回 None
        """
        error_count = state.get("error_count", 0)
        last_error = state.get("last_error")

        if self.should_intervene(error_count, error_type=last_error):
            return self.request_intervention(
                reason=f"Error threshold reached: {error_count} errors",
                context={"last_error": last_error},
                task_id=state.get("current_task")
            )

        return None

    def wait_for_human(self, request: Dict[str, Any]) -> bool:
        """等待人类响应

        在实际实现中，这可能通过以下方式：
        1. 发送通知（邮件、Slack等）
        2. 创建交互式提示
        3. 写入待处理文件供人类检查

        Returns:
            人类是否批准继续
        """
        print("\n" + "=" * 60)
        print("Human Intervention Required")
        print("=" * 60)
        print(f"Reason: {request.get('reason')}")
        print(f"Timestamp: {request.get('timestamp')}")
        if request.get("context"):
            print(f"Context: {json.dumps(request['context'], indent=2)}")
        print("=" * 60)

        # 写入待处理文件
        pending_file = self.state_manager.agent_dir / "PENDING_INTERVENTION.txt"
        with open(pending_file, "w") as f:
            f.write(f"Intervention Required\n")
            f.write(f"Reason: {request.get('reason')}\n")
            f.write(f"Time: {request.get('timestamp')}\n")
            f.write(f"Task: {request.get('task_id')}\n")

        # 简单的命令行交互
        response = input("\nDo you want to continue? (yes/no/skip): ").strip().lower()

        if response == "yes":
            # 删除待处理文件
            if pending_file.exists():
                pending_file.unlink()
            return True
        elif response == "skip":
            # 跳过当前任务
            if pending_file.exists():
                pending_file.unlink()
            return False
        else:
            # 终止
            print("Agent stopped. Please resolve the issue and restart.")
            exit(1)

    def notify_completion(self, summary: Dict[str, Any]) -> None:  # type: ignore[no-untyped-def]
        """通知任务完成"""
        completion_file = self.state_manager.agent_dir / "session_summary.txt"

        with open(completion_file, "w") as f:
            f.write(f"Session Completed: {datetime.now().isoformat()}\n")
            f.write(f"Tasks completed: {summary.get('completed', 0)}\n")
            f.write(f"Errors encountered: {summary.get('errors', 0)}\n")
