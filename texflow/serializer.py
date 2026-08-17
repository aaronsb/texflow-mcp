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
    DocumentClass,
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


# Common TikZ libraries loaded whenever tikzpicture is detected.
# These cover 95%+ of real diagrams with negligible compile overhead.
_TIKZ_BASE_LIBRARIES = {
    "arrows.meta", "positioning", "calc", "shapes.geometric",
    "shapes.misc", "fit", "backgrounds",
}


def _detect_tikz_libraries(doc: Document) -> set[str]:
    """Scan RawLatex blocks for tikz features and return needed libraries.

    Loads a common base set whenever tikzpicture is found, plus any
    libraries declared in block preamble fields.
    """
    has_tikz = False
    libs: set[str] = set()
    for block in doc._walk_blocks(doc.content):
        if isinstance(block, RawLatex):
            if "tikzpicture" in block.tex:
                has_tikz = True
            # Collect from explicit preamble declarations
            for line in block.preamble:
                m = re.match(r"\\usetikzlibrary\{(.+)\}", line)
                if m:
                    for lib_name in m.group(1).split(","):
                        libs.add(lib_name.strip())
    if has_tikz:
        libs.update(_TIKZ_BASE_LIBRARIES)
    return libs


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
    # Citations: [@key] or [@key, note]
    for m in re.finditer(r"\[@[^\]]+\]", text):
        protected.append((m.start(), m.end(), m.group()))
    # Literal LaTeX citation commands (defensive: in case text contains \cite{} directly)
    for m in re.finditer(r"\\(?:cite|textcite|parencite|autocite|fullcite|nocite)(?:\[[^\]]*\])?\{[^}]+\}", text):
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
    # Citations: [@key, note] → \cite[note]{key}, [@key] → \cite{key}
    text = re.sub(r"\[@([\w:./-]+),\s*(.+?)\]", r"\\cite[\2]{\1}", text)
    text = re.sub(r"\[@([\w:./-]+)\]", r"\\cite{\1}", text)
    return text


# --- Preamble ---


def _ieee_author_blocks(meta) -> str:
    """Build \\IEEEauthorblockN/A scaffold from metadata.

    author is split on ' and '; affiliations are index-matched.
    Falls back to a plain \\author list when no affiliations are set.
    """
    names = [n.strip() for n in meta.author.split(" and ") if n.strip()]
    if not names:
        return ""
    if not meta.affiliations:
        return " and ".join(escape_latex(n) for n in names)
    blocks: list[str] = []
    for i, name in enumerate(names):
        affil = meta.affiliations[i] if i < len(meta.affiliations) else (
            meta.affiliations[-1] if meta.affiliations else ""
        )
        if affil:
            affil_tex = affil.replace("\\n", " \\\\ ")
            blocks.append(
                f"\\IEEEauthorblockN{{{escape_latex(name)}}}\n"
                f"\\IEEEauthorblockA{{\\textit{{{escape_latex(affil_tex)}}}}}"
            )
        else:
            blocks.append(f"\\IEEEauthorblockN{{{escape_latex(name)}}}")
    return "\n\\and\n".join(blocks)


def _documentclass_line(doc: Document) -> str:
    """Emit the \\documentclass line, class-aware for IEEE classes."""
    layout = doc.layout
    cls = layout.document_class
    if cls == DocumentClass.IEEE_ACCESS:
        return "\\documentclass{ieeeaccess}"
    if cls == DocumentClass.IEEE_CONFERENCE:
        # Official IEEEtran conference mode (WIECON-ECE uses this class)
        return "\\documentclass[10pt, conference, letterpaper]{IEEEtran}"
    class_options: list[str] = [layout.font_size, layout.paper_size]
    if layout.columns == 2:
        class_options.append("twocolumn")
    return f"\\documentclass[{','.join(class_options)}]{{{cls.value}}}"


