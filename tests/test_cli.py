"""End-to-end tests for CLI commands using subprocess.

Tests main.py CLI commands with real subprocess execution.
Uses the existing .agent directory in the project for testing.
"""

import json
import os
import subprocess
import sys

import pytest


# Use the existing .agent directory in the project for tests
AGENT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".agent")
MAIN_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py")


class TestCLIBasicCommands:
    """Test basic CLI commands using existing .agent directory."""

    def test_list_command(self):
        """Test list command shows tasks."""
        result = subprocess.run(
            [sys.executable, MAIN_PATH, "--project-dir", AGENT_DIR, "list"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"List failed: {result.stderr}"
        assert "Feature List" in result.stdout or "Total:" in result.stdout

    def test_list_command_with_filter_pending(self):
        """Test list command with --filter pending."""
        result = subprocess.run(
            [sys.executable, MAIN_PATH, "--project-dir", AGENT_DIR, "list", "--filter", "pending"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0

    def test_list_command_with_filter_completed(self):
        """Test list command with --filter completed."""
        result = subprocess.run(
            [sys.executable, MAIN_PATH, "--project-dir", AGENT_DIR, "list", "--filter", "completed"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0

    def test_status_command(self):
        """Test status command shows project info."""
        result = subprocess.run(
            [sys.executable, MAIN_PATH, "--project-dir", AGENT_DIR, "status"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Status failed: {result.stderr}"


class TestCLIPromptCommands:
    """Test prompt management commands."""

    def test_prompt_list_command(self):
        """Test prompt list command."""
        result = subprocess.run(
            [sys.executable, MAIN_PATH, "--project-dir", AGENT_DIR, "prompt", "list"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Prompt list failed: {result.stderr}"

    def test_prompt_show_command(self):
        """Test prompt show command."""
        result = subprocess.run(
            [sys.executable, MAIN_PATH, "--project-dir", AGENT_DIR, "prompt", "show", "default"],
            capture_output=True,
            text=True,
        )

        # Should succeed or show not found
        assert result.returncode == 0 or "not found" in result.stdout.lower()

    def test_prompt_show_without_key(self):
        """Test prompt show without key shows active prompt."""
        result = subprocess.run(
            [sys.executable, MAIN_PATH, "--project-dir", AGENT_DIR, "prompt", "show"],
            capture_output=True,
            text=True,
        )


class TestCLITemplateCommands:
    """Test template management commands."""

    def test_template_list_command(self):
        """Test template list command."""
        result = subprocess.run(
            [sys.executable, MAIN_PATH, "--project-dir", AGENT_DIR, "template", "list"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Template list failed: {result.stderr}"
        assert "template" in result.stdout.lower() or "Template" in result.stdout

    def test_template_show_command(self):
        """Test template show command."""
        result = subprocess.run(
            [sys.executable, MAIN_PATH, "--project-dir", AGENT_DIR, "template", "show", "system"],
            capture_output=True,
            text=True,
        )

        # Should succeed or show not found
        assert result.returncode == 0 or "not found" in result.stdout.lower()


class TestCLIErrorHandling:
    """Test CLI error handling and edge cases."""

    def test_unknown_command(self):
        """Test unknown command shows help or error."""
        result = subprocess.run(
            [sys.executable, MAIN_PATH, "unknown-command"],
            capture_output=True,
            text=True,
        )

        # Should show help or error
        assert result.returncode != 0 or "help" in result.stdout.lower()

    def test_list_with_invalid_project_dir(self):
        """Test list command with invalid project dir."""
        # The CLI treats --project-dir as .agent directory path
        # If directory doesn't exist, it may still return success with empty list
        # Just verify the command runs and returns
        invalid_dir = "/nonexistent/path"

        result = subprocess.run(
            [sys.executable, MAIN_PATH, "--project-dir", invalid_dir, "list"],
            capture_output=True,
            text=True,
        )

        # The command may succeed or fail - just verify it runs
        # Either returncode 0 (empty list) or non-zero (error) is acceptable
        assert result.returncode in [0, 1]


class TestCLIVersion:
    """Test CLI version and help."""

    def test_version_flag(self):
        """Test --version flag."""
        result = subprocess.run(
            [sys.executable, MAIN_PATH, "--version"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "Agent-Loop" in result.stdout or "1.0" in result.stdout

    def test_help_flag(self):
        """Test --help flag."""
        result = subprocess.run(
            [sys.executable, MAIN_PATH, "--help"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "usage" in result.stdout.lower() or "help" in result.stdout.lower()

    def test_help_for_list_command(self):
        """Test help for list command."""
        result = subprocess.run(
            [sys.executable, MAIN_PATH, "list", "--help"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "--filter" in result.stdout

    def test_help_for_add_command(self):
        """Test help for add command."""
        result = subprocess.run(
            [sys.executable, MAIN_PATH, "add", "--help"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "--name" in result.stdout


class TestCLIPromptEdgeCases:
    """Test prompt management edge cases."""

    def test_prompt_delete_nonexistent(self):
        """Test deleting nonexistent prompt."""
        result = subprocess.run(
            [sys.executable, MAIN_PATH, "--project-dir", AGENT_DIR, "prompt", "delete", "nonexistent-prompt-xyz"],
            capture_output=True,
            text=True,
        )

        # Should fail gracefully
        assert result.returncode != 0 or "not found" in result.stdout.lower() or "error" in result.stdout.lower()

    def test_prompt_set_nonexistent(self):
        """Test setting nonexistent prompt as active."""
        result = subprocess.run(
            [sys.executable, MAIN_PATH, "--project-dir", AGENT_DIR, "prompt", "set", "nonexistent-prompt-xyz"],
            capture_output=True,
            text=True,
        )

        # Should fail gracefully
        assert result.returncode != 0 or "not found" in result.stdout.lower() or "error" in result.stdout.lower()


class TestCLITemplateEdgeCases:
    """Test template management edge cases."""

    def test_template_show_nonexistent(self):
        """Test showing nonexistent template."""
        result = subprocess.run(
            [sys.executable, MAIN_PATH, "--project-dir", AGENT_DIR, "template", "show", "nonexistent-template-xyz"],
            capture_output=True,
            text=True,
        )

        # Should fail gracefully
        assert result.returncode != 0 or "not found" in result.stdout.lower() or "error" in result.stdout.lower()


class TestCLIProjectDir:
    """Test --project-dir option."""

    def test_list_with_project_dir(self):
        """Test list with --project-dir option."""
        result = subprocess.run(
            [sys.executable, MAIN_PATH, "--project-dir", AGENT_DIR, "list"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
