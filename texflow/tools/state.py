"""Shared session state for MCP tools.

Holds the current in-memory Document and output directory.
The document auto-saves to disk after mutations and reloads on startup.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from pathlib import Path

from ..model import Document

_current_doc: Document | None = None
_output_dir: Path = Path.cwd()
_save_suppressed: bool = False


# --- Destructive action confirmation ---

_CONFIRMATION_TTL = 60.0  # seconds


@dataclass
class PendingConfirmation:
    action: str
    fingerprint: str
    created_at: float
    description: str


_pending_confirmation: PendingConfirmation | None = None


def _make_fingerprint(action: str, **kwargs: object) -> str:
    """Create a deterministic fingerprint from action + parameters."""
    parts = [action] + [f"{k}={v}" for k, v in sorted(kwargs.items()) if v is not None]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


def check_confirmation(action: str, **kwargs: object) -> PendingConfirmation | None:
    """Check if there's a valid pending confirmation matching these params.

    Returns the PendingConfirmation if matched (and consumes it).
    Returns None if no match or expired.
    """
    global _pending_confirmation
    if _pending_confirmation is None:
        return None

    fp = _make_fingerprint(action, **kwargs)
    pc = _pending_confirmation

    if pc.action == action and pc.fingerprint == fp:
        elapsed = time.monotonic() - pc.created_at
        if elapsed <= _CONFIRMATION_TTL:
            _pending_confirmation = None  # Consume the token
            return pc

    # Mismatch or expired: clear stale confirmation
    _pending_confirmation = None
    return None


def set_confirmation(action: str, description: str, **kwargs: object) -> None:
    """Set a pending confirmation for a destructive action."""
    global _pending_confirmation
    _pending_confirmation = PendingConfirmation(
        action=action,
        fingerprint=_make_fingerprint(action, **kwargs),
        created_at=time.monotonic(),
        description=description,
    )


def clear_confirmation() -> None:
    """Clear any pending confirmation (called on unrelated mutations)."""
    global _pending_confirmation
    _pending_confirmation = None

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
