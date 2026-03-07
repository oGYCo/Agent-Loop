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


def test_prompt_manager_caching():
    """Test caching mechanism for template loading."""
    import time as time_module

    with tempfile.TemporaryDirectory() as td:
        # Test 1: No cache by default (cache_ttl=None)
        pm = PromptManager(td)
        assert pm._cache_ttl is None
        assert pm._template_cache == {}
        print("21. cache disabled by default: OK")

        # Test 2: Enable caching with cache_ttl=0 (never expires)
        pm_with_cache = PromptManager(td, cache_ttl=0)
        assert pm_with_cache._cache_ttl == 0

        # First load should populate cache
        content1 = pm_with_cache.load_template("system")
        assert "system" in pm_with_cache._template_cache
        print("22. cache populated on first load: OK")

        # Second load should return cached content
        content2 = pm_with_cache.load_template("system")
        assert content1 == content2
        print("23. cache used for subsequent loads: OK")

        # Test 3: Manual clear_cache
        pm_with_cache.clear_cache()
        assert pm_with_cache._template_cache == {}
        print("24. clear_cache works: OK")

        # Test 4: refresh_template bypasses cache
        content_before = pm_with_cache.load_template("system")
        content_refreshed = pm_with_cache.refresh_template("system")
        assert content_before == content_refreshed
        # After refresh, should still have in cache
        assert "system" in pm_with_cache._template_cache
        print("25. refresh_template works: OK")

        # Test 5: Cache invalidation on save_template
        pm_save = PromptManager(td, cache_ttl=0)
        # Create template file first
        os.makedirs(os.path.join(td, "prompt_templates"))
        with open(os.path.join(td, "prompt_templates", "system.md"), "w") as f:
            f.write("Original content")

        # Load to populate cache
        pm_save.load_template("system")
        assert pm_save._template_cache["system"]["content"] == "Original content"

        # Save new content - should invalidate cache
        pm_save.save_template("system", "New content")

        # After save, cache should be cleared for that template
        # The next load should get fresh content (not cached)
        # But since we just saved, there's no cache entry anymore
        assert "system" not in pm_save._template_cache
        print("25a. cache invalidated on save_template: OK")

        # Test 6: Cache invalidation on reset_template
        pm_reset = PromptManager(td, cache_ttl=0)
        # Create and cache a custom template
        with open(os.path.join(td, "prompt_templates", "task.md"), "w") as f:
            f.write("Custom task template")
        pm_reset.load_template("task")
        assert pm_reset._template_cache["task"]["content"] == "Custom task template"

        # Reset should invalidate cache
        pm_reset.reset_template("task")
        assert "task" not in pm_reset._template_cache
        print("25b. cache invalidated on reset_template: OK")

        # Test 7: TTL expiration
        pm_ttl = PromptManager(td, cache_ttl=1)  # 1 second TTL
        content_ttl = pm_ttl.load_template("system")
        assert "system" in pm_ttl._template_cache

        # Wait for cache to expire
        time_module.sleep(1.5)

        # Cache should be expired, content should be reloaded
        content_ttl2 = pm_ttl.load_template("system")
        assert content_ttl == content_ttl2
        print("26. cache TTL expiration works: OK")

        # Test 8: use_cache=False bypasses cache
        pm_bypass = PromptManager(td, cache_ttl=0)
        # First create a user template file
        os.makedirs(os.path.join(td, "prompt_templates"), exist_ok=True)
        with open(os.path.join(td, "prompt_templates", "system.md"), "w") as f:
            f.write("File content")

        # Load normally to populate cache
        pm_bypass.load_template("system")

        # Manually modify cache to detect bypass
        pm_bypass._template_cache["system"]["content"] = "CACHED_CONTENT"

        # Load with use_cache=False should get actual file content
        actual_content = pm_bypass.load_template("system", use_cache=False)
        assert actual_content == "File content", f"Expected 'File content', got '{actual_content}'"
        print("27. use_cache=False bypasses cache: OK")


if __name__ == "__main__":
    test_render_template()
    test_scan_project_structure()
    test_prompt_manager_templates()
    test_prompt_manager_prompts_json()
    test_all_builtin_templates_exist()
    test_prompt_manager_caching()
    print("\n=== ALL TESTS PASSED ===")
