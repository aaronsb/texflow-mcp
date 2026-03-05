"""Formatters for the layout tool."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..model import Layout


def format_layout(lo: Layout) -> str:
    """Format current layout configuration."""
    lines = [
        "Current layout:",
        f"  Class: {lo.document_class.value}",
        f"  Columns: {lo.columns}",
        f"  Font size: {lo.font_size}",
        f"  Paper: {lo.paper_size}",
        f"  Margins: top={lo.margins.top}, bottom={lo.margins.bottom}, left={lo.margins.left}, right={lo.margins.right}",
    ]
    if lo.font_main:
        lines.append(f"  Main font: {lo.font_main}")
    if lo.font_sans:
        lines.append(f"  Sans font: {lo.font_sans}")
    if lo.font_mono:
        lines.append(f"  Mono font: {lo.font_mono}")
    if lo.header:
        lines.append(f"  Header: L={lo.header.left!r} C={lo.header.center!r} R={lo.header.right!r}")
    if lo.footer:
        lines.append(f"  Footer: L={lo.footer.left!r} C={lo.footer.center!r} R={lo.footer.right!r}")
    lines.append(f"  TOC: {lo.toc}  LOF: {lo.lof}  LOT: {lo.lot}")
    if lo.line_spacing:
        lines.append(f"  Line spacing: {lo.line_spacing}")
    if lo.section_break:
        lines.append(f"  Section break: {lo.section_break}")
    if lo.styles:
        lines.append(f"  Styles: {', '.join(lo.styles)}")
    return "\n".join(lines)
