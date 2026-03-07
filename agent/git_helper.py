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
        """Initialize GitHelper.

        Args:
            project_root: Path to the project root directory. Defaults to parent of agent package.
        """
        self.project_root = Path(project_root) if project_root else Path(__file__).parent.parent
        self.git_dir = self.project_root / ".git"

    def is_git_repo(self) -> bool:
        """Check if the project is a git repository.

        Returns:
            bool: True if .git directory exists, False otherwise.
        """
        return self.git_dir.exists()

    def init_repo(self) -> bool:
        """Initialize a git repository in the project root.

        Returns:
            bool: True if initialization succeeded or repo already exists, False on failure.
        """
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
        """Get git status in porcelain format.

        Returns:
            str: Git status output in short format, or an error message if not a repo.
        """
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
            error_msg = str(e) if str(e) else f"Unexpected error: {type(e).__name__}"
            return f"Error getting status: {error_msg}"

    def has_changes(self) -> bool:
        """Check if there are uncommitted changes.

        Returns:
            bool: True if there are uncommitted changes, False otherwise.
        """
        status = self.get_status()
        return bool(status)

    def get_recent_commits(self, count: int = 5) -> list[str]:
        """Get recent commit messages.

        Args:
            count: Number of recent commits to retrieve (default: 5).

        Returns:
            list[str]: List of recent commit messages, or empty list if not a repo.
        """
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
        """Get the current branch name.

        Returns:
            str: Current branch name, or "main" if not a repo or on detached HEAD.
        """
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
        """Create and switch to a new branch.

        Args:
            branch_name: Name of the new branch to create.

        Returns:
            bool: True if branch creation succeeded, False otherwise.
        """
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
        """Switch to an existing branch.

        Args:
            branch_name: Name of the branch to checkout.

        Returns:
            bool: True if checkout succeeded, False otherwise.
        """
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
        """Get git diff output.

        Args:
            target: Optional target to diff against (e.g., branch name, commit hash).

        Returns:
            str: Git diff output, or empty string if not a repo.
        """
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
