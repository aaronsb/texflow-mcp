"""Edit tool: structural content manipulation."""

from __future__ import annotations

from ..model import (
    Block,
    CodeBlock,
    Equation,
    Figure,
    ItemList,
    ListItem,
    Paragraph,
    RawLatex,
    Section,
    Table,
)
from .state import auto_save, require_doc


def edit_tool(
    action: str,
    block_type: str | None = None,
    section: str | None = None,
    position: int | None = None,
    content: str | None = None,
    title: str | None = None,
    level: int | None = None,
    language: str | None = None,
    path: str | None = None,
    caption: str | None = None,
    headers: list[str] | None = None,
    rows: list[list[str]] | None = None,
    target_section: str | None = None,
    target_position: int | None = None,
) -> str:
    """Manipulate document content structurally.

    Actions:
    - insert: Add a new block at a position within a section.
    - replace: Replace a block at a position with new content.
    - delete: Remove a block at a position.
    - move: Move a block from one location to another.

    Sections are addressed by title path (e.g., 'Methods/Data Collection').
    Blocks within a section are addressed by 0-based index.
    Use document(action='outline') to see current structure and indices.
    """
    match action:
        case "insert":
            return _insert(block_type, section, position, content, title, level,
                           language, path, caption, headers, rows)
        case "replace":
            return _replace(section, position, block_type, content, title, level,
                            language, path, caption, headers, rows)
        case "delete":
            return _delete(section, position)
        case "move":
            return _move(section, position, target_section, target_position)
        case _:
            return f"Unknown action: {action}. Valid: insert, replace, delete, move"


def _build_block(
    block_type: str | None,
    content: str | None = None,
    title: str | None = None,
    level: int | None = None,
    language: str | None = None,
    path: str | None = None,
    caption: str | None = None,
    headers: list[str] | None = None,
    rows: list[list[str]] | None = None,
) -> Block | str:
    """Build a Block from parameters. Returns error string on failure."""
    if not block_type:
        # Infer from what's provided
        if title and level:
            block_type = "section"
        elif path:
            block_type = "figure"
        elif headers or rows:
            block_type = "table"
        elif language:
            block_type = "code"
        elif content:
            block_type = "paragraph"
        else:
            return "Error: cannot infer block type. Provide block_type or sufficient parameters."

    match block_type:
        case "section":
            if not title:
                return "Error: section requires 'title'"
            return Section(title=title, level=level or 1)
        case "paragraph":
            if not content:
                return "Error: paragraph requires 'content'"
            return Paragraph(text=content)
        case "figure":
            if not path:
                return "Error: figure requires 'path' (image file path)"
            return Figure(path=path, caption=caption or "")
        case "table":
            return Table(
                caption=caption or "",
                headers=headers or [],
                rows=rows or [],
            )
        case "code":
            if not content:
                return "Error: code block requires 'content'"
            return CodeBlock(code=content, language=language or "", caption=caption or "")
        case "equation":
            if not content:
                return "Error: equation requires 'content' (LaTeX math)"
            return Equation(tex=content)
        case "list":
            if not content:
                return "Error: list requires 'content' (newline-separated items)"
            items = [ListItem(text=line.strip()) for line in content.splitlines() if line.strip()]
            return ItemList(items=items)
        case "raw":
            if not content:
                return "Error: raw block requires 'content' (LaTeX code)"
            return RawLatex(tex=content)
        case _:
            valid = "section, paragraph, figure, table, code, equation, list, raw"
            return f"Unknown block_type: {block_type}. Valid: {valid}"


def _get_container(section_path: str | None) -> tuple[list[Block], str]:
    """Get the block list to operate on. Returns (container, description)."""
    doc = require_doc()
    if not section_path:
        return doc.content, "document root"

    sec = doc.find_section(section_path)
    if sec is None:
        raise ValueError(f"Section not found: {section_path}")
    return sec.content, f"section '{section_path}'"


def _insert(block_type, section, position, content, title, level,
            language, path, caption, headers, rows) -> str:
    block = _build_block(block_type, content, title, level, language, path, caption, headers, rows)
    if isinstance(block, str):
        return block  # Error message

    try:
        container, desc = _get_container(section)
    except ValueError as e:
        return str(e)

    if position is None or position == -1 or position >= len(container):
        container.append(block)
        pos = len(container) - 1
    else:
        container.insert(position, block)
        pos = position

    auto_save()
    type_name = type(block).__name__
    return f"Inserted {type_name} at {desc}[{pos}]."


def _replace(section, position, block_type, content, title, level,
             language, path, caption, headers, rows) -> str:
    if position is None:
        return "Error: 'position' is required for replace."

    try:
        container, desc = _get_container(section)
    except ValueError as e:
        return str(e)

    if position < 0 or position >= len(container):
        return f"Error: position {position} out of range (0-{len(container)-1}) in {desc}."

    block = _build_block(block_type, content, title, level, language, path, caption, headers, rows)
    if isinstance(block, str):
        return block

    old_type = type(container[position]).__name__
    container[position] = block
    auto_save()
    new_type = type(block).__name__
    return f"Replaced {old_type} with {new_type} at {desc}[{position}]."


def _delete(section: str | None, position: int | None) -> str:
    if position is None:
        return "Error: 'position' is required for delete."

    try:
        container, desc = _get_container(section)
    except ValueError as e:
        return str(e)

    if position < 0 or position >= len(container):
        return f"Error: position {position} out of range (0-{len(container)-1}) in {desc}."

    removed = container.pop(position)
    auto_save()
    type_name = type(removed).__name__
    return f"Deleted {type_name} from {desc}[{position}]."


def _move(section: str | None, position: int | None,
          target_section: str | None, target_position: int | None) -> str:
    if position is None:
        return "Error: 'position' is required for move."

    try:
        src_container, src_desc = _get_container(section)
    except ValueError as e:
        return str(e)

    if position < 0 or position >= len(src_container):
        return f"Error: position {position} out of range (0-{len(src_container)-1}) in {src_desc}."

    block = src_container.pop(position)

    try:
        dst_container, dst_desc = _get_container(target_section)
    except ValueError as e:
        # Restore on failure
        src_container.insert(position, block)
        return str(e)

    if target_position is None or target_position == -1 or target_position >= len(dst_container):
        dst_container.append(block)
        dst_pos = len(dst_container) - 1
    else:
        dst_container.insert(target_position, block)
        dst_pos = target_position

    auto_save()
    type_name = type(block).__name__
    return f"Moved {type_name} from {src_desc}[{position}] to {dst_desc}[{dst_pos}]."
