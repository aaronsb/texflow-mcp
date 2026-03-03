"""Tests for queue tool."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from texflow.tools import state
from texflow.tools.queue import queue_tool


@pytest.fixture(autouse=True)
def reset_state(tmp_path):
    """Reset shared state before each test."""
    state._current_doc = None
    state._output_dir = tmp_path
    state._save_suppressed = False
    yield
    state._current_doc = None
    state._save_suppressed = False


class TestQueueBasics:
    def test_empty_operations(self):
        result = queue_tool([])
        assert "empty" in result

    def test_too_many_operations(self):
        ops = [{"tool": "edit", "action": "insert", "content": "x"}] * 51
        result = queue_tool(ops)
        assert "maximum 50" in result

    def test_single_operation(self):
        result = queue_tool([
            {"tool": "document", "action": "create", "title": "Test"},
        ])
        assert "1 of 1" in result
        assert "Success: 1" in result
        assert state.get_doc() is not None

    def test_invalid_operation_type(self):
        result = queue_tool(["not a dict"])
        assert "ERR" in result
        assert "must be a dict" in result

    def test_missing_tool_key(self):
        result = queue_tool([{"action": "create"}])
        assert "ERR" in result
        assert "Missing 'tool'" in result

    def test_unknown_tool(self):
        result = queue_tool([{"tool": "printer"}])
        assert "ERR" in result
        assert "unknown tool" in result


class TestQueueExecution:
    def test_multi_step_document_build(self):
        result = queue_tool([
            {"tool": "document", "action": "create", "title": "Queue Test", "author": "Bot"},
            {"tool": "edit", "action": "insert", "block_type": "section", "title": "Intro", "level": 1},
            {"tool": "edit", "action": "insert", "content": "Hello world.", "section": "Intro"},
            {"tool": "edit", "action": "insert", "block_type": "equation", "content": "E=mc^2", "section": "Intro"},
            {"tool": "layout", "columns": 2, "font": "palatino", "toc": True},
        ])
        assert "5 of 5" in result
        assert "Success: 5" in result
        assert "Errors: 0" in result

        doc = state.get_doc()
        assert doc.metadata.title == "Queue Test"
        assert doc.layout.columns == 2
        assert len(doc.content) == 1  # One section
        assert len(doc.content[0].content) == 2  # paragraph + equation

    def test_single_disk_write(self, tmp_path):
        """Queue should only write to disk once, not per-operation."""
        save_path = tmp_path / "document.texflow.json"

        result = queue_tool([
            {"tool": "document", "action": "create", "title": "Save Test"},
            {"tool": "edit", "action": "insert", "content": "First."},
            {"tool": "edit", "action": "insert", "content": "Second."},
            {"tool": "edit", "action": "insert", "content": "Third."},
        ])
        assert "Success: 4" in result

        # File should exist with final state
        assert save_path.exists()
        data = json.loads(save_path.read_text())
        assert len(data["content"]) == 3  # All three paragraphs

    def test_layout_in_queue(self):
        result = queue_tool([
            {"tool": "document", "action": "create"},
            {"tool": "layout", "columns": 3, "font_size": "11pt", "paper": "letter"},
        ])
        assert "Success: 2" in result
        doc = state.get_doc()
        assert doc.layout.columns == 3
        assert doc.layout.font_size == "11pt"
        assert doc.layout.paper_size == "letterpaper"

    def test_reference_in_queue(self):
        result = queue_tool([
            {"tool": "reference", "action": "example", "topic": "table"},
        ])
        assert "Success: 1" in result


class TestQueueErrorHandling:
    def test_stop_on_error_default(self):
        result = queue_tool([
            {"tool": "document", "action": "create"},
            {"tool": "edit", "action": "insert", "content": "Good."},
            {"tool": "edit", "action": "insert", "content": "Also good.", "section": "Nonexistent"},
            {"tool": "edit", "action": "insert", "content": "Never reached."},
        ])
        assert "3 of 4" in result
        assert "Success: 2" in result
        assert "Errors: 1" in result
        assert "Stopped at operation 3" in result

    def test_continue_on_error(self):
        result = queue_tool([
            {"tool": "document", "action": "create"},
            {"tool": "edit", "action": "insert", "content": "Good."},
            {"tool": "edit", "action": "insert", "content": "Bad.", "section": "Nonexistent"},
            {"tool": "edit", "action": "insert", "content": "Also good."},
        ], continue_on_error=True)
        assert "4 of 4" in result
        assert "Success: 3" in result
        assert "Errors: 1" in result
        assert "Stopped" not in result

    def test_error_in_first_op(self):
        result = queue_tool([
            {"tool": "edit", "action": "insert", "content": "No doc yet."},
        ])
        assert "Errors: 1" in result

    def test_save_suppression_restored_after_error(self):
        """Even if queue errors out, save suppression should be restored."""
        queue_tool([
            {"tool": "document", "action": "create"},
            {"tool": "edit", "action": "insert", "content": "x", "section": "Nope"},
        ])
        # Save suppression should be False after queue
        assert state._save_suppressed is False

    def test_save_suppression_restored_after_exception(self):
        """Save suppression is restored even on unexpected exceptions."""
        # Force an exception by passing something that will cause a TypeError
        queue_tool([
            {"tool": "document", "action": "create"},
        ])
        assert state._save_suppressed is False


class TestQueueResults:
    def test_result_format(self):
        result = queue_tool([
            {"tool": "document", "action": "create", "title": "Fmt Test"},
            {"tool": "edit", "action": "insert", "content": "Para."},
        ])
        lines = result.strip().split("\n")
        # First line: summary
        assert "2 of 2" in lines[0]
        # Should have numbered results
        assert "[1] ok:" in result
        assert "[2] ok:" in result

    def test_error_result_format(self):
        result = queue_tool([
            {"tool": "unknown_tool"},
        ])
        assert "[1] ERR:" in result
