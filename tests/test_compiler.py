"""Tests for the LaTeX compiler."""

import shutil
import tempfile
from pathlib import Path

import pytest

from texflow.compiler import CompileError, CompileResult, compile_tex, preview_page, _parse_errors
from texflow.model import Document, Metadata, Paragraph, Section
from texflow.serializer import serialize

HAS_XELATEX = shutil.which("xelatex") is not None
HAS_PDFLATEX = shutil.which("pdflatex") is not None
HAS_LATEX = HAS_XELATEX or HAS_PDFLATEX
HAS_PDFTOPPM = shutil.which("pdftoppm") is not None


def _minimal_tex() -> str:
    doc = Document(
        metadata=Metadata(title="Test"),
        content=[Section(title="Hello", level=1, content=[Paragraph(text="World")])],
    )
    return serialize(doc)


def test_compile_result_dataclass():
    r = CompileResult(success=True, pdf_path=Path("/tmp/test.pdf"))
    assert r.success is True
    assert r.errors == []


def test_parse_errors_from_log():
    log = """This is some log output
! Undefined control sequence.
l.42 \\badcommand

! Missing $ inserted.
l.55 some_text_
"""
    errors = _parse_errors(log)
    assert len(errors) == 2
    assert errors[0].message == "Undefined control sequence."
    assert errors[0].line == 42
    assert errors[1].message == "Missing $ inserted."
    assert errors[1].line == 55


def test_parse_errors_empty_log():
    assert _parse_errors("All good, no errors here.") == []


@pytest.mark.skipif(not HAS_LATEX, reason="No LaTeX engine installed")
def test_compile_minimal_document():
    tex = _minimal_tex()
    with tempfile.TemporaryDirectory() as tmpdir:
        result = compile_tex(tex, output_dir=Path(tmpdir), filename="test")
        assert result.tex_path is not None
        assert result.tex_path.exists()
        if result.success:
            assert result.pdf_path is not None
            assert result.pdf_path.exists()
            assert result.pdf_path.stat().st_size > 0


@pytest.mark.skipif(not HAS_LATEX, reason="No LaTeX engine installed")
def test_compile_with_errors():
    bad_tex = "\\documentclass{article}\n\\begin{document}\n\\badcommand\n\\end{document}"
    with tempfile.TemporaryDirectory() as tmpdir:
        result = compile_tex(bad_tex, output_dir=Path(tmpdir), filename="bad")
        assert result.tex_path is not None
        assert len(result.errors) > 0


@pytest.mark.skipif(not (HAS_LATEX and HAS_PDFTOPPM), reason="Requires LaTeX + pdftoppm")
def test_preview_page():
    tex = _minimal_tex()
    with tempfile.TemporaryDirectory() as tmpdir:
        result = compile_tex(tex, output_dir=Path(tmpdir))
        if result.success and result.pdf_path:
            preview = preview_page(result.pdf_path, page=1, dpi=72, output_dir=Path(tmpdir))
            assert preview is not None
            assert preview.png_path.exists()
            assert preview.file_size > 100
            assert preview.width > 0
            assert preview.height > 0


def test_preview_nonexistent_file():
    result = preview_page(Path("/tmp/nonexistent.pdf"))
    assert result is None


@pytest.mark.skipif(HAS_LATEX, reason="Only test when no LaTeX engine available")
def test_compile_without_engine():
    tex = _minimal_tex()
    with tempfile.TemporaryDirectory() as tmpdir:
        result = compile_tex(tex, output_dir=Path(tmpdir))
        assert result.success is False
        assert result.tex_path is not None
        assert result.tex_path.exists()
        assert any("No LaTeX engine" in e.message for e in result.errors)
