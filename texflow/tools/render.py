"""Render tool: compile, preview, export LaTeX."""

from __future__ import annotations

from pathlib import Path

from ..compiler import compile_tex, preview_page
from ..formatters import format_compile_result
from ..serializer import serialize
from .state import auto_save, get_output_dir, require_doc


def render_tool(
    action: str,
    output_path: str | None = None,
    page: int | None = None,
    dpi: int | None = None,
) -> str:
    """Compile and export the document.

    Actions:
    - compile: Serialize model to .tex, compile to PDF. Returns PDF path.
    - preview: Render a specific page as base64 PNG image.
    - tex: Export the raw .tex source. Returns the LaTeX content.
    - errors: Return structured compilation errors from last compile.
    """
    match action:
        case "compile":
            return _compile(output_path)
        case "preview":
            return _preview(page or 1, dpi or 150)
        case "tex":
            return _export_tex()
        case _:
            return f"Unknown action: {action}. Valid: compile, preview, tex"


_last_result = None


def _compile(output_path: str | None) -> str:
    global _last_result
    doc = require_doc()
    tex = serialize(doc)

    out_dir = Path(output_path) if output_path else get_output_dir()
    result = compile_tex(tex, output_dir=out_dir)
    _last_result = result

    auto_save()
    return format_compile_result(result)


def _preview(page: int, dpi: int) -> str:
    if _last_result and _last_result.pdf_path and _last_result.pdf_path.exists():
        b64 = preview_page(_last_result.pdf_path, page=page, dpi=dpi)
        if b64:
            return f"data:image/png;base64,{b64}"
        return "Preview failed. Ensure pdftoppm (poppler-utils) is installed."

    # Try compiling first
    doc = require_doc()
    tex = serialize(doc)
    result = compile_tex(tex, output_dir=get_output_dir())
    if result.success and result.pdf_path:
        b64 = preview_page(result.pdf_path, page=page, dpi=dpi)
        if b64:
            return f"data:image/png;base64,{b64}"
    return "Preview unavailable. Compile the document first with render(action='compile')."


def _export_tex() -> str:
    doc = require_doc()
    return serialize(doc)
