"""Shared formatting primitives used across all formatter modules."""

from __future__ import annotations


def truncate(text: str, max_len: int = 60, suffix: str = "...") -> str:
    """Truncate text with suffix if it exceeds max_len."""
    if len(text) <= max_len:
        return text
    return text[: max_len - len(suffix)] + suffix


def truncate_list(items: list[str], max_items: int, noun: str = "more") -> list[str]:
    """Return items[:max_items] with an overflow indicator if needed."""
    if len(items) <= max_items:
        return list(items)
    return list(items[:max_items]) + [f"  ... and {len(items) - max_items} {noun}"]


def indent(text: str, level: int = 2) -> str:
    """Indent each line of text by level spaces."""
    prefix = " " * level
    return "\n".join(prefix + line for line in text.splitlines())


def status_icon(ok: bool) -> str:
    """Consistent status icon for result lines."""
    return "ok" if ok else "ERR"
