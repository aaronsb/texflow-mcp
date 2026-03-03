"""Ingest markdown or raw text into a Document model.

Uses mistune 3.x in AST mode to parse markdown into tokens,
then maps those tokens to the document model block types.
"""

from __future__ import annotations

import re

import mistune

from .model import (
    CodeBlock,
    Document,
    Equation,
    Figure,
    ItemList,
    ListItem,
    Metadata,
    Paragraph,
    RawLatex,
    Section,
    Table,
)


def ingest_markdown(source: str) -> Document:
    """Parse markdown text into a Document model."""
    md = mistune.create_markdown(renderer="ast", plugins=["table"])

    # Strip YAML frontmatter before parsing (mistune sees --- as thematic_break)
    stripped, had_frontmatter = _strip_frontmatter(source)
    tokens = md(stripped)

    doc = Document()
    doc.metadata = _extract_metadata(source)
    doc.content = _tokens_to_blocks(tokens, skip_title=doc.metadata.title)
    _normalize_section_levels(doc.content)
    return doc


def _strip_frontmatter(source: str) -> tuple[str, bool]:
    """Remove YAML frontmatter from markdown source."""
    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", source, re.DOTALL)
    if fm_match:
        return source[fm_match.end():], True
    return source, False


def ingest_raw(text: str) -> Document:
    """Wrap raw text as a single-paragraph document for scaffolding."""
    doc = Document()
    if text.strip():
        doc.content = [Paragraph(text=text.strip())]
    return doc


def _extract_metadata(source: str) -> Metadata:
    """Extract metadata from YAML frontmatter or first H1."""
    meta = Metadata()

    # Try YAML frontmatter
    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", source, re.DOTALL)
    if fm_match:
        for line in fm_match.group(1).splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                key = key.strip().lower()
                value = value.strip().strip("\"'")
                if key == "title":
                    meta.title = value
                elif key == "author":
                    meta.author = value
                elif key == "date":
                    meta.date = value
                elif key == "abstract":
                    meta.abstract = value
        return meta

    # Fall back: first H1 becomes title
    h1_match = re.match(r"^#\s+(.+)", source, re.MULTILINE)
    if h1_match:
        meta.title = h1_match.group(1).strip()

    return meta


def _tokens_to_blocks(tokens: list[dict], skip_title: str = "") -> list:
    """Convert mistune AST tokens into a list of document model Blocks.

    Headings create nested Section structures. Content between headings
    is placed inside the current section (or at top level if no heading yet).
    If skip_title is set, an H1 matching that title is skipped (already in metadata).
    """
    root: list = []
    section_stack: list[tuple[int, list]] = []  # (level, content_list)

    def current_container() -> list:
        if section_stack:
            return section_stack[-1][1]
        return root

    for token in tokens:
        tok_type = token.get("type", "")

        if tok_type == "heading":
            level = token.get("attrs", {}).get("level", 1)
            title = _flatten_children(token.get("children", []))

            # Skip H1 if it matches the title already in metadata
            if level == 1 and skip_title and title.strip() == skip_title.strip():
                continue

            # Pop sections at same or deeper level
            while section_stack and section_stack[-1][0] >= level:
                section_stack.pop()

            section = Section(title=title, level=level)
            current_container().append(section)
            section_stack.append((level, section.content))

        elif tok_type == "paragraph":
            text = _flatten_children(token.get("children", []))
            # Check if paragraph contains only an image
            children = token.get("children", [])
            if len(children) == 1 and children[0].get("type") == "image":
                img = children[0]
                # Alt text is in children, not attrs
                alt = _flatten_children(img.get("children", []))
                current_container().append(Figure(
                    path=img.get("attrs", {}).get("url", ""),
                    caption=alt,
                ))
            else:
                current_container().append(Paragraph(text=text))

        elif tok_type == "block_code":
            code = token.get("raw", token.get("text", ""))
            info = token.get("attrs", {}).get("info", "")
            current_container().append(CodeBlock(code=code, language=info))

        elif tok_type == "list":
            ordered = token.get("attrs", {}).get("ordered", False)
            start = token.get("attrs", {}).get("start", 1) or 1
            items = _parse_list_items(token.get("children", []))
            current_container().append(ItemList(
                items=items,
                ordered=ordered,
                start=start,
            ))

        elif tok_type == "table":
            tbl = _parse_table(token)
            if tbl:
                current_container().append(tbl)

        elif tok_type == "block_math":
            tex = token.get("raw", token.get("text", ""))
            current_container().append(Equation(tex=tex))

        elif tok_type == "thematic_break":
            current_container().append(RawLatex(tex="\\bigskip\\hrule\\bigskip"))

        elif tok_type == "block_quote":
            text = _flatten_block_tokens(token.get("children", []))
            current_container().append(RawLatex(
                tex=f"\\begin{{quote}}\n{text}\n\\end{{quote}}"
            ))

        elif tok_type == "block_html":
            raw = token.get("raw", token.get("text", ""))
            if raw.strip():
                current_container().append(RawLatex(tex=f"% HTML: {raw.strip()[:80]}"))

    return root


