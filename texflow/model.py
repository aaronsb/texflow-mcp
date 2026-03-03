"""Document model for TeXFlow.

Dataclass hierarchy representing a LaTeX document at a semantic level.
The AI manipulates this model; the serializer converts it to .tex.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Union


class DocumentClass(Enum):
    ARTICLE = "article"
    REPORT = "report"
    BOOK = "book"
    MEMOIR = "memoir"
    LETTER = "letter"
    BEAMER = "beamer"


# --- Layout components ---


@dataclass
class Margins:
    top: str = "1in"
    bottom: str = "1in"
    left: str = "1in"
    right: str = "1in"


@dataclass
class HeaderFooter:
    left: str = ""
    center: str = ""
    right: str = ""


@dataclass
class Layout:
    document_class: DocumentClass = DocumentClass.ARTICLE
    columns: int = 1
    font_main: str | None = None
    font_sans: str | None = None
    font_mono: str | None = None
    font_size: str = "12pt"
    paper_size: str = "a4paper"
    margins: Margins = field(default_factory=Margins)
    header: HeaderFooter | None = None
    footer: HeaderFooter | None = None
    toc: bool = False
    lof: bool = False
    lot: bool = False
    line_spacing: float | None = None


# --- Metadata ---


@dataclass
class Metadata:
    title: str = ""
    author: str = ""
    date: str = "\\today"
    abstract: str = ""


# --- Bibliography ---


@dataclass
class BibEntry:
    key: str
    entry_type: str
    fields: dict[str, str] = field(default_factory=dict)


@dataclass
class Bibliography:
    style: str = "plain"
    entries: list[BibEntry] = field(default_factory=list)


# --- Content blocks ---


@dataclass
class Section:
    title: str
    level: int  # 1=section, 2=subsection, 3=subsubsection
    label: str = ""
    content: list[Block] = field(default_factory=list)


@dataclass
class Paragraph:
    text: str  # Inline markup: **bold**, *italic*, `code`, $math$, [text](url)


@dataclass
class Figure:
    path: str
    caption: str = ""
    label: str = ""
    width: str = "0.8\\textwidth"
    position: str = "htbp"


@dataclass
class Table:
    caption: str = ""
    label: str = ""
    headers: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    alignment: list[str] | None = None  # "l", "c", "r" per column
    position: str = "htbp"
    booktabs: bool = True


@dataclass
class CodeBlock:
    code: str
    language: str = ""
    caption: str = ""
    label: str = ""


@dataclass
class ItemList:
    items: list[ListItem] = field(default_factory=list)
    ordered: bool = False
    start: int = 1


@dataclass
class ListItem:
    text: str
    children: list[Block] = field(default_factory=list)


@dataclass
class Equation:
    tex: str  # Raw LaTeX math content
    numbered: bool = True
    label: str = ""


@dataclass
class RawLatex:
    tex: str  # Escape hatch: verbatim LaTeX


Block = Union[Section, Paragraph, Figure, Table, CodeBlock, ItemList, Equation, RawLatex]


# --- Document ---


@dataclass
class Document:
    metadata: Metadata = field(default_factory=Metadata)
    layout: Layout = field(default_factory=Layout)
    content: list[Block] = field(default_factory=list)
    bibliography: Bibliography | None = None
    save_path: Path | None = None  # Auto-persist location

    @property
    def required_packages(self) -> set[str]:
        """Packages needed based on current document state."""
        pkgs: set[str] = {"inputenc", "fontenc", "geometry", "hyperref"}

        layout = self.layout
        if layout.columns > 2:
            pkgs.add("multicol")
        if layout.header or layout.footer:
            pkgs.add("fancyhdr")
        if layout.line_spacing:
            pkgs.add("setspace")

        for block in self._walk_blocks(self.content):
            match block:
                case Figure():
                    pkgs.add("graphicx")
                case Table() if block.booktabs:
                    pkgs.add("booktabs")
                case CodeBlock():
                    pkgs.add("listings")
                case Equation():
                    pkgs.add("amsmath")
                    pkgs.add("amssymb")

        for block in self._walk_blocks(self.content):
            if isinstance(block, Paragraph) and "](http" in block.text:
                pkgs.add("hyperref")

        return pkgs

    def _walk_blocks(self, blocks: list[Block]) -> list[Block]:
        """Recursively collect all blocks including nested section content."""
        result: list[Block] = []
        for block in blocks:
            result.append(block)
            if isinstance(block, Section):
                result.extend(self._walk_blocks(block.content))
            elif isinstance(block, ItemList):
                for item in block.items:
                    result.extend(self._walk_blocks(item.children))
        return result

    def find_section(self, path: str) -> Section | None:
        """Find a section by title path (e.g., 'Methods/Data Collection')."""
        parts = path.split("/")
        blocks = self.content
        section = None
        for part in parts:
            found = False
            for block in blocks:
                if isinstance(block, Section) and block.title == part:
                    section = block
                    blocks = block.content
                    found = True
                    break
            if not found:
                return None
        return section

    def to_dict(self) -> dict:
        """Serialize document model to a JSON-compatible dict for persistence."""
        return _to_dict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Document:
        """Deserialize a document model from a dict."""
        return _from_dict(data)

    def save(self, path: Path | None = None) -> Path | None:
        """Persist the document model to a JSON file."""
        target = path or self.save_path
        if target is None:
            return None
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        self.save_path = target
        return target

    @classmethod
    def load(cls, path: Path) -> Document:
        """Load a document model from a JSON file."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        doc = cls.from_dict(data)
        doc.save_path = Path(path)
        return doc


