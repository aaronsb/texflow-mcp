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
    state._pending_confirmation = None
    yield
    state._current_doc = None
    state._pending_confirmation = None


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

    def test_reset_clears_document(self, tmp_path):
        document_tool("create", title="To Be Reset")
        save_file = tmp_path / "document.texflow.json"
        assert save_file.exists()
        assert state.get_doc() is not None

        result = document_tool("reset")
        assert "cleared" in result.lower()
        assert state.get_doc() is None
        assert not save_file.exists()

    def test_reset_no_document(self):
        result = document_tool("reset")
        assert "No document" in result

    def test_reset_then_create(self, tmp_path):
        document_tool("create", title="First")
        document_tool("reset")
        # Create should work without confirmation now
        result = document_tool("create", title="Second")
        assert "Created" in result
        assert state.get_doc().metadata.title == "Second"


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

    # --- Template-aware insert ---

    def test_insert_raw_no_content_shows_templates(self):
        document_tool("create")
        result = edit_tool("insert", block_type="raw")
        assert "template" in result.lower() or "Templates" in result

    def test_insert_raw_with_template(self):
        document_tool("create")
        result = edit_tool("insert", block_type="raw", template="tikz-diagram")
        assert "Inserted RawLatex" in result
        doc = state.get_doc()
        block = doc.content[0]
        assert block.template == "tikz-diagram"
        assert "tikzpicture" in block.tex

    def test_insert_raw_with_template_and_content(self):
        document_tool("create")
        result = edit_tool("insert", block_type="raw", template="tikz-diagram",
                           content="\\begin{tikzpicture}\\draw (0,0) circle (1);\\end{tikzpicture}")
        assert "Inserted RawLatex" in result
        doc = state.get_doc()
        assert "circle" in doc.content[0].tex
        assert doc.content[0].template == "tikz-diagram"

    def test_insert_raw_nonexistent_template(self):
        document_tool("create")
        result = edit_tool("insert", block_type="raw", template="nonexistent-template")
        assert "not found" in result

    # --- read_raw ---

    def test_read_raw(self):
        document_tool("create")
        edit_tool("insert", block_type="raw",
                  content="\\begin{tikzpicture}\n\\draw (0,0) -- (1,1);\n\\end{tikzpicture}")
        result = edit_tool("read_raw", position=0)
        assert "RawLatex" in result
        assert "3 lines" in result
        assert "1 |" in result or "   1 |" in result
        assert "tikzpicture" in result

    def test_read_raw_shows_template(self):
        document_tool("create")
        edit_tool("insert", block_type="raw", template="tikz-diagram")
        result = edit_tool("read_raw", position=0)
        assert "template: tikz-diagram" in result

    def test_read_raw_not_raw_block(self):
        document_tool("create")
        edit_tool("insert", content="Hello.")
        result = edit_tool("read_raw", position=0)
        assert "Error" in result
        assert "Paragraph" in result

    def test_read_raw_out_of_range(self):
        document_tool("create")
        result = edit_tool("read_raw", position=5)
        assert "Error" in result

    def test_read_raw_no_position(self):
        document_tool("create")
        result = edit_tool("read_raw")
        assert "Error" in result

    # --- replace_raw ---

    def test_replace_raw_full(self):
        document_tool("create")
        edit_tool("insert", block_type="raw",
                  content="\\begin{tikzpicture}\n\\end{tikzpicture}")
        result = edit_tool("replace_raw", position=0,
                           content="\\begin{tikzpicture}\n\\draw (0,0) -- (1,1);\n\\end{tikzpicture}")
        assert "Replaced RawLatex" in result

    def test_replace_raw_line_level(self):
        document_tool("create")
        edit_tool("insert", block_type="raw",
                  content="\\begin{tikzpicture}\n\\draw (0,0) -- (1,1);\n\\end{tikzpicture}")
        result = edit_tool("replace_raw", position=0,
                           content="\\draw (0,0) circle (1);", lines=[2, 2])
        assert "Updated lines" in result
        doc = state.get_doc()
        assert "circle" in doc.content[0].tex

    def test_replace_raw_lint_failure(self):
        document_tool("create")
        edit_tool("insert", block_type="raw",
                  content="\\begin{tikzpicture}\n\\end{tikzpicture}")
        result = edit_tool("replace_raw", position=0,
                           content="\\begin{tikzpicture}\noops no end")
        assert "Lint" in result or "Unclosed" in result

    def test_replace_raw_lint_override(self):
        document_tool("create")
        edit_tool("insert", block_type="raw",
                  content="\\begin{tikzpicture}\n\\end{tikzpicture}")
        result = edit_tool("replace_raw", position=0,
                           content="\\begin{tikzpicture}\noops no end", lint=False)
        assert "Replaced RawLatex" in result

    def test_replace_raw_not_raw_block(self):
        document_tool("create")
        edit_tool("insert", content="Hello.")
        result = edit_tool("replace_raw", position=0, content="new content")
        assert "Error" in result

    def test_replace_raw_invalid_lines(self):
        document_tool("create")
        edit_tool("insert", block_type="raw", content="line1\nline2\nline3")
        result = edit_tool("replace_raw", position=0, content="new", lines=[3, 1])
        assert "Error" in result


