# TeXFlow MCP

![License](https://img.shields.io/github/license/aaronsb/texflow-mcp)
![PyPI](https://img.shields.io/pypi/v/texflow-mcp)
![Python](https://img.shields.io/pypi/pyversions/texflow-mcp)

A LaTeX document compiler with an [MCP](https://modelcontextprotocol.io) interface. AI agents operate on a structured document model — sections, paragraphs, figures, tables — while TeXFlow handles all LaTeX mechanics: packages, preamble, fonts, and compilation.

## Install

```bash
pip install texflow-mcp
```

Or run without installing:

```bash
uvx texflow-mcp
```

### System dependencies (optional)

TeXFlow compiles documents to PDF using XeLaTeX (pdfLaTeX for the IEEE Access class). Without it, you can still build and export `.tex` files.

```bash
# Arch
pacman -S texlive-xetex texlive-fontsrecommended texlive-publishers

# Debian/Ubuntu
apt install texlive-xetex texlive-fonts-recommended texlive-publishers

# Fedora
dnf install texlive-xetex texlive-collection-fontsrecommended texlive-collection-publishers
```

`texlive-publishers` provides `IEEEtran.cls` for the IEEE classes. For page preview (PNG), install `poppler-utils` (provides `pdftoppm`).

## Configure with Claude Code

```bash
claude mcp add texflow -- uvx texflow-mcp
```

That's it. Restart Claude Code and the tools are available.

To set a workspace directory (where documents are saved):

```bash
claude mcp add texflow -- uvx texflow-mcp ~/Documents/TeXFlow
```

## Configure with Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "texflow": {
      "command": "uvx",
      "args": ["texflow-mcp"]
    }
  }
}
```

## How it works

TeXFlow has two entry flows, both converging on the same in-memory document model:

1. **Scaffold** — `document(action="create")` builds an empty document skeleton. Add content with `edit(action="insert")`.
2. **Markdown ingest** — `document(action="ingest", source="paper.md")` parses markdown into the model. Refine layout from there.

The model auto-saves to disk as JSON. LaTeX is only ever an output artifact — you never edit `.tex` directly. The model can be deep-copied into a different document class as a **variant** (`document(action="clone")`), and `edit(action="share")` registers a Table/Figure in a persisted shared store that every variant resolves at serialize time — fix once, both update. `document(action="switch")` moves between variants.

## Tools

| Tool | Purpose |
|------|---------|
| `document` | Create, ingest markdown, outline, read, update metadata, clone/switch variants, validate structure, manage bibliography |
| `layout` | Columns, fonts, paper, margins, headers/footers, TOC |
| `edit` | Insert, replace, delete, move, share/unshare blocks (section, paragraph, figure, table, code, equation, list, raw); table width fitting |
| `render` | Compile to PDF, preview page as PNG, export `.tex`, one-shot vision check |
| `reference` | Search LaTeX commands, symbols, packages, error help |
| `queue` | Batch multiple operations in one call |

Every response includes a workflow state hint showing where you are and what to do next.

## IEEE journal & conference papers

TeXFlow ships first-class support for two IEEE classes:

- `ieee-access` — `\documentclass{ieeeaccess}` (IEEE Access template). The class file is not bundled (IEEE distributes it only from its own channels): run `texflow/data/ieee/fetch_ieee_templates.sh` once to download it plus the template's fonts and logos. It compiles with **pdfLaTeX** (the class's `spotcolor.sty` needs pdfTeX primitives).
- `ieee-conference` — stock `IEEEtran.cls` conference mode (ships with TeX Live).

IEEE documents compile with a `bibtex` pass (`IEEEtran.bst` style) rather than biblatex/biber, and float widths are relative-only (`\linewidth`/`\textwidth`/`\columnwidth` fractions — absolute units silently misrender across IEEE templates). Wide tables and figures auto-promote to `table*`/`figure*` in two-column documents; `edit(fit="none")` opts out of table fitting.

## Quality checks

- `document(action="validate")` — structural QA without compiling: ragged table rows, empty cells, missing identifying headers, and significant-digit numeric consistency (catches `91.2` vs `0.912` unit shifts while ignoring `0.03` p-value columns).
- `render(action="check")` — full pipeline: compiles, renders every page, and merges log-parsed defects (hbox/vbox overflow, missing files, undefined refs) with a vision pass scored against a fixed defect taxonomy. It spawns the local `polaris` MCP server as a client and falls back to `gemini-media` on any failure; the report always names the provider and every degradation. Override via `TEXFLOW_VISION_POLARIS_CMD`, `TEXFLOW_VISION_GEMINI_CMD`, `TEXFLOW_VISION_GEMINI_KEY`, `TEXFLOW_VISION_GEMINI_MODEL`.

## Example session

```
> document(action="create", title="My Paper", document_class="article")

> queue(operations=[
    {"tool": "edit", "action": "insert", "block_type": "section", "title": "Introduction", "level": 1},
    {"tool": "edit", "action": "insert", "content": "This paper explores...", "section": "Introduction"},
    {"tool": "edit", "action": "insert", "block_type": "section", "title": "Methods", "level": 1},
    {"tool": "layout", "font": "palatino", "columns": 2}
  ])

> render(action="compile")
```

## Development

```bash
git clone https://github.com/aaronsb/texflow-mcp
cd texflow-mcp
uv sync
uv run pytest tests/ -v    # 520 passed, 1 skipped
uv run texflow              # Start MCP server
```

## License

MIT
