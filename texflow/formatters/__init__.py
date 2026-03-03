"""Shared formatting functions for TeXFlow tool output.

Centralizes text formatting to ensure consistent, scannable output
across all MCP tools. Tools compute results; formatters shape text.

Organized as a package — each domain has its own module with shared
primitives. This __init__ re-exports the public API so existing
imports continue to work unchanged.
"""

from .document import (
    format_blocks_as_prose,
    format_confirmation_warning,
    format_document_summary,
    format_ingest_result,
    format_outline,
    format_section_ingest_result,
    list_section_titles,
)
from .layout import format_layout
from .primitives import indent, status_icon, truncate, truncate_list
from .render import format_compile_result

__all__ = [
    # primitives
    "truncate",
    "truncate_list",
    "indent",
    "status_icon",
    # document
    "format_outline",
    "format_blocks_as_prose",
    "list_section_titles",
    "format_document_summary",
    "format_confirmation_warning",
    "format_ingest_result",
    "format_section_ingest_result",
    # layout
    "format_layout",
    # render
    "format_compile_result",
]
