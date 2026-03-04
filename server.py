"""TeXFlow MCP server — LaTeX document compiler with MCP interface."""

from __future__ import annotations

import sys
from pathlib import Path

from fastmcp import FastMCP

from texflow.tools.state import set_output_dir
from texflow.tools.document import document_tool
from texflow.tools.layout import layout_tool
from texflow.tools.edit import edit_tool
from texflow.tools.render import render_tool
from texflow.tools.reference import reference_tool
from texflow.tools.queue import queue_tool
from texflow.tools.workflow import state_hint, error_hint, WORKFLOW_MAP

mcp = FastMCP(
    "texflow",
    instructions=(
        "TeXFlow is a LaTeX document compiler. "
        "Use 'document' to create or ingest content, 'layout' to configure typesetting, "
        "'edit' to manipulate content structurally, 'render' to compile to PDF, "
        "'reference' for LaTeX documentation search, and "
        "'queue' to batch multiple operations in one call. "
        "Every response includes a workflow state hint showing where you are and what to do next."
    ),
)


def _with_hints(result: str) -> str:
    """Append workflow state hint and error guidance to a tool result."""
    extra = error_hint(result)
    return result + extra + state_hint()


# --- Workflow resource ---

@mcp.resource("texflow://workflow")
def workflow_map() -> str:
    """TeXFlow workflow map showing states and transitions."""
    return WORKFLOW_MAP + "\n" + state_hint()


# --- Document tool ---

@mcp.tool()
def document(
    action: str,
    document_class: str | None = None,
    title: str | None = None,
    author: str | None = None,
    date: str | None = None,
    abstract: str | None = None,
    source: str | None = None,
    section: str | None = None,
) -> str:
    """Create, ingest, and inspect documents.

    Actions:
    - create: Scaffold a new empty document. Optionally set class, title, author.
    - ingest: Parse markdown text or file path into the document model.
    - outline: Show document structure (sections, block counts).
    - read: Read content of a specific section as prose text.
    - update: Update document metadata (title, author, date, abstract).
    - reset: Clear the current document and saved state. Next create/ingest starts fresh.
    """
    return _with_hints(document_tool(
        action, document_class, title, author, date, abstract, source, section,
    ))


# --- Layout tool ---

@mcp.tool()
def layout(
    columns: int | None = None,
    font: str | None = None,
    font_sans: str | None = None,
    font_mono: str | None = None,
    font_size: str | None = None,
    paper: str | None = None,
    margins: str | None = None,
    header_left: str | None = None,
    header_center: str | None = None,
    header_right: str | None = None,
    footer_left: str | None = None,
    footer_center: str | None = None,
    footer_right: str | None = None,
    toc: bool | None = None,
    lof: bool | None = None,
    lot: bool | None = None,
    line_spacing: float | None = None,
    style: str | list[str] | None = None,
) -> str:
    """Configure document typesetting and layout.

    Only provided parameters are changed; others are left as-is.
    Returns the current full layout configuration after changes.
    """
    return _with_hints(layout_tool(
        columns, font, font_sans, font_mono, font_size, paper, margins,
        header_left, header_center, header_right,
        footer_left, footer_center, footer_right,
        toc, lof, lot, line_spacing, style,
    ))


# --- Edit tool ---

@mcp.tool()
def edit(
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
    template: str | None = None,
    lines: list[int] | None = None,
    lint: bool = True,
) -> str:
    """Manipulate document content structurally.

    Actions:
    - insert: Add a new block at a position within a section.
    - replace: Replace a block at a position with new content.
    - delete: Remove a block at a position.
    - move: Move a block from one location to another.
    - read_raw: Read a RawLatex block with line numbers.
    - replace_raw: Update a RawLatex block (full or line-level) with lint check.

    Sections are addressed by title path (e.g., 'Methods/Data Collection').
    Blocks within a section are addressed by 0-based index.
    Use document(action='outline') to see current structure and indices.
    """
    return _with_hints(edit_tool(
        action, block_type, section, position, content, title, level,
        language, path, caption, headers, rows, target_section, target_position,
        template, lines, lint,
    ))


# --- Render tool ---

@mcp.tool()
def render(
    action: str,
    output_path: str | None = None,
    page: int | None = None,
    dpi: int | None = None,
) -> str:
    """Compile and export the document.

    Actions:
    - compile: Serialize model to .tex, compile to PDF. Returns PDF path.
    - preview: Render a specific page as PNG file. Returns file path and dimensions.
    - tex: Export the raw .tex source. Returns the LaTeX content.
    """
    return _with_hints(render_tool(action, output_path, page, dpi))


# --- Reference tool ---

@mcp.tool()
def reference(
    action: str,
    query: str | None = None,
    description: str | None = None,
    name: str | None = None,
    error: str | None = None,
    topic: str | None = None,
    path: str | None = None,
) -> str:
    """Search LaTeX documentation, symbols, packages, and error solutions.

    Actions:
    - search: Search for LaTeX commands or general topics.
    - symbol: Find symbols by description (e.g., "approximately equal").
    - package: Get information about a LaTeX package.
    - check_style: Analyze a .tex file for best practices.
    - error_help: Get help for LaTeX error messages.
    - example: Get working examples for a topic (table, equation, figure, list, code).
    - templates: Browse available LaTeX templates. Optionally filter by category or slug.
    - capabilities: Enumerate system LaTeX support (engines, tools, packages).
    - styles: Browse document style presets. Optionally filter by slug or keyword.
    """
    return _with_hints(reference_tool(action, query, description, name, error, topic, path))


# --- Queue tool ---

@mcp.tool()
def queue(
    operations: list[dict],
    continue_on_error: bool = False,
) -> str:
    """Execute multiple operations in a single call.

    Each operation is a dict with 'tool' (document, layout, edit, render, reference)
    plus the arguments for that tool. Operations run sequentially; disk is written
    once at the end.

    Example:
        queue(operations=[
            {"tool": "document", "action": "create", "title": "My Doc"},
            {"tool": "edit", "action": "insert", "block_type": "section", "title": "Intro", "level": 1},
            {"tool": "edit", "action": "insert", "content": "Hello world.", "section": "Intro"},
            {"tool": "layout", "columns": 2, "font": "palatino"}
        ])

    Args:
        operations: List of operation dicts.
        continue_on_error: If False (default), stop on first error.
    """
    # Queue gets summary + state hint, no per-operation hints
    result = queue_tool(operations, continue_on_error)
    return result + state_hint()


def main():
    """Entry point for the texflow CLI."""
    # Optional workspace dir argument
    if len(sys.argv) > 1:
        workspace = Path(sys.argv[1])
        workspace.mkdir(parents=True, exist_ok=True)
        set_output_dir(workspace)

    mcp.run()


if __name__ == "__main__":
    main()