def _preamble(doc: Document) -> str:
    lines: list[str] = []
    layout = doc.layout
    is_ieee = layout.document_class.is_ieee

    lines.append(_documentclass_line(doc))
    lines.append("")

    # IEEE class boilerplate: lockout override, CC BY 4.0 pubid (Access only),
    # running header, and author blocks — the agent never has to remember these.
    if is_ieee:
        lines.append("\\IEEEoverridecommandlockouts")
        if layout.document_class == DocumentClass.IEEE_ACCESS:
            lines.append(
                "\\IEEEpubid{\\begin{minipage}{\\textwidth}\\footnotesize "
                "This work is licensed under a Creative Commons Attribution 4.0 License. "
                "For more information, see "
                "\\href{https://creativecommons.org/licenses/by/4.0/}"
                "{https://creativecommons.org/licenses/by/4.0/}.\\end{minipage}}"
            )
        if doc.metadata.title:
            first_author = doc.metadata.author.split(" and ")[0].strip()
            runner = first_author or "Author"
            lines.append(f"\\markboth{{{escape_latex(runner)}}}{{{escape_latex(doc.metadata.title)}}}")
        if doc.metadata.title:
            lines.append(f"\\title{{{escape_latex(doc.metadata.title)}}}")
        author_tex = _ieee_author_blocks(doc.metadata)
        if author_tex:
            lines.append(f"\\author{{{author_tex}}}")
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

    # Resolve style stack
    style_preamble: list[str] = []
    if layout.styles:
        from .styles import resolve_style_stack
        style_pkgs, style_preamble = resolve_style_stack(layout.styles)
        packages.update(style_pkgs)

    # Biblatex is emitted separately with style option
    has_bib = "biblatex" in packages
    if has_bib:
        packages.discard("biblatex")

    # Sort for deterministic output
    for pkg in sorted(packages):
        options = _package_options(pkg, doc)
        if options:
            lines.append(f"\\usepackage[{options}]{{{pkg}}}")
        else:
            lines.append(f"\\usepackage{{{pkg}}}")

    # Biblatex after other packages
    if has_bib and doc.bibliography:
        bib_style = doc.bibliography.style or "authoryear"
        lines.append(f"\\usepackage[style={bib_style},backend=biber]{{biblatex}}")
        lines.append("\\addbibresource{references.bib}")

    lines.append("")

    # Auto-detect tikz library needs from raw content
    auto_tikz_libs: set[str] = set()
    if "tikz" in packages or "pgfplots" in packages:
        auto_tikz_libs = _detect_tikz_libraries(doc)
        if auto_tikz_libs:
            lines.append(f"\\usetikzlibrary{{{','.join(sorted(auto_tikz_libs))}}}")
        if "pgfplots" in packages:
            lines.append("\\pgfplotsset{compat=1.18}")
        if auto_tikz_libs or "pgfplots" in packages:
            lines.append("")

    # Style preamble lines (after packages, before block-level preamble)
    if style_preamble:
        for line in style_preamble:
            lines.append(line)
        lines.append("")

    # Extra preamble lines from RawLatex blocks (e.g., \usetikzlibrary)
    extra_preamble: list[str] = []
    seen: set[str] = set()
    for block in doc._walk_blocks(doc.content):
        if isinstance(block, RawLatex) and block.preamble:
            for line in block.preamble:
                # Skip usetikzlibrary if auto-detection already covers those libs
                if auto_tikz_libs and line.startswith("\\usetikzlibrary"):
                    m = re.match(r"\\usetikzlibrary\{(.+)\}", line)
                    if m and all(lib.strip() in auto_tikz_libs for lib in m.group(1).split(",")):
                        continue
                if line not in seen:
                    seen.add(line)
                    extra_preamble.append(line)
    if extra_preamble:
        for line in extra_preamble:
            lines.append(line)
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

    # Metadata (IEEE classes emit \title/\author in the class boilerplate above)
    if not is_ieee:
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
            # If styles are applied, only set colorlinks=true — let style \hypersetup handle colors
            if doc.layout.styles:
                return "colorlinks=true"
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

    if doc.layout.document_class.is_ieee:
        if doc.metadata.keywords:
            lines.append("")
            lines.append("\\begin{IEEEkeywords}")
            lines.append(", ".join(escape_latex(k) for k in doc.metadata.keywords))
            lines.append("\\end{IEEEkeywords}")

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
        lines.append(_serialize_block(block, doc))
        lines.append("")

    if use_multicol:
        lines.append(f"\\end{{multicols}}")
        lines.append("")

    return "\n".join(lines)


def _end_document(doc: Document) -> str:
    lines: list[str] = []

    if doc.bibliography and doc.bibliography.entries:
        if doc.layout.document_class.is_ieee:
            # IEEE classes use plain bibtex, not biblatex
            lines.append("\\bibliographystyle{IEEEtran}")
            lines.append("\\bibliography{references}")
        else:
            lines.append("\\printbibliography")
        lines.append("")

    lines.append("\\end{document}")
    return "\n".join(lines)


# --- Block serializers ---

