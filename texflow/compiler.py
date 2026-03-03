"""Compile .tex to PDF and preview pages.

Handles xelatex subprocess, error parsing from .log files,
and page preview via pdftoppm (poppler-utils).
All external tools are optional with graceful degradation.
"""

from __future__ import annotations

import base64
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


def compile_tex(tex_content: str, output_dir: Path | None = None, filename: str = "document") -> CompileResult:
    """Compile a .tex string to PDF using xelatex.

    Runs xelatex twice for TOC/references. Falls back to pdflatex if xelatex
    is not available. Returns CompileResult with paths and any errors.
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

        errors: list[CompileError] = []
        warnings: list[str] = []
        log_content = ""

        # Run twice for cross-references
        for pass_num in range(2):
            try:
                proc = subprocess.run(
                    [engine, "-interaction=nonstopmode", "-halt-on-error", f"{filename}.tex"],
                    cwd=work_dir,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                log_content = proc.stdout
            except subprocess.TimeoutExpired:
                errors.append(CompileError(message="Compilation timed out after 60 seconds"))
                return CompileResult(success=False, tex_path=tex_path, errors=errors, log=log_content)
            except Exception as e:
                errors.append(CompileError(message=f"Compilation failed: {e}"))
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

        return CompileResult(
            success=success,
            pdf_path=final_pdf,
            tex_path=final_tex,
            errors=errors,
            warnings=warnings,
            log=log_content,
        )


def preview_page(pdf_path: Path, page: int = 1, dpi: int = 150) -> str | None:
    """Render a PDF page to a base64-encoded PNG string.

    Requires pdftoppm from poppler-utils. Returns None if not available.
    """
    if not shutil.which("pdftoppm"):
        return None

    if not pdf_path.exists():
        return None

    with tempfile.TemporaryDirectory(prefix="texflow_preview_") as tmp:
        out_prefix = Path(tmp) / "page"
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
        if png_path.exists():
            return base64.b64encode(png_path.read_bytes()).decode("ascii")

    return None


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
