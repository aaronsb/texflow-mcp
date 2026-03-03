"""Document tool: create, ingest, outline, read."""

from __future__ import annotations

from pathlib import Path

from ..formatters import format_blocks_as_prose, format_outline, list_section_titles
from ..ingestion import ingest_markdown, ingest_raw
from ..model import (
    Document,
    DocumentClass,
    Layout,
    Metadata,
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
        return f"Ingested {source_path.name} ({len(text)} chars).\n\n{format_outline(doc)}"

    # Treat as inline markdown text
    if source.strip().startswith("#") or source.strip().startswith("---"):
        doc = ingest_markdown(source)
    else:
        doc = ingest_raw(source)
    doc.save_path = get_output_dir() / "document.texflow.json"
    set_doc(doc)
    auto_save()
    return f"Ingested text ({len(source)} chars).\n\n{format_outline(doc)}"


def _outline() -> str:
    doc = require_doc()
    return format_outline(doc)


def _read(section_path: str | None) -> str:
    doc = require_doc()

    if not section_path:
        # Return all content as prose
        return format_blocks_as_prose(doc.content)

    sec = doc.find_section(section_path)
    if sec is None:
        available = list_section_titles(doc.content)
        return f"Section not found: {section_path}\nAvailable sections: {', '.join(available)}"

    return format_blocks_as_prose(sec.content)


