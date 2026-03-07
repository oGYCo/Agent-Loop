"""State Manager - 状态管理模块

负责读写 feature_list.json 和 progress.txt
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, cast


class ConfigValidationError(Exception):
    """配置验证错误"""

    def __init__(self, message: str = "Configuration validation failed") -> None:
        self.message = message
        super().__init__(self.message)


class FeatureListValidationError(Exception):
    """功能列表验证错误"""

    def __init__(self, message: str = "Feature list validation failed") -> None:
        self.message = message
        super().__init__(self.message)


class StateManager:
    """状态管理器"""

    def __init__(self, agent_dir: str | None = None) -> None:
        """Initialize StateManager.

        Args:
            agent_dir: Optional path to the .agent directory. Auto-detects if not provided.
        """
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
        """Load the feature list from feature_list.json.

        Returns:
            dict[str, Any]: The feature list data, or empty dict if file doesn't exist.
        """
        if not self.feature_list_path.exists():
            return {"features": []}

        with open(self.feature_list_path, "r", encoding="utf-8") as f:
            return cast(dict[str, Any], json.load(f))

    def save_feature_list(self, data: dict[str, Any]) -> None:
        """Save the feature list to feature_list.json.

        Args:
            data: The feature list data to save.
        """
        with open(self.feature_list_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_feature(self, feature_id: str) -> dict[str, Any] | None:
        """Get a specific feature by its ID.

        Args:
            feature_id: The ID of the feature to retrieve.

        Returns:
            dict[str, Any] | None: The feature dict if found, None otherwise.
        """
        data = self.load_feature_list()
        for feature in data.get("features", []):
            if feature.get("id") == feature_id:
                return cast(dict[str, Any], feature)
        return None

    def update_feature(self, feature_id: str, updates: dict[str, Any]) -> bool:
        """Update a feature's status. Only 'passes', 'status', and 'priority' fields can be modified.

        Args:
            feature_id: The ID of the feature to update.
            updates: Dict containing 'passes', 'status', and/or 'priority' fields to update.

        Returns:
            bool: True if feature was found and updated, False otherwise.
        """
        data = self.load_feature_list()
        updated = False

        for feature in data.get("features", []):
            if feature.get("id") == feature_id:
                # 只允许修改 passes, status, priority 字段
                if "passes" in updates:
                    feature["passes"] = updates["passes"]
                if "status" in updates:
                    feature["status"] = updates["status"]
                if "priority" in updates:
                    feature["priority"] = updates["priority"]
                feature["updated_at"] = datetime.now().strftime("%Y-%m-%d")
                updated = True

        if updated:
            self.save_feature_list(data)
        return updated

    def add_feature(self, feature: dict[str, Any]) -> None:
        """Add a new feature to the feature list.

        Args:
            feature: The feature dictionary to add.
        """
        data = self.load_feature_list()
        data["features"].append(feature)
        self.save_feature_list(data)

    # ========== Progress 操作 ==========

    def load_progress(self) -> str:
        """Load progress records from progress.txt.

        Returns:
            str: The progress content, or empty string if file doesn't exist.
        """
        if not self.progress_path.exists():
            return ""
        with open(self.progress_path, "r", encoding="utf-8") as f:
            return f.read()

    def save_progress(self, content: str) -> None:
        """Save progress records to progress.txt.

        Args:
            content: The progress content to save.
        """
        with open(self.progress_path, "w", encoding="utf-8") as f:
            f.write(content)

    def append_progress(self, entry: str) -> None:
        """Append a new entry to progress.txt.

        Args:
            entry: The progress entry to append.
        """
        with open(self.progress_path, "a", encoding="utf-8") as f:
            f.write(entry + "\n")

    def update_progress_summary(self, total: int, completed: int) -> None:
        """Update the progress summary in progress.txt.

        Args:
            total: Total number of features.
            completed: Number of completed features.
        """
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
        """Load the current state from state.json.

        Returns:
            dict[str, Any]: The current state data, or default state if file doesn't exist.
        """
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
        """Save the current state to state.json.

        Args:
            state: The state dictionary to save.
        """
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)

    def update_state(self, updates: dict[str, Any]) -> None:
        """Update specific fields in the current state.

        Args:
            updates: Dictionary of fields to update.
        """
        state = self.load_state()
        state.update(updates)
        self.save_state(state)

    # ========== Session History 操作 ==========

    def load_session_history(self) -> dict[str, Any]:
        """Load session history from session_history.json.

        Returns:
            dict[str, Any]: The session history data, or default empty history if file doesn't exist.
        """
        if not self.session_history_path.exists():
            return {"sessions": [], "total_sessions": 0}

        with open(self.session_history_path, "r", encoding="utf-8") as f:
            return cast(dict[str, Any], json.load(f))

    def save_session_history(self, data: dict[str, Any]) -> None:
        """Save session history to session_history.json.

        Args:
            data: The session history data to save.
        """
        with open(self.session_history_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def add_session(self, session: dict[str, Any]) -> None:
        """Add a new session record to session history.

        Args:
            session: The session dictionary to add.
        """
        data = self.load_session_history()
        data["sessions"].append(session)
        data["total_sessions"] = len(data["sessions"])
        self.save_session_history(data)

    # ========== Config 操作 ==========

    def load_config(self) -> dict[str, Any]:
        """Load configuration from config.json.

        Returns:
            dict[str, Any]: The config data, or empty dict if file doesn't exist.
        """
        if not self.config_path.exists():
            return {}

        with open(self.config_path, "r", encoding="utf-8") as f:
            return cast(dict[str, Any], json.load(f))

    def save_config(self, config: dict[str, Any]) -> None:
        """Save configuration to config.json.

        Args:
            config: The config dictionary to save.
        """
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

    def get_config(self, key: str, default: Any = None) -> Any:
        """Get a specific configuration value.

        Args:
            key: The configuration key to retrieve.
            default: Default value if key is not found.

        Returns:
            Any: The configuration value, or default if not found.
        """
        config = self.load_config()
        return config.get(key, default)

    # ========== Config Validation ==========

    def validate_config(self, config: dict[str, Any] | None = None) -> dict[str, Any]:
        """验证配置完整性

        Args:
            config: 要验证的配置字典，如果为None则从文件加载

        Returns:
            验证通过的配置字典

        Raises:
            ConfigValidationError: 配置验证失败
        """
        if config is None:
            config = self.load_config()

        # 定义必填字段及其类型
        required_fields = {
            "project_name": str,
            "project_type": str,
            "model": str,
            "session_type": str,
            "test_command": str,
            "test_pattern": str,
            "max_errors_before_intervention": int,
            "context_window_limit": int,
            "documentation_urls": dict,
        }

        errors: list[str] = []

        # 检查必填字段
        for field, expected_type in required_fields.items():
            if field not in config:
                errors.append(f"Missing required field: {field}")
            elif not isinstance(config[field], expected_type):
                actual_type = type(config[field]).__name__
                expected_type_name = expected_type.__name__
                errors.append(
                    f"Invalid type for '{field}': expected {expected_type_name}, got {actual_type}"
                )

        # 验证数值字段的取值范围（仅在类型正确时检查）
        if (
            "max_errors_before_intervention" in config
            and isinstance(config["max_errors_before_intervention"], int)
        ):
            if config["max_errors_before_intervention"] <= 0:
                errors.append(
                    "max_errors_before_intervention must be greater than 0"
                )

        if "context_window_limit" in config and isinstance(
            config["context_window_limit"], int
        ):
            if config["context_window_limit"] <= 0:
                errors.append("context_window_limit must be greater than 0")

        # documentation_urls 允许为空字典，但建议根据项目需求填写常用文档链接
        # 例如: {"main": "https://docs.example.com", "api": "https://api.example.com/docs"}

        if errors:
            raise ConfigValidationError("\n".join(errors))

        return config

    # ========== Feature List Validation ==========

    def validate_feature_list(
        self, data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """验证 feature_list.json 完整性

        Args:
            data: 要验证的 feature_list 数据，如果为 None 则从文件加载

        Returns:
            验证通过的特征列表字典

        Raises:
            FeatureListValidationError: 特征列表验证失败
        """
        if data is None:
            data = self.load_feature_list()

        errors: list[str] = []

        # 检查顶层结构
        if "features" not in data:
            errors.append("Missing required key: 'features'")
            raise FeatureListValidationError("\n".join(errors))

        if not isinstance(data["features"], list):
            errors.append("'features' must be a list")
            raise FeatureListValidationError("\n".join(errors))

        features = data["features"]

        if not features:
            errors.append("'features' list cannot be empty")

        # 检查重复的 ID
        seen_ids: set[str] = set()

        # 定义每个 feature 的必填字段
        required_fields = {
            "id": str,
            "name": str,
            "description": str,
            "priority": int,
            "status": str,
            "passes": bool,
            "created_at": str,
            "updated_at": str,
        }

        # 定义允许的 status 值
        valid_statuses = {"pending", "completed", "failed", "in_progress"}

        for idx, feature in enumerate(features):
            feature_id = feature.get("id", f"index_{idx}")

            # 检查必填字段
            for field, expected_type in required_fields.items():
                if field not in feature:
                    errors.append(
                        f"Feature '{feature_id}': Missing required field: '{field}'"
                    )
                elif not isinstance(feature[field], expected_type):
                    actual_type = type(feature[field]).__name__
                    expected_type_name = expected_type.__name__
                    errors.append(
                        f"Feature '{feature_id}': Invalid type for '{field}': "
                        f"expected {expected_type_name}, got {actual_type}"
                    )

            # 检查 priority 为正整数
            if "priority" in feature and isinstance(feature["priority"], int):
                if feature["priority"] <= 0:
                    errors.append(
                        f"Feature '{feature_id}': priority must be a positive integer"
                    )

            # 检查 status 为有效值
            if "status" in feature and isinstance(feature["status"], str):
                if feature["status"] not in valid_statuses:
                    errors.append(
                        f"Feature '{feature_id}': status must be one of "
                        f"{valid_statuses}, got '{feature['status']}'"
                    )

            # 检查 context_files 如果存在，必须是列表
            if "context_files" in feature:
                if not isinstance(feature["context_files"], list):
                    errors.append(
                        f"Feature '{feature_id}': context_files must be a list"
                    )

            # 检查 verify_command 如果存在，必须是字符串
            if "verify_command" in feature:
                if not isinstance(feature["verify_command"], str):
                    errors.append(
                        f"Feature '{feature_id}': verify_command must be a string"
                    )

            # 检查重复 ID
            if "id" in feature and isinstance(feature["id"], str):
                if feature["id"] in seen_ids:
                    errors.append(f"Duplicate feature ID: '{feature['id']}'")
                seen_ids.add(feature["id"])

        if errors:
            raise FeatureListValidationError("\n".join(errors))

        return data
