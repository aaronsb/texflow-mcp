---
status: Draft
date: 2026-03-03
deciders:
  - aaronsb
related: []
---

# ADR-200: Section-Targeted Ingestion and Destructive Action Guards

## Context

The `document(action="ingest")` tool replaces the entire in-memory document model. There is no way to ingest markdown into a specific section of an existing document. An agent building a multi-section document from separate markdown files must decompose content block-by-block via `edit(action="insert")`, defeating the purpose of the markdown ingestion pipeline.

Additionally, both `document(action="create")` and `document(action="ingest")` silently overwrite the existing document via `set_doc()`, creating a data-loss risk with no recovery path.

## Decision

### Section-targeted ingestion

`document(action="ingest", section="Methods", source="methods.md")` parses markdown and appends the resulting blocks into the named section. Heading levels in the markdown are normalized relative to the target section's level, so headings become subsections of the target.

A new `parse_markdown_blocks(source, base_level)` function in `ingestion.py` returns `list[Block]` (not a full `Document`) with section levels shifted by `base_level`. This reuses the existing `_tokens_to_blocks` and `_normalize_section_levels` pipeline, then applies a level offset.

### Double-call confirmation for whole-document replacement

When `document(action="create")` or `document(action="ingest")` (without `section`) would replace an existing document, the first call returns a warning describing what exists. The agent must issue an identical call to proceed. No flag or parameter bypasses this — only a second matching call within 60 seconds confirms the action.

The confirmation token is fingerprinted to the exact action + parameters (SHA-256 hash). Changing any parameter resets the confirmation. Any intervening mutation (edit, layout) invalidates the pending confirmation by calling `clear_confirmation()` at the top of `edit_tool()` and `layout_tool()`.

This pattern is intentionally not a `--force` flag because flags are easy for agents to learn to always include, which would negate the safety benefit. The double-call creates a deliberate friction that requires the agent to observe the warning and re-commit.

### Scope of the guard

Only whole-document replacement is guarded:
- `document(action="create")` when a document exists
- `document(action="ingest")` without `section` when a document exists

Not guarded (append/modify operations):
- `document(action="ingest", section="...")` — appends to a section
- `edit(action="insert/replace/delete/move")` — granular mutations
- `layout(...)` — changes typesetting, not content

### Math plugin

The mistune parser now loads `plugins=["table", "math"]` so `$$display math$$` produces `Equation` blocks and `$inline math$` is properly tokenized.

## Consequences

### Positive

- Agents can build documents incrementally from multiple markdown sources without manual block decomposition
- Accidental overwrites are prevented without adding bypass parameters
- The queue tool halts on confirmation warnings, preventing destructive batch operations

### Negative

- Whole-document replacement requires one extra round-trip for the confirmation call
- Agents must be aware of the double-call pattern

### Neutral

- The confirmation token is scoped to session state and does not persist across server restarts
- Section-targeted ingest uses append semantics — it never replaces section content

## Alternatives Considered

- **`--force` flag**: Rejected because flags are trivially learned and always applied, negating the safety benefit. The double-call pattern creates friction that cannot be automated away without the agent explicitly acknowledging the warning.
- **Separate `ingest_into` action on the edit tool**: Rejected in favor of extending the existing `document(action="ingest")` with the already-declared `section` parameter, which is more discoverable and consistent.
- **Confirmation dialog via separate `confirm` tool**: Rejected as over-engineered. The double-call pattern reuses the existing tool interface with no new tools or parameters.
