# TeXFlow MCP Server

## Project Overview

TeXFlow is a LaTeX document compiler with an MCP interface. The AI operates on a structured document model (sections, paragraphs, figures, tables) and the server handles all LaTeX mechanics — packages, preamble, compilation.

**Two entry flows:**
1. **Scaffold**: `document(action="create")` → empty document skeleton → AI builds content via `edit` tool
2. **Markdown ingest**: `document(action="ingest", source="file.md")` → populated model → AI refines layout

Both converge on an in-memory `Document` model that auto-saves to disk. LaTeX is only ever an output artifact.

**Feature areas beyond the basics:**
- **IEEE classes** — `ieee-access` (serializes to `\documentclass{ieeeaccess}`, needs template files in `texflow/data/ieee/`, compiles with **pdflatex** because `spotcolor.sty` uses pdfTeX primitives) and `ieee-conference` (stock `IEEEtran.cls`). IEEE docs use a `bibtex` pass with `IEEEtran.bst`, not biblatex/biber.
- **Table width fitting** — `edit(fit="auto")` promotes oversized tables to `table*` in two-column docs and picks tabularx / resizebox / adjustbox from a character-budget heuristic; `fit="none"` opts out. Figure/table widths must be relative (`0.8\textwidth`); absolute units are rejected.
- **Vision check** — `render(action="check")` compiles, renders every page, merges log-parsed defects with a vision pass scored against a fixed 4-category taxonomy.
- **Variants** — `document(action="clone")` deep-copies into a new document class (copy-on-clone); `edit(action="share")` registers a Table/Figure in a persisted shared store both variants resolve at serialize time.
- **Structural QA** — `document(action="validate")`: ragged rows, empty cells, missing identifying headers, significant-digit numeric consistency.

## Architecture

```
server.py                          # FastMCP entry point, 6 tool registrations
texflow/
  model.py                         # Document model dataclasses
  serializer.py                    # Model → .tex generation (engine-aware)
  ingestion.py                     # Markdown → model (mistune AST)
  compiler.py                      # .tex → PDF (xelatex/pdflatex subprocess)
  tools/
    state.py                       # Shared session state, auto-save
    document.py                    # create, ingest, outline, read, clone, switch, validate, bib
    layout.py                      # configure typesetting
    edit.py                        # insert, replace, delete, move, share blocks
    render.py                      # compile, preview, tex export, vision check
    reference.py                   # LaTeX documentation search
  data/
    font_map.json                  # Font name → LaTeX package
    class_defaults.json            # Document class defaults
    ieee/                          # ieeeaccess.cls + template fonts/logos (fetch_ieee_templates.sh)
    latex_reference/               # Commands, symbols, packages, errors
tests/
  test_model.py
  test_serializer.py
  test_ingestion.py
  test_compiler.py
  test_tools.py
  test_ieee.py
  test_table_fit.py
  test_clone_validate.py
  test_vision_check.py
  test_engine_aware.py
  fixtures/sample.md
```

## 6 MCP Tools

- **document** — create, ingest, outline, read, update, reset, clone, list_variants, switch, validate, bib_add/bib_remove/bib_list/bib_style
- **layout** — columns, fonts, paper, margins, headers/footers, TOC
- **edit** — insert/replace/delete/move/share/unshare blocks (section, paragraph, figure, table, code, equation, list, raw); table width fitting (`fit`, `span_columns`)
- **render** — compile to PDF, preview page as PNG, export .tex, one-shot vision check
- **reference** — search commands/symbols, package info, error help, style check, examples
- **queue** — batch multiple operations in one call

## Dependencies

```toml
[project]
dependencies = [
    "fastmcp>=3.0.0",
    "mistune>=3.2.0",
]
```

**System (optional, graceful degradation):** xelatex + pdflatex (compilation), pdftoppm (preview), texlive-publishers (IEEEtran.cls). `ieee-access` additionally needs `texflow/data/ieee/ieeeaccess.cls` — run `texflow/data/ieee/fetch_ieee_templates.sh`.

**Vision providers (optional):** `render(action="check")` spawns the local `polaris` MCP server as a client and falls back to `gemini-media` on any failure. Override via `TEXFLOW_VISION_POLARIS_CMD`, `TEXFLOW_VISION_GEMINI_CMD`, `TEXFLOW_VISION_GEMINI_KEY`, `TEXFLOW_VISION_GEMINI_MODEL`.

## Development

```bash
uv run pytest tests/ -v          # Run all tests (520 passed, 1 skipped)
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
6. **Engine-aware serialization** — `serialize()`/`_preamble()` take an engine; xelatex drops `T1 fontenc`/`utf8 inputenc` (TU/OpenType native, avoids xdvipdfmx ".vf or physical font" fatals). `_engine_for(doc)` forces pdflatex for `ieee-access` (spotcolor needs pdfTeX primitives); `compile_tex` honors the requested engine and never silently overrides it.
7. **Bundled class assets, not bundled classes** — IEEE class files are licensed for IEEE channels only, so `texflow/data/ieee/` ships a fetch script plus the *supporting* assets the class requires (template fonts, logos, spotcolor.sty, font maps). `_ieee_texinputs()` prepends the directory to `TEXINPUTS`/`TEXFONTS`/`FONTMAP` for every compile; a missing `ieeeaccess.cls` is reported as a clear, actionable warning before compile.
8. **Compile honesty** — `compile_tex` rejects stub PDFs (engine exits 0 but produces a <100-byte non-`%PDF` file, e.g. output-driver failures) as a CompileError, and surfaces the last 10 log lines + engine stderr when compilation fails without parseable errors.
9. **Shared blocks** — clone is copy-on-clone; `edit(action="share")` moves a Table/Figure into `shared.texflow.json` (persisted in the workspace) and both variants resolve it at serialize time. Re-sharing an already-shared block errors; `unshare` freezes a copy back into the document.
10. **QA in two tiers** — `validate` is pure-model structural QA (no compile); `check` is the full pipeline with a vision pass. Both are deterministic in reporting: the check report always names the vision provider and every degradation.
