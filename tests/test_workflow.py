"""Tests for workflow state machine."""

from __future__ import annotations

from pathlib import Path

import pytest

from texflow.tools import state
from texflow.tools.workflow import current_state, state_hint, error_hint, _is_styled, WORKFLOW_MAP


@pytest.fixture(autouse=True)
def reset_state(tmp_path):
    """Reset shared state before each test."""
    state._current_doc = None
    state._output_dir = tmp_path
    state._save_suppressed = False
    yield
    state._current_doc = None
    state._save_suppressed = False


class TestCurrentState:
    def test_no_document(self):
        assert current_state() == "no_document"

    def test_empty_document(self):
        from texflow.tools.document import document_tool
        document_tool("create", title="Test")
        assert current_state() == "empty"

    def test_drafting_with_content(self):
        from texflow.tools.document import document_tool
        from texflow.tools.edit import edit_tool
        document_tool("create")
        edit_tool("insert", content="Hello world.")
        assert current_state() == "drafting"

    def test_styled_with_custom_layout(self):
        from texflow.tools.document import document_tool
        from texflow.tools.edit import edit_tool
        from texflow.tools.layout import layout_tool
        document_tool("create")
        edit_tool("insert", content="Hello world.")
        layout_tool(columns=2)
        assert current_state() == "styled"

    def test_styled_with_font(self):
        from texflow.tools.document import document_tool
        from texflow.tools.edit import edit_tool
        from texflow.tools.layout import layout_tool
        document_tool("create")
        edit_tool("insert", content="Hello world.")
        layout_tool(font="palatino")
        assert current_state() == "styled"

    def test_styled_with_toc(self):
        from texflow.tools.document import document_tool
        from texflow.tools.edit import edit_tool
        from texflow.tools.layout import layout_tool
        document_tool("create")
        edit_tool("insert", content="Hello world.")
        layout_tool(toc=True)
        assert current_state() == "styled"

    def test_compiled_state(self, tmp_path):
        from texflow.tools.document import document_tool
        from texflow.tools.edit import edit_tool
        document_tool("create")
        edit_tool("insert", content="Hello world.")
        # Fake a compiled PDF
        (tmp_path / "document.pdf").write_text("fake pdf")
        assert current_state() == "compiled"

    def test_compiled_takes_priority_over_styled(self, tmp_path):
        from texflow.tools.document import document_tool
        from texflow.tools.edit import edit_tool
        from texflow.tools.layout import layout_tool
        document_tool("create")
        edit_tool("insert", content="Hello world.")
        layout_tool(columns=2)
        (tmp_path / "document.pdf").write_text("fake pdf")
        assert current_state() == "compiled"


class TestIsStyled:
    def test_default_layout_not_styled(self):
        from texflow.model import Layout
        lo = Layout()
        assert not _is_styled(lo)

    def test_columns_styled(self):
        from texflow.model import Layout
        lo = Layout(columns=2)
        assert _is_styled(lo)

    def test_font_styled(self):
        from texflow.model import Layout
        lo = Layout(font_main="palatino")
        assert _is_styled(lo)

    def test_font_sans_styled(self):
        from texflow.model import Layout
        lo = Layout(font_sans="helvet")
        assert _is_styled(lo)

    def test_font_mono_styled(self):
        from texflow.model import Layout
        lo = Layout(font_mono="inconsolata")
        assert _is_styled(lo)

    def test_custom_font_size_styled(self):
        from texflow.model import Layout
        lo = Layout(font_size="11pt")
        assert _is_styled(lo)

    def test_custom_paper_styled(self):
        from texflow.model import Layout
        lo = Layout(paper_size="letterpaper")
        assert _is_styled(lo)

    def test_toc_styled(self):
        from texflow.model import Layout
        lo = Layout(toc=True)
        assert _is_styled(lo)

    def test_lof_styled(self):
        from texflow.model import Layout
        lo = Layout(lof=True)
        assert _is_styled(lo)

    def test_lot_styled(self):
        from texflow.model import Layout
        lo = Layout(lot=True)
        assert _is_styled(lo)

    def test_line_spacing_styled(self):
        from texflow.model import Layout
        lo = Layout(line_spacing=1.5)
        assert _is_styled(lo)

    def test_header_styled(self):
        from texflow.model import Layout, HeaderFooter
        lo = Layout(header=HeaderFooter(left="Title"))
        assert _is_styled(lo)

    def test_footer_styled(self):
        from texflow.model import Layout, HeaderFooter
        lo = Layout(footer=HeaderFooter(center="Page \\thepage"))
        assert _is_styled(lo)


class TestStateHint:
    def test_no_document_hint(self):
        hint = state_hint()
        assert "[no_document]" in hint
        assert "document(create)" in hint

    def test_empty_hint(self):
        from texflow.tools.document import document_tool
        document_tool("create")
        hint = state_hint()
        assert "[empty]" in hint
        assert "edit(insert)" in hint

    def test_drafting_hint(self):
        from texflow.tools.document import document_tool
        from texflow.tools.edit import edit_tool
        document_tool("create")
        edit_tool("insert", content="Hello.")
        hint = state_hint()
        assert "[drafting]" in hint
        assert "render(compile)" in hint

    def test_compiled_hint(self, tmp_path):
        from texflow.tools.document import document_tool
        from texflow.tools.edit import edit_tool
        document_tool("create")
        edit_tool("insert", content="Hello.")
        (tmp_path / "document.pdf").write_text("fake")
        hint = state_hint()
        assert "[compiled]" in hint
        assert "render(preview)" in hint


class TestErrorHint:
    def test_no_document_error(self):
        hint = error_hint("No document loaded. Use document(action='create').")
        assert "document(action='create')" in hint

    def test_section_not_found(self):
        hint = error_hint("Section not found: 'Nonexistent'")
        assert "outline" in hint

    def test_position_out_of_range(self):
        hint = error_hint("Position 5 out of range for section with 3 blocks")
        assert "outline" in hint

    def test_unknown_block_type(self):
        hint = error_hint("Unknown block_type 'widget'")
        assert "section" in hint
        assert "paragraph" in hint

    def test_compilation_failed(self):
        hint = error_hint("Compilation failed: missing \\begin{document}")
        assert "reference" in hint

    def test_latex_error(self):
        hint = error_hint("LaTeX error: Undefined control sequence")
        assert "error_help" in hint

    def test_unknown_action_no_hint(self):
        hint = error_hint("Unknown action 'fly'")
        assert hint == ""

    def test_unknown_document_class_no_hint(self):
        hint = error_hint("Unknown document class 'zine'")
        assert hint == ""

    def test_missing_required_no_hint(self):
        hint = error_hint("Missing required parameter 'title'")
        assert hint == ""

    def test_normal_result_no_hint(self):
        hint = error_hint("Created new article document.")
        assert hint == ""

    def test_queue_mention_in_no_document(self):
        hint = state_hint()
        assert "queue()" in hint


class TestWorkflowMap:
    def test_map_contains_all_states(self):
        assert "no_document" in WORKFLOW_MAP
        assert "empty" in WORKFLOW_MAP
        assert "drafting" in WORKFLOW_MAP
        assert "styled" in WORKFLOW_MAP
        assert "compiled" in WORKFLOW_MAP

    def test_map_contains_transitions(self):
        assert "create/ingest" in WORKFLOW_MAP
        assert "edit(insert)" in WORKFLOW_MAP
        assert "layout()" in WORKFLOW_MAP
