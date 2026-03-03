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

TeXFlow compiles documents to PDF using XeLaTeX. Without it, you can still build and export `.tex` files.

```bash
# Arch
pacman -S texlive-xetex texlive-fontsrecommended texlive-fontsextra

# Debian/Ubuntu
apt install texlive-xetex texlive-fonts-recommended texlive-fonts-extra

# Fedora
dnf install texlive-xetex texlive-collection-fontsrecommended texlive-collection-fontsextra
```

For page preview (PNG), install `poppler-utils` (provides `pdftoppm`).

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

The model auto-saves to disk as JSON. LaTeX is only ever an output artifact — you never edit `.tex` directly.

## Tools

| Tool | Purpose |
|------|---------|
| `document` | Create, ingest markdown, show outline, read sections |
| `layout` | Columns, fonts, paper, margins, headers/footers, TOC |
| `edit` | Insert, replace, delete, move blocks (section, paragraph, figure, table, code, equation, list, raw) |
| `render` | Compile to PDF, preview page as PNG, export `.tex` |
| `reference` | Search LaTeX commands, symbols, packages, error help |
| `queue` | Batch multiple operations in one call |

Every response includes a workflow state hint showing where you are and what to do next.

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
uv run pytest tests/ -v    # 222 tests
uv run texflow              # Start MCP server
```

## License

MIT
