"""Formatters for the render tool: compilation results."""

from __future__ import annotations

from .primitives import truncate_list


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

    return "\n".join(lines)