_SECTION_COMMANDS = {1: "section", 2: "subsection", 3: "subsubsection"}


def _serialize_block(block: Block, doc: Document | None = None) -> str:
    if doc is not None:
        block = doc.resolve(block)
    match block:
        case Section():
            return _serialize_section(block, doc)
        case Paragraph():
            return _serialize_paragraph(block)
        case Figure():
            return _serialize_figure(block, doc)
        case Table():
            return _serialize_table(block, doc)
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


def _serialize_section(sec: Section, doc: Document | None = None) -> str:
    lines: list[str] = []

    # Page break before section ("none" explicitly opts out of layout default)
    break_mode = sec.page_break
    if break_mode == "none":
        break_mode = ""
    elif not break_mode and doc and doc.layout.section_break and sec.level == 1:
        break_mode = doc.layout.section_break
    if break_mode in ("before", "both"):
        lines.append("\\clearpage")

    cmd = _SECTION_COMMANDS.get(sec.level, "subsubsection")
    lines.append(f"\\{cmd}{{{escape_latex(sec.title)}}}")
    if sec.label:
        lines.append(f"\\label{{{sec.label}}}")
    lines.append("")
    for block in sec.content:
        lines.append(_serialize_block(block, doc))
        lines.append("")

    if break_mode in ("after", "both"):
        lines.append("\\clearpage")

    return "\n".join(lines)


def _serialize_paragraph(para: Paragraph) -> str:
    text = escape_latex(para.text)
    text = _convert_inline_markup(text)
    return text


def _serialize_figure(fig: Figure, doc: Document | None = None) -> str:
    span = fig.span_columns
    if doc is not None and (doc.layout.columns == 2 or doc.layout.document_class.is_ieee) and not span:
        # Auto-promote to figure* when wider than one column
        span = _is_wide_figure(fig, doc)
    env = "figure*" if span else "figure"
    lines = [
        f"\\begin{{{env}}}[{fig.position}]",
        "\\centering",
        f"\\includegraphics[width={fig.width}]{{{fig.path}}}",
    ]
    if fig.caption:
        lines.append(f"\\caption{{{escape_latex(fig.caption)}}}")
    if fig.label:
        lines.append(f"\\label{{{fig.label}}}")
    lines.append(f"\\end{{{env}}}")
    return "\n".join(lines)


def _is_wide_figure(fig: Figure, doc: Document) -> bool:
    """Heuristic: does the figure width exceed one column in a two-column layout?

    A \\textwidth-based fraction >= 0.55 of the full width cannot fit in a
    column (columns are roughly 0.48 of textwidth), so promote to figure*.
    \\columnwidth-relative widths are never promoted.
    """
    if doc.layout.columns != 2 and not doc.layout.document_class.is_ieee:
        return False
    m = re.match(r"^\s*(\d+(?:\.\d+)?)\s*\\(textwidth)\s*$", fig.width)
    if not m:
        return False
    return float(m.group(1)) >= 0.55


def _serialize_table(tbl: Table, doc: Document | None = None) -> str:
    ncols = len(tbl.headers) if tbl.headers else (len(tbl.rows[0]) if tbl.rows else 0)
    if ncols == 0:
        return "% Empty table"

    if tbl.alignment and len(tbl.alignment) == ncols:
        col_spec = " ".join(tbl.alignment)
    else:
        col_spec = " ".join(["l"] * ncols)

    if doc is not None and tbl.fit == "auto":
        tbl = _fit_table(tbl, doc, ncols)

    span = tbl.span_columns
    env = "table*" if span else "table"
    lines = [f"\\begin{{{env}}}[{tbl.position}]", "\\centering"]
    lines.extend(_table_body(tbl, ncols, col_spec))
    if tbl.caption:
        lines.append(f"\\caption{{{escape_latex(tbl.caption)}}}")
    if tbl.label:
        lines.append(f"\\label{{{tbl.label}}}")
    lines.append(f"\\end{{{env}}}")
    return "\n".join(lines)


# Estimated characters that fit in one textwidth, by column mode.
# Rough, calibration-free constants: ~90 chars at 12pt single-column article,
# ~48 chars per IEEE-style two-column column.
_FULL_WIDTH_CHARS = 90
_COLUMN_WIDTH_CHARS = 45


