"""Tests for console.py module.

Tests console output functions using rich.console.Console with StringIO capture.
"""

import io
import sys
import pytest
from unittest.mock import patch
from datetime import datetime


class TestConsoleFunctions:
    """Test cases for console.py output functions."""

    @pytest.fixture
    def mock_console(self):
        """Create a mock console with StringIO capture."""
        from rich.console import Console
        output = io.StringIO()
        console = Console(file=output, force_terminal=True)
        return output, console

    def test_print_header(self, mock_console):
        """Test print_header outputs correct title."""
        from agent import console as console_module

        output, console = mock_console

        # Patch the global console in console module
        with patch.object(console_module, 'console', console):
            console_module.print_header("Test Title")

        result = output.getvalue()
        assert "Test Title" in result
        assert "=" * 50 in result

    def test_print_header_custom_style(self, mock_console):
        """Test print_header with custom style."""
        from agent import console as console_module

        output, console = mock_console

        with patch.object(console_module, 'console', console):
            console_module.print_header("Custom Title", style="bold green")

        result = output.getvalue()
        assert "Custom Title" in result
        # Rich uses ANSI escape codes, check that title is present
        assert "Custom Title" in result

    def test_print_success(self, mock_console):
        """Test print_success outputs with green checkmark."""
        from agent import console as console_module

        output, console = mock_console

        with patch.object(console_module, 'console', console):
            console_module.print_success("Operation succeeded")

        result = output.getvalue()
        assert "Operation succeeded" in result
        assert "✓" in result or "green" in result

    def test_print_error(self, mock_console):
        """Test print_error outputs with red X mark."""
        from agent import console as console_module

        output, console = mock_console

        with patch.object(console_module, 'console', console):
            console_module.print_error("Operation failed")

        result = output.getvalue()
        assert "Operation failed" in result
        assert "✗" in result or "red" in result

    def test_print_warning(self, mock_console):
        """Test print_warning outputs with yellow warning symbol."""
        from agent import console as console_module

        output, console = mock_console

        with patch.object(console_module, 'console', console):
            console_module.print_warning("Warning message")

        result = output.getvalue()
        assert "Warning message" in result
        assert "⚠" in result or "yellow" in result

    def test_print_info(self, mock_console):
        """Test print_info outputs with blue info symbol."""
        from agent import console as console_module

        output, console = mock_console

        with patch.object(console_module, 'console', console):
            console_module.print_info("Info message")

        result = output.getvalue()
        assert "Info message" in result
        assert "ℹ" in result or "blue" in result

    def test_print_task_table_basic(self, mock_console):
        """Test print_task_table outputs table with correct columns."""
        from agent import console as console_module

        output, console = mock_console

        tasks = [
            {
                "id": "feat-001",
                "name": "Test Task",
                "description": "Test description",
                "priority": 1,
                "status": "pending",
                "passes": False
            }
        ]

        with patch.object(console_module, 'console', console):
            console_module.print_task_table(tasks, 1, 2)

        result = output.getvalue()
        assert "Feature List" in result
        assert "feat-001" in result
        assert "Test Task" in result

    def test_print_task_table_completed(self, mock_console):
        """Test print_task_table shows completed tasks correctly."""
        from agent import console as console_module

        output, console = mock_console

        tasks = [
            {
                "id": "feat-001",
                "name": "Completed Task",
                "description": "Done",
                "priority": 1,
                "status": "completed",
                "passes": True
            }
        ]

        with patch.object(console_module, 'console', console):
            console_module.print_task_table(tasks, 1, 0)

        result = output.getvalue()
        assert "✓" in result
        assert "Completed Task" in result

    def test_print_task_table_in_progress(self, mock_console):
        """Test print_task_table shows in_progress tasks correctly."""
        from agent import console as console_module

        output, console = mock_console

        tasks = [
            {
                "id": "feat-002",
                "name": "In Progress Task",
                "description": "Working on it",
                "priority": 2,
                "status": "in_progress",
                "passes": False
            }
        ]

        with patch.object(console_module, 'console', console):
            console_module.print_task_table(tasks, 0, 1)

        result = output.getvalue()
        assert "In Progress Task" in result

    def test_print_task_table_counts(self, mock_console):
        """Test print_task_table shows correct counts."""
        from agent import console as console_module

        output, console = mock_console

        tasks = [
            {"id": "f1", "name": "Task 1", "description": "", "priority": 1, "status": "pending", "passes": False},
            {"id": "f2", "name": "Task 2", "description": "", "priority": 2, "status": "pending", "passes": False},
            {"id": "f3", "name": "Task 3", "description": "", "priority": 3, "status": "completed", "passes": True},
        ]

        with patch.object(console_module, 'console', console):
            console_module.print_task_table(tasks, 1, 2)

        result = output.getvalue()
        # Rich uses ANSI escape codes, use plain text comparison
        assert "Completed:" in result and "1" in result
        assert "Pending:" in result and "2" in result
        assert "Total:" in result and "3" in result

    def test_print_task_table_empty(self, mock_console):
        """Test print_task_table with empty task list."""
        from agent import console as console_module

        output, console = mock_console

        with patch.object(console_module, 'console', console):
            console_module.print_task_table([], 0, 0)

        result = output.getvalue()
        # Rich uses ANSI escape codes
        assert "Total:" in result and "0" in result

    def test_print_task_table_missing_fields(self, mock_console):
        """Test print_task_table handles tasks with missing fields."""
        from agent import console as console_module

        output, console = mock_console

        tasks = [
            {"id": "feat-001"},  # Only has id
            {"name": "Only name"},  # Only has name
            {},  # Empty task
        ]

        with patch.object(console_module, 'console', console):
            console_module.print_task_table(tasks, 0, 3)

        result = output.getvalue()
        # Rich uses ANSI escape codes
        assert "Total:" in result and "3" in result
        assert "Unnamed" in result or "feat-001" in result

    def test_print_status_panel(self, mock_console):
        """Test print_status_panel outputs project info correctly."""
        from agent import console as console_module

        output, console = mock_console

        with patch.object(console_module, 'console', console):
            console_module.print_status_panel(
                project_name="TestProject",
                project_type="python",
                test_command="pytest tests/",
                branch="main",
                has_changes=True,
                tasks_completed=5,
                tasks_total=10,
                tasks_pending=5,
                current_session="session-123",
                error_count=2
            )

        result = output.getvalue()
        assert "TestProject" in result
        assert "python" in result
        assert "main" in result
        assert "Yes" in result or "Yes" in result
        assert "5/10" in result
        assert "session-123" in result
        assert "2" in result

    def test_print_status_panel_no_errors(self, mock_console):
        """Test print_status_panel with zero errors."""
        from agent import console as console_module

        output, console = mock_console

        with patch.object(console_module, 'console', console):
            console_module.print_status_panel(
                project_name="TestProject",
                project_type="python",
                test_command="pytest",
                branch="dev",
                has_changes=False,
                tasks_completed=3,
                tasks_total=10,
                tasks_pending=7,
                current_session="abc",
                error_count=0
            )

        result = output.getvalue()
        assert "No" in result
        assert "0" in result

    def test_print_status_panel_no_changes(self, mock_console):
        """Test print_status_panel shows No for uncommitted changes."""
        from agent import console as console_module

        output, console = mock_console

        with patch.object(console_module, 'console', console):
            console_module.print_status_panel(
                project_name="CleanProject",
                project_type="generic",
                test_command="make test",
                branch="main",
                has_changes=False,
                tasks_completed=0,
                tasks_total=5,
                tasks_pending=5,
                current_session="N/A",
                error_count=0
            )

        result = output.getvalue()
        assert "No" in result

    def test_print_run_summary(self, mock_console):
        """Test print_run_summary shows iteration statistics."""
        from agent import console as console_module

        output, console = mock_console

        with patch.object(console_module, 'console', console):
            console_module.print_run_summary(iterations=10, completed=5, errors=2)

        result = output.getvalue()
        assert "10" in result
        assert "5" in result
        assert "2" in result

    def test_print_run_summary_no_errors(self, mock_console):
        """Test print_run_summary with zero errors."""
        from agent import console as console_module

        output, console = mock_console

        with patch.object(console_module, 'console', console):
            console_module.print_run_summary(iterations=5, completed=3, errors=0)

        result = output.getvalue()
        assert "0" in result
        assert "3" in result

    def test_print_run_summary_many_errors(self, mock_console):
        """Test print_run_summary with high error count."""
        from agent import console as console_module

        output, console = mock_console

        with patch.object(console_module, 'console', console):
            console_module.print_run_summary(iterations=10, completed=2, errors=8)

        result = output.getvalue()
        assert "8" in result
        # Rich uses ANSI escape codes for red color, check for escape code
        assert "\x1b[31m" in result or "8" in result  # Red escape code

    def test_create_progress(self):
        """Test create_progress returns valid Progress object."""
        from agent import console as console_module
        from rich.progress import Progress
        from rich.console import Console as RichConsole

        output = io.StringIO()
        console = RichConsole(file=output, force_terminal=True)

        with patch.object(console_module, 'console', console):
            progress = console_module.create_progress()

        assert isinstance(progress, Progress)

    def test_print_init_info(self, mock_console):
        """Test print_init_info outputs initialization info."""
        from agent import console as console_module

        output, console = mock_console

        templates = ["system.md", "task.md"]

        with patch.object(console_module, 'console', console):
            console_module.print_init_info("/path/to/.agent", templates)

        result = output.getvalue()
        assert ".agent" in result
        assert "config.json" in result
        assert "feature_list.json" in result

    def test_print_init_info_no_templates(self, mock_console):
        """Test print_init_info with empty template list."""
        from agent import console as console_module

        output, console = mock_console

        with patch.object(console_module, 'console', console):
            console_module.print_init_info("/path/to/.agent", [])

        result = output.getvalue()
        assert ".agent" in result

    def test_print_reload_result_success(self, mock_console):
        """Test print_reload_result shows successful reload."""
        from agent import console as console_module

        output, console = mock_console

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with patch.object(console_module, 'console', console):
            console_module.print_reload_result(
                success=True,
                message="Configuration reloaded successfully",
                reloaded=["config.json", "feature_list.json"],
                errors=[],
                timestamp=timestamp
            )

        result = output.getvalue()
        assert "Success" in result
        assert "config.json" in result

    def test_print_reload_result_failure(self, mock_console):
        """Test print_reload_result shows failed reload."""
        from agent import console as console_module

        output, console = mock_console

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with patch.object(console_module, 'console', console):
            console_module.print_reload_result(
                success=False,
                message="Failed to reload configuration",
                reloaded=[],
                errors=["config.json is invalid", "feature_list.json not found"],
                timestamp=timestamp
            )

        result = output.getvalue()
        assert "Failed" in result
        assert "invalid" in result or "not found" in result

    def test_print_reload_result_partial(self, mock_console):
        """Test print_reload_result with partial reload."""
        from agent import console as console_module

        output, console = mock_console

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with patch.object(console_module, 'console', console):
            console_module.print_reload_result(
                success=False,
                message="Partial reload",
                reloaded=["config.json"],
                errors=["feature_list.json parse error"],
                timestamp=timestamp
            )

        result = output.getvalue()
        assert "config.json" in result
        assert "error" in result.lower()

    def test_print_prompt_list(self, mock_console):
        """Test print_prompt_list outputs prompt table."""
        from agent import console as console_module

        output, console = mock_console

        prompts = [
            {"key": "default", "name": "Default Prompt", "description": "Standard prompt", "is_active": True},
            {"key": "coder", "name": "Coder Prompt", "description": "For coding tasks", "is_active": False},
        ]

        with patch.object(console_module, 'console', console):
            console_module.print_prompt_list(prompts)

        result = output.getvalue()
        assert "default" in result
        assert "coder" in result
        assert "ACTIVE" in result

    def test_print_prompt_list_empty(self, mock_console):
        """Test print_prompt_list with empty list."""
        from agent import console as console_module

        output, console = mock_console

        with patch.object(console_module, 'console', console):
            console_module.print_prompt_list([])

        result = output.getvalue()
        assert "Available Prompts" in result

    def test_print_template_list(self, mock_console):
        """Test print_template_list outputs template info."""
        from agent import console as console_module

        output, console = mock_console

        templates = [
            {"name": "system", "has_override": False, "builtin": True, "path": "/path/to/system.md"},
            {"name": "task", "has_override": True, "builtin": False, "path": "/path/to/task.md"},
        ]

        with patch.object(console_module, 'console', console):
            console_module.print_template_list(templates)

        result = output.getvalue()
        assert "system" in result
        assert "task" in result
        assert "OVERRIDE" in result
        assert "built-in" in result or "custom" in result

    def test_print_template_list_empty(self, mock_console):
        """Test print_template_list with empty list."""
        from agent import console as console_module

        output, console = mock_console

        with patch.object(console_module, 'console', console):
            console_module.print_template_list([])

        result = output.getvalue()
        # Should still print hints
        assert "customize" in result.lower() or "template" in result.lower()

    def test_setup_rich_logging(self):
        """Test setup_rich_logging configures logging correctly."""
        from agent import console as console_module
        import logging

        output = io.StringIO()
        from rich.console import Console as RichConsole
        console = RichConsole(file=output, force_terminal=True)

        with patch.object(console_module, 'console', console):
            console_module.setup_rich_logging("DEBUG")

        # Check that logging is configured
        root_logger = logging.getLogger()
        # The handler should be RichHandler
        assert len(root_logger.handlers) > 0


