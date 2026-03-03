"""Workflow state: computed from document state, appended to tool responses."""

from __future__ import annotations

from pathlib import Path

from .state import get_doc, get_output_dir


# --- State definitions ---

STATES = {
    "no_document": {
        "hint": "document(create) or document(ingest) to start. Use queue() to scaffold a full document in one call.",
    },
    "empty": {
        "hint": "edit(insert) to add sections and content | layout() to configure styling | queue() to build in batch",
    },
    "drafting": {
        "hint": "edit() to add more content | layout() to style | render(compile) when ready",
    },
    "styled": {
        "hint": "render(compile) to build PDF | edit() to revise | layout() to restyle",
    },
    "compiled": {
        "hint": "render(preview) to view pages | edit()/layout() to iterate | render(compile) to rebuild",
    },
}

WORKFLOW_MAP = """\
Workflow:
  no_document ─create/ingest─► empty ─edit(insert)─► drafting ─layout()─► styled
                                                         ▲                    │
                                                         └──── edit() ◄──────┤
                                                                              ▼
                                                                          compiled
                                                                              │
                                                         edit()/layout() ─────┘

States:
  no_document  No document loaded
  empty        Document exists, no content yet
  drafting     Has content, default layout
  styled       Has content, layout customized
  compiled     PDF built successfully"""


def current_state() -> str:
    """Compute current workflow state from document state."""
    doc = get_doc()
    if doc is None:
        return "no_document"

    if not doc.content:
        return "empty"

    # Check if PDF exists
    out = get_output_dir()
    if (out / "document.pdf").exists():
        return "compiled"

    # Check if layout has been customized beyond defaults
    lo = doc.layout
    if _is_styled(lo):
        return "styled"

    return "drafting"


def _is_styled(lo) -> bool:
    """Check if layout has been customized beyond article defaults."""
    return any([
        lo.columns != 1,
        lo.font_main is not None,
        lo.font_sans is not None,
        lo.font_mono is not None,
        lo.font_size != "12pt",
        lo.paper_size != "a4paper",
        lo.header is not None,
        lo.footer is not None,
        lo.toc,
        lo.lof,
        lo.lot,
        lo.line_spacing is not None,
    ])


def state_hint() -> str:
    """Return the current state hint line for appending to tool responses."""
    s = current_state()
    info = STATES[s]
    return f"\n[{s}] {info['hint']}"


def error_hint(error_msg: str) -> str:
    """Return contextual help for common errors."""
    el = error_msg.lower()

    if "no document loaded" in el:
        return " Use document(action='create') or document(action='ingest') first."

    if "section not found" in el:
        return " Use document(action='outline') to see available sections."

    if "position" in el and "out of range" in el:
        return " Use document(action='outline') to see block indices."

    if "unknown block_type" in el:
        return " Valid types: section, paragraph, figure, table, code, equation, list, raw."

    if "unknown action" in el:
        return ""  # Already lists valid actions

    if "unknown document class" in el:
        return ""  # Already lists valid classes

    if "compilation failed" in el or "latex error" in el:
        return " Use reference(action='error_help', error='...') to decode LaTeX errors."

    if "missing" in el and ("required" in el or "parameter" in el):
        return ""  # Already says what's missing

    return ""
