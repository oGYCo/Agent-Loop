"""Prompt Manager - Production-grade prompt template system

Provides a fully configurable prompt management system with:
- Template-based prompts with {{variable}} substitution
- User-overridable templates via .agent/prompt_templates/
- Named system prompt variants via prompts.json
- Built-in defaults as fallback when no user config exists
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, cast


class PromptValidationError(Exception):
    """Prompt validation error"""

    def __init__(self, message: str = "Prompt validation failed") -> None:
        self.message = message
        super().__init__(self.message)


# ============================================================
# Template Rendering Engine
# ============================================================

_TEMPLATE_PATTERN = re.compile(r"\{\{(\w+)\}\}")


def render_template(template: str, variables: dict[str, str]) -> str:
    """Render a template by replacing {{variable}} placeholders with values.

    Uses safe substitution: unresolved variables are left as-is.
    This avoids breaking templates that reference variables not yet available.

    Args:
        template: Template string with {{variable_name}} placeholders
        variables: Dict mapping variable names to their string values

    Returns:
        Rendered template string
    """
    def _replacer(match: re.Match[str]) -> str:
        key = match.group(1).strip()
        return variables.get(key, match.group(0))

    return _TEMPLATE_PATTERN.sub(_replacer, template)


# ============================================================
# Project Structure Scanner
# ============================================================

def scan_project_structure(root: str, max_depth: int = 3, max_entries: int = 50) -> str:
    """Auto-detect and generate project structure tree.

    Respects .gitignore patterns and skips common non-essential directories.

    Args:
        root: Project root directory path
        max_depth: Maximum directory depth to scan
        max_entries: Maximum number of entries to include

    Returns:
        Tree-formatted string of the project structure
    """
    root_path = Path(root).resolve()

    ignore_names = {
        "__pycache__", ".git", ".hg", ".svn",
        "node_modules", ".tox", ".eggs",
        ".mypy_cache", ".pytest_cache", ".ruff_cache",
        "dist", "build", ".venv", "venv", "env",
        ".idea", ".vscode", ".DS_Store",
    }
    ignore_suffixes = {".pyc", ".pyo", ".so", ".dylib", ".egg-info"}

    gitignore_path = root_path / ".gitignore"
    if gitignore_path.exists():
        with open(gitignore_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    clean = line.rstrip("/")
                    if clean:
                        ignore_names.add(clean)

    lines: list[str] = []
    entry_count = 0

    def _should_ignore(name: str) -> bool:
        if name in ignore_names:
            return True
        for suffix in ignore_suffixes:
            if name.endswith(suffix):
                return True
        return False

    def _scan(dir_path: Path, prefix: str, depth: int) -> None:
        nonlocal entry_count

        if depth > max_depth or entry_count >= max_entries:
            return

        try:
            entries = sorted(dir_path.iterdir(), key=lambda e: (not e.is_dir(), e.name))
        except PermissionError:
            return

        visible = [e for e in entries if not _should_ignore(e.name)]

        for i, entry in enumerate(visible):
            if entry_count >= max_entries:
                lines.append(f"{prefix}\u2514\u2500\u2500 ...")
                return

            is_last = i == len(visible) - 1
            connector = "\u2514\u2500\u2500 " if is_last else "\u251c\u2500\u2500 "
            extension = "    " if is_last else "\u2502   "

            if entry.is_dir():
                lines.append(f"{prefix}{connector}{entry.name}/")
                entry_count += 1
                _scan(entry, prefix + extension, depth + 1)
            else:
                lines.append(f"{prefix}{connector}{entry.name}")
                entry_count += 1

    lines.append(f"{root_path.name}/")
    entry_count += 1
    _scan(root_path, "", 1)

    return "\n".join(lines)


# ============================================================
# Built-in Default Templates
# ============================================================
# These serve as fallbacks when no user override exists.
# Users can customize by placing files in .agent/prompt_templates/
# All templates use {{variable_name}} syntax for dynamic values.

_DEFAULT_SYSTEM_PROMPT = """\
You are an autonomous AI agent working on the {{project_name}} project.

