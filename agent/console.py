"""Console output utilities using rich library.

Provides colorful CLI output including tables, progress bars, and status panels.
"""

import logging
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich.text import Text

# Create console instance
console = Console()


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
