"""LaTeX file ingestion: parse .tex source back into the Document model."""

from __future__ import annotations

import re

from .model import (
    CodeBlock,
    Document,
    DocumentClass,
    Equation,
    Figure,
    ItemList,
    Layout,
    ListItem,
    Margins,
    Metadata,
    Paragraph,
    RawLatex,
    Section,
    Table,
)

# --- Regex patterns ---

_RE_DOCUMENTCLASS = re.compile(r"\\documentclass\[([^\]]*)\]\{(\w+)\}")
_RE_GEOMETRY = re.compile(r"\\usepackage\[([^\]]*)\]\{geometry\}")
_RE_TITLE = re.compile(r"\\title\{(.+)\}")
_RE_AUTHOR = re.compile(r"\\author\{(.+)\}")
_RE_DATE = re.compile(r"\\date\{(.+)\}")

_RE_SECTION = re.compile(r"\\(section|subsection|subsubsection)\{(.+)\}")
_RE_LABEL = re.compile(r"\\label\{([^}]+)\}")
_RE_BEGIN_ENV = re.compile(r"\\begin\{(\w+)\}(?:\[([^\]]*)\])?")
_RE_END_ENV = re.compile(r"\\end\{(\w+)\}")

_RE_INCLUDEGRAPHICS = re.compile(r"\\includegraphics\[([^\]]*)\]\{([^}]+)\}")
_RE_CAPTION = re.compile(r"\\caption\{(.+)\}")
_RE_TABULAR_BEGIN = re.compile(r"\\begin\{tabular\}\{([^}]+)\}")
_RE_LSTLISTING_OPTS = re.compile(r"\\begin\{lstlisting\}\[([^\]]*)\]")
_RE_SETCOUNTER = re.compile(r"\\setcounter\{enumi\}\{(\d+)\}")
_RE_DISPLAY_MATH_OPEN = re.compile(r"^\\\[$")
_RE_DISPLAY_MATH_CLOSE = re.compile(r"^\\\]$")

# Inline markup reversal
_RE_HREF = re.compile(r"\\href\{([^}]+)\}\{([^}]+)\}")
_RE_TEXTBF = re.compile(r"\\textbf\{([^}]+)\}")
_RE_TEXTIT = re.compile(r"\\textit\{([^}]+)\}")
_RE_TEXTTT = re.compile(r"\\texttt\{([^}]+)\}")

_SECTION_LEVELS = {"section": 1, "subsection": 2, "subsubsection": 3}

_SKIP_LINES = frozenset([
    "\\maketitle", "\\newpage", "\\clearpage", "\\cleardoublepage",
    "\\bigskip", "\\medskip", "\\smallskip", "\\noindent",
    "\\centering",
])

# Lines that set layout flags
_LAYOUT_LINES = {
    "\\tableofcontents": "toc",
    "\\listoffigures": "lof",
    "\\listoftables": "lot",
}

_UNESCAPE_MAP = [
    ("\\textasciitilde{}", "~"),
    ("\\textasciicircum{}", "^"),
    ("\\textbackslash{}", "\\"),
    ("\\&", "&"),
    ("\\%", "%"),
    ("\\$", "$"),
    ("\\#", "#"),
    ("\\_", "_"),
    ("\\{", "{"),
    ("\\}", "}"),
]


# --- Inline markup reversal ---


def _unescape_latex(text: str) -> str:
    """Reverse LaTeX escaping to recover plain text."""
    for latex, char in _UNESCAPE_MAP:
        text = text.replace(latex, char)
    return text


def _latex_inline_to_markdown(text: str) -> str:
    """Reverse LaTeX inline commands back to markdown-style markup.

    \\textbf{x} → **x**, \\textit{x} → *x*, \\texttt{x} → `x`,
    \\href{url}{text} → [text](url)
    """
    # href before others (both use braces)
    text = _RE_HREF.sub(r"[\2](\1)", text)
    text = _RE_TEXTBF.sub(r"**\1**", text)
    text = _RE_TEXTIT.sub(r"*\1*", text)
    text = _RE_TEXTTT.sub(r"`\1`", text)
    return text


def _convert_line(text: str) -> str:
    """Convert a line of LaTeX text back to markdown-style markup."""
    text = _latex_inline_to_markdown(text)
    text = _unescape_latex(text)
    return text


