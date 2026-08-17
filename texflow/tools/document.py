"""Document tool: create, ingest, outline, read, update, clone, validate."""

from __future__ import annotations

import copy
import re
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
    Paragraph,
    Section,
    Table,
    Figure,
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
    variants_dir,
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
    keywords: list[str] | None = None,
    affiliations: list[str] | None = None,
    variant: str | None = None,
) -> str:
    """Create, ingest, and inspect documents.

    Actions:
    - create: Scaffold a new empty document. Optionally set class, title, author.
    - ingest: Parse markdown text or file path into the document model.
    - outline: Show document structure (sections, block counts).
    - read: Read content of a specific section as prose text.
    - update: Update document metadata (title, author, date, abstract, keywords, affiliations).
    - reset: Clear the current document and saved state. Next create/ingest starts fresh.
    - clone: Derive a variant document from the current one (e.g. ieee-conference
      cut-down from the Access version). Content is deep-copied; blocks are only
      shared with edit(action='share').
    - list_variants: List derived variants.
    - switch: Load a variant (provide its variant name).
    - validate: Structural QA pass (empty table cells, numeric consistency,
      missing identifying columns, absolute-unit figure widths).
    - bib_add: Add a bibliography entry (provide BibTeX-format entry as source).
    - bib_remove: Remove a bibliography entry by key (provide key as source).
    - bib_list: List all bibliography entries.
    - bib_style: Set bibliography style (provide style name as source, e.g. "authoryear", "numeric").
    """
    match action:
        case "create":
            return _create(document_class, title, author, date, abstract, keywords, affiliations)
        case "ingest":
            return _ingest(source, section)
        case "outline":
            return _outline()
        case "read":
            return _read(section)
        case "update":
            return _update(title, author, date, abstract, keywords, affiliations)
        case "reset":
            return _reset()
        case "clone":
            return _clone(document_class)
        case "list_variants":
            return _list_variants()
        case "switch":
            return _switch(variant)
        case "validate":
            return _validate()
        case "bib_add":
            return _bib_add(source)
        case "bib_remove":
            return _bib_remove(source)
        case "bib_list":
            return _bib_list()
        case "bib_style":
            return _bib_style(source)
        case _:
            return (f"Unknown action: {action}. Valid actions: create, ingest, outline, read, update, "
                    "reset, clone, list_variants, switch, validate, bib_add, bib_remove, bib_list, bib_style")


def _create(
    doc_class: str | None,
    title: str | None,
    author: str | None,
    date: str | None,
    abstract: str | None,
    keywords: list[str] | None = None,
    affiliations: list[str] | None = None,
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
            keywords=keywords or [],
            affiliations=affiliations or [],
        ),
        layout=Layout(document_class=cls),
        save_path=get_output_dir() / "document.texflow.json",
    )
    if cls.is_ieee:
        # IEEE classes are always two-column; the layout knob stays consistent
        doc.layout.columns = 2
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
    keywords: list[str] | None = None,
    affiliations: list[str] | None = None,
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
    if keywords is not None:
        doc.metadata.keywords = keywords
        changes.append(f"keywords={keywords!r}")
    if affiliations is not None:
        doc.metadata.affiliations = affiliations
        changes.append(f"affiliations={affiliations!r}")

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


# --- Variant workflow (multi-paper) ---

_VARIANT_SAFE = re.compile(r"[^\w.-]+")


def _clone(doc_class: str | None) -> str:
    """Derive a variant document from the current one.

    Deep-copies all content — blocks are NOT shared by default. To make a
    block live-shared across variants (fix once, both update), use
    edit(action='share') on the source document.
    """
    if not doc_class:
        return "Error: 'document_class' is required for clone (e.g. 'ieee-conference')."
    try:
        cls = DocumentClass(doc_class.lower())
    except ValueError:
        valid = ", ".join(c.value for c in DocumentClass)
        return f"Unknown document class: {doc_class}. Valid classes: {valid}"

    try:
        doc = require_doc()
    except ValueError as e:
        return str(e)

    variant_doc = copy.deepcopy(doc)
    variant_doc.layout = copy.deepcopy(doc.layout)
    variant_doc.layout.document_class = cls
    variant_doc.metadata = copy.deepcopy(doc.metadata)
    if cls.is_ieee:
        variant_doc.layout.columns = 2

    name = f"{cls.value}"
    vdir = variants_dir()
    vdir.mkdir(parents=True, exist_ok=True)
    save_path = vdir / f"{_VARIANT_SAFE.sub('-', name)}.texflow.json"
    variant_doc.save_path = save_path

    # Record the derivation on both sides
    base_name = doc.save_path.name if doc.save_path else "document.texflow.json"
    if save_path.name not in doc.variants:
        doc.variants.append(save_path.name)
        auto_save()
    variant_doc.variants = list(doc.variants)
    variant_doc.shared = doc.shared

    set_doc(variant_doc)
    variant_doc.save(save_path)
    auto_save()
    return (
        f"Cloned '{base_name}' → {cls.value} variant at {save_path}.\n"
        "Content is deep-copied: trim and rephrase freely. Use "
        "edit(action='share', ...) if a block should stay identical across "
        "both variants (fix once, both update)."
    )


def _list_variants() -> str:
    vdir = variants_dir()
    if not vdir.exists():
        return "No variants yet. Use document(action='clone', document_class='ieee-conference')."
    files = sorted(p for p in vdir.iterdir() if p.suffix == ".json")
    if not files:
        return "No variants yet. Use document(action='clone', document_class='ieee-conference')."
    current = get_doc()
    current_name = current.save_path.name if current and current.save_path else ""
    lines = ["Variants:"]
    for p in files:
        marker = " (current)" if p.name == current_name else ""
        lines.append(f"  - {p.name}{marker}")
    return "\n".join(lines)


