"""Tests for GitHelper module"""

import pytest
import os
import tempfile
import subprocess
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from git_helper import GitHelper


class TestGitHelper:
    """Test cases for GitHelper"""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def git_helper(self, temp_dir):
        """Create GitHelper with temporary directory"""
        return GitHelper(project_root=temp_dir)

    @pytest.fixture
    def initialized_repo(self, temp_dir):
        """Create and initialize a git repository"""
        subprocess.run(["git", "init"], cwd=temp_dir, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=temp_dir,
            check=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=temp_dir,
            check=True
        )
        # Create initial commit
        test_file = Path(temp_dir) / "README.md"
        test_file.write_text("# Test Project")
        subprocess.run(["git", "add", "-A"], cwd=temp_dir, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=temp_dir,
            check=True
        )
        return temp_dir

    def test_is_git_repo_false(self, git_helper):
        """Test is_git_repo returns False for non-repo"""
        assert git_helper.is_git_repo() is False

    def test_is_git_repo_true(self, git_helper, initialized_repo):
        """Test is_git_repo returns True for git repo"""
        helper = GitHelper(project_root=initialized_repo)
        assert helper.is_git_repo() is True

    def test_init_repo(self, git_helper):
        """Test initializing a git repository"""
        result = git_helper.init_repo()
        assert result is True
        assert git_helper.is_git_repo() is True

    def test_init_repo_already_exists(self, git_helper, initialized_repo):
        """Test init_repo when repo already exists"""
        helper = GitHelper(project_root=initialized_repo)
        result = helper.init_repo()
        assert result is True

    def test_get_status_clean(self, git_helper, initialized_repo):
        """Test getting status of clean repo"""
        helper = GitHelper(project_root=initialized_repo)
        status = helper.get_status()
        assert status == ""

    def test_get_status_with_changes(self, git_helper, initialized_repo):
        """Test getting status with uncommitted changes"""
        helper = GitHelper(project_root=initialized_repo)
        # Create a new file
        test_file = Path(initialized_repo) / "new_file.txt"
        test_file.write_text("New content")

        status = helper.get_status()
        assert "new_file.txt" in status

    def test_has_changes_false(self, git_helper, initialized_repo):
        """Test has_changes returns False for clean repo"""
        helper = GitHelper(project_root=initialized_repo)
        assert helper.has_changes() is False

    def test_has_changes_true(self, git_helper, initialized_repo):
        """Test has_changes returns True with changes"""
        helper = GitHelper(project_root=initialized_repo)
        test_file = Path(initialized_repo) / "new_file.txt"
        test_file.write_text("New content")

        assert helper.has_changes() is True

    def test_stage_and_commit(self, git_helper, initialized_repo):
        """Test staging and committing changes"""
        helper = GitHelper(project_root=initialized_repo)
        test_file = Path(initialized_repo) / "new_file.txt"
        test_file.write_text("New content")

        result = helper.stage_and_commit("Add new file")
        assert result is True

        # Verify the commit was made
        status = helper.get_status()
        assert status == ""

    def test_stage_and_commit_no_changes(self, git_helper, initialized_repo):
        """Test stage_and_commit with no changes"""
        helper = GitHelper(project_root=initialized_repo)
        result = helper.stage_and_commit("Empty commit")
        assert result is True  # Should return True even with no changes

    def test_get_recent_commits(self, git_helper, initialized_repo):
        """Test getting recent commits"""
        helper = GitHelper(project_root=initialized_repo)

        # Make a commit
        test_file = Path(initialized_repo) / "new_file.txt"
        test_file.write_text("New content")
        helper.stage_and_commit("Add new file")

        commits = helper.get_recent_commits(3)
        assert len(commits) >= 1

    def test_get_recent_commits_not_repo(self, git_helper):
        """Test getting recent commits when not a repo"""
        commits = git_helper.get_recent_commits()
        assert commits == []

    def test_get_current_branch(self, git_helper, initialized_repo):
        """Test getting current branch"""
        helper = GitHelper(project_root=initialized_repo)
        branch = helper.get_current_branch()
        assert branch == "main"

    def test_get_current_branch_not_repo(self, git_helper):
        """Test getting current branch when not a repo"""
        branch = git_helper.get_current_branch()
        assert branch == "main"

    def test_create_branch(self, git_helper, initialized_repo):
        """Test creating a new branch"""
        helper = GitHelper(project_root=initialized_repo)
        result = helper.create_branch("feature-branch")
        assert result is True

        branch = helper.get_current_branch()
        assert branch == "feature-branch"

    def test_create_branch_not_repo(self, git_helper):
        """Test creating branch when not a repo"""
        result = git_helper.create_branch("feature-branch")
        assert result is False

    def test_checkout_branch(self, git_helper, initialized_repo):
        """Test checking out a branch"""
        helper = GitHelper(project_root=initialized_repo)

        # Create a branch first
        helper.create_branch("feature-branch")

        # Switch back to main
        result = helper.checkout_branch("main")
        assert result is True
        assert helper.get_current_branch() == "main"

    def test_checkout_branch_not_repo(self, git_helper):
        """Test checking out branch when not a repo"""
        result = git_helper.checkout_branch("main")
        assert result is False

    def test_get_diff(self, git_helper, initialized_repo):
        """Test getting diff"""
        helper = GitHelper(project_root=initialized_repo)

        # Make changes
        test_file = Path(initialized_repo) / "README.md"
        test_file.write_text("# Test Project\n\nModified content")

        diff = helper.get_diff()
        assert "Modified content" in diff

    def test_get_diff_not_repo(self, git_helper):
        """Test getting diff when not a repo"""
        diff = git_helper.get_diff()
        assert diff == ""

    def test_get_status_not_repo(self, git_helper):
        """Test getting status when not a repo"""
        status = git_helper.get_status()
        assert status == "Not a git repository"