# --- Preamble parsing ---


def _parse_margins(opts: str) -> Margins:
    """Parse geometry options like 'top=1in,bottom=1in,...' into Margins."""
    margins = Margins()
    for part in opts.split(","):
        part = part.strip()
        if "=" in part:
            key, val = part.split("=", 1)
            key = key.strip()
            val = val.strip()
            if key in ("top", "bottom", "left", "right"):
                setattr(margins, key, val)
    return margins


def _parse_preamble(text: str) -> tuple[Metadata, Layout]:
    """Extract metadata and layout from LaTeX preamble."""
    meta = Metadata()
    layout = Layout()

    for line in text.splitlines():
        line = line.strip()

        # Document class
        m = _RE_DOCUMENTCLASS.match(line)
        if m:
            opts, cls = m.group(1), m.group(2)
            try:
                layout.document_class = DocumentClass(cls.lower())
            except ValueError:
                pass
            for opt in opts.split(","):
                opt = opt.strip()
                if opt.endswith("pt") and opt[:-2].isdigit():
                    layout.font_size = opt
                elif opt == "twocolumn":
                    layout.columns = 2
                elif opt in ("a4paper", "letterpaper", "a5paper", "b5paper", "legalpaper"):
                    layout.paper = opt
            continue

        # Geometry
        m = _RE_GEOMETRY.match(line)
        if m:
            layout.margins = _parse_margins(m.group(1))
            continue

        # Metadata
        m = _RE_TITLE.match(line)
        if m:
            meta.title = _unescape_latex(m.group(1))
            continue
        m = _RE_AUTHOR.match(line)
        if m:
            meta.author = _unescape_latex(m.group(1))
            continue
        m = _RE_DATE.match(line)
        if m:
            meta.date = m.group(1)
            continue

        # Line spacing
        if line == "\\onehalfspacing":
            layout.line_spacing = 1.5
        elif line == "\\doublespacing":
            layout.line_spacing = 2.0
        elif line.startswith("\\linespread{"):
            m2 = re.match(r"\\linespread\{([^}]+)\}", line)
            if m2:
                try:
                    layout.line_spacing = float(m2.group(1))
                except ValueError:
                    pass

    return meta, layout


# --- Environment parsers ---


def _parse_figure_env(lines: list[str], position: str) -> Figure:
    """Parse \\begin{figure}...\\end{figure} lines into a Figure block."""
    path = ""
    caption = ""
    label = ""
    width = "0.8\\textwidth"

    for line in lines:
        line = line.strip()
        m = _RE_INCLUDEGRAPHICS.search(line)
        if m:
            opts, path = m.group(1), m.group(2)
            wm = re.search(r"width=([^\],]+)", opts)
            if wm:
                width = wm.group(1)
            continue
        m = _RE_CAPTION.search(line)
        if m:
            caption = _unescape_latex(m.group(1))
            continue
        m = _RE_LABEL.search(line)
        if m:
            label = m.group(1)

    return Figure(path=path, caption=caption, label=label, width=width, position=position or "htbp")


def _parse_equation_env(lines: list[str]) -> Equation:
    """Parse \\begin{equation}...\\end{equation} lines into Equation."""
    label = ""
    tex_lines: list[str] = []
    for line in lines:
        m = _RE_LABEL.search(line.strip())
        if m:
            label = m.group(1)
        else:
            tex_lines.append(line)
    return Equation(tex="\n".join(tex_lines).strip(), numbered=True, label=label)


def _parse_code_env(lines: list[str], options: str) -> CodeBlock:
    """Parse \\begin{lstlisting}...\\end{lstlisting} lines into CodeBlock."""
    language = ""
    caption = ""
    label = ""

    if options:
        lm = re.search(r"language=(\w+)", options)
        if lm:
            language = lm.group(1)
        cm = re.search(r"caption=\{([^}]*)\}", options)
        if cm:
            caption = _unescape_latex(cm.group(1))
        lbl = re.search(r"label=\{([^}]*)\}", options)
        if lbl:
            label = lbl.group(1)

    return CodeBlock(code="\n".join(lines), language=language, caption=caption, label=label)


