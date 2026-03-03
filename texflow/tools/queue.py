"""Queue tool: execute multiple operations in a single call."""

from __future__ import annotations

from .state import auto_save, suppress_save
from .document import document_tool
from .layout import layout_tool
from .edit import edit_tool
from .render import render_tool
from .reference import reference_tool


def queue_tool(
    operations: list[dict],
    continue_on_error: bool = False,
) -> str:
    """Execute a queue of operations sequentially.

    Each operation is a dict with a 'tool' key and the arguments for that tool.
    Operations execute in order. Auto-save happens once at the end.

    Args:
        operations: List of operation dicts, each with 'tool' plus tool-specific args.
        continue_on_error: If False (default), stop on first error.
                          If True, execute all operations and report errors.

    Returns:
        Formatted results showing per-operation outcomes.
    """
    if not operations:
        return "Error: 'operations' list is empty."

    if len(operations) > 50:
        return "Error: maximum 50 operations per queue."

    results: list[tuple[int, str, str]] = []  # (index, status, message)
    stop_index = -1

    # Suppress per-operation saves; we'll save once at the end
    suppress_save(True)
    try:
        for i, op in enumerate(operations):
            if not isinstance(op, dict):
                msg = f"Operation must be a dict, got {type(op).__name__}"
                results.append((i, "error", msg))
                if not continue_on_error:
                    stop_index = i
                    break
                continue

            tool = op.get("tool")
            if not tool:
                msg = "Missing 'tool' key in operation"
                results.append((i, "error", msg))
                if not continue_on_error:
                    stop_index = i
                    break
                continue

            try:
                result = _dispatch(tool, op)
                is_error = _is_error_result(result)
                status = "error" if is_error else "ok"
                results.append((i, status, result))

                if is_error and not continue_on_error:
                    stop_index = i
                    break

            except Exception as e:
                results.append((i, "error", str(e)))
                if not continue_on_error:
                    stop_index = i
                    break
    finally:
        suppress_save(False)

    # Single save after all operations
    auto_save()

    return _format_results(results, len(operations), stop_index)


_ERROR_PREFIXES = (
    "Error:", "Unknown action", "Unknown block_type", "No document loaded",
    "Section not found", "File not found", "Compilation failed",
)


def _is_error_result(result: str) -> bool:
    """Detect whether a tool result string represents an error."""
    return any(result.startswith(p) for p in _ERROR_PREFIXES)


def _dispatch(tool: str, op: dict) -> str:
    """Dispatch a single operation to the appropriate tool function."""
    # Strip 'tool' key, pass the rest as kwargs
    kwargs = {k: v for k, v in op.items() if k != "tool"}

    match tool:
        case "document":
            return document_tool(**kwargs)
        case "layout":
            return layout_tool(**kwargs)
        case "edit":
            return edit_tool(**kwargs)
        case "render":
            return render_tool(**kwargs)
        case "reference":
            return reference_tool(**kwargs)
        case _:
            return f"Error: unknown tool '{tool}'. Valid: document, layout, edit, render, reference"


def _format_results(
    results: list[tuple[int, str, str]],
    total: int,
    stop_index: int,
) -> str:
    success_count = sum(1 for _, s, _ in results if s == "ok")
    error_count = sum(1 for _, s, _ in results if s == "error")

    lines = [f"Executed {len(results)} of {total} operations. Success: {success_count}, Errors: {error_count}"]

    if stop_index >= 0:
        lines.append(f"Stopped at operation {stop_index + 1} due to error.")

    lines.append("")

    for idx, status, msg in results:
        icon = "ok" if status == "ok" else "ERR"
        # First line of result only for compact display
        first_line = msg.split("\n")[0]
        lines.append(f"  [{idx + 1}] {icon}: {first_line}")

    return "\n".join(lines)
