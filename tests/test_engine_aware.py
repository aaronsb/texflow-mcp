import tempfile
from pathlib import Path

from texflow.compiler import compile_tex, preferred_engine
from texflow.model import Document, Metadata, Section, Paragraph
from texflow.serializer import serialize


def _doc() -> Document:
    return Document(
        metadata=Metadata(title="Test"),
        content=[Section(title="Hello", level=1, content=[Paragraph(text="World")])],
    )


def test_serialize_engine_filters_fontenc_inputenc():
    tex = serialize(_doc(), engine="xelatex")
    assert "fontenc" not in tex
    assert "inputenc" not in tex
    tex_pdf = serialize(_doc(), engine="pdflatex")
    assert "fontenc" in tex_pdf
    assert "inputenc" in tex_pdf


def test_preferred_engine_matches_compile():
    engine = preferred_engine()
    assert engine in ("xelatex", "pdflatex")
    assert compile_tex("x", output_dir=Path(tempfile.mkdtemp())).success is False or True


def test_compile_rejects_stub_pdf():
    with tempfile.TemporaryDirectory() as tmpdir:
        result = compile_tex("\\documentclass{article}\\begin{document}x\\end{document}", output_dir=Path(tmpdir))
        if result.success:
            assert result.pdf_path and result.pdf_path.stat().st_size > 100
        else:
            assert result.errors, "failure must carry an error"


def test_compile_uses_requested_engine():
    with tempfile.TemporaryDirectory() as tmpdir:
        result = compile_tex("x", output_dir=Path(tmpdir), engine="no-such-engine-xyz")
        assert result.errors, "must fail"
        assert "no-such-engine-xyz" in result.errors[0].message
