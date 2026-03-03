"""Document tool: create, ingest, outline, read."""

from __future__ import annotations

from pathlib import Path

from ..ingestion import ingest_markdown, ingest_raw
from ..model import (
    Document,
    DocumentClass,
    Layout,
    Metadata,
    Paragraph,
    Section,
)
from .state import auto_save, get_output_dir, require_doc, set_doc


def document_tool(
    action: str,
    document_class: str | None = None,
    title: str | None = None,
    author: str | None = None,
    source: str | None = None,
    section: str | None = None,
) -> str:
    """Create, ingest, and inspect documents.

    Actions:
    - create: Scaffold a new empty document. Optionally set class, title, author.
    - ingest: Parse markdown text or file path into the document model.
    - outline: Show document structure (sections, block counts).
    - read: Read content of a specific section as prose text.
    """
    match action:
        case "create":
            return _create(document_class, title, author)
        case "ingest":
            return _ingest(source)
        case "outline":
            return _outline()
        case "read":
            return _read(section)
        case _:
            return f"Unknown action: {action}. Valid actions: create, ingest, outline, read"


def _create(doc_class: str | None, title: str | None, author: str | None) -> str:
    cls = DocumentClass.ARTICLE
    if doc_class:
        try:
            cls = DocumentClass(doc_class.lower())
        except ValueError:
            valid = ", ".join(c.value for c in DocumentClass)
            return f"Unknown document class: {doc_class}. Valid classes: {valid}"

    doc = Document(
        metadata=Metadata(
            title=title or "",
            author=author or "",
        ),
        layout=Layout(document_class=cls),
        save_path=get_output_dir() / "document.texflow.json",
    )
    set_doc(doc)
    auto_save()

    parts = [f"Created new {cls.value} document."]
    if title:
        parts.append(f"Title: {title}")
    if author:
        parts.append(f"Author: {author}")
    parts.append("")
    parts.append("The document is empty. Use edit(action='insert') to add content,")
    parts.append("or layout() to configure typesetting.")
    return "\n".join(parts)


def _ingest(source: str | None) -> str:
    if not source:
        return "Error: 'source' is required. Provide markdown text or a file path."

    # Check if source is a file path
    source_path = Path(source)
    if source_path.exists() and source_path.is_file():
        text = source_path.read_text(encoding="utf-8")
        doc = ingest_markdown(text)
        doc.save_path = get_output_dir() / "document.texflow.json"
        set_doc(doc)
        auto_save()
        return f"Ingested {source_path.name} ({len(text)} chars).\n\n{_format_outline(doc)}"

    # Treat as inline markdown text
    if source.strip().startswith("#") or source.strip().startswith("---"):
        doc = ingest_markdown(source)
    else:
        doc = ingest_raw(source)
    doc.save_path = get_output_dir() / "document.texflow.json"
    set_doc(doc)
    auto_save()
    return f"Ingested text ({len(source)} chars).\n\n{_format_outline(doc)}"


def _outline() -> str:
    doc = require_doc()
    return _format_outline(doc)


def _read(section_path: str | None) -> str:
    doc = require_doc()

    if not section_path:
        # Return all content as prose
        return _blocks_to_prose(doc.content)

    sec = doc.find_section(section_path)
    if sec is None:
        available = _list_section_titles(doc.content)
        return f"Section not found: {section_path}\nAvailable sections: {', '.join(available)}"

    return _blocks_to_prose(sec.content)


# --- Helpers ---

def _format_outline(doc: Document) -> str:
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
        _outline_blocks(doc.content, lines, indent=2)

    return "\n".join(lines)


def _outline_blocks(blocks: list, lines: list[str], indent: int = 0) -> None:
    prefix = " " * indent
    for i, block in enumerate(blocks):
        if isinstance(block, Section):
            count = len([b for b in block.content if not isinstance(b, Section)])
            sub_count = len([b for b in block.content if isinstance(b, Section)])
            info = f"{count} blocks"
            if sub_count:
                info += f", {sub_count} subsections"
            lines.append(f"{prefix}[{i}] Section: {block.title} ({info})")
            _outline_blocks(block.content, lines, indent + 2)
        else:
            type_name = type(block).__name__
            preview = ""
            if isinstance(block, Paragraph):
                preview = f": {block.text[:60]}..." if len(block.text) > 60 else f": {block.text}"
            lines.append(f"{prefix}[{i}] {type_name}{preview}")


def _blocks_to_prose(blocks: list) -> str:
    parts: list[str] = []
    for block in blocks:
        if isinstance(block, Section):
            parts.append(f"### {block.title}")
            parts.append(_blocks_to_prose(block.content))
        elif isinstance(block, Paragraph):
            parts.append(block.text)
        else:
            type_name = type(block).__name__
            parts.append(f"[{type_name}]")
    return "\n\n".join(parts)


def _list_section_titles(blocks: list, prefix: str = "") -> list[str]:
    titles: list[str] = []
    for block in blocks:
        if isinstance(block, Section):
            path = f"{prefix}/{block.title}" if prefix else block.title
            titles.append(path)
            titles.extend(_list_section_titles(block.content, path))
    return titles