## Before Starting Any Task

You MUST read the project's context files to understand the codebase:
{{context_files_list}}

Use the Read tool to read these files completely before starting work.

## Your Workflow

1. Read project context and relevant documentation
2. Understand the current task requirements
3. Read and understand relevant source files
4. Plan your approach - keep changes minimal and focused
5. Implement the solution
6. Test and verify your changes
7. Commit and push changes with descriptive messages
8. Record lessons learned in the .agent/MEMORY.txt file

## Available Tools

You have access to the following tool categories:
- **File Tools**: Read, Write, Edit, Glob, Grep - for file operations
- **Terminal Tools**: Bash - for running commands
- **Web Tools**: WebSearch, WebFetch - for searching information
- **Browser Tools**: Navigate, Snapshot, Click, Type - for browser automation

## Working Principles

1. **Read context first** - Always understand the project before making changes
2. **Minimal changes** - Make the smallest focused change per task
3. **Test thoroughly** - Verify all changes with tests
4. **Commit regularly** - Save progress with clear commit messages
5. **Document learnings** - Update project documentation with insights

## Important Rules

- NEVER assume or guess - always use tools to verify
- NEVER use hardcoded values - use config files
- NEVER skip tests - always verify with real data
- ALWAYS provide enough context for the next agent iteration
- ALWAYS think about how your changes integrate with the system
"""

_DEFAULT_TASK_TEMPLATE = """\
# Task: {{task_name}}

## Task ID
`{{task_id}}`

## Description
{{task_description}}

## Priority
{{task_priority}} (lower = higher priority)

## Project Structure
```
{{project_structure}}
```

## Current Git Status
```
Branch: {{current_branch}}
{{git_status}}
```

## Project Guidelines
{{project_guidelines}}

## Your Task Context

Before starting:

1. **Read project documentation** - Understand project guidelines and architecture
2. **Read relevant source files** - Understand the code you'll modify
3. **Plan your change** - Keep it minimal and focused
4. **Implement** - Make the smallest possible change
5. **Test** - Run tests to verify
6. **Commit and push** - Save and push progress with git
7. **Record learnings** - Document what you learned

## Key Instructions

- Make ONE small atomic change
- If task is too large, complete only a part and update status to "in_progress"
- Always provide context for the next agent
- Run tests before marking as complete
- Use simple commit messages like "fix: description" or "feat: description"
- Push changes to the remote repository after committing

## Verification
{{verify_command}}

## Post-Task Actions
After completing this task, you MUST:
1. Review and update the task list - check if any pending tasks need priority adjustments, removal, or new tasks added
2. Update project memory - extract key learnings from this task
3. Consider if project documentation needs updates based on new patterns or insights discovered
4. Commit and push all changes

Start by reading the project documentation and the relevant source files for this task.
"""

_DEFAULT_SELF_REVIEW_TEMPLATE = """\
## Post-Task Self-Review

You just completed: **{{completed_task_name}}**

### Current Project Context

**Git Info:**
- Branch: {{current_branch}}
- Recent commits:
{{recent_commits}}
- Status: {{git_status}}

**Task Status:**
- Completed tasks: {{completed_count}}
- Pending tasks: {{pending_count}}
- Failed tasks: {{failed_count}}

### Step 1: Gather Context (REQUIRED)

Before making any decisions, you MUST gather sufficient context:

1. Read the task list file - understand all pending tasks and their dependencies
2. Read project documentation - understand current guidelines
3. Read project memory file - understand accumulated lessons
4. Run `git diff` to see what files were changed in recent commits
5. Check the main code files to understand current architecture

### Step 2: Analyze and Decide

After gathering context, analyze:

1. Which pending tasks are now obsolete (dependencies completed)?
2. Which task priorities should change based on project state?
3. Are there any new tasks that should be added based on recent changes?
4. Are there duplicate or overlapping tasks that should be merged?

