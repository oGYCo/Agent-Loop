"""Console output utilities using rich.

Provides colorful CLI output for regular commands and a unified renderer for
streaming Claude SDK events.
"""

import json
import logging
from typing import Any, Callable, Dict, List, Optional

from rich import box
from rich.console import Console, Group, RenderableType
from rich.logging import RichHandler
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.rule import Rule
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

# Create console instance
console = Console()


class AgentConsoleRenderer:
    """Render Claude SDK events in a consistent, compact format."""

    _MAX_TEXT_CHARS = 900
    _MAX_TEXT_LINES = 18
    _MAX_JSON_ITEMS = 8
    _MAX_JSON_DEPTH = 3
    _INTERNAL_STOP_REASONS = {"tool_use", "end_turn"}

    def __init__(self, console_getter: Callable[[], Console] | None = None) -> None:
        self._console_getter = console_getter or (lambda: console)
        self.reset_session()

    @property
    def _console(self) -> Console:
        return self._console_getter()

    def reset_session(self) -> None:
        self._tool_counter = 0
        self._tool_numbers: dict[str, int] = {}
        self._tool_names: dict[str, str] = {}
        self._active_stream_label: str | None = None

    def finish_stream(self) -> None:
        if self._active_stream_label is not None:
            self._console.print()
            self._active_stream_label = None

    @property
    def tool_count(self) -> int:
        return self._tool_counter

    def render_phase(self, title: str, subtitle: str | None = None, style: str = "magenta") -> None:
        self.finish_stream()
        self._console.print()
        self._console.print(Rule(Text(title, style=f"bold {style}"), style=style))
        if subtitle:
            self._console.print(Text(subtitle, style="dim"))

    def stream_text(self, text: str, label: str = "Agent", style: str = "bold cyan") -> None:
        if not text:
            return

        if self._active_stream_label != label:
            self.finish_stream()
            self._console.print()
            self._console.print(Text(f"{label}: ", style=style), end="")
            self._active_stream_label = label

        self._console.print(text, end="", markup=False, highlight=False, soft_wrap=True)

    def stream_assistant_text(self, text: str) -> None:
        self.stream_text(text, label="Agent", style="bold cyan")

    def stream_thinking_text(self, text: str) -> None:
        preview = self._truncate_text(text, max_chars=400, max_lines=6)
        self.stream_text(preview, label="Thinking", style="bold yellow")

    def render_tool_call(
        self,
        tool_name: str,
        tool_input: Any,
        tool_use_id: str | None = None,
    ) -> int:
        tool_number = self._register_tool(tool_name, tool_use_id)
        self.finish_stream()

        title = Text.assemble(
            ("Tool ", "bold cyan"),
            (str(tool_number), "bold white"),
            ("  ", "white"),
            (tool_name, "bold cyan"),
        )

        self._console.print()
        self._console.print(
            Panel(
                self._build_tool_call_body(tool_name, tool_input),
                title=title,
                border_style="cyan",
                box=box.ROUNDED,
                padding=(0, 1),
            )
        )
        return tool_number

    def render_tool_result(
        self,
        result: Any,
        *,
        tool_name: str | None = None,
        tool_use_id: str | None = None,
        is_error: bool = False,
    ) -> None:
        resolved_tool_name = self._resolve_tool_name(tool_name, tool_use_id)
        tool_number = self._register_tool(resolved_tool_name, tool_use_id)
        status_style = "red" if is_error else "green"
        status_text = "failed" if is_error else "completed"

        title = Text.assemble(
            ("Tool ", f"bold {status_style}"),
            (str(tool_number), "bold white"),
            ("  ", "white"),
            (resolved_tool_name, f"bold {status_style}"),
            ("  ", "white"),
            (status_text, status_style),
        )

        self.finish_stream()
        self._console.print(
            Panel(
                self._build_result_body(result),
                title=title,
                border_style=status_style,
                box=box.ROUNDED,
                padding=(0, 1),
            )
        )

    def render_notification(
        self,
        notification_type: str,
        message: str,
        details: Any | None = None,
    ) -> None:
        body = self._build_key_value_table(
            [
                ("Type", notification_type or "info"),
                ("Message", self._truncate_text(message, max_chars=220, max_lines=4) or "-"),
            ]
        )

        renderables: list[RenderableType] = [body]
        if details:
            renderables.append(Text("Details", style="bold yellow"))
            renderables.append(self._render_json_preview(details))

        self.finish_stream()
        self._console.print()
        self._console.print(
            Panel(
                Group(*renderables),
                title=Text("Notification", style="bold yellow"),
                border_style="yellow",
                box=box.ROUNDED,
                padding=(0, 1),
            )
        )

    def render_stop_reason(self, reason: str | None) -> None:
        if not reason or reason in self._INTERNAL_STOP_REASONS:
            return

        self.finish_stream()
        self._console.print()
        self._console.print(
            Panel(
                Text(f"Stop reason: {reason}", style="bold yellow"),
                title=Text("Claude SDK", style="bold yellow"),
                border_style="yellow",
                box=box.ROUNDED,
                padding=(0, 1),
            )
        )

    def render_session_stop(self, session_id: str | None, reason: str | None = None) -> None:
        rows = [("Session", session_id or "-")]
        if reason:
            rows.append(("Reason", reason))

        self.finish_stream()
        self._console.print()
        self._console.print(
            Panel(
                self._build_key_value_table(rows),
                title=Text("Session Ended", style="bold blue"),
                border_style="blue",
                box=box.ROUNDED,
                padding=(0, 1),
            )
        )

    def render_restart_required(self) -> None:
        self.finish_stream()
        self._console.print()
        self._console.print(
            Panel(
                Group(
                    Text("The agent modified its own code and needs a restart.", style="bold"),
                    Text("Restart the process to continue with the updated code.", style="dim"),
                ),
                title=Text("Code Changes Detected", style="bold red"),
                border_style="red",
                box=box.DOUBLE,
                padding=(0, 1),
            )
        )

    def render_human_intervention(self, request: Dict[str, Any]) -> None:
        rows = [
            ("Reason", request.get("reason", "-")),
            ("Time", request.get("timestamp", "-")),
        ]
        if request.get("task_id"):
            rows.append(("Task", request["task_id"]))

        renderables: list[RenderableType] = [self._build_key_value_table(rows)]
        if request.get("context"):
            renderables.append(Text("Context", style="bold yellow"))
            renderables.append(self._render_json_preview(request["context"]))

        self.finish_stream()
        self._console.print()
        self._console.print(
            Panel(
                Group(*renderables),
                title=Text("Human Intervention Required", style="bold yellow"),
                border_style="yellow",
                box=box.DOUBLE,
                padding=(0, 1),
            )
        )

    def render_shutdown_notice(self, signal_name: str, force: bool = False) -> None:
        self.finish_stream()
        if force:
            title = Text("Force Exit", style="bold red")
            body = Text(f"Stopping immediately ({signal_name}).", style="bold red")
            border_style = "red"
        else:
            title = Text("Graceful Shutdown", style="bold yellow")
            body = Group(
                Text(f"Received {signal_name}.", style="bold yellow"),
                Text("Finishing the current task before exit. Press Ctrl+C again to force quit.", style="dim"),
            )
            border_style = "yellow"

        self._console.print()
        self._console.print(
            Panel(
                body,
                title=title,
                border_style=border_style,
                box=box.ROUNDED,
                padding=(0, 1),
            )
        )

    def _register_tool(self, tool_name: str, tool_use_id: str | None) -> int:
        if tool_use_id:
            if tool_use_id not in self._tool_numbers:
                self._tool_counter += 1
                self._tool_numbers[tool_use_id] = self._tool_counter
            self._tool_names[tool_use_id] = tool_name
            return self._tool_numbers[tool_use_id]

        self._tool_counter += 1
        return self._tool_counter

    def _resolve_tool_name(self, tool_name: str | None, tool_use_id: str | None) -> str:
        if tool_name:
            return tool_name
        if tool_use_id and tool_use_id in self._tool_names:
            return self._tool_names[tool_use_id]
        return "unknown"

    def _build_tool_call_body(self, tool_name: str, tool_input: Any) -> RenderableType:
        if tool_name == "TodoWrite" and isinstance(tool_input, dict):
            todos = tool_input.get("todos", [])
            renderables: list[RenderableType] = []
            renderables.append(self._build_key_value_table([("Items", str(len(todos)))]))
            renderables.append(self._build_todo_table(todos))
            return Group(*renderables)

        if tool_name == "Bash" and isinstance(tool_input, dict):
            rows: list[tuple[str, str]] = []
            if tool_input.get("description"):
                rows.append(("Description", self._inline_preview(tool_input["description"])))
            renderables = []
            if rows:
                renderables.append(self._build_key_value_table(rows))
            if tool_input.get("command"):
                renderables.append(Text("Command", style="bold cyan"))
                renderables.append(self._render_text_block(tool_input["command"], lexer="bash"))
            return Group(*renderables)

        if tool_name in {"Read", "Write", "Edit", "MultiEdit"} and isinstance(tool_input, dict):
            rows = []
            if tool_input.get("file_path"):
                rows.append(("File", str(tool_input["file_path"])))
            if tool_input.get("offset") is not None:
                rows.append(("Offset", str(tool_input["offset"])))
            if tool_input.get("limit") is not None:
                rows.append(("Limit", str(tool_input["limit"])))
            if tool_name == "Edit" and "replace_all" in tool_input:
                rows.append(("Replace all", str(bool(tool_input["replace_all"]))))
            if tool_name == "MultiEdit" and isinstance(tool_input.get("edits"), list):
                rows.append(("Edits", str(len(tool_input["edits"]))))

            renderables = [self._build_key_value_table(rows)] if rows else []
            for field, label in (
                ("content", "Content"),
                ("old_string", "Old text"),
                ("new_string", "New text"),
            ):
                if tool_input.get(field):
                    renderables.append(Text(label, style="bold cyan"))
                    renderables.append(self._render_text_block(tool_input[field]))

            if tool_name == "MultiEdit" and isinstance(tool_input.get("edits"), list):
                renderables.append(Text("Edit preview", style="bold cyan"))
                renderables.append(self._render_json_preview({"edits": tool_input["edits"]}))

            return Group(*renderables) if renderables else self._render_json_preview(tool_input)

        if tool_name in {"Glob", "Grep", "WebSearch", "WebFetch", "AskUserQuestion"} and isinstance(tool_input, dict):
            rows = []
            for label, key in (
                ("Pattern", "pattern"),
                ("Path", "path"),
                ("Query", "query"),
                ("URL", "url"),
                ("Prompt", "prompt"),
                ("Question", "question"),
                ("Description", "description"),
            ):
                if tool_input.get(key):
                    rows.append((label, self._inline_preview(tool_input[key])))
            if rows:
                return self._build_key_value_table(rows)

        if isinstance(tool_input, dict):
            simple_rows = [
                (str(key), self._inline_preview(value))
                for key, value in list(tool_input.items())[:4]
                if not isinstance(value, (dict, list))
            ]
            renderables = [self._build_key_value_table(simple_rows)] if simple_rows else []
            renderables.append(self._render_json_preview(tool_input))
            return Group(*renderables)

        return self._render_json_preview(tool_input)

    def _build_result_body(self, result: Any) -> RenderableType:
        if isinstance(result, dict):
            rows = []
            if result.get("exit_code") is not None:
                rows.append(("Exit code", str(result["exit_code"])))
            if rows:
                renderables: list[RenderableType] = [self._build_key_value_table(rows)]
                for key, label in (("stdout", "stdout"), ("stderr", "stderr")):
                    if result.get(key):
                        renderables.append(Text(label, style="bold cyan"))
                        renderables.append(self._render_text_block(result[key]))
                extra = {k: v for k, v in result.items() if k not in {"exit_code", "stdout", "stderr"}}
                if extra:
                    renderables.append(self._render_json_preview(extra))
                return Group(*renderables)
            return self._render_json_preview(result)

        if isinstance(result, list):
            return self._render_json_preview(result)

        text = str(result or "").strip("\n")
        if not text:
            return Text("No output", style="dim")
        return self._render_text_block(text)

    def _build_todo_table(self, todos: List[Dict[str, Any]]) -> Table:
        table = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold magenta", pad_edge=False)
        table.add_column("State", width=6, no_wrap=True)
        table.add_column("Task", style="white")

        icon_map = {
            "completed": "[bold green]done[/bold green]",
            "in_progress": "[bold cyan]doing[/bold cyan]",
            "pending": "[dim]todo[/dim]",
        }

        for todo in todos[: self._MAX_JSON_ITEMS]:
            status = str(todo.get("status", "pending"))
            label = todo.get("activeForm") or todo.get("content") or "Untitled"
            table.add_row(icon_map.get(status, status), self._truncate_text(str(label), max_chars=90, max_lines=2))

        if len(todos) > self._MAX_JSON_ITEMS:
            table.add_row("[dim]...[/dim]", f"[dim]{len(todos) - self._MAX_JSON_ITEMS} more items[/dim]")

        return table

    def _build_key_value_table(self, rows: List[tuple[str, str]]) -> Table:
        table = Table.grid(padding=(0, 1))
        table.add_column(style="bold cyan", no_wrap=True)
        table.add_column(style="white")
        for key, value in rows:
            table.add_row(key, value or "-")
        return table

    def _render_json_preview(self, payload: Any) -> RenderableType:
        sanitized = self._sanitize_value(payload)
        formatted = json.dumps(sanitized, ensure_ascii=False, indent=2, default=str)
        return Syntax(formatted, "json", word_wrap=True, line_numbers=False, background_color="default")

    def _render_text_block(self, text: Any, lexer: str = "text") -> RenderableType:
        preview = self._truncate_text(str(text), self._MAX_TEXT_CHARS, self._MAX_TEXT_LINES)
        return Syntax(preview, lexer, word_wrap=True, line_numbers=False, background_color="default")

    def _inline_preview(self, value: Any, max_chars: int = 100) -> str:
        if isinstance(value, str):
            return self._truncate_text(value, max_chars=max_chars, max_lines=2).replace("\n", " ")
        if isinstance(value, (dict, list)):
            preview = json.dumps(self._sanitize_value(value), ensure_ascii=False, default=str)
            return self._truncate_text(preview, max_chars=max_chars, max_lines=2).replace("\n", " ")
        return self._truncate_text(str(value), max_chars=max_chars, max_lines=2).replace("\n", " ")

    def _truncate_text(self, text: str, max_chars: int, max_lines: int) -> str:
        lines = text.splitlines()
        truncated_lines = lines[:max_lines]
        output = "\n".join(truncated_lines)
        line_suffix = ""
        if len(lines) > max_lines:
            line_suffix = f"\n... ({len(lines) - max_lines} more lines)"
        if len(output) > max_chars:
            output = output[:max_chars].rstrip() + "..."
            line_suffix = ""
        return f"{output}{line_suffix}" if output or line_suffix else text

    def _sanitize_value(self, value: Any, depth: int = 0) -> Any:
        if depth >= self._MAX_JSON_DEPTH:
            return self._inline_preview(value, max_chars=140)

        if isinstance(value, str):
            return self._truncate_text(value, self._MAX_TEXT_CHARS, self._MAX_TEXT_LINES)

        if isinstance(value, dict):
            items = list(value.items())
            preview = {
                str(key): self._sanitize_value(val, depth + 1)
                for key, val in items[: self._MAX_JSON_ITEMS]
            }
            if len(items) > self._MAX_JSON_ITEMS:
                preview["..."] = f"{len(items) - self._MAX_JSON_ITEMS} more fields"
            return preview

        if isinstance(value, list):
            preview = [self._sanitize_value(item, depth + 1) for item in value[: self._MAX_JSON_ITEMS]]
            if len(value) > self._MAX_JSON_ITEMS:
                preview.append(f"... {len(value) - self._MAX_JSON_ITEMS} more items")
            return preview

        if isinstance(value, tuple):
            return [self._sanitize_value(item, depth + 1) for item in value[: self._MAX_JSON_ITEMS]]

        return value