def _parse_table_env(lines: list[str], position: str) -> Table:
    """Parse \\begin{table}...\\end{table} lines into Table."""
    caption = ""
    label = ""
    headers: list[str] = []
    rows: list[list[str]] = []
    alignment: list[str] | None = None
    booktabs = False

    in_tabular = False
    after_toprule = False
    after_midrule = False

    for line in lines:
        stripped = line.strip()

        m = _RE_CAPTION.search(stripped)
        if m:
            caption = _unescape_latex(m.group(1))
            continue
        m = _RE_LABEL.search(stripped)
        if m:
            label = m.group(1)
            continue

        m = _RE_TABULAR_BEGIN.search(stripped)
        if m:
            col_spec = m.group(1)
            alignment = [c for c in col_spec if c in "lcr"]
            in_tabular = True
            continue

        if stripped == "\\end{tabular}":
            in_tabular = False
            continue

        if not in_tabular:
            continue

        if stripped in ("\\toprule", "\\bottomrule"):
            booktabs = True
            if stripped == "\\toprule":
                after_toprule = True
            continue
        if stripped == "\\midrule":
            booktabs = True
            after_midrule = True
            continue
        if stripped in ("\\hline",):
            continue
        if stripped in ("\\centering",):
            continue

        # Parse a data row: cell & cell & ... \\
        if "\\\\" in stripped:
            row_text = stripped.replace("\\\\", "").strip()
            if row_text:
                cells = [_unescape_latex(c.strip()) for c in row_text.split("&")]
                if after_toprule and not after_midrule:
                    headers = cells
                else:
                    rows.append(cells)

    return Table(
        caption=caption, label=label, headers=headers, rows=rows,
        alignment=alignment, position=position or "htbp", booktabs=booktabs,
    )


def _parse_list_env(lines: list[str], ordered: bool) -> ItemList:
    """Parse \\begin{itemize/enumerate}...\\end{...} lines into ItemList."""
    items: list[ListItem] = []
    start = 1
    current_text = ""

    for line in lines:
        stripped = line.strip()

        m = _RE_SETCOUNTER.search(stripped)
        if m:
            start = int(m.group(1)) + 1
            continue

        if stripped.startswith("\\item"):
            # Flush previous item
            if current_text:
                items.append(ListItem(text=_convert_line(current_text.strip())))
            current_text = stripped[5:].strip()  # text after \item
        elif stripped:
            # Continuation line
            if current_text:
                current_text += " " + stripped
            else:
                current_text = stripped

    # Flush last item
    if current_text:
        items.append(ListItem(text=_convert_line(current_text.strip())))

    return ItemList(items=items, ordered=ordered, start=start)


# --- Body parsing ---


