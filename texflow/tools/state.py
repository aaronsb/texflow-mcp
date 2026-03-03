"""Shared session state for MCP tools.

Holds the current in-memory Document and output directory.
The document auto-saves to disk after mutations.
"""

from __future__ import annotations

from pathlib import Path

from ..model import Document

_current_doc: Document | None = None
_output_dir: Path = Path.cwd()


def get_doc() -> Document | None:
    return _current_doc


def set_doc(doc: Document) -> None:
    global _current_doc
    _current_doc = doc


def require_doc() -> Document:
    if _current_doc is None:
        raise ValueError("No document loaded. Use document(action='create') or document(action='ingest') first.")
    return _current_doc


def get_output_dir() -> Path:
    return _output_dir


def set_output_dir(path: Path) -> None:
    global _output_dir
    _output_dir = path
    _output_dir.mkdir(parents=True, exist_ok=True)


def auto_save() -> Path | None:
    """Auto-save the current document model to disk."""
    if _current_doc is None:
        return None
    save_path = _current_doc.save_path
    if save_path is None:
        save_path = _output_dir / "document.texflow.json"
    return _current_doc.save(save_path)