agent_output = AgentConsoleRenderer(lambda: console)


def setup_rich_logging(level: str = "INFO") -> None:
    """Configure rich-based logging handler.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)]
    )


def print_header(title: str, style: str = "bold cyan") -> None:
    """Print a header with rich styling.

    Args:
        title: Header title
        style: Rich style string
    """
    console.print(f"\n[bold]{'=' * 50}[/bold]")
    console.print(f"[{style}]{title}[/{style}]")
    console.print(f"[bold]{'=' * 50}[/bold]\n")


def print_success(message: str) -> None:
    """Print success message in green.

    Args:
        message: Message to print
    """
    console.print(f"[bold green]✓[/bold green] {message}")


def print_error(message: str) -> None:
    """Print error message in red.

    Args:
        message: Message to print
    """
    console.print(f"[bold red]✗[/bold red] {message}")


def print_warning(message: str) -> None:
    """Print warning message in yellow.

    Args:
        message: Message to print
    """
    console.print(f"[bold yellow]⚠[/bold yellow] {message}")


def print_info(message: str) -> None:
    """Print info message in blue.

    Args:
        message: Message to print
    """
    console.print(f"[bold blue]ℹ[/bold blue] {message}")


def print_task_table(tasks: List[Dict[str, Any]], completed_count: int, pending_count: int) -> None:
    """Print task list as a rich table.

    Args:
        tasks: List of task dictionaries
        completed_count: Number of completed tasks
        pending_count: Number of pending tasks
    """
    table = Table(title="Feature List", show_header=True, header_style="bold magenta")
    table.add_column("Status", style="cyan", width=8)
    table.add_column("ID", style="dim", width=15)
    table.add_column("Name", style="white", width=25)
    table.add_column("Priority", justify="center", style="yellow", width=10)
    table.add_column("Description", style="white")

    for task in tasks:
        status_icon = "[bold green]✓[/bold green]" if task.get("passes") else "[bold dim]○[/bold dim]"
        status_text = task.get("status", "pending")

        # Color code by status
        if status_text == "completed":
            status_style = "green"
        elif status_text == "in_progress":
            status_style = "blue"
        else:
            status_style = "dim"

        table.add_row(
            status_icon,
            f"[dim]{task.get('id', 'N/A')}[/dim]",
            task.get("name", "Unnamed"),
            str(task.get("priority", 99)),
            f"[{status_style}]{task.get('description', '')}[/{status_style}]"
        )

    console.print(table)
    console.print(f"\n[bold]Total:[/bold] {len(tasks)} | [bold green]Completed:[/bold green] {completed_count} | [bold yellow]Pending:[/bold yellow] {pending_count}")


def print_status_panel(
    project_name: str,
    project_type: str,
    test_command: str,
    branch: str,
    has_changes: bool,
    tasks_completed: int,
    tasks_total: int,
    tasks_pending: int,
    current_session: str,
    error_count: int
) -> None:
    """Print status as a rich panel.

    Args:
        project_name: Name of the project
        project_type: Type of project
        test_command: Test command
        branch: Git branch
        has_changes: Whether there are uncommitted changes
        tasks_completed: Number of completed tasks
        tasks_total: Total number of tasks
        tasks_pending: Number of pending tasks
        current_session: Current session ID
        error_count: Error count
    """
    # Create status table
    status_table = Table.grid(padding=1)
    status_table.add_column("key", style="bold cyan")
    status_table.add_column("value", style="white")

    status_table.add_row("Project", f"[white]{project_name}[/white]")
    status_table.add_row("Type", f"[white]{project_type}[/white]")
    status_table.add_row("Test Command", f"[dim]{test_command}[/dim]")
    status_table.add_row("", "")  # Spacer
    status_table.add_row("[bold]Git[/bold]", "")
    status_table.add_row("  Branch", f"[white]{branch}[/white]")
    status_table.add_row("  Has Changes", "[bold yellow]Yes[/bold yellow]" if has_changes else "[dim]No[/dim]")
    status_table.add_row("", "")  # Spacer
    status_table.add_row("[bold]Tasks[/bold]", "")
    status_table.add_row("  Completed", f"[bold green]{tasks_completed}/{tasks_total}[/bold green]")
    status_table.add_row("  Pending", f"[bold yellow]{tasks_pending}[/bold yellow]")
    status_table.add_row("", "")  # Spacer
    status_table.add_row("[bold]Session[/bold]", "")
    status_table.add_row("  Current", f"[dim]{current_session}[/dim]")
    status_table.add_row("  Errors", f"[bold red]{error_count}[/bold red]" if error_count > 0 else f"[dim]{error_count}[/dim]")

    panel = Panel(
        status_table,
        title="[bold cyan]Agent Status[/bold cyan]",
        border_style="cyan",
        padding=(1, 2)
    )
    console.print(panel)


def print_run_summary(iterations: int, completed: int, errors: int) -> None:
    """Print run summary with rich styling.

    Args:
        iterations: Number of iterations run
        completed: Number of tasks completed
        errors: Number of errors encountered
    """
    summary_table = Table.grid(padding=1)
    summary_table.add_column("label", style="bold")
    summary_table.add_column("value", style="white")

    summary_table.add_row("Iterations", str(iterations))
    summary_table.add_row("Tasks Completed", f"[bold green]{completed}[/bold green]")
    summary_table.add_row("Errors", f"[bold red]{errors}[/bold red]" if errors > 0 else f"[dim]{errors}[/dim]")

    panel = Panel(
        summary_table,
        title="[bold cyan]Agent Run Summary[/bold cyan]",
        border_style="cyan",
        padding=(1, 2)
    )
    console.print(panel)


def create_progress() -> Progress:
    """Create a rich progress bar instance.

    Returns:
        Configured Progress instance
    """
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    )


def print_init_info(agent_dir: str, created_templates: List[str]) -> None:
    """Print initialization information with rich styling.

    Args:
        agent_dir: Agent directory path
        created_templates: List of created template names
    """
    init_table = Table.grid(padding=1)
    init_table.add_column("key", style="bold cyan")
    init_table.add_column("value", style="white")

    init_table.add_row("Project directory", f"[white]{agent_dir}[/white]")
    init_table.add_row("Configuration files", "")
    init_table.add_row("  -", "[dim]config.json[/dim]")
    init_table.add_row("  -", "[dim]feature_list.json[/dim]")
    init_table.add_row("  -", "[dim]progress.txt[/dim]")
    init_table.add_row("  -", "[dim]session_history.json[/dim]")
    init_table.add_row("  -", "[dim]state.json[/dim]")

    if created_templates:
        init_table.add_row("", "")
        init_table.add_row("Prompt templates", f"[dim]({len(created_templates)} templates)[/dim]")
        for t in created_templates:
            init_table.add_row("  -", f"[dim]{t}[/dim]")

    panel = Panel(
        init_table,
        title="[bold green]Project Initialized[/bold green]",
        border_style="green",
        padding=(1, 2)
    )
    console.print(panel)

    console.print("\n[bold]To add features, edit .agent/feature_list.json[/bold]")
    console.print("[bold]To customize prompts, edit files in .agent/prompt_templates/[/bold]")
    console.print("[bold]To run the agent, use: uv run python main.py run[/bold]")


def print_reload_result(success: bool, message: str, reloaded: List[str], errors: List[str], timestamp: str) -> None:
    """Print reload result with rich styling.

    Args:
        success: Whether reload was successful
        message: Result message
        reloaded: List of reloaded files
        errors: List of errors
        timestamp: Timestamp of reload
    """
    if success:
        status = "[bold green]✓ Success[/bold green]"
    else:
        status = "[bold red]✗ Failed[/bold red]"

    result_table = Table.grid(padding=1)
    result_table.add_column("key", style="bold cyan")
    result_table.add_column("value", style="white")

    result_table.add_row("Status", status)
    result_table.add_row("Message", message)

    if reloaded:
        result_table.add_row("Reloaded files", ", ".join(reloaded))

    if errors:
        result_table.add_row("", "")
        result_table.add_row("Errors", "")
        for error in errors:
            result_table.add_row("  -", f"[bold red]{error}[/bold red]")

    result_table.add_row("Timestamp", timestamp)

    panel = Panel(
        result_table,
        title="[bold cyan]Reload Result[/bold cyan]",
        border_style="cyan",
        padding=(1, 2)
    )
    console.print(panel)


def print_prompt_list(prompts: List[Dict[str, Any]]) -> None:
    """Print prompt list as a rich table.

    Args:
        prompts: List of prompt dictionaries
    """
    table = Table(title="Available Prompts", show_header=True, header_style="bold magenta")
    table.add_column("Key", style="cyan", width=15)
    table.add_column("Name", style="white", width=25)
    table.add_column("Description", style="white")

    for p in prompts:
        active_mark = " [bold green]ACTIVE[/bold green]" if p.get("is_active") else ""
        table.add_row(
            p.get("key", ""),
            f"{p.get('name', '')}{active_mark}",
            p.get("description", "")
        )

    console.print(table)


def print_template_list(templates: List[Dict[str, Any]]) -> None:
    """Print template list with rich styling.

    Args:
        templates: List of template dictionaries
    """
    for t in templates:
        override_mark = " [bold yellow]OVERRIDE[/bold yellow]" if t.get("has_override") else ""
        builtin_mark = " (built-in)" if t.get("builtin") else " (custom)"

        console.print(f"  [bold]{t.get('name')}[/bold]{override_mark}[dim]{builtin_mark}[/dim]")
        if t.get("path"):
            console.print(f"    [dim]Path: {t['path']}[/dim]")

    console.print("\n[dim]To customize a template, edit: .agent/prompt_templates/<name>.md[/dim]")
    console.print("[dim]To scaffold all templates: uv run python main.py template scaffold[/dim]")