### Step 3: Execute Changes

- Use Edit or Write tools to modify the task list
- DO NOT create new self-review tasks
- Only modify what truly needs to be changed
- After completing, summarize what changes you made

Please start by gathering context, then analyze and make updates.
"""

_DEFAULT_MEMORY_CLEANUP_TEMPLATE = """\
## Memory File Optimization

{{cleanup_suggestions}}

### Current Context

- Branch: {{current_branch}}
- Recent commits:
{{recent_commits}}

### Step 1: Gather Context (REQUIRED)

Before making any decisions, you MUST gather sufficient context:

1. Read the project memory file - understand current content structure
2. Read the task list - understand completed tasks and recent work
3. Run `git diff HEAD~5 --stat` to see what files changed recently
4. Read recent code files to understand new patterns or changes

### Step 2: Analyze

After gathering context, analyze:

1. **What to DELETE**: Redundant, duplicate, or outdated content
2. **What to UPDATE**: Incorrect or stale information that needs fixing
3. **What to ADD**: New insights, patterns, or lessons from recent work

### Step 3: Execute

- Use Edit or Write tools to make changes
- Keep essential technical details and key learnings
- Merge similar sections to reduce duplication
- Add new lessons learned from recent tasks
- After completing, summarize what you added, updated, and deleted

Please start by gathering context, then analyze and make updates.
"""

_DEFAULT_CLAUDE_MD_CLEANUP_TEMPLATE = """\
## Project Documentation Optimization

{{cleanup_suggestions}}

### Current Context

- Branch: {{current_branch}}
- Recent commits:
{{recent_commits}}

### Step 1: Gather Context (REQUIRED)

Before making any decisions, you MUST gather sufficient context:

1. Read project documentation - understand current content structure and guidelines
2. Read the task list - understand completed tasks and recent work
3. Run `git diff HEAD~5 --stat` to see what files changed recently
4. Read recent code files to understand new patterns or APIs used
5. Read the project memory file for recent lessons learned

### Step 2: Analyze

After gathering context, analyze:

1. **What to DELETE**: Redundant, duplicate, or outdated content
2. **What to UPDATE**: Incorrect or stale commands, configurations, or guidelines
3. **What to ADD**: New project patterns, commands, or insights from recent work

### Step 3: Execute

- Use Edit or Write tools to make changes
- Keep essential project guidelines and technical details
- Merge similar sections to reduce duplication
- Update outdated commands or configurations
- Add new patterns or insights from recent work
- After completing, summarize what you added, updated, and deleted

