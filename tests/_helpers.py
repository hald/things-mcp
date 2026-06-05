"""Shared test helpers."""


def tool_text(result):
    """Return the human-readable text from a tool result.

    Read tools now return a FastMCP ToolResult (text + structured_content);
    a few tools and error paths still return plain strings. This normalizes
    both so text-based assertions work either way.
    """
    if isinstance(result, str):
        return result
    return result.content[0].text