def _estimate_table_chars(tbl: Table, ncols: int) -> int:
    """Estimate rendered width of a table in characters (ignoring markup)."""
    widths = [0] * ncols
    if tbl.headers:
        for i, h in enumerate(tbl.headers[:ncols]):
            widths[i] = max(widths[i], len(h))
    for row in tbl.rows:
        for i, cell in enumerate(row[:ncols]):
            widths[i] = max(widths[i], len(cell))
    # 2 chars per cell padding + inter-column space, 1 for the leading edge
    return sum(widths) + ncols * 2 + 1


def _fit_table(tbl: Table, doc: Document, ncols: int) -> Table:
    """Apply width-fitting decisions for fit="auto".

    Priority:
    1. Two-column/IEEE layout: promote to table* when the table cannot fit a
       single column (the classic IEEE failure mode).
    2. Within the chosen width, fall back through tabularx (long text cells),
       resizebox (numeric-heavy, few rows), adjustbox (catch-all).
    Never silently clips.
    """
    from dataclasses import replace

    two_column = doc.layout.columns == 2 or doc.layout.document_class.is_ieee
    avail = _COLUMN_WIDTH_CHARS if two_column else _FULL_WIDTH_CHARS
    est = _estimate_table_chars(tbl, ncols)

    if two_column and not tbl.span_columns and est > avail:
        # Too wide for a column: span full width, then re-evaluate.
        tbl = replace(tbl, span_columns=True)
        avail = _FULL_WIDTH_CHARS

    if est <= avail:
        return tbl

    long_cells = any(len(c) > 25 for row in tbl.rows for c in row[:ncols])
    if long_cells:
        return replace(tbl, fit="tabularx")
    if est <= avail * 2:
        return replace(tbl, fit="resizebox")
    return replace(tbl, fit="adjustbox")


def _table_body(tbl: Table, ncols: int, col_spec: str) -> list[str]:
    """Emit the tabular core of a table, honoring the fit mode."""
    if tbl.fit == "tabularx":
        return _tabularx_body(tbl, ncols, col_spec)
    if tbl.fit == "resizebox":
        inner = _plain_tabular(tbl, ncols, col_spec)
        return [f"\\resizebox{{{tbl.width or '\\linewidth'}}}{{!}}{{"] + inner + ["}"]
    if tbl.fit == "adjustbox":
        inner = _plain_tabular(tbl, ncols, col_spec)
        return [f"\\adjustbox{{max width={tbl.width or '\\linewidth'}}}{{"] + inner + ["}"]
    return _plain_tabular(tbl, ncols, col_spec)


def _tabularx_body(tbl: Table, ncols: int, col_spec: str) -> list[str]:
    """tabularx with the widest column promoted to X."""
    cells = col_spec.split()
    if len(cells) < ncols:
        cells = ["l"] * ncols
    # Widest cell's column becomes flexible X
    col_lens = [len(c) for c in cells]
    widths = [0] * ncols
    if tbl.headers:
        for i, h in enumerate(tbl.headers[:ncols]):
            widths[i] = max(widths[i], len(h))
    for row in tbl.rows:
        for i, c in enumerate(row[:ncols]):
            widths[i] = max(widths[i], len(c))
    widest = widths.index(max(widths))
    cells[widest] = "X"
    lines = [f"\\begin{{tabularx}}{{{tbl.width or '\\linewidth'}}}{{{' '.join(cells)}}}"]
    lines.extend(_tablular_rows(tbl, ncols))
    lines.append("\\end{tabularx}")
    return lines


def _plain_tabular(tbl: Table, ncols: int, col_spec: str) -> list[str]:
    lines = [f"\\begin{{tabular}}{{{col_spec}}}"]
    lines.extend(_tablular_rows(tbl, ncols))
    lines.append("\\end{tabular}")
    return lines


def _tablular_rows(tbl: Table, ncols: int) -> list[str]:
    lines: list[str] = []
    if tbl.booktabs:
        lines.append("\\toprule")
    if tbl.headers:
        lines.append(" & ".join(escape_latex(h) for h in tbl.headers[:ncols]) + " \\\\")
        if tbl.booktabs:
            lines.append("\\midrule")
    for row in tbl.rows:
        cells = [escape_latex(c) for c in row[:ncols]]
        while len(cells) < ncols:
            cells.append("")
        lines.append(" & ".join(cells) + " \\\\")
    if tbl.booktabs:
        lines.append("\\bottomrule")
    return lines


