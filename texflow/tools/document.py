"""Document tool: create, ingest, outline, read, update."""

from __future__ import annotations

from pathlib import Path

from ..formatters import (
    format_blocks_as_prose,
    format_confirmation_warning,
    format_document_summary,
    format_ingest_result,
    format_outline,
    format_section_ingest_result,
    list_section_titles,
)
from ..ingestion import ingest_markdown, ingest_raw, parse_markdown_blocks
from ..model import (
    BibEntry,
    Bibliography,
    Document,
    DocumentClass,
    Layout,
    Metadata,
    Section,
)
from .state import (
    auto_save,
    check_confirmation,
    clear_doc,
    get_doc,
    get_output_dir,
    require_doc,
    set_confirmation,
    set_doc,
)


def _looks_like_path(source: str) -> bool:
    """Check if source could plausibly be a file path (not inline content)."""
    return "\n" not in source and len(source) < 4096


def document_tool(
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
    - bib_add: Add a bibliography entry (provide BibTeX-format entry as source).
    - bib_remove: Remove a bibliography entry by key (provide key as source).
    - bib_list: List all bibliography entries.
    - bib_style: Set bibliography style (provide style name as source, e.g. "authoryear", "numeric").
    """
    match action:
        case "create":
            return _create(document_class, title, author, date, abstract)
        case "ingest":
            return _ingest(source, section)
        case "outline":
            return _outline()
        case "read":
            return _read(section)
        case "update":
            return _update(title, author, date, abstract)
        case "reset":
            return _reset()
        case "bib_add":
            return _bib_add(source)
        case "bib_remove":
            return _bib_remove(source)
        case "bib_list":
            return _bib_list()
        case "bib_style":
            return _bib_style(source)
        case _:
            return f"Unknown action: {action}. Valid actions: create, ingest, outline, read, update, reset, bib_add, bib_remove, bib_list, bib_style"


def _create(
    doc_class: str | None,
    title: str | None,
    author: str | None,
    date: str | None,
    abstract: str | None,
) -> str:
    cls = DocumentClass.ARTICLE
    if doc_class:
        try:
            cls = DocumentClass(doc_class.lower())
        except ValueError:
            valid = ", ".join(c.value for c in DocumentClass)
            return f"Unknown document class: {doc_class}. Valid classes: {valid}"

    # Guard against accidental whole-document replacement
    existing = get_doc()
    if existing is not None:
        confirmed = check_confirmation(
            "create", document_class=cls.value, title=title, author=author,
        )
        if confirmed is None:
            desc = format_document_summary(existing)
            set_confirmation(
                "create", desc, document_class=cls.value, title=title, author=author,
            )
            return format_confirmation_warning(
                desc,
                action_verb="Creating a new document",
                tool_hint="document(action='create')",
            )

    doc = Document(
        metadata=Metadata(
            title=title or "",
            author=author or "",
            date=date or "\\today",
            abstract=abstract or "",
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


def _update(
    title: str | None,
    author: str | None,
    date: str | None,
    abstract: str | None,
) -> str:
    try:
        doc = require_doc()
    except ValueError as e:
        return str(e)
    changes: list[str] = []

    if title is not None:
        doc.metadata.title = title
        changes.append(f"title={title!r}")
    if author is not None:
        doc.metadata.author = author
        changes.append(f"author={author!r}")
    if date is not None:
        doc.metadata.date = date
        changes.append(f"date={date!r}")
    if abstract is not None:
        doc.metadata.abstract = abstract
        changes.append(f"abstract set ({len(abstract)} chars)")

    if not changes:
        return "No changes (no parameters provided)."

    auto_save()
    return f"Updated metadata: {', '.join(changes)}"


def _ingest(source: str | None, section: str | None = None) -> str:
    if not source:
        return "Error: 'source' is required. Provide markdown text or a file path."

    # Section-targeted ingest: append into existing section
    if section is not None:
        return _ingest_into_section(source, section)

    # Whole-document ingest: check for destructive overwrite
    existing = get_doc()
    if existing is not None:
        confirmed = check_confirmation("ingest", source=source)
        if confirmed is None:
            desc = format_document_summary(existing)
            set_confirmation("ingest", desc, source=source)
            return format_confirmation_warning(
                desc,
                action_verb="Ingesting",
                tool_hint="document(action='ingest')",
            )

    # Preserve existing layout through whole-document replacement
    existing_layout = existing.layout if existing is not None else None

    # Check if source is a file path
    if _looks_like_path(source):
        source_path = Path(source)
        if source_path.exists() and source_path.is_file():
            text = source_path.read_text(encoding="utf-8")
            if source_path.suffix.lower() == ".tex":
                from ..tex_ingestion import ingest_tex, parse_bib_file
                doc = ingest_tex(text)
                # Load sibling .bib file if present
                bib_path = source_path.parent / "references.bib"
                if bib_path.exists():
                    entries = parse_bib_file(bib_path.read_text(encoding="utf-8"))
                    if entries:
                        if doc.bibliography is None:
                            doc.bibliography = Bibliography()
                        doc.bibliography.entries = entries
            else:
                doc = ingest_markdown(text)
            if existing_layout is not None and not source_path.suffix.lower() == ".tex":
                doc.layout = existing_layout
            doc.save_path = get_output_dir() / "document.texflow.json"
            set_doc(doc)
            auto_save()
            return format_ingest_result(source_path.name, len(text), doc)

    # Treat as inline markdown text
    if source.strip().startswith("#") or source.strip().startswith("---"):
        doc = ingest_markdown(source)
    else:
        doc = ingest_raw(source)
    if existing_layout is not None:
        doc.layout = existing_layout
    doc.save_path = get_output_dir() / "document.texflow.json"
    set_doc(doc)
    auto_save()
    return format_ingest_result("text", len(source), doc)


def _ingest_into_section(source: str, section_path: str) -> str:
    """Ingest markdown content into an existing section."""
    doc = require_doc()

    target = doc.find_section(section_path)
    if target is None:
        available = list_section_titles(doc.content)
        return f"Error: Section not found: {section_path}\nAvailable sections: {', '.join(available)}"

    # Read source
    if _looks_like_path(source):
        source_path = Path(source)
        if source_path.exists() and source_path.is_file():
            text = source_path.read_text(encoding="utf-8")
            source_label = source_path.name
        else:
            text = source
            source_label = f"text ({len(text)} chars)"
    else:
        text = source
        source_label = f"text ({len(text)} chars)"

    blocks = parse_markdown_blocks(text, base_level=target.level)

    if not blocks:
        return f"No content found in {source_label}."

    target.content.extend(blocks)
    auto_save()

    block_count = len(blocks)
    section_count = sum(1 for b in blocks if isinstance(b, Section))
    return format_section_ingest_result(source_label, section_path, block_count, section_count)


def _reset() -> str:
    """Clear the current document and saved state file."""
    existing = get_doc()
    if existing is None:
        return "No document to reset."
    clear_doc()
    return "Document cleared. Use document(action='create') or document(action='ingest') to start fresh."


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


# --- Bibliography actions ---

import re

_RE_BIB_ENTRY = re.compile(
    r"@(\w+)\s*\{\s*([\w:./-]+)\s*,\s*(.*?)\s*\}$",
    re.DOTALL | re.MULTILINE,
)
_RE_BIB_FIELD = re.compile(r"(\w+)\s*=\s*\{([^}]*)\}")

_VALID_BIB_STYLES = {
    "authoryear", "numeric", "alphabetic", "authortitle",
    "verbose", "reading", "draft", "apa", "ieee", "nature",
    "science", "chicago-authordate", "mla",
}


def _parse_bibtex_entry(text: str) -> BibEntry | None:
    """Parse a single BibTeX entry string into a BibEntry."""
    m = _RE_BIB_ENTRY.search(text)
    if not m:
        return None
    entry_type = m.group(1).lower()
    key = m.group(2)
    body = m.group(3)
    fields: dict[str, str] = {}
    for fm in _RE_BIB_FIELD.finditer(body):
        fields[fm.group(1).lower()] = fm.group(2)
    return BibEntry(key=key, entry_type=entry_type, fields=fields)


def _bib_add(source: str | None) -> str:
    if not source:
        return "Error: 'source' is required. Provide a BibTeX entry, e.g.:\n@article{key, author={...}, title={...}, year={2024}}"
    doc = require_doc()
    entry = _parse_bibtex_entry(source)
    if not entry:
        return "Error: Could not parse BibTeX entry. Expected format:\n@type{key, field = {value}, ...}"
    if doc.bibliography is None:
        doc.bibliography = Bibliography()
    existing = doc.bibliography.find_entry(entry.key)
    if existing:
        return f"Error: Entry with key '{entry.key}' already exists. Remove it first or use a different key."
    doc.bibliography.entries.append(entry)
    auto_save()
    fields_summary = ", ".join(f"{k}={v[:30]}..." if len(v) > 30 else f"{k}={v}" for k, v in entry.fields.items())
    return f"Added @{entry.entry_type}{{{entry.key}}} ({fields_summary}). {len(doc.bibliography.entries)} total entries."


def _bib_remove(source: str | None) -> str:
    if not source:
        return "Error: 'source' is required. Provide the citation key to remove."
    doc = require_doc()
    if not doc.bibliography or not doc.bibliography.entries:
        return "No bibliography entries to remove."
    key = source.strip()
    before = len(doc.bibliography.entries)
    doc.bibliography.entries = [e for e in doc.bibliography.entries if e.key != key]
    if len(doc.bibliography.entries) == before:
        return f"Error: No entry with key '{key}' found."
    auto_save()
    return f"Removed entry '{key}'. {len(doc.bibliography.entries)} entries remaining."


def _bib_list() -> str:
    doc = require_doc()
    if not doc.bibliography or not doc.bibliography.entries:
        return "No bibliography entries. Use document(action='bib_add', source='@article{key, ...}') to add entries."
    lines = [f"Bibliography ({len(doc.bibliography.entries)} entries, style: {doc.bibliography.style}):", ""]
    for entry in doc.bibliography.entries:
        title = entry.fields.get("title", "")
        author = entry.fields.get("author", "")
        year = entry.fields.get("year", "")
        summary = f"  @{entry.entry_type}{{{entry.key}}}"
        if author:
            summary += f" — {author}"
        if title:
            summary += f", \"{title}\""
        if year:
            summary += f" ({year})"
        lines.append(summary)
    return "\n".join(lines)


def _bib_style(source: str | None) -> str:
    if not source:
        return f"Error: 'source' is required. Valid styles: {', '.join(sorted(_VALID_BIB_STYLES))}"
    doc = require_doc()
    style = source.strip().lower()
    if style not in _VALID_BIB_STYLES:
        return f"Unknown style '{style}'. Valid styles: {', '.join(sorted(_VALID_BIB_STYLES))}"
    if doc.bibliography is None:
        doc.bibliography = Bibliography()
    doc.bibliography.style = style
    auto_save()
    return f"Bibliography style set to '{style}'."


