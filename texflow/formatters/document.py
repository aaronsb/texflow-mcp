"""Formatters for the document tool: outlines, prose, confirmations, ingest results."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .primitives import truncate

if TYPE_CHECKING:
    from ..model import Block, Document


# --- Outline ---


def format_outline(doc: Document) -> str:
    """Format document structure as an outline."""
    from ..model import Section

    lines = ["Document outline:"]
    if doc.metadata.title:
        lines.append(f"  Title: {doc.metadata.title}")
    if doc.metadata.author:
        lines.append(f"  Author: {doc.metadata.author}")
    lines.append(f"  Class: {doc.layout.document_class.value}")
    lines.append(f"  Columns: {doc.layout.columns}")
    lines.append("")

    if not doc.content:
        lines.append("  (empty)")
    else:
        _outline_blocks(doc.content, lines, level=2)

    return "\n".join(lines)


def _outline_blocks(blocks: list[Block], lines: list[str], level: int = 0) -> None:
    """Recursively format block tree for outline display."""
    from ..model import Paragraph, Section

    prefix = " " * level
    for i, block in enumerate(blocks):
        if isinstance(block, Section):
            count = len([b for b in block.content if not isinstance(b, Section)])
            sub_count = len([b for b in block.content if isinstance(b, Section)])
            info = f"{count} blocks"
            if sub_count:
                info += f", {sub_count} subsections"
            lines.append(f"{prefix}[{i}] Section: {block.title} ({info})")
            _outline_blocks(block.content, lines, level + 2)
        else:
            type_name = type(block).__name__
            preview = ""
            if isinstance(block, Paragraph):
                preview = f": {truncate(block.text)}"
            lines.append(f"{prefix}[{i}] {type_name}{preview}")


# --- Prose rendering ---


def format_blocks_as_prose(blocks: list[Block]) -> str:
    """Render blocks as readable prose text."""
    from ..model import Paragraph, Section

    parts: list[str] = []
    for block in blocks:
        if isinstance(block, Section):
            parts.append(f"### {block.title}")
            parts.append(format_blocks_as_prose(block.content))
        elif isinstance(block, Paragraph):
            parts.append(block.text)
        else:
            type_name = type(block).__name__
            parts.append(f"[{type_name}]")
    return "\n\n".join(parts)


# --- Section titles ---


def list_section_titles(blocks: list[Block], prefix: str = "") -> list[str]:
    """Collect all section title paths from block tree."""
    from ..model import Section

    titles: list[str] = []
    for block in blocks:
        if isinstance(block, Section):
            path = f"{prefix}/{block.title}" if prefix else block.title
            titles.append(path)
            titles.extend(list_section_titles(block.content, path))
    return titles


# --- Confirmation warnings ---


def format_document_summary(doc: Document) -> str:
    """Summarize an existing document for confirmation warnings."""
    from ..model import Section

    parts = []
    if doc.metadata.title:
        parts.append(f"Title: {doc.metadata.title}")
    all_blocks = doc._walk_blocks(doc.content)
    section_count = sum(1 for b in all_blocks if isinstance(b, Section))
    parts.append(f"Content: {len(all_blocks)} block(s), {section_count} section(s)")
    return "\n".join(parts)


def format_confirmation_warning(description: str, action_verb: str, tool_hint: str) -> str:
    """Format a destructive-action confirmation warning.

    Args:
        description: Summary of the existing document (from format_document_summary).
        action_verb: What the action does, e.g. "Creating a new document" or "Ingesting".
        tool_hint: The call the agent should repeat, e.g. "document(action='create')".
    """
    return (
        f"Warning: A document already exists.\n"
        f"{description}\n\n"
        f"{action_verb} will discard all existing content.\n"
        f"Call {tool_hint} again with the same parameters to confirm."
    )


# --- Ingest results ---


def format_ingest_result(source_label: str, char_count: int, doc: Document) -> str:
    """Format the result of a whole-document ingest."""
    return f"Ingested {source_label} ({char_count} chars).\n\n{format_outline(doc)}"


def format_section_ingest_result(
    source_label: str, section_path: str, block_count: int, section_count: int,
) -> str:
    """Format the result of a section-targeted ingest."""
    parts = [f"Ingested {source_label} into section '{section_path}': {block_count} block(s)"]
    if section_count:
        parts.append(f" ({section_count} subsection(s))")
    parts.append(".")
    return "".join(parts)