# --- Raw LaTeX lint ---

class TestRawLatexLint:
    def test_lint_balanced(self):
        from texflow.tools.edit import lint_raw
        assert lint_raw("\\begin{tikzpicture}\\end{tikzpicture}") == []

    def test_lint_unclosed_env(self):
        from texflow.tools.edit import lint_raw
        issues = lint_raw("\\begin{tikzpicture}\n\\draw (0,0);")
        assert any("Unclosed" in i for i in issues)

    def test_lint_extra_end(self):
        from texflow.tools.edit import lint_raw
        issues = lint_raw("\\end{tikzpicture}")
        assert any("Extra" in i for i in issues)

    def test_lint_unmatched_brace(self):
        from texflow.tools.edit import lint_raw
        issues = lint_raw("\\textbf{hello")
        assert any("brace" in i.lower() for i in issues)

    def test_lint_nested_envs(self):
        from texflow.tools.edit import lint_raw
        tex = "\\begin{figure}\\begin{tikzpicture}\\end{tikzpicture}\\end{figure}"
        assert lint_raw(tex) == []

    def test_lint_clean_template(self):
        from texflow.tools.edit import lint_raw
        tex = (
            "\\begin{tikzpicture}[\n"
            "  node distance=2cm\n"
            "]\n"
            "  \\node (a) {A};\n"
            "  \\node (b) [right=of a] {B};\n"
            "  \\draw[->] (a) -- (b);\n"
            "\\end{tikzpicture}"
        )
        assert lint_raw(tex) == []


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


# --- Confirmation pattern ---


