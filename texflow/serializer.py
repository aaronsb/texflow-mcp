"""Serialize a Document model to a complete .tex file.

Three phases:
1. Preamble: documentclass, packages, fonts, geometry, headers
2. Body: walk block tree, dispatch per type
3. End: close document environment
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .model import (
    Block,
    CodeBlock,
    Document,
    Equation,
    Figure,
    HeaderFooter,
    ItemList,
    Layout,
    Paragraph,
    RawLatex,
    Section,
    Table,
)

_DATA_DIR = Path(__file__).parent / "data"
_FONT_MAP: dict | None = None


def _load_font_map() -> dict:
    global _FONT_MAP
    if _FONT_MAP is None:
        fp = _DATA_DIR / "font_map.json"
        if fp.exists():
            _FONT_MAP = json.loads(fp.read_text(encoding="utf-8"))
        else:
            _FONT_MAP = {}
    return _FONT_MAP


# --- LaTeX escaping ---

_LATEX_SPECIAL = re.compile(r"([&%$#_{}~^\\])")
_LATEX_ESCAPE_MAP = {
    "&": "\\&",
    "%": "\\%",
    "$": "\\$",
    "#": "\\#",
    "_": "\\_",
    "{": "\\{",
    "}": "\\}",
    "~": "\\textasciitilde{}",
    "^": "\\textasciicircum{}",
    "\\": "\\textbackslash{}",
}


def escape_latex(text: str) -> str:
    """Escape LaTeX special characters in plain text.

    Preserves inline math ($...$), bold (**...**), italic (*...*),
    inline code (`...`), and links ([text](url)).
    """
    # Extract protected spans first
    protected: list[tuple[int, int, str]] = []

    # Inline math: $...$
    for m in re.finditer(r"\$[^$]+\$", text):
        protected.append((m.start(), m.end(), m.group()))
    # Bold: **...**
    for m in re.finditer(r"\*\*[^*]+\*\*", text):
        protected.append((m.start(), m.end(), m.group()))
    # Italic: *...*  (but not **)
    for m in re.finditer(r"(?<!\*)\*(?!\*)[^*]+\*(?!\*)", text):
        protected.append((m.start(), m.end(), m.group()))
    # Inline code: `...`
    for m in re.finditer(r"`[^`]+`", text):
        protected.append((m.start(), m.end(), m.group()))
    # Links: [text](url)
    for m in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", text):
        protected.append((m.start(), m.end(), m.group()))

    if not protected:
        return _LATEX_SPECIAL.sub(lambda m: _LATEX_ESCAPE_MAP[m.group()], text)

    # Sort by position, non-overlapping
    protected.sort(key=lambda x: x[0])
    merged: list[tuple[int, int, str]] = []
    for start, end, span in protected:
        if merged and start < merged[-1][1]:
            continue  # skip overlapping
        merged.append((start, end, span))

    parts: list[str] = []
    pos = 0
    for start, end, span in merged:
        if pos < start:
            chunk = text[pos:start]
            parts.append(_LATEX_SPECIAL.sub(lambda m: _LATEX_ESCAPE_MAP[m.group()], chunk))
        parts.append(span)
        pos = end
    if pos < len(text):
        chunk = text[pos:]
        parts.append(_LATEX_SPECIAL.sub(lambda m: _LATEX_ESCAPE_MAP[m.group()], chunk))

    return "".join(parts)


def _convert_inline_markup(text: str) -> str:
    """Convert markdown-style inline markup to LaTeX commands.

    Handles: **bold**, *italic*, `code`, $math$ (passthrough), [text](url).
    """
    # Links first (before other processing)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\\href{\2}{\1}", text)
    # Bold
    text = re.sub(r"\*\*([^*]+)\*\*", r"\\textbf{\1}", text)
    # Italic (not bold)
    text = re.sub(r"(?<!\*)\*(?!\*)([^*]+)\*(?!\*)", r"\\textit{\1}", text)
    # Inline code
    text = re.sub(r"`([^`]+)`", r"\\texttt{\1}", text)
    return text


# --- Preamble ---


def _preamble(doc: Document) -> str:
    lines: list[str] = []
    layout = doc.layout

    # Document class with options
    class_options: list[str] = [layout.font_size, layout.paper_size]
    if layout.columns == 2:
        class_options.append("twocolumn")
    lines.append(f"\\documentclass[{','.join(class_options)}]{{{layout.document_class.value}}}")
    lines.append("")

    # Packages
    packages = doc.required_packages
    font_map = _load_font_map()

    # Add font packages
    for font_name in [layout.font_main, layout.font_sans, layout.font_mono]:
        if font_name and font_name in font_map:
            pkg_info = font_map[font_name]
            if pkg_info.get("package"):
                packages.add(pkg_info["package"])

    # Sort for deterministic output
    for pkg in sorted(packages):
        options = _package_options(pkg, doc)
        if options:
            lines.append(f"\\usepackage[{options}]{{{pkg}}}")
        else:
            lines.append(f"\\usepackage{{{pkg}}}")

    lines.append("")

    # Line spacing
    if layout.line_spacing:
        if layout.line_spacing == 1.5:
            lines.append("\\onehalfspacing")
        elif layout.line_spacing == 2.0:
            lines.append("\\doublespacing")
        else:
            lines.append(f"\\linespread{{{layout.line_spacing}}}")
        lines.append("")

    # Header/footer
    if layout.header or layout.footer:
        lines.append("\\pagestyle{fancy}")
        lines.append("\\fancyhf{}")  # Clear defaults
        if layout.header:
            _emit_hf(lines, "head", layout.header)
        if layout.footer:
            _emit_hf(lines, "foot", layout.footer)
        else:
            lines.append("\\fancyfoot[C]{\\thepage}")
        lines.append("\\renewcommand{\\headrulewidth}{0.4pt}")
        lines.append("")

    # Metadata
    if doc.metadata.title:
        lines.append(f"\\title{{{escape_latex(doc.metadata.title)}}}")
    if doc.metadata.author:
        lines.append(f"\\author{{{escape_latex(doc.metadata.author)}}}")
    if doc.metadata.date:
        lines.append(f"\\date{{{doc.metadata.date}}}")
    if doc.metadata.title or doc.metadata.author:
        lines.append("")

    return "\n".join(lines)


def _package_options(pkg: str, doc: Document) -> str:
    """Return option string for a package, or empty string."""
    match pkg:
        case "inputenc":
            return "utf8"
        case "fontenc":
            return "T1"
        case "geometry":
            m = doc.layout.margins
            return f"top={m.top},bottom={m.bottom},left={m.left},right={m.right}"
        case "hyperref":
            return "colorlinks=true,linkcolor=blue,urlcolor=cyan,citecolor=green"
        case _:
            return ""


def _emit_hf(lines: list[str], kind: str, hf: HeaderFooter) -> None:
    if hf.left:
        lines.append(f"\\fancy{kind}[L]{{{hf.left}}}")
    if hf.center:
        lines.append(f"\\fancy{kind}[C]{{{hf.center}}}")
    if hf.right:
        lines.append(f"\\fancy{kind}[R]{{{hf.right}}}")


# --- Body ---


def _begin_document(doc: Document) -> str:
    lines: list[str] = ["\\begin{document}"]

    if doc.metadata.title:
        lines.append("\\maketitle")

    if doc.metadata.abstract:
        lines.append("")
        lines.append("\\begin{abstract}")
        lines.append(escape_latex(doc.metadata.abstract))
        lines.append("\\end{abstract}")

    if doc.layout.toc:
        lines.append("")
        lines.append("\\tableofcontents")
        lines.append("\\newpage")

    if doc.layout.lof:
        lines.append("\\listoffigures")

    if doc.layout.lot:
        lines.append("\\listoftables")

    lines.append("")
    return "\n".join(lines)


def _body(doc: Document) -> str:
    lines: list[str] = []
    use_multicol = doc.layout.columns > 2

    if use_multicol:
        lines.append(f"\\begin{{multicols}}{{{doc.layout.columns}}}")
        lines.append("")

    for block in doc.content:
        lines.append(_serialize_block(block))
        lines.append("")

    if use_multicol:
        lines.append(f"\\end{{multicols}}")
        lines.append("")

    return "\n".join(lines)


def _end_document(doc: Document) -> str:
    lines: list[str] = []

    if doc.bibliography and doc.bibliography.entries:
        lines.append(f"\\bibliographystyle{{{doc.bibliography.style}}}")
        lines.append("\\bibliography{references}")
        lines.append("")

    lines.append("\\end{document}")
    return "\n".join(lines)


# --- Block serializers ---

_SECTION_COMMANDS = {1: "section", 2: "subsection", 3: "subsubsection"}


def _serialize_block(block: Block) -> str:
    match block:
        case Section():
            return _serialize_section(block)
        case Paragraph():
            return _serialize_paragraph(block)
        case Figure():
            return _serialize_figure(block)
        case Table():
            return _serialize_table(block)
        case CodeBlock():
            return _serialize_code(block)
        case ItemList():
            return _serialize_list(block)
        case Equation():
            return _serialize_equation(block)
        case RawLatex():
            return block.tex
        case _:
            return f"% Unknown block type: {type(block).__name__}"


def _serialize_section(sec: Section) -> str:
    cmd = _SECTION_COMMANDS.get(sec.level, "subsubsection")
    lines = [f"\\{cmd}{{{escape_latex(sec.title)}}}"]
    if sec.label:
        lines.append(f"\\label{{{sec.label}}}")
    lines.append("")
    for block in sec.content:
        lines.append(_serialize_block(block))
        lines.append("")
    return "\n".join(lines)


def _serialize_paragraph(para: Paragraph) -> str:
    text = escape_latex(para.text)
    text = _convert_inline_markup(text)
    return text


def _serialize_figure(fig: Figure) -> str:
    lines = [
        f"\\begin{{figure}}[{fig.position}]",
        "\\centering",
        f"\\includegraphics[width={fig.width}]{{{fig.path}}}",
    ]
    if fig.caption:
        lines.append(f"\\caption{{{escape_latex(fig.caption)}}}")
    if fig.label:
        lines.append(f"\\label{{{fig.label}}}")
    lines.append("\\end{figure}")
    return "\n".join(lines)


def _serialize_table(tbl: Table) -> str:
    ncols = len(tbl.headers) if tbl.headers else (len(tbl.rows[0]) if tbl.rows else 0)
    if ncols == 0:
        return "% Empty table"

    if tbl.alignment and len(tbl.alignment) == ncols:
        col_spec = " ".join(tbl.alignment)
    else:
        col_spec = " ".join(["l"] * ncols)

    lines = [f"\\begin{{table}}[{tbl.position}]", "\\centering"]
    lines.append(f"\\begin{{tabular}}{{{col_spec}}}")

    if tbl.booktabs:
        lines.append("\\toprule")

    if tbl.headers:
        lines.append(" & ".join(escape_latex(h) for h in tbl.headers) + " \\\\")
        if tbl.booktabs:
            lines.append("\\midrule")

    for row in tbl.rows:
        cells = [escape_latex(c) for c in row]
        # Pad or trim to ncols
        while len(cells) < ncols:
            cells.append("")
        lines.append(" & ".join(cells[:ncols]) + " \\\\")

    if tbl.booktabs:
        lines.append("\\bottomrule")

    lines.append("\\end{tabular}")
    if tbl.caption:
        lines.append(f"\\caption{{{escape_latex(tbl.caption)}}}")
    if tbl.label:
        lines.append(f"\\label{{{tbl.label}}}")
    lines.append("\\end{table}")
    return "\n".join(lines)


def _serialize_code(cb: CodeBlock) -> str:
    options: list[str] = []
    if cb.language:
        options.append(f"language={cb.language}")
    if cb.caption:
        options.append(f"caption={{{escape_latex(cb.caption)}}}")
    if cb.label:
        options.append(f"label={{{cb.label}}}")

    opt_str = f"[{', '.join(options)}]" if options else ""
    lines = [f"\\begin{{lstlisting}}{opt_str}"]
    lines.append(cb.code)
    lines.append("\\end{lstlisting}")
    return "\n".join(lines)


def _serialize_list(lst: ItemList) -> str:
    env = "enumerate" if lst.ordered else "itemize"
    lines = [f"\\begin{{{env}}}"]
    if lst.ordered and lst.start != 1:
        lines.append(f"\\setcounter{{enumi}}{{{lst.start - 1}}}")
    for item in lst.items:
        lines.append(f"\\item {_convert_inline_markup(escape_latex(item.text))}")
        for child in item.children:
            lines.append(_serialize_block(child))
    lines.append(f"\\end{{{env}}}")
    return "\n".join(lines)


def _serialize_equation(eq: Equation) -> str:
    if eq.numbered:
        lines = ["\\begin{equation}"]
        if eq.label:
            lines.append(f"\\label{{{eq.label}}}")
        lines.append(eq.tex)
        lines.append("\\end{equation}")
    else:
        lines = ["\\[", eq.tex, "\\]"]
    return "\n".join(lines)


# --- Public API ---


def serialize(doc: Document) -> str:
    """Serialize a Document model to a complete .tex string."""
    parts = [
        _preamble(doc),
        _begin_document(doc),
        _body(doc),
        _end_document(doc),
    ]
    return "\n".join(parts)
