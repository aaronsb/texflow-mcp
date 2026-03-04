"""Formatters for the render tool: compilation results and previews."""

from __future__ import annotations

from .primitives import truncate_list

_TEX_DERIVED_NOTE = (
    "Note: The .tex file is regenerated from the document model on every compile. "
    "Edits to .tex will be overwritten. Use edit() and layout() to make changes."
)


def format_compile_result(result) -> str:
    """Format compilation result (success/failure with errors and warnings)."""
    lines: list[str] = []
    if result.success:
        lines.append("Compilation successful.")
        if result.pdf_path:
            lines.append(f"PDF: {result.pdf_path}")
        if result.tex_path:
            lines.append(f"TeX: {result.tex_path}")
    else:
        lines.append("Compilation failed.")
        if result.tex_path:
            lines.append(f"TeX written to: {result.tex_path}")
        if result.errors:
            lines.append("")
            lines.append("Errors:")
            for err in result.errors:
                loc = f" (line {err.line})" if err.line else ""
                lines.append(f"  - {err.message}{loc}")

    if result.warnings:
        lines.append("")
        warning_lines = [f"  - {w}" for w in result.warnings]
        truncated = truncate_list(warning_lines, 5, "more warnings")
        lines.append(f"Warnings ({len(result.warnings)}):")
        lines.extend(truncated)

    lines.append("")
    lines.append(_TEX_DERIVED_NOTE)

    return "\n".join(lines)


def format_preview_result(preview) -> str:
    """Format preview result with file path and dimensions."""
    size_kb = preview.file_size / 1024
    lines = [
        f"Preview saved: page {preview.page}",
        f"  PNG: {preview.png_path}",
        f"  Dimensions: {preview.width} x {preview.height} px",
        f"  Size: {size_kb:.1f} KB",
        "",
        "The preview image is saved to disk. Share the file path with the user.",
    ]
    return "\n".join(lines)
