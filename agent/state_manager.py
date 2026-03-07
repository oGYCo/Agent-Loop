"""State Manager - 状态管理模块

负责读写 feature_list.json 和 progress.txt
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, cast


class StateManager:
    """状态管理器"""

    def __init__(self, agent_dir: Optional[str] = None) -> None:
        if agent_dir is None:
            # __file__ is agent/state_manager.py, go up two levels to project root
            agent_dir = str(Path(__file__).parent.parent / ".agent")
        self.agent_dir: Path = Path(agent_dir)
        self.feature_list_path = self.agent_dir / "feature_list.json"
        self.progress_path = self.agent_dir / "progress.txt"
        self.state_path = self.agent_dir / "state.json"
        self.session_history_path = self.agent_dir / "session_history.json"
        self.config_path = self.agent_dir / "config.json"

    # ========== Feature List 操作 ==========

    def load_feature_list(self) -> dict[str, Any]:
        """加载功能列表"""
        if not self.feature_list_path.exists():
            return {"features": []}

        with open(self.feature_list_path, "r", encoding="utf-8") as f:
            return cast(dict[str, Any], json.load(f))

    def save_feature_list(self, data: dict[str, Any]) -> None:
        """保存功能列表"""
        with open(self.feature_list_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_feature(self, feature_id: str) -> Optional[dict[str, Any]]:
        """获取指定功能"""
        data = self.load_feature_list()
        for feature in data.get("features", []):
            if feature.get("id") == feature_id:
                return cast(dict[str, Any], feature)
        return None

    def update_feature(self, feature_id: str, updates: dict[str, Any]) -> bool:
        """更新功能状态（仅允许修改 passes 字段）"""
        data = self.load_feature_list()
        updated = False

        for feature in data.get("features", []):
            if feature.get("id") == feature_id:
                # 只允许修改 passes 字段
                if "passes" in updates:
                    feature["passes"] = updates["passes"]
                if "status" in updates:
                    feature["status"] = updates["status"]
                feature["updated_at"] = datetime.now().strftime("%Y-%m-%d")
                updated = True

        if updated:
            self.save_feature_list(data)
        return updated

    def add_feature(self, feature: dict[str, Any]) -> None:
        """添加新功能"""
        data = self.load_feature_list()
        data["features"].append(feature)
        self.save_feature_list(data)

    # ========== Progress 操作 ==========

    def load_progress(self) -> str:
        """加载进度记录"""
        if not self.progress_path.exists():
            return ""
        with open(self.progress_path, "r", encoding="utf-8") as f:
            return f.read()

    def save_progress(self, content: str) -> None:
        """保存进度记录"""
        with open(self.progress_path, "w", encoding="utf-8") as f:
            f.write(content)

    def append_progress(self, entry: str) -> None:
        """追加进度记录"""
        with open(self.progress_path, "a", encoding="utf-8") as f:
            f.write(entry + "\n")

    def update_progress_summary(self, total: int, completed: int) -> None:
        """更新进度摘要"""
        data = self.load_feature_list()
        lines = []

        if self.progress_path.exists():
            with open(self.progress_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

        # 更新统计信息
        new_lines = []
        in_status = False
        for line in lines:
            if "Total Features:" in line:
                new_lines.append(f"Total Features: {total}\n")
                continue
            if "Completed:" in line:
                new_lines.append(f"Completed: {completed}\n")
                continue
            if "Pending:" in line:
                new_lines.append(f"Pending: {total - completed}\n")
                continue
            new_lines.append(line)

        self.save_progress("".join(new_lines))

    # ========== State 操作 ==========

    def load_state(self) -> dict[str, Any]:
        """加载当前状态"""
        if not self.state_path.exists():
            return {
                "current_session": {
                    "id": None,
                    "start_time": None,
                    "agent_type": "init"
                },
                "current_task": None,
                "error_count": 0,
                "last_error": None,
                "context_used": 0
            }

        with open(self.state_path, "r", encoding="utf-8") as f:
            return cast(dict[str, Any], json.load(f))

    def save_state(self, state: dict[str, Any]) -> None:
        """保存当前状态"""
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)

    def update_state(self, updates: dict[str, Any]) -> None:
        """更新状态"""
        state = self.load_state()
        state.update(updates)
        self.save_state(state)

    # ========== Session History 操作 ==========

    def load_session_history(self) -> dict[str, Any]:
        """加载会话历史"""
        if not self.session_history_path.exists():
            return {"sessions": [], "total_sessions": 0}

        with open(self.session_history_path, "r", encoding="utf-8") as f:
            return cast(dict[str, Any], json.load(f))

    def save_session_history(self, data: dict[str, Any]) -> None:
        """保存会话历史"""
        with open(self.session_history_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def add_session(self, session: dict[str, Any]) -> None:
        """添加会话记录"""
        data = self.load_session_history()
        data["sessions"].append(session)
        data["total_sessions"] = len(data["sessions"])
        self.save_session_history(data)

    # ========== Config 操作 ==========

    def load_config(self) -> dict[str, Any]:
        """加载配置"""
        if not self.config_path.exists():
            return {}

        with open(self.config_path, "r", encoding="utf-8") as f:
            return cast(dict[str, Any], json.load(f))

    def save_config(self, config: dict[str, Any]) -> None:
        """保存配置"""
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

    def get_config(self, key: str, default: Any = None) -> Any:
        """获取配置项"""
        config = self.load_config()
        return config.get(key, default)