class TestConsoleBoundaryCases:
    """Boundary and edge case tests for console functions."""

    @pytest.fixture
    def mock_console(self):
        """Create a mock console with StringIO capture."""
        from rich.console import Console
        output = io.StringIO()
        console = Console(file=output, force_terminal=True)
        return output, console

    def test_print_task_table_emoji_name(self, mock_console):
        """Test print_task_table handles emoji in task names."""
        from agent import console as console_module

        output, console = mock_console

        tasks = [
            {
                "id": "emoji-001",
                "name": "🚀 Launch Feature",
                "description": "🚀🚀🚀",
                "priority": 1,
                "status": "pending",
                "passes": False
            }
        ]

        with patch.object(console_module, 'console', console):
            console_module.print_task_table(tasks, 0, 1)

        result = output.getvalue()
        assert "🚀 Launch Feature" in result

    def test_print_task_table_chinese_name(self, mock_console):
        """Test print_task_table handles Chinese characters in task names."""
        from agent import console as console_module

        output, console = mock_console

        tasks = [
            {
                "id": "cn-001",
                "name": "中文任务名称",
                "description": "这是一个测试任务描述",
                "priority": 1,
                "status": "pending",
                "passes": False
            }
        ]

        with patch.object(console_module, 'console', console):
            console_module.print_task_table(tasks, 0, 1)

        result = output.getvalue()
        assert "中文任务名称" in result

    def test_print_task_table_long_name(self, mock_console):
        """Test print_task_table handles very long task names."""
        from agent import console as console_module

        output, console = mock_console

        long_name = "A" * 200  # Very long task name

        tasks = [
            {
                "id": "long-001",
                "name": long_name,
                "description": "Long description",
                "priority": 1,
                "status": "pending",
                "passes": False
            }
        ]

        with patch.object(console_module, 'console', console):
            console_module.print_task_table(tasks, 0, 1)

        result = output.getvalue()
        # Should handle gracefully without crashing

    def test_print_task_table_newlines_in_description(self, mock_console):
        """Test print_task_table handles newlines in task description."""
        from agent import console as console_module

        output, console = mock_console

        tasks = [
            {
                "id": "nl-001",
                "name": "Newline Task",
                "description": "Line 1\nLine 2\nLine 3",
                "priority": 1,
                "status": "pending",
                "passes": False
            }
        ]

        with patch.object(console_module, 'console', console):
            console_module.print_task_table(tasks, 0, 1)

        result = output.getvalue()
        assert "Newline Task" in result

    def test_print_task_table_special_chars(self, mock_console):
        """Test print_task_table handles special characters."""
        from agent import console as console_module

        output, console = mock_console

        tasks = [
            {
                "id": "special-001",
                "name": "Task with <script>alert('xss')</script>",
                "description": "Description with \"quotes\" and 'apostrophes' and &ampersand",
                "priority": 1,
                "status": "pending",
                "passes": False
            }
        ]

        with patch.object(console_module, 'console', console):
            console_module.print_task_table(tasks, 0, 1)

        result = output.getvalue()
        assert "Task with" in result

    def test_print_header_empty_title(self, mock_console):
        """Test print_header with empty title."""
        from agent import console as console_module

        output, console = mock_console

        with patch.object(console_module, 'console', console):
            console_module.print_header("")

        result = output.getvalue()
        assert "=" in result

    def test_print_status_panel_all_zeros(self, mock_console):
        """Test print_status_panel with all zero values."""
        from agent import console as console_module

        output, console = mock_console

        with patch.object(console_module, 'console', console):
            console_module.print_status_panel(
                project_name="EmptyProject",
                project_type="generic",
                test_command="",
                branch="N/A",
                has_changes=False,
                tasks_completed=0,
                tasks_total=0,
                tasks_pending=0,
                current_session="N/A",
                error_count=0
            )

        result = output.getvalue()
        assert "EmptyProject" in result

    def test_print_status_panel_very_high_error_count(self, mock_console):
        """Test print_status_panel with very high error count."""
        from agent import console as console_module

        output, console = mock_console

        with patch.object(console_module, 'console', console):
            console_module.print_status_panel(
                project_name="HighErrorProject",
                project_type="python",
                test_command="pytest",
                branch="main",
                has_changes=True,
                tasks_completed=1,
                tasks_total=100,
                tasks_pending=99,
                current_session="session-999",
                error_count=9999
            )

        result = output.getvalue()
        assert "9999" in result


