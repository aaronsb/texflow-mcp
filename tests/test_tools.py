"""Tests for MCP tool functions."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from texflow.tools import state
from texflow.tools.document import document_tool
from texflow.tools.layout import layout_tool
from texflow.tools.edit import edit_tool
from texflow.tools.render import render_tool
from texflow.tools.reference import reference_tool


@pytest.fixture(autouse=True)
def reset_state(tmp_path):
    """Reset shared state before each test."""
    state._current_doc = None
    state._output_dir = tmp_path
    yield
    state._current_doc = None


# --- Document tool ---

class TestDocumentTool:
    def test_create_default(self):
        result = document_tool("create")
        assert "Created new article document" in result
        assert state.get_doc() is not None

    def test_create_with_class_and_title(self):
        result = document_tool("create", document_class="report", title="My Report", author="Alice")
        assert "report" in result
        assert "My Report" in result
        assert "Alice" in result
        doc = state.get_doc()
        assert doc.metadata.title == "My Report"
        assert doc.metadata.author == "Alice"

    def test_create_invalid_class(self):
        result = document_tool("create", document_class="newspaper")
        assert "Unknown document class" in result

    def test_ingest_markdown(self):
        md = textwrap.dedent("""\
            # Test Doc

            ## Introduction

            Hello world.

            ## Methods

            Some methods here.
        """)
        result = document_tool("ingest", source=md)
        assert "Ingested text" in result
        doc = state.get_doc()
        assert doc is not None
        assert len(doc.content) > 0

    def test_ingest_file(self, tmp_path):
        md_file = tmp_path / "test.md"
        md_file.write_text("# Title\n\nParagraph here.\n")
        result = document_tool("ingest", source=str(md_file))
        assert "Ingested test.md" in result

    def test_ingest_no_source(self):
        result = document_tool("ingest")
        assert "Error" in result

    def test_outline(self):
        document_tool("create", title="Outline Test")
        edit_tool("insert", block_type="section", title="Intro", level=1)
        edit_tool("insert", content="Hello.", section="Intro")
        result = document_tool("outline")
        assert "Intro" in result
        assert "Paragraph" in result

    def test_read_all(self):
        document_tool("create")
        edit_tool("insert", block_type="paragraph", content="First paragraph.")
        result = document_tool("read")
        assert "First paragraph." in result

    def test_read_section(self):
        document_tool("create")
        edit_tool("insert", block_type="section", title="Methods", level=1)
        edit_tool("insert", content="Method details.", section="Methods")
        result = document_tool("read", section="Methods")
        assert "Method details." in result

    def test_read_missing_section(self):
        document_tool("create")
        result = document_tool("read", section="Nonexistent")
        assert "not found" in result

    def test_unknown_action(self):
        result = document_tool("foobar")
        assert "Unknown action" in result

    def test_auto_save(self, tmp_path):
        document_tool("create", title="Save Test")
        save_file = tmp_path / "document.texflow.json"
        assert save_file.exists()
        data = json.loads(save_file.read_text())
        assert data["metadata"]["title"] == "Save Test"


# --- Layout tool ---

class TestLayoutTool:
    def test_no_changes(self):
        document_tool("create")
        result = layout_tool()
        assert "No changes" in result
        assert "Current layout" in result

    def test_set_columns(self):
        document_tool("create")
        result = layout_tool(columns=2)
        assert "columns=2" in result
        assert state.get_doc().layout.columns == 2

    def test_invalid_columns(self):
        document_tool("create")
        result = layout_tool(columns=0)
        assert "Error" in result

    def test_set_font_size(self):
        document_tool("create")
        result = layout_tool(font_size="11pt")
        assert "font_size=11pt" in result

    def test_invalid_font_size(self):
        document_tool("create")
        result = layout_tool(font_size="14pt")
        assert "Error" in result

    def test_set_paper(self):
        document_tool("create")
        result = layout_tool(paper="letter")
        assert "letterpaper" in result

    def test_invalid_paper(self):
        document_tool("create")
        result = layout_tool(paper="tabloid")
        assert "Error" in result

    def test_set_margins_uniform(self):
        document_tool("create")
        result = layout_tool(margins="1in")
        assert "margins=1in" in result
        m = state.get_doc().layout.margins
        assert m.top == "1in"
        assert m.left == "1in"

    def test_set_margins_individual(self):
        document_tool("create")
        result = layout_tool(margins="top=2cm,left=1.5cm")
        doc = state.get_doc()
        assert doc.layout.margins.top == "2cm"
        assert doc.layout.margins.left == "1.5cm"

    def test_set_header(self):
        document_tool("create")
        result = layout_tool(header_left="Title", header_right="\\thepage")
        assert "header updated" in result
        h = state.get_doc().layout.header
        assert h.left == "Title"
        assert h.right == "\\thepage"

    def test_set_footer(self):
        document_tool("create")
        result = layout_tool(footer_center="Page \\thepage")
        assert "footer updated" in result

    def test_set_toc(self):
        document_tool("create")
        result = layout_tool(toc=True)
        assert "toc=True" in result
        assert state.get_doc().layout.toc is True

    def test_set_line_spacing(self):
        document_tool("create")
        result = layout_tool(line_spacing=1.5)
        assert "line_spacing=1.5" in result

    def test_multiple_changes(self):
        document_tool("create")
        result = layout_tool(columns=3, font="palatino", toc=True)
        assert "columns=3" in result
        assert "font=palatino" in result
        assert "toc=True" in result


# --- Edit tool ---

class TestEditTool:
    def test_insert_paragraph(self):
        document_tool("create")
        result = edit_tool("insert", block_type="paragraph", content="Hello world.")
        assert "Inserted Paragraph" in result

    def test_insert_section(self):
        document_tool("create")
        result = edit_tool("insert", block_type="section", title="Introduction", level=1)
        assert "Inserted Section" in result

    def test_insert_into_section(self):
        document_tool("create")
        edit_tool("insert", block_type="section", title="Methods", level=1)
        result = edit_tool("insert", content="Method details.", section="Methods")
        assert "Inserted Paragraph" in result
        assert "'Methods'" in result

    def test_insert_infer_type(self):
        document_tool("create")
        result = edit_tool("insert", content="Auto-inferred paragraph.")
        assert "Inserted Paragraph" in result

    def test_insert_figure(self):
        document_tool("create")
        result = edit_tool("insert", block_type="figure", path="image.png", caption="A figure")
        assert "Inserted Figure" in result

    def test_insert_table(self):
        document_tool("create")
        result = edit_tool("insert", block_type="table",
                          headers=["A", "B"], rows=[["1", "2"]], caption="Data")
        assert "Inserted Table" in result

    def test_insert_code(self):
        document_tool("create")
        result = edit_tool("insert", block_type="code", content="print('hi')", language="python")
        assert "Inserted CodeBlock" in result

    def test_insert_equation(self):
        document_tool("create")
        result = edit_tool("insert", block_type="equation", content="E = mc^2")
        assert "Inserted Equation" in result

    def test_insert_list(self):
        document_tool("create")
        result = edit_tool("insert", block_type="list", content="Item 1\nItem 2\nItem 3")
        assert "Inserted ItemList" in result

    def test_insert_raw(self):
        document_tool("create")
        result = edit_tool("insert", block_type="raw", content="\\newpage")
        assert "Inserted RawLatex" in result

    def test_replace(self):
        document_tool("create")
        edit_tool("insert", content="Old text.")
        result = edit_tool("replace", position=0, content="New text.")
        assert "Replaced Paragraph with Paragraph" in result
        doc = state.get_doc()
        assert doc.content[0].text == "New text."

    def test_replace_out_of_range(self):
        document_tool("create")
        edit_tool("insert", content="Only block.")
        result = edit_tool("replace", position=5, content="New.")
        assert "Error" in result

    def test_delete(self):
        document_tool("create")
        edit_tool("insert", content="Delete me.")
        result = edit_tool("delete", position=0)
        assert "Deleted Paragraph" in result
        assert len(state.get_doc().content) == 0

    def test_delete_out_of_range(self):
        document_tool("create")
        result = edit_tool("delete", position=0)
        assert "Error" in result

    def test_move(self):
        document_tool("create")
        edit_tool("insert", block_type="section", title="A", level=1)
        edit_tool("insert", block_type="section", title="B", level=1)
        edit_tool("insert", content="In A.", section="A")
        # Move paragraph from A to B
        result = edit_tool("move", section="A", position=0, target_section="B")
        assert "Moved Paragraph" in result

    def test_unknown_action(self):
        document_tool("create")
        result = edit_tool("spin")
        assert "Unknown action" in result

    def test_missing_section(self):
        document_tool("create")
        result = edit_tool("insert", content="x", section="Nonexistent")
        assert "not found" in result

    def test_build_block_unknown_type(self):
        document_tool("create")
        result = edit_tool("insert", block_type="video", content="x")
        assert "Unknown block_type" in result


# --- Render tool ---

class TestRenderTool:
    def test_tex_export(self):
        document_tool("create", title="TeX Test")
        edit_tool("insert", content="Hello.")
        result = render_tool("tex")
        assert "\\documentclass" in result
        assert "\\begin{document}" in result
        assert "Hello." in result

    def test_unknown_action(self):
        result = render_tool("deploy")
        assert "Unknown action" in result

    def test_no_document(self):
        with pytest.raises(ValueError, match="No document loaded"):
            render_tool("tex")


# --- Reference tool ---

class TestReferenceTool:
    def test_search(self):
        result = reference_tool("search", query="section")
        # Should return results or "No results" — either is valid depending on data
        assert isinstance(result, str)

    def test_search_no_query(self):
        result = reference_tool("search")
        assert "Error" in result

    def test_symbol_no_description(self):
        result = reference_tool("symbol")
        assert "Error" in result

    def test_package_no_name(self):
        result = reference_tool("package")
        assert "Error" in result

    def test_package_not_found(self):
        result = reference_tool("package", name="nonexistent_pkg_xyz")
        assert "not found" in result

    def test_error_help_no_error(self):
        result = reference_tool("error_help")
        assert "Error" in result

    def test_error_help_generic(self):
        result = reference_tool("error_help", error="Undefined control sequence \\foo")
        assert "Undefined control sequence" in result

    def test_error_help_missing_dollar(self):
        result = reference_tool("error_help", error="Missing $ inserted")
        assert "math" in result.lower()

    def test_example(self):
        result = reference_tool("example", topic="table")
        assert "tabular" in result

    def test_example_not_found(self):
        result = reference_tool("example", topic="quantum_physics")
        assert "No examples" in result

    def test_example_no_topic(self):
        result = reference_tool("example")
        assert "Error" in result

    def test_check_style_no_path(self):
        result = reference_tool("check_style")
        assert "Error" in result

    def test_check_style_missing_file(self):
        result = reference_tool("check_style", path="/nonexistent/file.tex")
        assert "not found" in result

    def test_check_style_clean(self, tmp_path):
        tex_file = tmp_path / "clean.tex"
        tex_file.write_text("\\documentclass{article}\n\\begin{document}\nHello.\n\\end{document}\n")
        result = reference_tool("check_style", path=str(tex_file))
        assert "passed" in result or "0 warnings" in result

    def test_check_style_deprecated(self, tmp_path):
        tex_file = tmp_path / "old.tex"
        tex_file.write_text("{\\bf bold text}\n")
        result = reference_tool("check_style", path=str(tex_file))
        assert "deprecated" in result
        assert "\\textbf" in result

    def test_unknown_action(self):
        result = reference_tool("nope")
        assert "Unknown action" in result
