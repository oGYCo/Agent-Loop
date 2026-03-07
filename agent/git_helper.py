"""Git Helper - Git操作模块

保持环境清洁，确保下session可恢复
"""

import subprocess
import os
from pathlib import Path
from typing import Optional


class GitHelper:
    """Git操作辅助类"""

    def __init__(self, project_root: Optional[str] = None) -> None:
        self.project_root = Path(project_root) if project_root else Path(__file__).parent.parent
        self.git_dir = self.project_root / ".git"

    def is_git_repo(self) -> bool:
        """检查是否为git仓库"""
        return self.git_dir.exists()

    def init_repo(self) -> bool:
        """初始化git仓库"""
        if self.is_git_repo():
            return True

        try:
            subprocess.run(
                ["git", "init"],
                cwd=self.project_root,
                check=True,
                capture_output=True
            )
            # 创建初始提交（如果有待提交的文件）
            result = subprocess.run(
                ["git", "add", "-A"],
                cwd=self.project_root,
                check=True,
                capture_output=True
            )
            # 检查是否有文件需要提交
            status_result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )
            if status_result.stdout.strip():
                subprocess.run(
                    ["git", "commit", "-m", "Initial commit"],
                    cwd=self.project_root,
                    check=True,
                    capture_output=True,
                    env={**os.environ, "GIT_AUTHOR_NAME": "Agent", "GIT_AUTHOR_EMAIL": "agent@local"}
                )
            return True
        except subprocess.CalledProcessError as e:
            print(f"Failed to init git repo: {e}")
            return False

    def get_status(self) -> str:
        """获取git状态"""
        if not self.is_git_repo():
            return "Not a git repository"

        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )
            return result.stdout.strip()
        except Exception as e:
            return f"Error getting status: {e}"

    def has_changes(self) -> bool:
        """检查是否有未提交的更改"""
        status = self.get_status()
        return bool(status)

    def stage_and_commit(self, message: str) -> bool:
        """暂存并提交更改"""
        if not self.is_git_repo():
            print("Not a git repository, initializing...")
            if not self.init_repo():
                return False

        try:
            # 添加所有更改
            subprocess.run(
                ["git", "add", "-A"],
                cwd=self.project_root,
                check=True,
                capture_output=True
            )

            # 检查是否有需要提交的内容
            result = subprocess.run(
                ["git", "diff", "--cached", "--quiet"],
                cwd=self.project_root
            )
            if result.returncode == 0:
                return True  # 没有要提交的内容

            # 提交
            subprocess.run(
                ["git", "commit", "-m", message],
                cwd=self.project_root,
                check=True,
                capture_output=True,
                env={**os.environ, "GIT_AUTHOR_NAME": "Agent", "GIT_AUTHOR_EMAIL": "agent@local"}
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"Failed to commit: {e}")
            return False

    def get_recent_commits(self, count: int = 5) -> list[str]:
        """获取最近的提交记录"""
        if not self.is_git_repo():
            return []

        try:
            result = subprocess.run(
                ["git", "log", f"-{count}", "--oneline"],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )
            return result.stdout.strip().split("\n")
        except Exception:
            return []

    def get_current_branch(self) -> str:
        """获取当前分支"""
        if not self.is_git_repo():
            return "main"

        try:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )
            return result.stdout.strip() or "main"
        except Exception:
            return "main"

    def create_branch(self, branch_name: str) -> bool:
        """创建新分支"""
        if not self.is_git_repo():
            return False

        try:
            subprocess.run(
                ["git", "checkout", "-b", branch_name],
                cwd=self.project_root,
                check=True,
                capture_output=True
            )
            return True
        except subprocess.CalledProcessError:
            return False

    def checkout_branch(self, branch_name: str) -> bool:
        """切换分支"""
        if not self.is_git_repo():
            return False

        try:
            subprocess.run(
                ["git", "checkout", branch_name],
                cwd=self.project_root,
                check=True,
                capture_output=True
            )
            return True
        except subprocess.CalledProcessError:
            return False

    def get_diff(self, target: Optional[str] = None) -> str:
        """获取差异"""
        if not self.is_git_repo():
            return ""

        try:
            cmd = ["git", "diff"]
            if target:
                cmd.append(target)

            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True
            )
            return result.stdout
        except Exception:
            return ""
