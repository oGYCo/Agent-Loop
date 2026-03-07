"""Session Manager - 会话管理模块

处理上下文窗口，保持会话状态
"""

import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path

from .state_manager import StateManager


class SessionManager:
    """会话管理器"""

    def __init__(self, state_manager: Optional[StateManager] = None) -> None:
        self.state_manager = state_manager or StateManager()
        self.config = self.state_manager.load_config()
        self.context_limit = self.config.get("context_window_limit", 100000)

    def check_context_usage(self, messages: List[Dict[str, Any]]) -> tuple[bool, int]:
        """检查上下文使用情况

        Returns:
            (is_over_limit: bool, token_count: int)
        """
        # 简单估算：每4个字符约等于1个token
        total_chars = sum(len(json.dumps(m)) for m in messages)
        estimated_tokens = total_chars // 4

        return estimated_tokens > self.context_limit, estimated_tokens

    def summarize_old_messages(self, messages: List[Dict[str, Any]], keep_recent: int = 10) -> List[Dict[str, Any]]:
        """总结旧消息以节省上下文

        Args:
            messages: 消息列表
            keep_recent: 保留最近的消息数量

        Returns:
            精简后的消息列表
        """
        if len(messages) <= keep_recent:
            return messages

        # 保留最近的消息
        recent = messages[-keep_recent:]

        # 总结早期消息
        summary = {
            "role": "system",
            "content": f"Previous session summary: {len(messages) - keep_recent} messages were processed."
        }

        return [summary] + recent

    def should_resume_session(self, session_id: str) -> bool:
        """检查是否应该恢复之前的会话"""
        state = self.state_manager.load_state()
        current_session = state.get("current_session", {})

        if not current_session.get("id"):
            return False

        # 检查上一个会话是否未正常结束
        history = self.state_manager.load_session_history()
        for session in history.get("sessions", []):
            if session.get("id") == session_id:
                return session.get("status") != "completed"

        return False

    def get_session_summary(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话摘要"""
        history = self.state_manager.load_session_history()

        for session in history.get("sessions", []):
            if session.get("id") == session_id:
                return session

        return None

    def create_checkpoint(self, session_id: str, data: Dict[str, Any]) -> None:
        """创建会话检查点"""
        checkpoint_file = self.state_manager.agent_dir / f"checkpoint_{session_id}.json"

        checkpoint = {
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "data": data
        }

        with open(checkpoint_file, "w") as f:
            json.dump(checkpoint, f, indent=2)

    def load_checkpoint(self, session_id: str) -> Optional[Dict[str, Any]]:
        """加载会话检查点"""
        checkpoint_file = self.state_manager.agent_dir / f"checkpoint_{session_id}.json"

        if not checkpoint_file.exists():
            return None

        with open(checkpoint_file, "r") as f:
            return json.load(f)

    def cleanup_checkpoints(self, keep_latest: int = 3) -> None:
        """清理旧检查点"""
        agent_dir = self.state_manager.agent_dir

        # 获取所有检查点文件
        checkpoints = sorted(
            agent_dir.glob("checkpoint_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )

        # 删除旧的检查点
        for checkpoint in checkpoints[keep_latest:]:
            checkpoint.unlink()

    def manage_context(self, messages: List[Dict[str, Any]], force_summarize: bool = False) -> List[Dict[str, Any]]:
        """管理上下文

        Args:
            messages: 当前消息列表
            force_summarize: 是否强制总结

        Returns:
            管理后的消息列表
        """
        is_over_limit, token_count = self.check_context_usage(messages)

        if is_over_limit or force_summarize:
            return self.summarize_old_messages(messages)

        return messages

    def get_session_stats(self) -> Dict[str, Any]:
        """获取会话统计信息"""
        history = self.state_manager.load_session_history()
        state = self.state_manager.load_state()

        sessions = history.get("sessions", [])
        completed_sessions = [s for s in sessions if s.get("status") == "completed"]

        return {
            "total_sessions": len(sessions),
            "completed_sessions": len(completed_sessions),
            "current_session": state.get("current_session", {}),
            "context_limit": self.context_limit
        }
