"""Shared formatting functions for TeXFlow tool output.

Centralizes text formatting to ensure consistent, scannable output
across all MCP tools. Tools compute results; formatters shape text.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .model import Block, Document, Layout


# --- Shared primitives ---


def truncate(text: str, max_len: int = 60, suffix: str = "...") -> str:
    """Truncate text with suffix if it exceeds max_len."""
    if len(text) <= max_len:
        return text
    return text[: max_len - len(suffix)] + suffix


def truncate_list(items: list[str], max_items: int, noun: str = "more") -> list[str]:
    """Return items[:max_items] with an overflow indicator if needed."""
    if len(items) <= max_items:
        return list(items)
    return list(items[:max_items]) + [f"  ... and {len(items) - max_items} {noun}"]


def indent(text: str, level: int = 2) -> str:
    """Indent each line of text by level spaces."""
    prefix = " " * level
    return "\n".join(prefix + line for line in text.splitlines())


def status_icon(ok: bool) -> str:
    """Consistent status icon for result lines."""
    return "ok" if ok else "ERR"


# --- Document formatting ---


def format_outline(doc: Document) -> str:
    """Format document structure as an outline."""
    from .model import Section

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
    from .model import Paragraph, Section

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


def format_blocks_as_prose(blocks: list[Block]) -> str:
    """Render blocks as readable prose text."""
    from .model import Paragraph, Section

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


def list_section_titles(blocks: list[Block], prefix: str = "") -> list[str]:
    """Collect all section title paths from block tree."""
    from .model import Section

    titles: list[str] = []
    for block in blocks:
        if isinstance(block, Section):
            path = f"{prefix}/{block.title}" if prefix else block.title
            titles.append(path)
            titles.extend(list_section_titles(block.content, path))
    return titles


# --- Layout formatting ---


def format_layout(lo: Layout) -> str:
    """Format current layout configuration."""
    lines = [
        "Current layout:",
        f"  Class: {lo.document_class.value}",
        f"  Columns: {lo.columns}",
        f"  Font size: {lo.font_size}",
        f"  Paper: {lo.paper_size}",
        f"  Margins: top={lo.margins.top}, bottom={lo.margins.bottom}, left={lo.margins.left}, right={lo.margins.right}",
    ]
    if lo.font_main:
        lines.append(f"  Main font: {lo.font_main}")
    if lo.font_sans:
        lines.append(f"  Sans font: {lo.font_sans}")
    if lo.font_mono:
        lines.append(f"  Mono font: {lo.font_mono}")
    if lo.header:
        lines.append(f"  Header: L={lo.header.left!r} C={lo.header.center!r} R={lo.header.right!r}")
    if lo.footer:
        lines.append(f"  Footer: L={lo.footer.left!r} C={lo.footer.center!r} R={lo.footer.right!r}")
    lines.append(f"  TOC: {lo.toc}  LOF: {lo.lof}  LOT: {lo.lot}")
    if lo.line_spacing:
        lines.append(f"  Line spacing: {lo.line_spacing}")
    return "\n".join(lines)


# --- Render formatting ---


def format_compile_result(result) -> str:
    """Format compilation result (success/failure with errors and warnings)."""
    lines: list[str] = []
    if result.success:
        lines.append("Compilation successful.")
        if result.pdf_path:
            lines.append(f"PDF: {result.pdf_path}")
        if result.tex_path:
            lines.append(f"TeX: {result.tex_path}")
    else:
        lines.append("Compilation failed.")
        if result.tex_path:
            lines.append(f"TeX written to: {result.tex_path}")
        if result.errors:
            lines.append("")
            lines.append("Errors:")
            for err in result.errors:
                loc = f" (line {err.line})" if err.line else ""
                lines.append(f"  - {err.message}{loc}")

    if result.warnings:
        lines.append("")
        warning_lines = [f"  - {w}" for w in result.warnings]
        truncated = truncate_list(warning_lines, 5, "more warnings")
        lines.append(f"Warnings ({len(result.warnings)}):")
        lines.extend(truncated)

    return "\n".join(lines)
