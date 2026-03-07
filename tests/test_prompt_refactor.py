"""Verification tests for the refactored prompt template system."""
import tempfile
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.prompt_manager import render_template, scan_project_structure, PromptManager

def test_render_template():
    result = render_template("Hello {{name}}, you are {{role}}!", {"name": "Agent", "role": "assistant"})
    assert result == "Hello Agent, you are assistant!", f"Got: {result}"
    print("1. render_template basic: OK")

    # Safe substitution (missing vars left as-is)
    result = render_template("Hello {{name}}, your {{missing}} is great", {"name": "Agent"})
    assert "{{missing}}" in result, f"Got: {result}"
    assert "Agent" in result
    print("2. render_template safe: OK")

    # Empty variables
    result = render_template("No vars here", {})
    assert result == "No vars here"
    print("3. render_template no vars: OK")

    # Code block with braces should not break
    result = render_template("Code: {single} and {{var}}", {"var": "value"})
    assert "{single}" in result
    assert "value" in result
    print("4. render_template code-safe: OK")


def test_scan_project_structure():
    tree = scan_project_structure(".")
    assert "Agent-Loop/" in tree
    assert "agent/" in tree
    assert "__pycache__" not in tree
    # .git directory should be excluded (but .gitignore file is fine)
    assert "├── .git/" not in tree and "└── .git/" not in tree
    print("5. scan_project_structure: OK")
    print(f"   Tree preview: {tree[:200]}...")


def test_prompt_manager_templates():
    with tempfile.TemporaryDirectory() as td:
        pm = PromptManager(td)

        # Built-in template
        system = pm.load_template("system")
        assert "{{project_name}}" in system
        print("6. load_template builtin: OK")

        # User override
        os.makedirs(os.path.join(td, "prompt_templates"))
        with open(os.path.join(td, "prompt_templates", "system.md"), "w") as f:
            f.write("Custom system for {{project_name}}")
        overridden = pm.load_template("system")
        assert overridden == "Custom system for {{project_name}}"
        print("7. load_template override: OK")

        # render_template method
        rendered = pm.render_template("system", {"project_name": "MyProject"})
        assert rendered == "Custom system for MyProject"
        print("8. render_template method: OK")

        # scaffold
        pm2 = PromptManager(td + "/new")
        created = pm2.scaffold_templates()
        assert len(created) == 5
        print(f"9. scaffold_templates: OK ({len(created)} files)")

        # list_templates
        templates = pm2.list_templates()
        assert len(templates) >= 5
        print(f"10. list_templates: OK ({len(templates)} templates)")

        # reset_template
        pm2.save_template("system", "custom override")
        assert pm2.load_template("system") == "custom override"
        pm2.reset_template("system")
        assert "{{project_name}}" in pm2.load_template("system")
        print("11. reset_template: OK")

        # Unknown template raises ValueError
        try:
            pm.load_template("nonexistent_template_xyz")
            assert False, "Should have raised ValueError"
        except ValueError:
            print("12. unknown template raises ValueError: OK")


def test_prompt_manager_prompts_json():
    with tempfile.TemporaryDirectory() as td:
        pm = PromptManager(td)

        # Default prompts
        prompt = pm.get_active_prompt()
        assert "{{project_name}}" in prompt
        print("13. get_active_prompt: OK")

        # Active prompt name
        name = pm.get_active_prompt_name()
        assert name == "Default Agent"
        print("14. get_active_prompt_name: OK")

        # List prompts
        prompts = pm.list_prompts()
        keys = [p["key"] for p in prompts]
        assert "default" in keys
        assert "coder" in keys
        assert "researcher" in keys
        assert "reviewer" in keys
        print(f"15. list_prompts: OK ({len(prompts)} prompts)")

        # Add prompt
        result = pm.add_prompt("custom", "Custom", "A custom prompt", "Custom system prompt")
        assert result is True
        print("16. add_prompt: OK")

        # Set active
        pm.set_active_prompt("coder")
        assert pm.get_active_prompt_name() == "Coder"
        print("17. set_active_prompt: OK")

        # Update prompt
        pm.update_prompt("custom", {"name": "Modified Custom"})
        p = pm.get_prompt("custom")
        assert p is not None
        assert p["name"] == "Modified Custom"
        print("18. update_prompt: OK")

        # Delete prompt
        pm.delete_prompt("custom")
        assert pm.get_prompt("custom") is None
        print("19. delete_prompt: OK")


def test_all_builtin_templates_exist():
    expected = ["system", "task", "self_review", "memory_cleanup", "claude_md_cleanup"]
    pm = PromptManager("/tmp/nonexistent_test_dir")
    for name in expected:
        content = pm.get_builtin_template(name)
        assert content is not None, f"Missing builtin template: {name}"
        assert len(content) > 50, f"Template {name} too short"
    print(f"20. all builtin templates exist: OK ({len(expected)} templates)")


if __name__ == "__main__":
    test_render_template()
    test_scan_project_structure()
    test_prompt_manager_templates()
    test_prompt_manager_prompts_json()
    test_all_builtin_templates_exist()
    print("\n=== ALL TESTS PASSED ===")
