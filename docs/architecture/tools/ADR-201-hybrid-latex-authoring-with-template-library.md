---
status: Draft
date: 2026-03-03
deciders:
  - aaronsb
related:
  - ADR-200
---

# ADR-201: Hybrid LaTeX Authoring with Template Library

## Context

TeXFlow's document model handles the 80% case well: sections, paragraphs, figures, tables, equations, lists. But field testing revealed that agents hit a wall when they need LaTeX constructs the model doesn't express — mixed column layouts, TikZ diagrams, custom theorem environments, algorithm blocks, complex multi-row tables, landscape pages.

The current escape hatch is `RawLatex` blocks: opaque strings serialized verbatim. This works but has problems:

- No package detection — the agent must know which packages to add manually
- No syntax validation — broken LaTeX in a raw block silently produces compile errors
- No discoverability — the agent must know LaTeX well enough to write it from scratch
- No editing support — raw blocks are opaque blobs, not inspectable/editable sub-structures

Meanwhile, other LaTeX MCP servers (TeXstudio MCP, MCP LaTeX Server) take a file-centric approach where the agent writes raw .tex and the server handles compilation. This gives full LaTeX expressiveness but loses all structural safety.

The goal is to bridge both worlds: keep the document model as the structural backbone, but give agents a supported path to raw LaTeX that includes discoverability, templates, validation, and guided editing.

## Decision

### 1. Template Library

Maintain a library of pre-built LaTeX snippet templates as `.tex` files organized by category:

```
texflow/data/templates/
  manifest.json              # Category index with metadata
  layout/
    two-column-switch.tex
    landscape-page.tex
    side-by-side.tex
  math/
    theorem-environment.tex
    proof-block.tex
    aligned-equations.tex
  figures/
    tikz-diagram.tex
    side-by-side-figures.tex
    subfigure-grid.tex
  tables/
    multirow-table.tex
    longtable.tex
  code/
    algorithm.tex
    minted-listing.tex
  misc/
    epigraph.tex
    custom-title-page.tex
```

Each template is a `.tex` file with YAML frontmatter — self-describing, no external index needed. The server globs `templates/**/*.tex` on startup and builds the index in memory:

```latex
---
name: tikz-diagram
category: figures
description: TikZ picture with node-based layout
packages:
  - tikz
preamble:
  - "\\usetikzlibrary{arrows.meta,positioning}"
---
\begin{tikzpicture}[
  node distance=2cm,
  every node/.style={draw, rounded corners, minimum height=1cm}
]
  % CONTENT: diagram nodes and edges
  \node (a) {Node A};
  \node (b) [right=of a] {Node B};
  \draw[->] (a) -- (b);
\end{tikzpicture}
```

This means anyone can drop a new `.tex` file with frontmatter into the templates directory and it's immediately available — no manifest to update. The directory structure is just organizational; the frontmatter `category` field is the source of truth for grouping.

### 2. Hybrid Editing Flow

Extend the `edit` tool with a raw-LaTeX-aware workflow. The interaction pattern:

```
1. Agent:  edit(action="insert", section="Methods", position=2, block_type="raw")
   Server: "Insert at Methods[2] is valid. Available templates:
            1. tikz-diagram — TikZ picture with node-based layout
            2. algorithm — Algorithm2e pseudocode block
            3. (empty) — blank raw LaTeX block
            Specify template and initial content."

2. Agent:  edit(action="insert", section="Methods", position=2,
                block_type="raw", template="tikz-diagram",
                content="<filled-in LaTeX>")
   Server: "Inserted raw block at Methods[2]. Added packages: tikz.
            Added preamble: \usetikzlibrary{...}"

3. Agent:  edit(action="read_raw", section="Methods", position=2)
   Server: Returns the raw LaTeX content with line numbers

4. Agent:  edit(action="replace_raw", section="Methods", position=2,
                content="<updated LaTeX>")
   Server: "Updated. Lint check: OK."
           — or —
           "Updated. Lint warning: unclosed environment at line 4.
            Auto-fix available. Call with auto_fix=true to apply."

5. Agent:  edit(action="replace_raw", section="Methods", position=2,
                lines=[4, 6], content="<fixed lines>")
   Server: "Replaced lines 4-6. Lint check: OK."
```

### 3. Smart Package Resolution

Extend `Document.required_packages` to scan `RawLatex.tex` content for known patterns:

| Pattern | Package |
|---------|---------|
| `\begin{tikzpicture}` | `tikz` |
| `\includegraphics` | `graphicx` |
| `\multirow` | `multirow` |
| `\begin{algorithm}` | `algorithm2e` |
| `\begin{landscape}` | `pdflscape` |
| `\begin{longtable}` | `longtable` |
| `\begin{minted}` | `minted` |
| `\begin{subfigure}` | `subcaption` |

Templates declare their own requirements, but the scanner catches ad-hoc raw blocks too.

### 4. Lint Integration

Add a lightweight LaTeX fragment validator that:

- Checks environment open/close balance (`\begin{X}` has matching `\end{X}`)
- Detects common errors (unescaped `%`, `&` outside tabular, unmatched braces)
- Optionally attempts auto-fix for simple issues (close unclosed environments, escape special chars)
- Reports line numbers relative to the raw block, not the full document

This runs on raw blocks before serialization, not on the full .tex output.

## Consequences

### Positive

- Agents can express any LaTeX construct without leaving the document model
- Templates reduce agent effort — browse and fill rather than write from scratch
- Package resolution eliminates a class of "missing package" compile errors
- Line-level editing of raw blocks enables iterative refinement
- Lint catches errors before compilation, faster feedback loop

### Negative

- Template library is a maintenance surface — templates can go stale or have bugs
- Lint is necessarily incomplete — LaTeX is not context-free, some errors can't be caught without compilation
- More complex edit tool API — agents need to learn the raw block workflow
- Risk of agents over-relying on raw blocks instead of using the document model

### Neutral

- The document model remains the primary authoring path — templates are an escape hatch, not a replacement
- Template library can grow incrementally — start small, add based on demand
- Lint patterns and package detection patterns share the same scanning infrastructure
- Templates are self-indexed via frontmatter — adding templates is just dropping a .tex file

## Alternatives Considered

- **Document model only (status quo)** — Keep the model as the only authoring path, extend it to cover more LaTeX constructs. Rejected because the long tail of LaTeX features makes this a losing game — there will always be constructs the model can't express.

- **File-centric approach (like TeXstudio MCP)** — Let agents write .tex files directly, server only handles compilation. Rejected because it abandons the structural safety of the document model and requires agents to write complete, correct LaTeX.

- **Smart RawLatex only (no templates)** — Just add package detection and lint to existing raw blocks. Viable as a Phase 1 but doesn't solve discoverability — agents still need to know LaTeX well enough to write blocks from scratch.

- **External template registry (not in repo)** — Host templates separately, fetch on demand. Rejected for now — in-repo templates are simpler, version-controlled, and work offline. Could revisit if the library grows very large.
