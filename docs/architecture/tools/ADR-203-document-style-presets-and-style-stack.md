---
status: Draft
date: 2026-03-04
deciders:
  - aaronsb
related:
  - ADR-201
  - ADR-202
---

# ADR-203: Document Style Presets and Style Stack

## Context

TeXFlow's template library (ADR-201, ADR-202) provides block-level content templates — you insert a theorem, a chart, or a callout box. But there's no mechanism for **document-level visual identity**: color palettes, heading styles, typography pairings, paragraph spacing, link colors.

The current `Layout` dataclass handles structural concerns (columns, margins, fonts, headers/footers) but not aesthetic ones. Users who want a "modern blue" look must manually know which LaTeX packages to use (`titlesec`, `xcolor`, `hyperref` options) and inject raw preamble lines — defeating the purpose of a structured document model.

LaTeX supports rich global styling through preamble commands. Packages like `titlesec` (heading formatting), `xcolor` (color definitions), `parskip` (paragraph spacing), and `caption` (caption formatting) all work by setting global state in the preamble. Crucially, this styling is **not scopeable** to individual sections — a `\titleformat` applies everywhere.

The current system also only targets academic document styles. Users want newsletters, reports, resumes, technical manuals — documents where visual design matters as much as content.

## Decision

### Style presets as preamble bundles

Introduce **style presets** — YAML files in `data/styles/` that declare packages and preamble lines with no body content. Each preset bundles a coherent visual identity: colors, heading format, typography, spacing.

```yaml
# data/styles/modern-blue.yaml
name: Modern Blue
description: Clean sans-serif with blue headings, parskip spacing
packages:
  - titlesec
  - xcolor
  - parskip
preamble:
  - \definecolor{heading}{HTML}{1A5276}
  - \definecolor{accent}{HTML}{2E86C1}
  - \titleformat{\section}{\Large\bfseries\sffamily\color{heading}}{}{0em}{}[\color{accent}\titlerule]
  - \titleformat{\subsection}{\large\bfseries\sffamily\color{heading}}{}{0em}{}
  - \hypersetup{linkcolor=accent,urlcolor=accent,citecolor=heading}
```

### Style stack on Layout

Add a `styles: list[str]` field to the `Layout` dataclass. The serializer resolves the stack in order:

1. Collect packages from all styles (union, deduplicated)
2. Emit preamble lines in stack order (later styles win on conflicts)
3. Style preamble is emitted after packages but before RawLatex block preamble lines

### Application via layout tool

```
layout(style="modern-blue")              # Set stack to ["modern-blue"]
layout(style=["modern-blue", "compact"]) # Set multi-style stack
layout(style=[])                         # Clear all styles
```

Individual `layout()` params still work alongside styles. The font from `layout(font="libertine")` is applied independently of (and after) the style stack, so explicit params override style defaults.

### Style browsing via reference tool

```
reference(action="styles")                # List all available styles
reference(action="styles", query="blue")  # Search/filter styles
```

### Serialization order

The full preamble assembly order becomes:

1. `\documentclass` with options
2. `\usepackage` lines (from document content + layout + style stack, sorted)
3. **Style preamble lines** (stack order — later wins)
4. RawLatex block preamble lines (template-specific, e.g. `\newtcbtheorem`)
5. Line spacing, header/footer config
6. Metadata (`\title`, `\author`, `\date`)

This order ensures styles set defaults that block-level preamble can override, and explicit layout params take final precedence.

### No per-section scoping

LaTeX preamble commands are document-global. A `\titleformat` or `\definecolor` cannot be scoped to a single section without fragile `\begingroup` hacks. The style stack is strictly document-level. Per-block visual overrides remain possible through RawLatex with explicit formatting.

### Initial style presets

| Preset | Character |
|--------|-----------|
| `modern-blue` | Sans-serif headings, blue accent, parskip, clean rules |
| `classic-serif` | Traditional serif, muted colors, indented paragraphs |
| `minimal` | No heading decoration, generous whitespace, neutral palette |
| `newsletter` | Drop caps, pull quotes, decorative rules, two-tone palette |
| `technical` | Monospace accents, gray palette, numbered everything |
| `warm-earth` | Earth-tone palette, serif body, warm accent colors |

## Consequences

### Positive

- One-call visual identity: `layout(style="modern-blue")` transforms a document
- Composable: stack styles for layered effects, override with explicit params
- Extensible: adding a preset is just a YAML file, no code changes
- Non-academic documents become first-class (newsletters, reports, resumes)

### Negative

- Style conflicts in stacks may produce unexpected results (last-write-wins is simple but not always intuitive)
- No per-section scoping — this is a LaTeX limitation, not a design choice
- Users may expect more granularity than preamble-level styling can deliver

### Neutral

- Style YAML files use the same frontmatter parser as templates (`_parse_frontmatter`)
- Hyperref color options currently hardcoded in `_package_options` must become style-aware (styles can override via `\hypersetup`)
- The `data/styles/` directory is separate from `data/templates/` to avoid confusion between block-level and document-level concerns

## Alternatives Considered

- **Extend Layout with granular style properties** (`heading_color`, `link_color`, `heading_font`, etc.) — Rejected because the Layout dataclass would grow unboundedly and each new property requires serializer code. Preamble bundles are more flexible and require no code changes to add new presets.

- **KOMA-Script document classes** (`scrartcl`, `scrreprt`) — Powerful built-in theming but introduces a parallel option system that's hard to abstract. KOMA's `\KOMAoptions` and font commands don't compose well with standard packages like `titlesec`. Could be revisited later as a preset that sets the document class.

- **Style templates as RawLatex blocks** — Works today (insert a raw block with preamble lines and empty body) but is invisible in the document outline, confusing to users, and can't be stacked or replaced cleanly.

- **CSS-like cascading** with per-section overrides — Appealing in theory but LaTeX has no DOM or cascade model. Attempting to scope `\titleformat` per-section would require wrapping every section in groups and resetting commands, which is fragile and breaks many packages.