# --- Serialization helpers ---

def _to_dict(obj) -> dict | list | str | int | float | bool | None:
    """Recursively serialize dataclass instances to dicts."""
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, set):
        return sorted(obj)
    if isinstance(obj, list):
        return [_to_dict(item) for item in obj]
    if isinstance(obj, dict):
        return {k: _to_dict(v) for k, v in obj.items()}
    if hasattr(obj, "__dataclass_fields__"):
        result = {"_type": type(obj).__name__}
        for name in obj.__dataclass_fields__:
            val = getattr(obj, name)
            if val is not None:
                result[name] = _to_dict(val)
        return result
    return obj


_BLOCK_TYPES: dict[str, type] = {
    "Section": Section,
    "Paragraph": Paragraph,
    "Figure": Figure,
    "Table": Table,
    "CodeBlock": CodeBlock,
    "ItemList": ItemList,
    "ListItem": ListItem,
    "Equation": Equation,
    "RawLatex": RawLatex,
}

_TOP_TYPES: dict[str, type] = {
    "Document": Document,
    "Metadata": Metadata,
    "Layout": Layout,
    "Margins": Margins,
    "HeaderFooter": HeaderFooter,
    "Bibliography": Bibliography,
    "BibEntry": BibEntry,
    **_BLOCK_TYPES,
}


def _from_dict(data) -> any:
    """Recursively deserialize dicts back to dataclass instances."""
    if isinstance(data, list):
        return [_from_dict(item) for item in data]
    if not isinstance(data, dict):
        return data
    type_name = data.get("_type")
    if type_name is None:
        return {k: _from_dict(v) for k, v in data.items()}

    cls = _TOP_TYPES.get(type_name)
    if cls is None:
        return data

    fields = {}
    for name, field_info in cls.__dataclass_fields__.items():
        if name in data:
            val = data[name]
            # Handle enum fields
            if field_info.type == "DocumentClass" or (
                hasattr(field_info, "type") and field_info.type is DocumentClass
            ):
                val = DocumentClass(val)
            elif name == "save_path" and val is not None:
                val = Path(val)
            else:
                val = _from_dict(val)
            fields[name] = val

    return cls(**fields)