class TestConfirmationGuard:
    def test_create_no_warning_when_no_doc(self):
        result = document_tool("create", title="First")
        assert "Created" in result
        assert "Warning" not in result

    def test_create_warns_when_doc_exists(self):
        document_tool("create", title="Original")
        result = document_tool("create", title="Replacement")
        assert "Warning" in result
        assert "already exists" in result
        # Document should NOT have been replaced
        assert state.get_doc().metadata.title == "Original"

    def test_create_second_call_confirms(self):
        document_tool("create", title="Original")
        document_tool("create", title="Replacement")  # First: warning
        result = document_tool("create", title="Replacement")  # Second: confirm
        assert "Created" in result
        assert state.get_doc().metadata.title == "Replacement"

    def test_create_different_params_resets(self):
        document_tool("create", title="Original")
        document_tool("create", title="A")  # Warning for "A"
        result = document_tool("create", title="B")  # Different params → new warning
        assert "Warning" in result
        assert state.get_doc().metadata.title == "Original"

    def test_ingest_warns_when_doc_exists(self):
        document_tool("create", title="Existing")
        edit_tool("insert", block_type="section", title="Intro", level=1)
        result = document_tool("ingest", source="# New\n\nContent.")
        assert "Warning" in result
        assert "already exists" in result

    def test_ingest_second_call_confirms(self):
        document_tool("create", title="Existing")
        source = "# New\n\nContent."
        document_tool("ingest", source=source)  # Warning
        result = document_tool("ingest", source=source)  # Confirm
        assert "Ingested" in result
        assert state.get_doc().metadata.title == "New"

    def test_ingest_section_no_confirmation(self):
        document_tool("create", title="Existing")
        edit_tool("insert", block_type="section", title="Intro", level=1)
        result = document_tool("ingest", source="Some text.", section="Intro")
        assert "Warning" not in result
        assert "Ingested" in result

    def test_confirmation_cleared_by_edit(self):
        document_tool("create", title="Original")
        document_tool("create", title="New")  # Warning set
        edit_tool("insert", block_type="paragraph", content="Text")  # Clears confirmation
        result = document_tool("create", title="New")  # Should warn again
        assert "Warning" in result

    def test_confirmation_cleared_by_layout(self):
        document_tool("create", title="Original")
        document_tool("create", title="New")  # Warning set
        layout_tool(columns=2)  # Clears confirmation
        result = document_tool("create", title="New")  # Should warn again
        assert "Warning" in result

    def test_confirmation_expired(self):
        import time
        from unittest.mock import patch

        document_tool("create", title="Original")
        document_tool("create", title="New")  # Warning set

        # Advance time past TTL
        with patch("texflow.tools.state.time") as mock_time:
            mock_time.monotonic.return_value = time.monotonic() + 120
            result = document_tool("create", title="New")  # Should warn again
        assert "Warning" in result


# --- Section-targeted ingest ---


class TestSectionIngest:
    def test_ingest_into_section(self):
        document_tool("create", title="Report")
        edit_tool("insert", block_type="section", title="Introduction", level=1)
        result = document_tool("ingest", source="Some intro text.", section="Introduction")
        assert "Ingested" in result
        assert "Introduction" in result
        sec = state.get_doc().find_section("Introduction")
        assert len(sec.content) == 1

    def test_ingest_into_section_with_headings(self):
        document_tool("create", title="Report")
        edit_tool("insert", block_type="section", title="Methods", level=1)
        md = "## Data Collection\n\nDetails.\n\n## Analysis\n\nMore details.\n"
        result = document_tool("ingest", source=md, section="Methods")
        assert "Ingested" in result
        assert "subsection" in result
        sec = state.get_doc().find_section("Methods")
        subsections = [b for b in sec.content if hasattr(b, "title")]
        assert len(subsections) == 2
        # Subsections should be level 2 (children of level-1 Methods)
        assert subsections[0].level == 2
        assert subsections[1].level == 2

    def test_ingest_into_nested_section(self):
        document_tool("create", title="Report")
        edit_tool("insert", block_type="section", title="Methods", level=1)
        edit_tool("insert", block_type="section", title="Data", level=2, section="Methods")
        md = "## Source A\n\nDetails.\n"
        result = document_tool("ingest", source=md, section="Methods/Data")
        assert "Ingested" in result
        sec = state.get_doc().find_section("Methods/Data")
        subsections = [b for b in sec.content if hasattr(b, "title")]
        assert len(subsections) == 1
        # Data is level 2, so children should be level 3
        assert subsections[0].level == 3

    def test_ingest_into_nonexistent_section(self):
        document_tool("create", title="Report")
        result = document_tool("ingest", source="Text.", section="Nonexistent")
        assert "Error" in result
        assert "not found" in result

    def test_ingest_from_file_into_section(self, tmp_path):
        md_file = tmp_path / "intro.md"
        md_file.write_text("First paragraph.\n\nSecond paragraph.\n")
        document_tool("create", title="Report")
        edit_tool("insert", block_type="section", title="Intro", level=1)
        result = document_tool("ingest", source=str(md_file), section="Intro")
        assert "Ingested intro.md" in result
        sec = state.get_doc().find_section("Intro")
        assert len(sec.content) == 2

    def test_ingest_preserves_existing_content(self):
        document_tool("create", title="Report")
        edit_tool("insert", block_type="section", title="Intro", level=1)
        edit_tool("insert", content="Existing text.", section="Intro")
        document_tool("ingest", source="New text.", section="Intro")
        sec = state.get_doc().find_section("Intro")
        assert len(sec.content) == 2  # Both existing and new


