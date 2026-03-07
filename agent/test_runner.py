"""Test Runner - 测试执行模块

验证功能完成度
"""

import shlex
import subprocess
import logging
from pathlib import Path
from typing import Tuple, Dict, Any

from .state_manager import StateManager

logger = logging.getLogger(__name__)


class AgentTestRunner:
    """测试运行器"""

    def __init__(self, state_manager: StateManager | None = None) -> None:
        """Initialize TestRunner.

        Args:
            state_manager: Optional StateManager instance. Creates a new one if not provided.
        """
        self.state_manager = state_manager or StateManager()
        self.config = self.state_manager.load_config()

    def run_tests(self, test_command: str | None = None) -> Tuple[bool, str]:
        """Run tests and return the result.

        Args:
            test_command: Optional test command to run. Uses config default if not provided.

        Returns:
            Tuple[bool, str]: A tuple of (success, output) where success is True if tests passed.
        """
        test_command = test_command or self.config.get("test_command", "pytest")

        try:
            # 运行测试命令 - 使用 shlex.split 防止命令注入
            cmd_list = shlex.split(test_command)
            result = subprocess.run(
                cmd_list,
                shell=False,
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
            error_msg = str(e) if str(e) else f"Unexpected error: {type(e).__name__}"
            return False, f"Test execution failed: {error_msg}"

    def run_test_for_feature(self, feature_id: str) -> Tuple[bool, str]:
        """Run tests for a specific feature.

        Args:
            feature_id: The ID of the feature to run tests for.

        Returns:
            Tuple[bool, str]: A tuple of (success, output).
        """
        feature = self.state_manager.get_feature(feature_id)
        if not feature:
            return False, f"Feature {feature_id} not found"

        # 运行测试
        test_command = self.config.get("test_command", "pytest")
        success, output = self.run_tests(test_command)

        return success, output

    def verify_feature(self, feature: Dict[str, Any]) -> bool:
        """Verify if a feature is complete based on its verification rules.

        Args:
            feature: The feature dictionary containing verification configuration.

        Returns:
            bool: True if the feature passed verification, False otherwise.
        """
        feature_id = feature.get("id")

        # 如果配置了自动验证命令
        verify_command = feature.get("verify_command")
        if verify_command:
            try:
                # 使用 shlex.split 防止命令注入
                cmd_list = shlex.split(verify_command)
                result = subprocess.run(
                    cmd_list,
                    shell=False,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                return result.returncode == 0
            except Exception as e:
                logger.warning(f"Feature verification failed for {feature.get('id')}: {e}")
                return False

        # 没有 verify_command 时返回 False，不自动运行测试
        return False
