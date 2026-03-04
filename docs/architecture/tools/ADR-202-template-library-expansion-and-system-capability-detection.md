---
status: Draft
date: 2026-03-04
deciders:
  - aaronsb
  - claude
related:
  - ADR-201
---

# ADR-202: Template Library Expansion and System Capability Detection

## Context

ADR-201 delivered the hybrid LaTeX authoring system with 8 initial templates, smart package detection, and raw block editing. Field testing revealed several gaps:

1. **Template coverage is thin.** The 8 templates cover basic TikZ, tables, math alignment, code, landscape, and subfigures — but miss high-frequency needs like charts/plots, theorems, bibliographies, callout boxes, algorithm pseudocode, and cross-references.

2. **No system capability awareness.** Templates declare LaTeX package dependencies but TeXFlow has no way to check if those packages (or required system tools like `pygmentize`, `biber`) are actually installed. Failures surface as cryptic LaTeX compilation errors.

3. **No dependency tracking in frontmatter.** Templates can declare `packages` and `preamble` lines, but cannot express system tool requirements (`pygmentize` for minted) or engine constraints (`xelatex` for fontspec).

4. **Missing chart/plot support.** pgfplots is the standard for publication-quality data visualization in LaTeX but has no template coverage (line, bar, scatter, pie charts).

5. **No citation workflow.** Bibliography management (biblatex/biber) is fundamental to academic writing but has no template or guidance.

## Decision

Three workstreams, independently shippable:

### Workstream 1: Template Library Expansion (~25 new templates)

Expand from 8 to ~30 templates across existing and new categories:

**math** (5 new):
- `theorem-proof` — amsthm with `\newtheorem` preamble declarations
- `matrix` — pmatrix/bmatrix/vmatrix bracket variants
- `cases-piecewise` — piecewise functions with `\text{}` in cases
- `siunitx-quantities` — SI units with `\qty{}`, `S` column type
- `gather-split` — gather and split environments (complement to align)

**diagrams** (4 new):
- `pgfplots-lineplot` — scientific line plot with axis, legend, grid
- `pgfplots-barchart` — grouped bar chart with categorical x-axis
- `pgfplots-scatter` — scatter plot with data points
- `tikz-state-machine` — finite automata with `automata` library

**tables** (2 new):
- `tabularx-full-width` — auto-expanding `X` columns
- `colored-rows` — alternating row colors with colortbl

**layout** (3 new):
- `two-column-mixed` — multicol inline column switching
- `minipage-side-by-side` — horizontal content blocks (the `%` gotcha)
- `wrapfigure` — text-wrapped figures

**code** (2 new):
- `listings-styled` — styled code listing (no external deps, alternative to minted)
- `algorithm-pseudocode` — `algorithm` + `algpseudocode` for CS papers

**figures** (2 new):
- `figure-with-notes` — figure with source attribution note
- `figure-local-image` — simple `\includegraphics` from local file path

**references** (new category, 2 templates):
- `biblatex-citations` — biblatex with biber backend, author-year style
- `hyperref-cleveref` — smart cross-references (load order matters)

**callouts** (new category, 2 templates):
- `tcolorbox-note` — colored info/warning/tip boxes
- `tcolorbox-theorem` — boxed theorem environments

**charts** (new category, 2 templates):
- `pgfplots-piechart` — pie chart visualization
- `gantt-chart` — project timeline with pgfgantt

**styles** (new category, TBD):
- Font presets, color palettes, column rules/dividers

### Workstream 2: System Capability Detection

New `texflow/capabilities.py` module:

- `SystemCapabilities` dataclass: engines, tools, packages, tex distribution
- `check_capabilities(packages)` — lazy probe with session cache
- Engine detection via `shutil.which` (xelatex, pdflatex, lualatex)
- Package detection via `kpsewhich` (batch check, ~20ms for 8 packages)
- System tool detection (biber, bibtex, pygmentize, pdftoppm)
- `format_missing_warnings()` — human-readable diagnostics

Integration points:
- `reference(action="templates", query="slug")` — show availability status
- Pre-compile check in `render(action="compile")` — warn before cryptic errors
- New `reference(action="capabilities")` — enumerate system LaTeX support

### Workstream 3: Template Dependency Frontmatter

Extend template YAML frontmatter with:
```yaml
requires_tools:
  - pygmentize      # system binary
requires_engine:
  - xelatex         # engine constraint (omit if engine-agnostic)
```

Extend `Template` dataclass with `requires_tools: list[str]` and `requires_engine: list[str]`. The existing `_parse_frontmatter` already handles arbitrary list keys.

### Workstream 4: Package Detection Expansion

Add patterns to `_RAW_PACKAGE_PATTERNS` in model.py:
- `\begin{axis}` → pgfplots
- `\begin{ganttchart}` → pgfgantt
- `\begin{algorithmic}` → algpseudocode
- `\begin{wrapfigure}` → wrapfig
- `\begin{tabularx}` → tabularx
- `\printbibliography` → biblatex
- `\cref{` / `\Cref{` → cleveref
- `\qty{` / `\SI{` → siunitx
- `\begin{cases}` → amsmath
- `\begin{mytheorem}` → tcolorbox (via detection of `\newtcbtheorem`)

## Consequences

### Positive

- AI agents can produce publication-quality documents without memorizing LaTeX boilerplate
- "Missing library X" warnings prevent cryptic compilation failures
- Template browsing becomes a practical workflow for discovering LaTeX capabilities
- Charts and plots cover the most requested missing feature class
- Citation management unlocks academic paper workflows

### Negative

- More templates means more maintenance surface
- Capability detection adds subprocess calls (mitigated by caching)
- Some templates (minted, biblatex) require system tools beyond base LaTeX

### Neutral

- Template count grows from 8 to ~30, requiring the browse/search UX to scale
- New categories (references, callouts, charts, styles) expand the taxonomy
- Package detection patterns grow from 21 to ~30+

## Alternatives Considered

- **External template registry (CTAN/Overleaf):** Rejected — requires network access and adds latency. Local templates are instant and curated for AI authoring.
- **PyYAML for frontmatter:** Rejected — adds a dependency for minimal gain. The regex parser handles all needed cases.
- **Runtime package installation (tlmgr):** Rejected — too invasive. Detection and warning is the right boundary; installation is the user's responsibility.