Please start by gathering context, then analyze and make updates.
"""

# Registry of all built-in templates
_BUILTIN_TEMPLATES: dict[str, str] = {
    "system": _DEFAULT_SYSTEM_PROMPT,
    "task": _DEFAULT_TASK_TEMPLATE,
    "self_review": _DEFAULT_SELF_REVIEW_TEMPLATE,
    "memory_cleanup": _DEFAULT_MEMORY_CLEANUP_TEMPLATE,
    "claude_md_cleanup": _DEFAULT_CLAUDE_MD_CLEANUP_TEMPLATE,
}

# System prompt variant extensions (appended to base system prompt)
_SYSTEM_PROMPT_VARIANTS: dict[str, dict[str, str]] = {
    "default": {
        "name": "Default Agent",
        "description": "Default autonomous agent prompt for general task execution",
        "extension": "",
    },
    "coder": {
        "name": "Coder",
        "description": "Specialized for coding tasks with emphasis on testing and quality",
        "extension": (
            "\n\n## Special Focus\n"
            "- Always write tests before completing\n"
            "- Follow the project's coding standards\n"
            "- Run tests to verify changes"
        ),
    },
    "researcher": {
        "name": "Researcher",
        "description": "Specialized for research and exploration tasks",
        "extension": (
            "\n\n## Special Focus\n"
            "- Thoroughly research before implementing\n"
            "- Consider multiple approaches\n"
            "- Document findings clearly"
        ),
    },
    "reviewer": {
        "name": "Reviewer",
        "description": "Specialized for code review and quality assurance",
        "extension": (
            "\n\n## Special Focus\n"
            "- Review code changes thoroughly\n"
            "- Check for edge cases and potential bugs\n"
            "- Suggest improvements and best practices"
        ),
    },
}


class PromptManager:
    """Production-grade prompt template manager.

    Provides a fully configurable prompt system with:
    - Template-based prompts with {{variable}} substitution
    - User-overridable templates via .agent/prompt_templates/
    - Named system prompt variants via prompts.json
    - Built-in defaults as fallback

    Template Resolution Order:
        1. .agent/prompt_templates/{name}.md (user override, if exists)
        2. Built-in defaults (embedded in code)

    Available Templates:
        - system: Base system prompt
        - task: Task execution prompt
        - self_review: Post-task self-review
        - memory_cleanup: Memory file optimization
        - claude_md_cleanup: Project documentation optimization
    """

    def __init__(self, agent_dir: Optional[str] = None) -> None:
        """Initialize PromptManager.

        Args:
            agent_dir: Path to the .agent directory. Auto-detects if not provided.
        """
        if agent_dir is None:
            agent_dir = str(Path(__file__).parent.parent / ".agent")
        self.agent_dir: Path = Path(agent_dir)
        self.prompts_path = self.agent_dir / "prompts.json"
        self.templates_dir = self.agent_dir / "prompt_templates"

    # ============================================================
    # Template Operations
    # ============================================================

    def load_template(self, name: str) -> str:
        """Load a template by name.

        Resolution order:
            1. User override in .agent/prompt_templates/{name}.md
            2. Built-in default

        Args:
            name: Template name (e.g., "system", "task", "self_review")

        Returns:
            Template content string

        Raises:
            ValueError: If template name is unknown and no user file exists
        """
        user_template = self.templates_dir / f"{name}.md"
        if user_template.exists():
            with open(user_template, "r", encoding="utf-8") as f:
                return f.read()

        if name in _BUILTIN_TEMPLATES:
            return _BUILTIN_TEMPLATES[name]

        raise ValueError(
            f"Unknown template: '{name}'. "
            f"Available built-in templates: {list(_BUILTIN_TEMPLATES.keys())}"
        )

    def render_template(self, name: str, variables: dict[str, str]) -> str:
        """Load and render a template with variable substitution.

        Args:
            name: Template name
            variables: Dict mapping variable names to values

        Returns:
            Rendered template string
        """
        template = self.load_template(name)
        return render_template(template, variables)

    def save_template(self, name: str, content: str) -> None:
        """Save a user template override.

        Creates the prompt_templates directory if it doesn't exist.

        Args:
            name: Template name
            content: Template content
        """
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        template_path = self.templates_dir / f"{name}.md"
        with open(template_path, "w", encoding="utf-8") as f:
            f.write(content)

    def list_templates(self) -> list[dict[str, Any]]:
        """List all available templates with their override status.

        Returns:
            List of dicts with keys: name, has_override, builtin, path
        """
        templates = []

        for name in _BUILTIN_TEMPLATES:
            user_path = self.templates_dir / f"{name}.md"
            templates.append({
                "name": name,
                "has_override": user_path.exists(),
                "builtin": True,
                "path": str(user_path) if user_path.exists() else None,
            })

        if self.templates_dir.exists():
            for f in sorted(self.templates_dir.glob("*.md")):
                name = f.stem
                if name not in _BUILTIN_TEMPLATES:
                    templates.append({
                        "name": name,
                        "has_override": True,
                        "builtin": False,
                        "path": str(f),
                    })

        return templates

    def reset_template(self, name: str) -> bool:
        """Reset a template to built-in default by removing user override.

        Args:
            name: Template name to reset

        Returns:
            True if override was removed, False if no override existed
        """
        user_path = self.templates_dir / f"{name}.md"
        if user_path.exists():
            user_path.unlink()
            return True
        return False

    def scaffold_templates(self) -> list[str]:
        """Create all default template files in .agent/prompt_templates/.

        Only creates files that don't already exist (won't overwrite user customizations).

        Returns:
            List of created template file names
        """
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        created = []

        for name, content in _BUILTIN_TEMPLATES.items():
            template_path = self.templates_dir / f"{name}.md"
            if not template_path.exists():
                with open(template_path, "w", encoding="utf-8") as f:
                    f.write(content)
                created.append(f"{name}.md")

        return created

    def get_builtin_template(self, name: str) -> Optional[str]:
        """Get a built-in template by name (ignoring user overrides).

        Args:
            name: Template name

        Returns:
            Built-in template content, or None if not found
        """
        return _BUILTIN_TEMPLATES.get(name)

    # ============================================================
    # System Prompt Operations (prompts.json)
    # ============================================================

    def load_prompts(self) -> dict[str, Any]:
        """Load prompts from prompts.json.

        Returns:
            dict[str, Any]: The prompts data, or default prompts if file doesn't exist.
        """
        if not self.prompts_path.exists():
            return self._create_default_prompts()

        with open(self.prompts_path, "r", encoding="utf-8") as f:
            return cast(dict[str, Any], json.load(f))

    def save_prompts(self, data: dict[str, Any]) -> None:
        """Save prompts to prompts.json.

        Args:
            data: The prompts data to save.
        """
        with open(self.prompts_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _create_default_prompts(self) -> dict[str, Any]:
        """Create default prompts configuration using templates."""
        base_system = self.load_template("system")
        now = datetime.now().strftime("%Y-%m-%d")

        prompts: dict[str, Any] = {}
        for key, variant in _SYSTEM_PROMPT_VARIANTS.items():
            system_content = base_system + variant["extension"]
            prompts[key] = {
                "name": variant["name"],
                "description": variant["description"],
                "system": system_content,
                "created_at": now,
                "updated_at": now,
            }

        return {
            "active_prompt": "default",
            "prompts": prompts,
            "created_at": now,
            "updated_at": now,
        }

    def get_active_prompt(self) -> str:
        """Get the currently active prompt content.

        Returns:
            str: The active system prompt content (may contain {{variables}}).
        """
        data = self.load_prompts()
        active_key = data.get("active_prompt", "default")
        prompts = data.get("prompts", {})

        if active_key not in prompts:
            active_key = "default"

        prompt = prompts.get(active_key, {}).get("system", "")
        if not prompt:
            prompt = self.load_template("system")

        return prompt

    def get_active_prompt_name(self) -> str:
        """Get the name of the currently active prompt.

        Returns:
            str: The name of the active prompt.
        """
        data = self.load_prompts()
        active_key = data.get("active_prompt", "default")
        prompts = data.get("prompts", {})

        if active_key not in prompts:
            active_key = "default"

        return cast(str, prompts.get(active_key, {}).get("name", "default"))

    def list_prompts(self) -> list[dict[str, Any]]:
        """List all available prompts.

        Returns:
            list[dict[str, Any]]: List of prompts with their metadata.
        """
        data = self.load_prompts()
        prompts = data.get("prompts", {})
        active_key = data.get("active_prompt", "default")

        result = []
        for key, prompt in prompts.items():
            result.append({
                "key": key,
                "name": prompt.get("name", key),
                "description": prompt.get("description", ""),
                "is_active": key == active_key,
                "created_at": prompt.get("created_at", ""),
                "updated_at": prompt.get("updated_at", "")
            })

        return result

    def get_prompt(self, key: str) -> Optional[dict[str, Any]]:
        """Get a specific prompt by its key.

        Args:
            key: The key of the prompt to retrieve.

        Returns:
            Optional[dict[str, Any]]: The prompt dict if found, None otherwise.
        """
        data = self.load_prompts()
        prompts = data.get("prompts", {})
        return cast(Optional[dict[str, Any]], prompts.get(key))

    def add_prompt(self, key: str, name: str, description: str, system_prompt: str) -> bool:
        """Add a new prompt.

        Args:
            key: Unique identifier for the prompt.
            name: Display name for the prompt.
            description: Description of the prompt's purpose.
            system_prompt: The system prompt content.

        Returns:
            bool: True if prompt was added, False if key already exists.
        """
        data = self.load_prompts()
        prompts = data.get("prompts", {})

        if key in prompts:
            return False

        prompts[key] = {
            "name": name,
            "description": description,
            "system": system_prompt,
            "created_at": datetime.now().strftime("%Y-%m-%d"),
            "updated_at": datetime.now().strftime("%Y-%m-%d")
        }

        data["prompts"] = prompts
        data["updated_at"] = datetime.now().strftime("%Y-%m-%d")
        self.save_prompts(data)
        return True

    def update_prompt(self, key: str, updates: dict[str, Any]) -> bool:
        """Update an existing prompt.

        Args:
            key: The key of the prompt to update.
            updates: Dict containing fields to update (name, description, system).

        Returns:
            bool: True if prompt was found and updated, False otherwise.
        """
        data = self.load_prompts()
        prompts = data.get("prompts", {})

        if key not in prompts:
            return False

        for field in ("name", "description", "system"):
            if field in updates:
                prompts[key][field] = updates[field]

        prompts[key]["updated_at"] = datetime.now().strftime("%Y-%m-%d")

        data["prompts"] = prompts
        data["updated_at"] = datetime.now().strftime("%Y-%m-%d")
        self.save_prompts(data)
        return True

    def delete_prompt(self, key: str) -> bool:
        """Delete a prompt.

        Args:
            key: The key of the prompt to delete.

        Returns:
            bool: True if prompt was deleted, False if not found or if it's the last prompt.
        """
        data = self.load_prompts()
        prompts = data.get("prompts", {})

        if key not in prompts or len(prompts) <= 1:
            return False

        del prompts[key]

        if data.get("active_prompt") == key:
            data["active_prompt"] = "default" if "default" in prompts else list(prompts.keys())[0]

        data["prompts"] = prompts
        data["updated_at"] = datetime.now().strftime("%Y-%m-%d")
        self.save_prompts(data)
        return True

    def set_active_prompt(self, key: str) -> bool:
        """Set the active prompt.

        Args:
            key: The key of the prompt to activate.

        Returns:
            bool: True if prompt was activated, False if not found.
        """
        data = self.load_prompts()
        prompts = data.get("prompts", {})

        if key not in prompts:
            return False

        data["active_prompt"] = key
        data["updated_at"] = datetime.now().strftime("%Y-%m-%d")
        self.save_prompts(data)
        return True

    def validate_prompts(self, data: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """Validate prompts configuration.

        Args:
            data: The prompts data to validate, or None to load from file.

        Returns:
            dict[str, Any]: Validated prompts data.

        Raises:
            PromptValidationError: Validation failed.
        """
        if data is None:
            data = self.load_prompts()

        errors: list[str] = []

        if "prompts" not in data:
            errors.append("Missing required key: 'prompts'")
        elif not isinstance(data["prompts"], dict):
            errors.append("'prompts' must be an object")
        elif not data["prompts"]:
            errors.append("'prompts' cannot be empty")

        prompts = data.get("prompts", {})
        for key, prompt in prompts.items():
            if not isinstance(prompt, dict):
                errors.append(f"Prompt '{key}' must be an object")
                continue

            for field in ("name", "description", "system"):
                if field not in prompt:
                    errors.append(f"Prompt '{key}': Missing required field: '{field}'")
                elif not isinstance(prompt[field], str):
                    errors.append(f"Prompt '{key}': Field '{field}' must be a string")

        if errors:
            raise PromptValidationError("\n".join(errors))

        return data
