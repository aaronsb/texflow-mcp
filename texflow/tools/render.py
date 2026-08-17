"""Render tool: compile, preview, export LaTeX."""

from __future__ import annotations

from pathlib import Path

from ..compiler import compile_tex, preview_all_pages, preview_page, parse_log_defects
from ..formatters import format_check_result, format_compile_result, format_preview_result
from ..serializer import serialize, serialize_bib
from .state import auto_save, get_output_dir, require_doc


def render_tool(
    action: str,
    output_path: str | None = None,
    page: int | None = None,
    dpi: int | None = None,
    vision: str = "auto",
) -> str:
    """Compile and export the document.

    Actions:
    - compile: Serialize model to .tex, compile to PDF. Returns PDF path.
    - preview: Render a specific page as PNG file. Returns file path and dimensions.
    - tex: Export the raw .tex source. Returns the LaTeX content.
    - errors: Return structured compilation errors from last compile.
    - check: One-shot structural QA pass. Compiles, then scores every rendered
      page with a vision provider (image-space: overflow, tiny text, misplaced
      floats, clipped tables) and merges in log-parsed defects (hbox/vbox
      overflow, missing files, undefined refs). vision: auto (polaris, falls
      back to gemini), polaris, gemini, none.
    """
    match action:
        case "compile":
            return _compile(output_path)
        case "preview":
            return _preview(page or 1, dpi or 150)
        case "tex":
            return _export_tex()
        case "check":
            return _check(dpi or 120, vision)
        case _:
            return f"Unknown action: {action}. Valid: compile, preview, tex, check"


_last_result = None


def _compile(output_path: str | None) -> str:
    global _last_result
    doc = require_doc()
    tex = serialize(doc)
    bib = serialize_bib(doc) or None

    # Pre-compile capability check
    warnings = _check_packages(doc)

    out_dir = Path(output_path) if output_path else get_output_dir()
    result = compile_tex(tex, output_dir=out_dir, bib_content=bib)
    _last_result = result

    auto_save()
    output = format_compile_result(result)
    if warnings:
        output += "\n\nPackage warnings:\n" + "\n".join(f"  - {w}" for w in warnings)
    return output


def _check_packages(doc) -> list[str]:
    """Check if required packages are available on the system."""
    warnings: list[str] = []
    try:
        from ..capabilities import check_capabilities, format_missing_warnings
        needed = sorted(doc.required_packages)
        caps = check_capabilities(packages=needed)
        warnings = format_missing_warnings(caps, needed_packages=needed)
    except Exception:
        pass

    if getattr(doc, "document_class", None) and doc.document_class.is_ieee:
        from ..model import DocumentClass
        if doc.document_class == DocumentClass.IEEE_ACCESS:
            ieee_dir = Path(__file__).resolve().parent.parent / "data" / "ieee"
            if not (ieee_dir / "ieeeaccess.cls").exists():
                warnings.append(
                    "ieeeaccess.cls is not installed. Run fetch_ieee_templates.sh in "
                    "texflow/data/ieee/ to download it from the IEEE Author Center "
                    "(class files are licensed, never bundled)."
                )
    return warnings


def _check(dpi: int, vision: str) -> str:
    """One-shot structural QA: compile, render all pages, log + vision defects."""
    global _last_result
    doc = require_doc()

    # Compile fresh; the check must judge the current model state.
    tex = serialize(doc)
    bib = serialize_bib(doc) or None
    out_dir = get_output_dir()
    result = compile_tex(tex, output_dir=out_dir, bib_content=bib)
    _last_result = result
    auto_save()

    log_defects = parse_log_defects(result.log) if result.log else []

    pngs: list[Path] = []
    if result.success and result.pdf_path:
        pngs = [p.png_path for p in preview_all_pages(result.pdf_path, dpi=dpi, output_dir=out_dir)]

    from ..vision import run_vision_check
    vision_report = run_vision_check(pngs, provider=vision)

    return format_check_result(result, log_defects, vision_report, pngs)


def _preview(page: int, dpi: int) -> str:
    pdf_path = None
    if _last_result and _last_result.pdf_path and _last_result.pdf_path.exists():
        pdf_path = _last_result.pdf_path
    else:
        # Try compiling first
        doc = require_doc()
        tex = serialize(doc)
        result = compile_tex(tex, output_dir=get_output_dir())
        if result.success and result.pdf_path:
            pdf_path = result.pdf_path

    if pdf_path is None:
        return "Preview unavailable. Compile the document first with render(action='compile')."

    preview = preview_page(pdf_path, page=page, dpi=dpi, output_dir=get_output_dir())
    if preview is None:
        return "Preview failed. Ensure pdftoppm (poppler-utils) is installed."

    return format_preview_result(preview)


def _export_tex() -> str:
    doc = require_doc()
    return serialize(doc)
