"""Compile .tex to PDF and preview pages.

Handles xelatex subprocess, error parsing from .log files,
and page preview via pdftoppm (poppler-utils).
All external tools are optional with graceful degradation.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CompileResult:
    success: bool
    pdf_path: Path | None = None
    tex_path: Path | None = None
    errors: list[CompileError] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    log: str = ""


@dataclass
class CompileError:
    line: int | None = None
    message: str = ""
    context: str = ""


def _run_engine(engine: str, filename: str, work_dir: Path) -> tuple[str, CompileError | None]:
    """Run a single LaTeX engine pass. Returns (stdout, error_or_none)."""
    try:
        proc = subprocess.run(
            [engine, "-interaction=nonstopmode", "-halt-on-error", f"{filename}.tex"],
            cwd=work_dir,
            capture_output=True,
            text=True,
            timeout=60,
        )
        return proc.stdout, None
    except subprocess.TimeoutExpired:
        return "", CompileError(message="Compilation timed out after 60 seconds")
    except Exception as e:
        return "", CompileError(message=f"Compilation failed: {e}")


def compile_tex(
    tex_content: str,
    output_dir: Path | None = None,
    filename: str = "document",
    bib_content: str | None = None,
) -> CompileResult:
    """Compile a .tex string to PDF using xelatex.

    Runs xelatex → (biber) → xelatex → xelatex for cross-references and
    bibliography. Falls back to pdflatex if xelatex is not available.
    Returns CompileResult with paths and any errors.
    """
    if not shutil.which("xelatex") and not shutil.which("pdflatex"):
        # No LaTeX engine available — write .tex only
        if output_dir:
            tex_path = output_dir / f"{filename}.tex"
        else:
            tex_path = Path(tempfile.mkdtemp()) / f"{filename}.tex"
        tex_path.parent.mkdir(parents=True, exist_ok=True)
        tex_path.write_text(tex_content, encoding="utf-8")
        return CompileResult(
            success=False,
            tex_path=tex_path,
            errors=[CompileError(message="No LaTeX engine found. Install xelatex or pdflatex.")],
        )

    engine = "xelatex" if shutil.which("xelatex") else "pdflatex"

    with tempfile.TemporaryDirectory(prefix="texflow_") as tmp:
        work_dir = Path(tmp)
        tex_path = work_dir / f"{filename}.tex"
        tex_path.write_text(tex_content, encoding="utf-8")

        # Write .bib file if provided
        if bib_content:
            bib_path = work_dir / "references.bib"
            bib_path.write_text(bib_content, encoding="utf-8")

        errors: list[CompileError] = []
        warnings: list[str] = []
        log_content = ""

        # Pass 1: xelatex
        log_content, err = _run_engine(engine, filename, work_dir)
        if err:
            errors.append(err)
            return CompileResult(success=False, tex_path=tex_path, errors=errors, log=log_content)

        # Pass 2: biber (conditional — only when bib content provided and biber available)
        if bib_content and shutil.which("biber"):
            try:
                subprocess.run(
                    ["biber", filename],
                    cwd=work_dir,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
            except (subprocess.TimeoutExpired, Exception) as e:
                errors.append(CompileError(message=f"Biber failed: {e}"))

        # Pass 3 & 4: xelatex (resolve references and bibliography)
        for _ in range(2):
            log_content, err = _run_engine(engine, filename, work_dir)
            if err:
                errors.append(err)
                return CompileResult(success=False, tex_path=tex_path, errors=errors, log=log_content)

        # Parse log for errors and warnings
        log_path = work_dir / f"{filename}.log"
        if log_path.exists():
            log_content = log_path.read_text(encoding="utf-8", errors="replace")
            errors = _parse_errors(log_content)
            warnings = _parse_warnings(log_content)

        pdf_path = work_dir / f"{filename}.pdf"
        success = pdf_path.exists() and not errors

        # Copy outputs to output_dir if specified
        final_tex = tex_path
        final_pdf = pdf_path if pdf_path.exists() else None
        if output_dir and output_dir != work_dir:
            output_dir.mkdir(parents=True, exist_ok=True)
            final_tex = output_dir / f"{filename}.tex"
            shutil.copy2(tex_path, final_tex)
            if pdf_path.exists():
                final_pdf = output_dir / f"{filename}.pdf"
                shutil.copy2(pdf_path, final_pdf)
            # Copy .bib file too
            bib_src = work_dir / "references.bib"
            if bib_src.exists():
                shutil.copy2(bib_src, output_dir / "references.bib")

        return CompileResult(
            success=success,
            pdf_path=final_pdf,
            tex_path=final_tex,
            errors=errors,
            warnings=warnings,
            log=log_content,
        )


@dataclass
class PreviewResult:
    png_path: Path
    page: int
    width: int
    height: int
    file_size: int  # bytes


def preview_page(
    pdf_path: Path,
    page: int = 1,
    dpi: int = 150,
    output_dir: Path | None = None,
) -> PreviewResult | None:
    """Render a PDF page to a PNG file saved alongside the PDF.

    Requires pdftoppm from poppler-utils. Returns PreviewResult with
    file path and dimensions, or None if unavailable.
    """
    if not shutil.which("pdftoppm"):
        return None

    if not pdf_path.exists():
        return None

    dest_dir = output_dir or pdf_path.parent
    dest_dir.mkdir(parents=True, exist_ok=True)
    out_prefix = dest_dir / f"preview-page{page}"

    try:
        subprocess.run(
            [
                "pdftoppm",
                "-png",
                "-r", str(dpi),
                "-f", str(page),
                "-l", str(page),
                "-singlefile",
                str(pdf_path),
                str(out_prefix),
            ],
            capture_output=True,
            timeout=30,
        )
    except (subprocess.TimeoutExpired, Exception):
        return None

    png_path = Path(f"{out_prefix}.png")
    if not png_path.exists():
        return None

    width, height = _get_png_dimensions(png_path)

    return PreviewResult(
        png_path=png_path,
        page=page,
        width=width,
        height=height,
        file_size=png_path.stat().st_size,
    )


def _get_png_dimensions(path: Path) -> tuple[int, int]:
    """Read PNG width and height from the IHDR chunk (bytes 16-23)."""
    try:
        with open(path, "rb") as f:
            f.read(16)  # Skip PNG signature (8) + IHDR chunk header (8)
            width = int.from_bytes(f.read(4), "big")
            height = int.from_bytes(f.read(4), "big")
            return width, height
    except Exception:
        return 0, 0


def _parse_errors(log: str) -> list[CompileError]:
    """Extract error messages from a LaTeX log file."""
    errors: list[CompileError] = []
    # Pattern: ! Error message
    for match in re.finditer(r"^! (.+?)$", log, re.MULTILINE):
        msg = match.group(1).strip()
        # Try to find line number
        line_match = re.search(r"l\.(\d+)", log[match.end():match.end() + 200])
        line_num = int(line_match.group(1)) if line_match else None
        # Get a bit of context
        ctx_start = max(0, match.start() - 50)
        ctx_end = min(len(log), match.end() + 200)
        context = log[ctx_start:ctx_end].strip()
        errors.append(CompileError(line=line_num, message=msg, context=context))
    return errors


def _parse_warnings(log: str) -> list[str]:
    """Extract warnings from a LaTeX log file."""
    warnings: list[str] = []
    for match in re.finditer(r"(?:LaTeX|Package) Warning: (.+?)(?:\n\n|\Z)", log, re.DOTALL):
        warning = match.group(1).strip()
        # Collapse whitespace
        warning = re.sub(r"\s+", " ", warning)
        if len(warning) > 200:
            warning = warning[:200] + "..."
        warnings.append(warning)
    return warnings