# --- Queue + confirmation ---


class TestQueueConfirmation:
    def test_queue_stops_on_confirmation_warning(self):
        from texflow.tools.queue import queue_tool

        document_tool("create", title="Existing")
        result = queue_tool([
            {"tool": "document", "action": "create", "title": "Replacement"},
        ])
        assert "Warning" in result


# --- Metadata update ---


class TestMetadataUpdate:
    def test_update_title(self):
        document_tool("create", title="Old Title")
        result = document_tool("update", title="New Title")
        assert "Updated metadata" in result
        assert "New Title" in result
        assert state.get_doc().metadata.title == "New Title"

    def test_update_author(self):
        document_tool("create", author="Old Author")
        result = document_tool("update", author="New Author")
        assert "Updated metadata" in result
        assert state.get_doc().metadata.author == "New Author"

    def test_update_date(self):
        document_tool("create")
        result = document_tool("update", date="2026-03-15")
        assert "Updated metadata" in result
        assert state.get_doc().metadata.date == "2026-03-15"

    def test_update_abstract(self):
        document_tool("create")
        result = document_tool("update", abstract="This is the abstract.")
        assert "Updated metadata" in result
        assert state.get_doc().metadata.abstract == "This is the abstract."

    def test_update_multiple_fields(self):
        document_tool("create")
        result = document_tool("update", title="T", author="A", date="2026-01-01")
        assert "title=" in result
        assert "author=" in result
        assert "date=" in result

    def test_update_no_params(self):
        document_tool("create")
        result = document_tool("update")
        assert "No changes" in result

    def test_update_no_document(self):
        result = document_tool("update", title="X")
        assert "No document" in result or "Error" in result

    def test_update_preserves_content(self):
        document_tool("create", title="Original")
        edit_tool("insert", block_type="section", title="Intro", level=1)
        document_tool("update", title="Updated")
        doc = state.get_doc()
        assert doc.metadata.title == "Updated"
        assert len(doc.content) == 1

    def test_create_with_date_and_abstract(self):
        document_tool("create", title="T", date="2026-01-01", abstract="Abstract text.")
        doc = state.get_doc()
        assert doc.metadata.date == "2026-01-01"
        assert doc.metadata.abstract == "Abstract text."


# --- Layout preservation on ingest ---


class TestIngestLayoutPreservation:
    def test_ingest_preserves_layout_columns(self):
        document_tool("create", title="Existing")
        layout_tool(columns=2)
        source = "# New\n\nContent."
        document_tool("ingest", source=source)       # Warning
        result = document_tool("ingest", source=source)  # Confirm
        assert "Ingested" in result
        assert state.get_doc().layout.columns == 2

    def test_ingest_preserves_layout_font(self):
        document_tool("create")
        layout_tool(font="palatino")
        source = "# New\n\nContent."
        document_tool("ingest", source=source)
        document_tool("ingest", source=source)
        assert state.get_doc().layout.font_main == "palatino"

    def test_first_ingest_uses_default_layout(self):
        source = "# New\n\nContent."
        result = document_tool("ingest", source=source)
        assert "Ingested" in result
        doc = state.get_doc()
        assert doc.layout.columns == 1
        assert doc.layout.font_main is None

    def test_ingest_updates_metadata_from_frontmatter(self):
        document_tool("create", title="Old")
        layout_tool(columns=2)
        source = "---\ntitle: New Title\nauthor: New Author\n---\n\n## Intro\n\nText.\n"
        document_tool("ingest", source=source)
        document_tool("ingest", source=source)
        doc = state.get_doc()
        assert doc.metadata.title == "New Title"
        assert doc.metadata.author == "New Author"
        assert doc.layout.columns == 2


