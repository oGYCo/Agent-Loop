"""Greeting module with a simple greeting function."""


def greeting(name: str = "World") -> str:
    """Return a greeting message.

    Args:
        name: The name to greet. Defaults to "World".

    Returns:
        A greeting message string.
    """
    return f"Hello, {name}!"