_LISTINGS_LANGUAGES = {
    "abap", "acm", "acsl", "ada", "algol", "ant", "assembler", "awk",
    "bash", "basic", "c", "caml", "clean", "cobol", "comal", "command.com",
    "comsol", "csh", "delphi", "eiffel", "elan", "elisp", "erlang", "euphoria",
    "fortran", "gcl", "gnuplot", "go", "haskell", "html", "idl", "inform",
    "java", "jvmis", "ksh", "lisp", "llvm", "logo", "lua", "make",
    "mathematica", "matlab", "mercury", "metapost", "miranda", "ml", "modula-2",
    "mupad", "nastran", "oberon-2", "ocl", "octave", "oz", "pascal", "perl",
    "php", "plasm", "pli", "postscript", "pov", "prolog", "promela", "python",
    "r", "reduce", "rexx", "rsl", "ruby", "rust", "s", "sas", "scala", "scilab",
    "sh", "shelxl", "simula", "sparql", "sql", "swift", "tcl", "tex",
    "vbscript", "verilog", "vhdl", "vrml", "xml", "xslt",
}


def _serialize_code(cb: CodeBlock) -> str:
    options: list[str] = []
    if cb.language and cb.language.lower() in _LISTINGS_LANGUAGES:
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


_TEX_HEADER = (
    "% Generated by TeXFlow — do not edit.\n"
    "% Changes will be overwritten on next compile.\n"
    "% Use the TeXFlow edit() and layout() tools to modify the document."
)


def serialize(doc: Document) -> str:
    """Serialize a Document model to a complete .tex string."""
    parts = [
        _TEX_HEADER,
        _preamble(doc),
        _begin_document(doc),
        _body(doc),
        _end_document(doc),
    ]
    return "\n".join(parts)


def serialize_bib(doc: Document) -> str:
    """Serialize bibliography entries to BibTeX .bib format."""
    if not doc.bibliography or not doc.bibliography.entries:
        return ""
    parts = []
    for entry in doc.bibliography.entries:
        field_lines = ",\n".join(
            f"  {k} = {{{v}}}" for k, v in entry.fields.items()
        )
        parts.append(f"@{entry.entry_type}{{{entry.key},\n{field_lines}\n}}")
    return "\n\n".join(parts) + "\n"


# --- biblatex → bibtex compatibility scan (IEEE classes) ---

_BIBLATEX_ONLY_COMMANDS = {
    r"\parencite", r"\textcite", r"\autocite", r"\footcite", r"\smartcite",
    r"\citeauthor", r"\citeyear", r"\citetitle", r"\citeurl", r"\fullcite",
    r"\cites", r"\parencites", r"\autocites", r"\textcites", r"\footcites",
    r"\citealp", r"\citealt", r"\citeauthor*", r"\citeyearpar",
}

_BIBLATEX_ONLY_FIELDS = {
    "date", "journaltitle", "location", "origdate", "eventdate",
    "urldate", "pubstate", "langid", "shorttitle", "entrysubtype",
    "holder", "addendum", "related", "eprinttype", "eprintclass",
}

_BIBLATEX_CMD_RE = re.compile(
    r"\\(" + "|".join(
        re.escape(c.lstrip("\\").rstrip("*")) for c in _BIBLATEX_ONLY_COMMANDS
    ) + r")(?:\*)?(?:\[[^\]]*\])?\{",
)


def scan_biblatex_compat(doc: Document) -> list[str]:
    """Find biblatex-only constructs that would fail under plain bibtex.

    Returns human-readable findings (empty = IEEE bibtex path is safe).
    Only meaningful for IEEE classes, which switch to bibtex + IEEEtran.bst.
    """
    findings: list[str] = []

    for block in doc._walk_blocks(doc.content):
        text = ""
        if isinstance(block, Paragraph):
            text = block.text
        elif isinstance(block, RawLatex):
            text = block.tex
        if not text:
            continue
        for m in _BIBLATEX_CMD_RE.finditer(text):
            cmd = m.group(1)
            findings.append(
                f"biblatex-only command '\\{cmd}' in paragraph/raw block — "
                "plain bibtex does not define it; rewrite as \\cite{...}"
            )

    if doc.bibliography:
        for entry in doc.bibliography.entries:
            for field in entry.fields:
                if field.lower() in _BIBLATEX_ONLY_FIELDS:
                    findings.append(
                        f"biblatex-only field '{field}' in @{entry.entry_type}{{{entry.key}}} — "
                        "plain bibtex may ignore or mis-parse it; use year/journal/address instead"
                    )

    # De-duplicate, keep order
    seen: set[str] = set()
    unique = [f for f in findings if not (f in seen or seen.add(f))]
    return unique