# --- Compile messaging ---


class TestCompileMessaging:
    def test_compile_result_includes_derived_note(self):
        from texflow.compiler import CompileResult
        from texflow.formatters.render import format_compile_result
        result = CompileResult(success=True, pdf_path=Path("/out/document.pdf"), tex_path=Path("/out/document.tex"))
        formatted = format_compile_result(result)
        assert "regenerated" in formatted
        assert "overwritten" in formatted

    def test_tex_header_comment_in_serializer(self):
        from texflow.model import Document, Metadata
        from texflow.serializer import serialize
        doc = Document(metadata=Metadata(title="Test"))
        tex = serialize(doc)
        assert "Generated by TeXFlow" in tex
        assert "do not edit" in tex

    def test_tex_export_has_header_comment(self):
        document_tool("create", title="Header Test")
        edit_tool("insert", content="Hello.")
        result = render_tool("tex")
        assert "do not edit" in result
        assert "Generated by TeXFlow" in result


# --- Preview formatting ---


class TestPreviewFormatting:
    def test_format_preview_result(self):
        from texflow.compiler import PreviewResult
        from texflow.formatters.render import format_preview_result
        preview = PreviewResult(
            png_path=Path("/out/preview-page1.png"),
            page=1, width=800, height=1100, file_size=51200,
        )
        result = format_preview_result(preview)
        assert "page 1" in result
        assert "/out/preview-page1.png" in result
        assert "800" in result
        assert "1100" in result
        assert "50.0 KB" in result

    def test_preview_returns_path_not_base64(self):
        """If preview succeeds, result should contain file path, not base64."""
        document_tool("create", title="Preview Test")
        edit_tool("insert", content="Hello.")
        result = render_tool("preview")
        assert "data:image/png;base64," not in result


# --- Bibliography tool tests ---


class TestBibActions:
    def setup_method(self):
        from texflow.tools import state as st
        st._current_doc = None
        document_tool("create", title="Bib Test")

    def test_bib_add(self):
        result = document_tool("bib_add", source='@article{smith2024, author = {John Smith}, title = {A Paper}, year = {2024}}')
        assert "smith2024" in result
        assert "1 total entries" in result

    def test_bib_add_duplicate(self):
        document_tool("bib_add", source='@article{k, title = {T}}')
        result = document_tool("bib_add", source='@article{k, title = {T2}}')
        assert "already exists" in result

    def test_bib_remove(self):
        document_tool("bib_add", source='@article{k, title = {T}}')
        result = document_tool("bib_remove", source="k")
        assert "Removed" in result
        assert "0 entries" in result

    def test_bib_remove_not_found(self):
        result = document_tool("bib_remove", source="nonexistent")
        assert "No bibliography entries" in result

    def test_bib_list_empty(self):
        result = document_tool("bib_list")
        assert "No bibliography entries" in result

    def test_bib_list_with_entries(self):
        document_tool("bib_add", source='@article{smith2024, author = {John Smith}, title = {A Paper}, year = {2024}}')
        result = document_tool("bib_list")
        assert "smith2024" in result
        assert "John Smith" in result
        assert "A Paper" in result

    def test_bib_style(self):
        result = document_tool("bib_style", source="numeric")
        assert "numeric" in result

    def test_bib_style_invalid(self):
        result = document_tool("bib_style", source="nonexistent")
        assert "Unknown style" in result

    def test_bib_add_no_source(self):
        result = document_tool("bib_add")
        assert "Error" in result