def _switch(variant: str | None) -> str:
    if not variant:
        return "Error: 'variant' is required (see document(action='list_variants'))."
    path = variants_dir() / variant
    if not path.exists() and not variant.endswith(".json"):
        path = variants_dir() / f"{variant}.texflow.json"
    if not path.exists():
        return f"Error: variant '{variant}' not found. See document(action='list_variants')."
    current = get_doc()
    doc = Document.load(path)
    doc.shared = current.shared if current is not None else {}
    set_doc(doc)
    auto_save()
    return f"Switched to variant '{variant}' ({doc.layout.document_class.value})."


# --- Structural QA (review-artifact awareness) ---

_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")


def _walk_all_blocks(doc):
    """Yield (section_path, index, block) for every block, latest first."""
    def rec(blocks, prefix):
        for i, b in enumerate(blocks):
            yield prefix, i, b
            if isinstance(b, Section):
                yield from rec(b.content, f"{prefix}/{b.title}" if prefix else b.title)
    yield from rec(doc.content, "")


def _table_numbers(tbl: Table) -> list[str]:
    nums: list[str] = []
    for row in tbl.rows:
        for cell in row:
            nums.extend(_NUM_RE.findall(cell))
    if tbl.headers:
        for h in tbl.headers:
            nums.extend(_NUM_RE.findall(h))
    return nums


def _validate() -> str:
    """Structural QA: the kind of issues that slip past layout checks."""
    try:
        doc = require_doc()
    except ValueError as e:
        return str(e)

    findings: list[str] = []
    blocks = list(_walk_all_blocks(doc))

    # Numeric consistency: abstract + prose numbers vs table numbers
    prose_nums: list[str] = []
    if doc.metadata.abstract:
        prose_nums.extend(_NUM_RE.findall(doc.metadata.abstract))
    for _, _, b in blocks:
        if isinstance(b, Paragraph):
            prose_nums.extend(_NUM_RE.findall(b.text))
    table_nums: dict[str, str] = {}
    for _, _, b in blocks:
        if isinstance(b, Table):
            table_nums[b.label or b.caption or "table"] = ", ".join(_table_numbers(b))

    def _sig_digits(s: str) -> str:
        # Significant digits only: "0.912" / "91.2" / "0.9125" -> "912",
        # "0.03" -> "3". Catches unit shifts (91.2 vs 0.912) and precision
        # drift (0.912 vs 0.9125); ignores p-value columns (0.03 vs 0.912).
        return re.sub(r"[^0-9]", "", s).lstrip("0")

    for label, nums in table_nums.items():
        for n in _NUM_RE.findall(nums):
            ns = _sig_digits(n)
            for p in prose_nums:
                if p == n:
                    continue  # exact agreement is fine
                ps = _sig_digits(p)
                same_scale = ps == ns or (
                    len(ps) >= 2 and len(ns) >= 2
                    and (ps.startswith(ns) or ns.startswith(ps))
                )
                if same_scale:
                    findings.append(
                        f"numeric inconsistency: '{p}' (abstract/prose) vs '{n}' ({label}) — "
                        "same figures, different value; verify which is correct"
                    )
                    break  # one flag per table number

    # Table cell QA + identifying columns
    for path, idx, b in blocks:
        if not isinstance(b, Table):
            continue
        loc = f"'{path}'[{idx}]" if path else f"[{idx}]"
        ncols = len(b.headers) if b.headers else (len(b.rows[0]) if b.rows else 0)
        if ncols == 0:
            findings.append(f"empty table at {loc} — no headers or rows")
            continue
        for r, row in enumerate(b.rows):
            if len(row) < ncols:
                findings.append(f"table at {loc} row {r + 1}: {ncols - len(row)} cell(s) missing")
            if row and any(not c.strip() for c in row):
                findings.append(f"table at {loc} row {r + 1}: empty cell(s); LaTeX will print a blank space")
        if b.headers and all(not h.strip() or _NUM_RE.match(h) for h in b.headers if h):
            findings.append(f"table at {loc}: all headers numeric/empty — missing identifying column names")

    # Figure width policy
    for path, idx, b in blocks:
        if isinstance(b, Figure):
            loc = f"'{path}'[{idx}]" if path else f"[{idx}]"
            if not re.match(r"^\d+(?:\.\d+)?\\(?:linewidth|textwidth|columnwidth)$", b.width):
                findings.append(
                    f"figure at {loc}: width '{b.width}' uses absolute units; "
                    "IEEE-safe sizing is a \\linewidth/\\textwidth/\\columnwidth fraction"
                )

    if not findings:
        return "Validation clean — no structural issues found."
    lines = [f"Validation found {len(findings)} issue(s):", ""]
    lines.extend(f"  - {f}" for f in findings)
    return "\n".join(lines)


# --- Bibliography actions ---

_VALID_BIB_STYLES = {
    "authoryear", "numeric", "alphabetic", "authortitle",
    "verbose", "reading", "draft", "apa", "ieee", "nature",
    "science", "chicago-authordate", "mla",
}


def _bib_add(source: str | None) -> str:
    if not source:
        return "Error: 'source' is required. Provide a BibTeX entry, e.g.:\n@article{key, author={...}, title={...}, year={2024}}"
    doc = require_doc()
    from ..tex_ingestion import parse_bib_entry
    entry = parse_bib_entry(source)
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


