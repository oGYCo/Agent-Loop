"""Test Runner - 测试执行模块

验证功能完成度
"""

import subprocess
import os
from pathlib import Path
from typing import Tuple, Optional, Dict, Any

from .state_manager import StateManager


class TestRunner:
    """测试运行器"""

    def __init__(self, state_manager: Optional[StateManager] = None) -> None:
        self.state_manager = state_manager or StateManager()
        self.config = self.state_manager.load_config()

    def run_tests(self, test_command: Optional[str] = None) -> Tuple[bool, str]:
        """运行测试并返回结果

        Returns:
            (success: bool, output: str)
        """
        test_command = test_command or self.config.get("test_command", "pytest")

        try:
            # 运行测试命令
            result = subprocess.run(
                test_command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )

            output = result.stdout + "\n" + result.stderr
            success = result.returncode == 0

            return success, output

        except subprocess.TimeoutExpired:
            return False, "Test execution timed out after 5 minutes"
        except Exception as e:
            return False, f"Test execution failed: {str(e)}"

    def run_test_for_feature(self, feature_id: str) -> Tuple[bool, str]:
        """为特定功能运行测试

        根据 feature_id 查找对应的测试
        """
        feature = self.state_manager.get_feature(feature_id)
        if not feature:
            return False, f"Feature {feature_id} not found"

        # 获取项目根目录
        project_root = Path(__file__).parent.parent

        # 构建测试命令
        test_pattern = self.config.get("test_pattern", "test_*.py")
        test_command = self.config.get("test_command", "pytest")

        # 运行测试
        success, output = self.run_tests(test_command)

        return success, output

    def verify_feature(self, feature: Dict[str, Any]) -> bool:
        """验证功能是否完成

        根据功能的验证规则进行验证
        """
        feature_id = feature.get("id")

        # 如果配置了自动验证命令
        verify_command = feature.get("verify_command")
        if verify_command:
            try:
                result = subprocess.run(
                    verify_command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                return result.returncode == 0
            except Exception:
                return False

        # 默认运行通用测试
        feature_id_str: str = feature_id if feature_id else ""
        success, _ = self.run_test_for_feature(feature_id_str)
        return success
