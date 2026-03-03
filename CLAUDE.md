# TeXFlow MCP Server

## Project Overview

TeXFlow is a LaTeX document compiler with an MCP interface. The AI operates on a structured document model (sections, paragraphs, figures, tables) and the server handles all LaTeX mechanics — packages, preamble, compilation.

**Two entry flows:**
1. **Scaffold**: `document(action="create")` → empty document skeleton → AI builds content via `edit` tool
2. **Markdown ingest**: `document(action="ingest", source="file.md")` → populated model → AI refines layout

Both converge on an in-memory `Document` model that auto-saves to disk. LaTeX is only ever an output artifact.

## Architecture

```
server.py                          # FastMCP entry point, 5 tool registrations
texflow/
  model.py                         # Document model dataclasses
  serializer.py                    # Model → .tex generation
  ingestion.py                     # Markdown → model (mistune AST)
  compiler.py                      # .tex → PDF (xelatex subprocess)
  tools/
    state.py                       # Shared session state, auto-save
    document.py                    # create, ingest, outline, read
    layout.py                      # configure typesetting
    edit.py                        # insert, replace, delete, move blocks
    render.py                      # compile, preview, tex export
    reference.py                   # LaTeX documentation search
  data/
    font_map.json                  # Font name → LaTeX package
    class_defaults.json            # Document class defaults
    latex_reference/               # Commands, symbols, packages, errors
tests/
  test_model.py
  test_serializer.py
  test_ingestion.py
  test_compiler.py
  test_tools.py
  fixtures/sample.md
```

## 5 MCP Tools

- **document** — create, ingest, outline, read
- **layout** — columns, fonts, paper, margins, headers/footers, TOC
- **edit** — insert/replace/delete/move blocks (section, paragraph, figure, table, code, equation, list, raw)
- **render** — compile to PDF, preview page as PNG, export .tex
- **reference** — search commands/symbols, package info, error help, style check, examples

## Dependencies

```toml
[project]
dependencies = [
    "fastmcp>=3.0.0",
    "mistune>=3.2.0",
]
```

**System (optional, graceful degradation):** xelatex (compilation), pdftoppm (preview)

## Development

```bash
uv run pytest tests/ -v          # Run all tests
uv run texflow                   # Start MCP server
uv run texflow /path/to/workspace  # With workspace directory
```

## Claude Desktop Configuration

```json
{
  "mcpServers": {
    "texflow": {
      "command": "uv",
      "args": ["--directory", "/path/to/texflow-mcp", "run", "texflow"]
    }
  }
}
```

## Key Design Decisions

1. **Document model as source of truth** — all edits operate on dataclasses, never raw LaTeX
2. **Implicit package resolution** — adding a Figure adds `graphicx`, an Equation adds `amsmath`
3. **Section tree addressing** — sections addressed by title path (e.g., "Methods/Data Collection")
4. **Auto-persistence** — model saves to JSON after every mutation
5. **Inline markup preservation** — paragraphs store `**bold**`, `*italic*`, `$math$`; serializer converts to LaTeX