def _parse_list_items(children: list[dict]) -> list[ListItem]:
    items: list[ListItem] = []
    for child in children:
        if child.get("type") == "list_item":
            item_children = child.get("children", [])
            text_parts: list[str] = []
            nested: list = []
            for ic in item_children:
                if ic.get("type") == "paragraph":
                    text_parts.append(_flatten_children(ic.get("children", [])))
                elif ic.get("type") == "list":
                    # Nested list
                    ordered = ic.get("attrs", {}).get("ordered", False)
                    start = ic.get("attrs", {}).get("start", 1) or 1
                    sub_items = _parse_list_items(ic.get("children", []))
                    nested.append(ItemList(items=sub_items, ordered=ordered, start=start))
                else:
                    text_parts.append(_flatten_children(ic.get("children", [])))
            items.append(ListItem(
                text=" ".join(text_parts),
                children=nested,
            ))
    return items


def _parse_table(token: dict) -> Table | None:
    """Parse a mistune table token into a Table block."""
    children = token.get("children", [])
    headers: list[str] = []
    rows: list[list[str]] = []
    aligns: list[str] = []

    for child in children:
        child_type = child.get("type", "")
        if child_type == "table_head":
            for cell in child.get("children", []):
                if cell.get("type") == "table_cell":
                    headers.append(_flatten_children(cell.get("children", [])))
                    attrs = cell.get("attrs", {})
                    align = attrs.get("align", "left") or "left"
                    aligns.append(align[0])  # 'l', 'c', 'r'
        elif child_type == "table_body":
            for row_token in child.get("children", []):
                if row_token.get("type") == "table_row":
                    row: list[str] = []
                    for cell in row_token.get("children", []):
                        if cell.get("type") == "table_cell":
                            row.append(_flatten_children(cell.get("children", [])))
                    rows.append(row)

    if not headers and not rows:
        return None

    return Table(
        headers=headers,
        rows=rows,
        alignment=aligns if aligns else None,
    )


def _flatten_children(children: list[dict]) -> str:
    """Flatten inline token children back to markdown-like markup string."""
    parts: list[str] = []
    for child in children:
        tok_type = child.get("type", "")
        if tok_type == "text":
            parts.append(child.get("raw", child.get("text", "")))
        elif tok_type == "codespan":
            parts.append(f"`{child.get('raw', child.get('text', ''))}`")
        elif tok_type == "strong":
            inner = _flatten_children(child.get("children", []))
            parts.append(f"**{inner}**")
        elif tok_type == "emphasis":
            inner = _flatten_children(child.get("children", []))
            parts.append(f"*{inner}*")
        elif tok_type == "link":
            inner = _flatten_children(child.get("children", []))
            url = child.get("attrs", {}).get("url", "")
            parts.append(f"[{inner}]({url})")
        elif tok_type == "image":
            alt = child.get("attrs", {}).get("alt", "")
            src = child.get("attrs", {}).get("src", "")
            parts.append(f"![{alt}]({src})")
        elif tok_type == "inline_math":
            parts.append(f"${child.get('raw', child.get('text', ''))}$")
        elif tok_type == "softbreak":
            parts.append(" ")
        elif tok_type == "linebreak":
            parts.append("\n")
        else:
            # Recurse for unknown types with children
            if "children" in child:
                parts.append(_flatten_children(child["children"]))
            elif "raw" in child:
                parts.append(child["raw"])
            elif "text" in child:
                parts.append(child["text"])
    return "".join(parts)


def _flatten_block_tokens(tokens: list[dict]) -> str:
    """Flatten block-level tokens to a single text string."""
    parts: list[str] = []
    for token in tokens:
        if token.get("type") == "paragraph":
            parts.append(_flatten_children(token.get("children", [])))
        elif "children" in token:
            parts.append(_flatten_children(token["children"]))
    return "\n\n".join(parts)


def _normalize_section_levels(blocks: list, _offset: int | None = None) -> None:
    """Normalize section levels so the top-level sections start at level 1.

    If all top-level sections are H2 (e.g., because H1 was the title and was
    skipped), shift everything up so H2 becomes level 1, H3 becomes level 2, etc.
    """
    if _offset is None:
        # Find minimum section level at the top
        min_level = None
        for block in blocks:
            if isinstance(block, Section):
                if min_level is None or block.level < min_level:
                    min_level = block.level
        if min_level is None or min_level <= 1:
            return
        _offset = min_level - 1

    for block in blocks:
        if isinstance(block, Section):
            block.level = max(1, block.level - _offset)
            _normalize_section_levels(block.content, _offset)