def _parse_body(text: str) -> tuple[list, dict[str, bool]]:
    """Parse document body into blocks. Returns (blocks, layout_flags)."""
    root: list = []
    section_stack: list[tuple[int, list]] = []
    layout_flags: dict[str, bool] = {}

    def current_container() -> list:
        return section_stack[-1][1] if section_stack else root

    def flush_paragraph():
        nonlocal para_lines
        if para_lines:
            text = " ".join(para_lines)
            text = _convert_line(text)
            if text.strip():
                current_container().append(Paragraph(text=text))
            para_lines = []

    para_lines: list[str] = []
    lines = text.splitlines()
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Skip empty lines (flush paragraph)
        if not stripped:
            flush_paragraph()
            i += 1
            continue

        # Skip known layout/skip lines
        if stripped in _SKIP_LINES:
            flush_paragraph()
            i += 1
            continue

        # Layout flag lines
        if stripped in _LAYOUT_LINES:
            flush_paragraph()
            layout_flags[_LAYOUT_LINES[stripped]] = True
            i += 1
            continue

        # Abstract environment → metadata (handled by caller)
        if stripped.startswith("\\begin{abstract}"):
            flush_paragraph()
            abstract_lines: list[str] = []
            i += 1
            while i < len(lines):
                if lines[i].strip() == "\\end{abstract}":
                    break
                abstract_lines.append(lines[i])
                i += 1
            layout_flags["_abstract"] = "\n".join(abstract_lines)  # type: ignore[assignment]
            i += 1
            continue

        # Section commands
        m = _RE_SECTION.match(stripped)
        if m:
            flush_paragraph()
            cmd, title = m.group(1), m.group(2)
            level = _SECTION_LEVELS[cmd]
            title = _unescape_latex(title)

            # Pop sections at same or deeper level
            while section_stack and section_stack[-1][0] >= level:
                section_stack.pop()

            # Check for label on next line
            label = ""
            if i + 1 < len(lines):
                lm = _RE_LABEL.match(lines[i + 1].strip())
                if lm:
                    label = lm.group(1)
                    i += 1

            section = Section(title=title, level=level, label=label)
            current_container().append(section)
            section_stack.append((level, section.content))
            i += 1
            continue

        # Display math \[...\]
        if _RE_DISPLAY_MATH_OPEN.match(stripped):
            flush_paragraph()
            math_lines: list[str] = []
            i += 1
            while i < len(lines):
                if _RE_DISPLAY_MATH_CLOSE.match(lines[i].strip()):
                    break
                math_lines.append(lines[i])
                i += 1
            current_container().append(
                Equation(tex="\n".join(math_lines).strip(), numbered=False)
            )
            i += 1
            continue

        # Environment begin
        m_env = _RE_BEGIN_ENV.match(stripped)
        if m_env:
            flush_paragraph()
            env_name = m_env.group(1)
            env_opts = m_env.group(2) or ""

            # For lstlisting, check for options on same line
            if env_name == "lstlisting":
                m_lst = _RE_LSTLISTING_OPTS.match(stripped)
                if m_lst:
                    env_opts = m_lst.group(1)

            # Collect environment body
            env_lines: list[str] = []
            depth = 1
            i += 1
            while i < len(lines) and depth > 0:
                s = lines[i].strip()
                inner_m = _RE_BEGIN_ENV.match(s)
                if inner_m and inner_m.group(1) == env_name:
                    depth += 1
                end_m = _RE_END_ENV.match(s)
                if end_m and end_m.group(1) == env_name:
                    depth -= 1
                    if depth == 0:
                        break
                env_lines.append(lines[i])
                i += 1
            i += 1  # skip \end line

            # Dispatch to environment parser
            block = _dispatch_env(env_name, env_lines, env_opts)
            current_container().append(block)
            continue

        # Regular text line → accumulate for paragraph
        para_lines.append(stripped)
        i += 1

    flush_paragraph()
    return root, layout_flags


def _dispatch_env(env_name: str, lines: list[str], opts: str):
    """Dispatch environment to the appropriate parser."""
    match env_name:
        case "figure" | "figure*":
            return _parse_figure_env(lines, opts)
        case "table" | "table*":
            return _parse_table_env(lines, opts)
        case "equation" | "equation*":
            return _parse_equation_env(lines)
        case "lstlisting":
            return _parse_code_env(lines, opts)
        case "itemize":
            return _parse_list_env(lines, ordered=False)
        case "enumerate":
            return _parse_list_env(lines, ordered=True)
        case _:
            # Unknown environment → RawLatex
            env_text = f"\\begin{{{env_name}}}"
            if opts:
                env_text = f"\\begin{{{env_name}}}[{opts}]"
            env_text += "\n" + "\n".join(lines) + f"\n\\end{{{env_name}}}"
            return RawLatex(tex=env_text)


# --- Main entry point ---


def ingest_tex(source: str) -> Document:
    """Parse a LaTeX source string into a Document model.

    Handles TeXFlow-generated .tex files with near-lossless round-trip fidelity.
    External .tex files get best-effort parsing with unrecognized content
    falling back to RawLatex blocks.
    """
    # Split at \begin{document}
    marker = "\\begin{document}"
    idx = source.find(marker)
    if idx == -1:
        # No \begin{document} — treat entire source as body
        preamble_text = ""
        body_text = source
    else:
        preamble_text = source[:idx]
        body_text = source[idx + len(marker):]

    # Strip \end{document}
    end_marker = "\\end{document}"
    end_idx = body_text.rfind(end_marker)
    if end_idx != -1:
        body_text = body_text[:end_idx]

    # Parse phases
    metadata, layout = _parse_preamble(preamble_text)
    content, layout_flags = _parse_body(body_text)

    # Apply layout flags
    if layout_flags.get("toc"):
        layout.toc = True
    if layout_flags.get("lof"):
        layout.lof = True
    if layout_flags.get("lot"):
        layout.lot = True
    if "_abstract" in layout_flags:
        metadata.abstract = _unescape_latex(str(layout_flags["_abstract"]))

    return Document(metadata=metadata, layout=layout, content=content)