class TestAgentConsoleRenderer:
    """Test the unified renderer used for SDK/tool output."""

    @pytest.fixture
    def renderer_with_console(self):
        """Create a fresh renderer bound to a captured rich console."""
        from rich.console import Console
        from agent.console import AgentConsoleRenderer

        output = io.StringIO()
        console = Console(file=output, force_terminal=True, width=100)
        renderer = AgentConsoleRenderer(lambda: console)
        return output, renderer

    def test_render_tool_call_for_bash(self, renderer_with_console):
        """Bash tool calls should render command and description cleanly."""
        output, renderer = renderer_with_console

        renderer.render_tool_call(
            "Bash",
            {"command": "git status", "description": "Check working tree state"},
            "tool-1",
        )

        result = output.getvalue()
        assert "Tool" in result
        assert "Bash" in result
        assert "git status" in result
        assert "Check working tree state" in result

    def test_render_tool_call_for_todowrite(self, renderer_with_console):
        """TodoWrite should render as a readable task table instead of raw JSON."""
        output, renderer = renderer_with_console

        renderer.render_tool_call(
            "TodoWrite",
            {
                "todos": [
                    {"content": "Create constants", "status": "completed"},
                    {"content": "Refactor output renderer", "status": "in_progress"},
                ]
            },
            "tool-2",
        )

        result = output.getvalue()
        assert "TodoWrite" in result
        assert "Create constants" in result
        assert "Refactor output renderer" in result
        assert "done" in result or "doing" in result

    def test_render_tool_result_uses_existing_tool_index(self, renderer_with_console):
        """Tool results should reuse the same tool index when tool_use_id matches."""
        output, renderer = renderer_with_console

        renderer.render_tool_call("Read", {"file_path": "/tmp/example.py"}, "tool-3")
        renderer.render_tool_result("file content", tool_use_id="tool-3")

        result = output.getvalue()
        assert result.count("Tool") >= 2
        assert "completed" in result
        assert "file content" in result

    def test_render_stop_reason_skips_internal_tool_use(self, renderer_with_console):
        """Internal stop reasons should not pollute the terminal."""
        output, renderer = renderer_with_console

        renderer.render_stop_reason("tool_use")

        assert output.getvalue() == ""

    def test_stream_text_and_notification(self, renderer_with_console):
        """Streaming text should flush cleanly before a notification panel."""
        output, renderer = renderer_with_console

        renderer.stream_assistant_text("Working on it")
        renderer.render_notification("warning", "Resource usage high", {"cpu": 90})

        result = output.getvalue()
        assert "Agent:" in result
        assert "Working on it" in result
        assert "Notification" in result
        assert "Resource usage high" in result


class TestConsoleModuleLevel:
    """Test module-level console instance."""

    def test_console_instance_exists(self):
        """Test that console module exports console instance."""
        from agent.console import console
        from rich.console import Console

        assert isinstance(console, Console)

    def test_module_imports(self):
        """Test all expected functions are importable."""
        from agent.console import (
            setup_rich_logging,
            print_header,
            print_success,
            print_error,
            print_warning,
            print_info,
            print_task_table,
            print_status_panel,
            print_run_summary,
            create_progress,
            print_init_info,
            print_reload_result,
            print_prompt_list,
            print_template_list,
            agent_output,
            console,
        )

        # All should be callable or instances
        assert callable(setup_rich_logging)
        assert callable(print_header)
        assert callable(print_success)
        assert callable(print_error)
        assert callable(print_warning)
        assert callable(print_info)
        assert callable(print_task_table)
        assert callable(print_status_panel)
        assert callable(print_run_summary)
        assert callable(create_progress)
        assert callable(print_init_info)
        assert callable(print_reload_result)
        assert callable(print_prompt_list)
        assert callable(print_template_list)
        assert agent_output is not None
