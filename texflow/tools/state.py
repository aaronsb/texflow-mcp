"""Shared session state for MCP tools.

Holds the current in-memory Document and output directory.
The document auto-saves to disk after mutations and reloads on startup.
"""

from __future__ import annotations

import hashlib
import json
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
_SHARED_FILENAME = "shared.texflow.json"
_VARIANTS_DIR = "variants"


def get_doc() -> Document | None:
    global _current_doc
    if _current_doc is None:
        _current_doc = _try_load()
        if _current_doc is not None:
            _current_doc.shared = _load_shared()
    return _current_doc


def set_doc(doc: Document) -> None:
    global _current_doc
    _current_doc = doc


def clear_doc() -> None:
    """Clear the in-memory document and remove the saved state file."""
    global _current_doc
    if _current_doc is not None and _current_doc.save_path is not None:
        try:
            _current_doc.save_path.unlink(missing_ok=True)
        except OSError:
            pass
    _current_doc = None


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

    Also persists the shared-block store. No-ops when save is suppressed
    (e.g., during queue execution).
    """
    if _save_suppressed or _current_doc is None:
        return None
    save_path = _current_doc.save_path
    if save_path is None:
        save_path = _output_dir / _SAVE_FILENAME
    saved = _current_doc.save(save_path)
    _save_shared(_current_doc.shared)
    return saved


def _shared_path() -> Path:
    return _output_dir / _SHARED_FILENAME


def _load_shared() -> dict:
    """Load the shared-block store (both variants resolve against it)."""
    path = _shared_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_shared(shared: dict) -> None:
    path = _shared_path()
    if shared:
        path.write_text(json.dumps(shared, indent=2), encoding="utf-8")
    elif path.exists():
        path.unlink(missing_ok=True)


def variants_dir() -> Path:
    """Directory holding derived document variants."""
    return _output_dir / _VARIANTS_DIR


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
