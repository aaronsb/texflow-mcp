"""Shared session state for MCP tools.

Holds the current in-memory Document and output directory.
The document auto-saves to disk after mutations and reloads on startup.
"""

from __future__ import annotations

from pathlib import Path

from ..model import Document

_current_doc: Document | None = None
_output_dir: Path = Path.cwd()
_save_suppressed: bool = False

_SAVE_FILENAME = "document.texflow.json"


def get_doc() -> Document | None:
    global _current_doc
    if _current_doc is None:
        _current_doc = _try_load()
    return _current_doc


def set_doc(doc: Document) -> None:
    global _current_doc
    _current_doc = doc


def require_doc() -> Document:
    doc = get_doc()
    if doc is None:
        raise ValueError("No document loaded. Use document(action='create') or document(action='ingest') first.")
    return doc


def get_output_dir() -> Path:
    return _output_dir


def set_output_dir(path: Path) -> None:
    global _output_dir
    _output_dir = path
    _output_dir.mkdir(parents=True, exist_ok=True)


def auto_save() -> Path | None:
    """Auto-save the current document model to disk.

    No-ops when save is suppressed (e.g., during queue execution).
    """
    if _save_suppressed or _current_doc is None:
        return None
    save_path = _current_doc.save_path
    if save_path is None:
        save_path = _output_dir / _SAVE_FILENAME
    return _current_doc.save(save_path)


def suppress_save(suppress: bool = True) -> None:
    """Suppress or re-enable auto-save. Used by queue to batch disk writes."""
    global _save_suppressed
    _save_suppressed = suppress


def _try_load() -> Document | None:
    """Try to load a previously saved document from the output directory."""
    save_path = _output_dir / _SAVE_FILENAME
    if save_path.exists():
        try:
            return Document.load(save_path)
        except Exception:
            return None
    return None
