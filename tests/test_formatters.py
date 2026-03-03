"""Tests for shared formatting functions."""

from __future__ import annotations

from texflow.formatters import (
    format_blocks_as_prose,
    format_compile_result,
    format_layout,
    format_outline,
    indent,
    list_section_titles,
    status_icon,
    truncate,
    truncate_list,
)
from texflow.model import (
    Document,
    DocumentClass,
    Layout,
    Metadata,
    Paragraph,
    Section,
)


# --- Shared primitives ---


class TestTruncate:
    def test_short_text_unchanged(self):
        assert truncate("hello", 10) == "hello"

    def test_exact_length_unchanged(self):
        assert truncate("hello", 5) == "hello"

    def test_long_text_truncated(self):
        assert truncate("hello world", 8) == "hello..."

    def test_custom_suffix(self):
        assert truncate("hello world", 8, suffix="~") == "hello w~"

    def test_default_60_chars(self):
        text = "a" * 100
        result = truncate(text)
        assert len(result) == 60
        assert result.endswith("...")


class TestTruncateList:
    def test_short_list_unchanged(self):
        items = ["a", "b", "c"]
        assert truncate_list(items, 5) == ["a", "b", "c"]

    def test_exact_count_unchanged(self):
        items = ["a", "b", "c"]
        assert truncate_list(items, 3) == ["a", "b", "c"]

    def test_overflow_appends_indicator(self):
        items = ["a", "b", "c", "d", "e"]
        result = truncate_list(items, 3)
        assert len(result) == 4
        assert result[:3] == ["a", "b", "c"]
        assert "2 more" in result[3]

    def test_custom_noun(self):
        items = ["a", "b", "c"]
        result = truncate_list(items, 1, noun="more warnings")
        assert "2 more warnings" in result[1]

    def test_does_not_mutate_input(self):
        items = ["a", "b", "c"]
        truncate_list(items, 2)
        assert len(items) == 3


class TestIndent:
    def test_single_line(self):
        assert indent("hello") == "  hello"

    def test_multi_line(self):
        assert indent("a\nb") == "  a\n  b"

    def test_custom_level(self):
        assert indent("hello", level=4) == "    hello"


class TestStatusIcon:
    def test_ok(self):
        assert status_icon(True) == "ok"

    def test_error(self):
        assert status_icon(False) == "ERR"


# --- Document formatting ---


class TestFormatOutline:
    def test_empty_document(self):
        doc = Document(
            metadata=Metadata(title="Test"),
            layout=Layout(),
        )
        result = format_outline(doc)
        assert "Test" in result
        assert "(empty)" in result

    def test_with_content(self):
        doc = Document(
            metadata=Metadata(title="My Doc", author="Alice"),
            layout=Layout(),
            content=[
                Section(title="Intro", level=1, content=[
                    Paragraph(text="Hello world."),
                ]),
            ],
        )
        result = format_outline(doc)
        assert "My Doc" in result
        assert "Alice" in result
        assert "Intro" in result
        assert "Paragraph" in result
        assert "Hello world." in result

    def test_long_paragraph_truncated(self):
        long_text = "x" * 100
        doc = Document(
            metadata=Metadata(),
            layout=Layout(),
            content=[Paragraph(text=long_text)],
        )
        result = format_outline(doc)
        assert "..." in result
        assert long_text not in result


class TestFormatBlocksAsProse:
    def test_paragraph(self):
        blocks = [Paragraph(text="Hello.")]
        assert "Hello." in format_blocks_as_prose(blocks)

    def test_section_with_content(self):
        blocks = [Section(title="Intro", level=1, content=[
            Paragraph(text="Content here."),
        ])]
        result = format_blocks_as_prose(blocks)
        assert "### Intro" in result
        assert "Content here." in result


class TestListSectionTitles:
    def test_flat_sections(self):
        blocks = [
            Section(title="A", level=1),
            Section(title="B", level=1),
        ]
        assert list_section_titles(blocks) == ["A", "B"]

    def test_nested_sections(self):
        blocks = [
            Section(title="A", level=1, content=[
                Section(title="A1", level=2),
            ]),
        ]
        titles = list_section_titles(blocks)
        assert "A" in titles
        assert "A/A1" in titles


# --- Layout formatting ---


class TestFormatLayout:
    def test_default_layout(self):
        lo = Layout()
        result = format_layout(lo)
        assert "Current layout:" in result
        assert "article" in result
        assert "Columns: 1" in result
        assert "12pt" in result

    def test_custom_layout(self):
        lo = Layout(columns=2, font_main="palatino", toc=True)
        result = format_layout(lo)
        assert "Columns: 2" in result
        assert "palatino" in result
        assert "TOC: True" in result


# --- Render formatting ---


class TestFormatCompileResult:
    def test_success(self):
        from types import SimpleNamespace
        result = SimpleNamespace(
            success=True,
            pdf_path="/tmp/doc.pdf",
            tex_path="/tmp/doc.tex",
            errors=[],
            warnings=[],
        )
        text = format_compile_result(result)
        assert "Compilation successful" in text
        assert "/tmp/doc.pdf" in text

    def test_failure_with_errors(self):
        from types import SimpleNamespace
        result = SimpleNamespace(
            success=False,
            pdf_path=None,
            tex_path="/tmp/doc.tex",
            errors=[SimpleNamespace(message="Undefined control sequence", line=42)],
            warnings=[],
        )
        text = format_compile_result(result)
        assert "Compilation failed" in text
        assert "Undefined control sequence" in text
        assert "line 42" in text

    def test_warnings_truncated(self):
        from types import SimpleNamespace
        result = SimpleNamespace(
            success=True,
            pdf_path="/tmp/doc.pdf",
            tex_path="/tmp/doc.tex",
            errors=[],
            warnings=[f"warning {i}" for i in range(10)],
        )
        text = format_compile_result(result)
        assert "Warnings (10):" in text
        assert "5 more warnings" in text
