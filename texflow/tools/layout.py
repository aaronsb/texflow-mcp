"""Layout tool: configure document typesetting."""

from __future__ import annotations

import json
from pathlib import Path

from ..model import DocumentClass, HeaderFooter, Layout, Margins
from .state import auto_save, require_doc

_DATA_DIR = Path(__file__).parent.parent / "data"


def layout_tool(
    columns: int | None = None,
    font: str | None = None,
    font_sans: str | None = None,
    font_mono: str | None = None,
    font_size: str | None = None,
    paper: str | None = None,
    margins: str | None = None,
    header_left: str | None = None,
    header_center: str | None = None,
    header_right: str | None = None,
    footer_left: str | None = None,
    footer_center: str | None = None,
    footer_right: str | None = None,
    toc: bool | None = None,
    lof: bool | None = None,
    lot: bool | None = None,
    line_spacing: float | None = None,
) -> str:
    """Configure document typesetting and layout.

    Only provided parameters are changed; others are left as-is.
    Returns the current full layout configuration after changes.
    """
    doc = require_doc()
    lo = doc.layout
    changes: list[str] = []

    if columns is not None:
        if columns < 1:
            return "Error: columns must be >= 1"
        lo.columns = columns
        changes.append(f"columns={columns}")

    if font is not None:
        _validate_font(font)
        lo.font_main = font
        changes.append(f"font={font}")

    if font_sans is not None:
        lo.font_sans = font_sans
        changes.append(f"font_sans={font_sans}")

    if font_mono is not None:
        lo.font_mono = font_mono
        changes.append(f"font_mono={font_mono}")

    if font_size is not None:
        valid_sizes = {"10pt", "11pt", "12pt"}
        if font_size not in valid_sizes:
            return f"Error: font_size must be one of: {', '.join(sorted(valid_sizes))}"
        lo.font_size = font_size
        changes.append(f"font_size={font_size}")

    if paper is not None:
        paper_map = {
            "a4": "a4paper", "a4paper": "a4paper",
            "letter": "letterpaper", "letterpaper": "letterpaper",
            "legal": "legalpaper", "legalpaper": "legalpaper",
            "a5": "a5paper", "a5paper": "a5paper",
        }
        if paper.lower() not in paper_map:
            return f"Error: unknown paper size. Valid: {', '.join(sorted(set(paper_map.values())))}"
        lo.paper_size = paper_map[paper.lower()]
        changes.append(f"paper={lo.paper_size}")

    if margins is not None:
        lo.margins = _parse_margins(margins)
        changes.append(f"margins={margins}")

    # Header
    if any(v is not None for v in [header_left, header_center, header_right]):
        if lo.header is None:
            lo.header = HeaderFooter()
        if header_left is not None:
            lo.header.left = header_left
        if header_center is not None:
            lo.header.center = header_center
        if header_right is not None:
            lo.header.right = header_right
        changes.append("header updated")

    # Footer
    if any(v is not None for v in [footer_left, footer_center, footer_right]):
        if lo.footer is None:
            lo.footer = HeaderFooter()
        if footer_left is not None:
            lo.footer.left = footer_left
        if footer_center is not None:
            lo.footer.center = footer_center
        if footer_right is not None:
            lo.footer.right = footer_right
        changes.append("footer updated")

    if toc is not None:
        lo.toc = toc
        changes.append(f"toc={toc}")

    if lof is not None:
        lo.lof = lof
        changes.append(f"lof={lof}")

    if lot is not None:
        lo.lot = lot
        changes.append(f"lot={lot}")

    if line_spacing is not None:
        lo.line_spacing = line_spacing
        changes.append(f"line_spacing={line_spacing}")

    auto_save()

    # Format response
    lines = []
    if changes:
        lines.append(f"Updated: {', '.join(changes)}")
    else:
        lines.append("No changes (no parameters provided).")
    lines.append("")
    lines.append(_format_layout(lo))
    return "\n".join(lines)


def _validate_font(name: str) -> None:
    """Warn if font is unknown (non-fatal)."""
    fp = _DATA_DIR / "font_map.json"
    if fp.exists():
        font_map = json.loads(fp.read_text(encoding="utf-8"))
        if name not in font_map:
            pass  # Unknown font — still allowed, user might have it installed


def _parse_margins(spec: str) -> Margins:
    """Parse margin spec: '1in' (uniform) or 'top=1in,left=0.75in,...'"""
    if "=" not in spec:
        return Margins(top=spec, bottom=spec, left=spec, right=spec)

    m = Margins()
    for part in spec.split(","):
        part = part.strip()
        if "=" in part:
            key, _, val = part.partition("=")
            key = key.strip()
            val = val.strip()
            if key == "top":
                m.top = val
            elif key == "bottom":
                m.bottom = val
            elif key == "left":
                m.left = val
            elif key == "right":
                m.right = val
    return m


def _format_layout(lo: Layout) -> str:
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
    return "\n".join(lines)
