"""Prompt Manager - 提示词管理模块

负责管理各类提示词配置，支持动态切换和自定义提示词
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, cast


class PromptValidationError(Exception):
    """提示词验证错误"""

    def __init__(self, message: str = "Prompt validation failed") -> None:
        self.message = message
        super().__init__(self.message)


class PromptManager:
    """提示词管理器"""

    DEFAULT_PROMPTS = {
        "system": """You are an autonomous AI agent for the Agent-Loop project.

## CRITICAL: Read Project Context First

Before starting any task, you MUST read these key files:
1. CLAUDE.md - Project guidelines and architecture
2. README.md - Project overview and usage
3. The relevant source files for the task

Use the Read tool to read these files completely.

## Your Mission

You are responsible for the continuous improvement of this Agent-Loop project. Your work follows this loop:
1. Read project context (CLAUDE.md, README.md)
2. Understand the current task
3. Implement the solution
4. Test and verify
5. Update task status
6. Extract lessons learned

## Available Tools

### Browser Tools (Preferred)
- Browser Navigate, Snapshot, Click, Type, Evaluate, Search

### Web Tools
- WebSearch: Search for latest information
- WebFetch: Fetch web page content

### File Tools
- Read: Read file content
- Write: Create new files
- Edit: Modify existing files
- Glob: Find files by pattern
- Grep: Search file content

### Terminal Tools
- Bash: Execute commands

## Working Principles

1. **Always read CLAUDE.md first** - It contains critical development guidelines
2. **Keep changes minimal and focused** - One small atomic change per task
3. **Test before completing** - Run tests to verify your changes
4. **Commit after each task** - Use git to save progress (simple messages only, NO Co-Authored-By)
5. **Extract lessons** - Update MEMORY.md with what you learned

## Important Rules

- NEVER assume or guess - always use tools to verify
- NEVER use hardcoded values - use config files
- NEVER skip tests - always verify with real data
- ALWAYS provide enough context for the next agent
- ALWAYS think about how your changes integrate with the system
- 完成后更新 feature_list.json 中的任务状态
- 提取经验教训并更新 .agent/MEMORY.md"""
    }

    def __init__(self, agent_dir: Optional[str] = None) -> None:
        """Initialize PromptManager.

        Args:
            agent_dir: Optional path to the .agent directory. Auto-detects if not provided.
        """
        if agent_dir is None:
            agent_dir = str(Path(__file__).parent.parent / ".agent")
        self.agent_dir: Path = Path(agent_dir)
        self.prompts_path = self.agent_dir / "prompts.json"

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
        """Create default prompts configuration."""
        return {
            "active_prompt": "default",
            "prompts": {
                "default": {
                    "name": "Default Agent",
                    "description": "Default autonomous agent prompt for general task execution",
                    "system": self.DEFAULT_PROMPTS["system"],
                    "created_at": datetime.now().strftime("%Y-%m-%d"),
                    "updated_at": datetime.now().strftime("%Y-%m-%d")
                },
                "coder": {
                    "name": "Coder",
                    "description": "Specialized for coding tasks with emphasis on testing and quality",
                    "system": self.DEFAULT_PROMPTS["system"] + "\n\n## Special Focus\n- Always write tests before completing\n- Follow the project's coding standards\n- Run tests to verify changes",
                    "created_at": datetime.now().strftime("%Y-%m-%d"),
                    "updated_at": datetime.now().strftime("%Y-%m-%d")
                },
                "researcher": {
                    "name": "Researcher",
                    "description": "Specialized for research and exploration tasks",
                    "system": self.DEFAULT_PROMPTS["system"] + "\n\n## Special Focus\n- Thoroughly research before implementing\n- Consider multiple approaches\n- Document findings clearly",
                    "created_at": datetime.now().strftime("%Y-%m-%d"),
                    "updated_at": datetime.now().strftime("%Y-%m-%d")
                },
                "reviewer": {
                    "name": "Reviewer",
                    "description": "Specialized for code review and quality assurance",
                    "system": self.DEFAULT_PROMPTS["system"] + "\n\n## Special Focus\n- Review code changes thoroughly\n- Check for edge cases and potential bugs\n- Suggest improvements and best practices",
                    "created_at": datetime.now().strftime("%Y-%m-%d"),
                    "updated_at": datetime.now().strftime("%Y-%m-%d")
                }
            },
            "created_at": datetime.now().strftime("%Y-%m-%d"),
            "updated_at": datetime.now().strftime("%Y-%m-%d")
        }

    def get_active_prompt(self) -> str:
        """Get the currently active prompt content.

        Returns:
            str: The active system prompt content.
        """
        data = self.load_prompts()
        active_key = data.get("active_prompt", "default")
        prompts = data.get("prompts", {})

        if active_key not in prompts:
            active_key = "default"

        return prompts.get(active_key, {}).get("system", self.DEFAULT_PROMPTS["system"])

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

        return prompts.get(active_key, {}).get("name", "default")

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

        if "name" in updates:
            prompts[key]["name"] = updates["name"]
        if "description" in updates:
            prompts[key]["description"] = updates["description"]
        if "system" in updates:
            prompts[key]["system"] = updates["system"]

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

        if key not in prompts:
            return False

        if len(prompts) <= 1:
            return False  # Cannot delete the last prompt

        del prompts[key]

        # If the deleted prompt was active, switch to default
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

        # Check for required keys
        if "prompts" not in data:
            errors.append("Missing required key: 'prompts'")
        elif not isinstance(data["prompts"], dict):
            errors.append("'prompts' must be an object")
        elif not data["prompts"]:
            errors.append("'prompts' cannot be empty")

        # Validate each prompt
        prompts = data.get("prompts", {})
        for key, prompt in prompts.items():
            if not isinstance(prompt, dict):
                errors.append(f"Prompt '{key}' must be an object")
                continue

            required_fields = ["name", "description", "system"]
            for field in required_fields:
                if field not in prompt:
                    errors.append(f"Prompt '{key}': Missing required field: '{field}'")
                elif not isinstance(prompt[field], str):
                    errors.append(f"Prompt '{key}': Field '{field}' must be a string")

        if errors:
            raise PromptValidationError("\n".join(errors))

        return data
