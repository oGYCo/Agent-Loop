# Contributing to Agent-Loop

Thank you for your interest in contributing to Agent-Loop! This guide will help you get started.

## Code of Conduct

Please be respectful and professional in all interactions. We expect all contributors to adhere to our [Code of Conduct](CODE_OF_CONDUCT.md).

## Ways to Contribute

- **Bug Reports**: Help us identify issues
- **Feature Requests**: Suggest new functionality
- **Code Contributions**: Implement features or fix bugs
- **Documentation**: Improve docs and guides
- **Testing**: Add or improve test coverage

## Getting Started

### Prerequisites

- Python 3.11+
- uv (package manager)
- Git

### Development Environment Setup

1. **Fork and Clone**

```bash
git clone https://github.com/your-username/agent-loop.git
cd agent-loop
```

2. **Install Dependencies**

```bash
# Install with uv (recommended)
uv sync

# Or install dev dependencies
uv sync --group dev
```

3. **Create a Branch**

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/bug-description
```

4. **Verify Setup**

```bash
# Run tests to ensure everything works
uv run pytest tests/ -v

# Check type hints
uv run mypy agent/
```

## Development Workflow

### Code Style

We use the following tools for code quality:

- **Ruff**: Linting and formatting
- **MyPy**: Type checking

```bash
# Run linting
uv run ruff check agent/

# Auto-fix linting issues
uv run ruff check --fix agent/

# Type checking
uv run mypy agent/
```

### Writing Code

1. Follow PEP 8 style guidelines
2. Add type hints to all new functions
3. Write docstrings for public APIs
4. Keep functions focused and small

### Commit Messages

Use clear, descriptive commit messages:

```
feat: Add Slack notification support

- Add SlackNotifier class
- Support Block Kit message formatting
- Add webhook configuration options

Closes #123
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `refactor`: Code refactoring
- `test`: Adding tests
- `chore`: Maintenance

### Running Tests

```bash
# Run all tests
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_agent_core.py -v

# Run with coverage
uv run pytest tests/ --cov=agent --cov-report=term-missing

# Quick test (fail-fast)
uv run pytest tests/ -x -q
```

### Testing Guidelines

- All new code should have tests
- Tests should be deterministic (no flaky tests)
- Use descriptive test names
- Follow Arrange-Act-Assert pattern

```python
def test_task_selector_prioritizes_by_priority():
    # Arrange
    tasks = [
        {"priority": 3, "status": "pending", "passes": False},
        {"priority": 1, "status": "pending", "passes": False},
        {"priority": 2, "status": "pending", "passes": False},
    ]

    # Act
    selector = TaskSelector()
    selected = selector.select_task(tasks)

    # Assert
    assert selected["priority"] == 1
```

## Pull Request Process

### Before Submitting

1. **Run Tests**: Ensure all tests pass
2. **Run Linting**: Fix any linting issues
3. **Run Type Check**: Verify type hints
4. **Update Docs**: Document new features

### Creating a PR

1. Push your branch to your fork
2. Open a Pull Request against `main`
3. Fill out the PR template
4. Link related issues

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Refactoring

## Testing
Describe testing done

## Checklist
- [ ] Tests pass
- [ ] Linting passes
- [ ] Type hints added/updated
- [ ] Documentation updated
```

### Review Process

- At least one approval required
- Address all review comments
- Keep PRs focused and small

## Project Structure

```
agent-loop/
├── agent/                 # Main package
│   ├── agent_core.py     # Core agent logic
│   ├── task_selector.py  # Task selection
│   └── ...
├── tests/                 # Test suite
├── docs/                  # Documentation
├── dashboards/           # Grafana dashboards
├── static/               # Web dashboard
├── main.py              # CLI entry
├── api.py               # API server
└── pyproject.toml       # Project config
```

## Adding New Features

### New Agent Module

1. Create module in `agent/`
2. Add to `agent/__init__.py`
3. Add tests in `tests/`
4. Update documentation

### New CLI Command

1. Add to `main.py`
2. Add tests
3. Update README CLI Reference

### New API Endpoint

1. Add route in `api.py`
2. Add request/response models
3. Add tests
4. Update API documentation

## Questions?

- Open an issue for bugs/feature requests
- Use discussions for questions
- Join our community chat

## Recognition

Contributors will be recognized in:
- CONTRIBUTORS.md file
- Release notes
- GitHub contributors graph

---

Thank you for contributing to Agent-Loop!
