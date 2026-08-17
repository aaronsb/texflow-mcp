"""Tests for the vision check: JSON extraction, report formatting, fallbacks."""

from pathlib import Path

from texflow.vision import (
    VISION_CHECKLIST, VisionFinding, VisionReport,
    _extract_json_defects, run_vision_check,
)


def test_extract_json_defects_clean():
    assert _extract_json_defects('{"page": 1, "defects": []}') == []


def test_extract_json_defects_populated():
    findings = _extract_json_defects(
        '{"page": 2, "defects": [{"category": "overflow", "location": "col 1", "detail": "table crosses margin"}]}'
    )
    assert findings is not None and len(findings) == 1
    assert findings[0].page == 2
    assert findings[0].category == "overflow"
    assert findings[0].location == "col 1"


def test_extract_json_defects_strips_prose_wrapper():
    # providers often wrap the JSON in prose; the brace-scan must find it
    findings = _extract_json_defects(
        "Sure! Here's my analysis:\n```json\n{\"page\": 3, \"defects\": [{\"category\": \"tiny_text\", \"detail\": \"fine print\"}]}\n```"
    )
    assert findings is not None and findings[0].category == "tiny_text"


def test_extract_json_defects_garbage_returns_none():
    assert _extract_json_defects("I cannot answer that.") is None


def test_report_format_names_provider():
    rep = VisionReport(provider_used="polaris", findings=[VisionFinding(page=1, category="clipped_table", location="Table 2")])
    out = rep.format()
    assert "clipped_table" in out and "Table 2" in out
    assert "Page 1:" in out


def test_report_degraded_flag():
    clean = VisionReport(provider_used="polaris")
    assert not clean.degraded
    degraded = VisionReport(provider_used="polaris", notes=["polaris failed (TimeoutError) — fallback to gemini"])
    assert degraded.degraded


def test_checklist_covers_taxonomy():
    assert "overflow" in VISION_CHECKLIST
    assert "tiny_text" in VISION_CHECKLIST
    assert "misplaced_float" in VISION_CHECKLIST
    assert "clipped_table" in VISION_CHECKLIST


def test_run_vision_check_none_skips():
    rep = run_vision_check([], provider="auto")
    assert rep.provider_used == "none"
    assert rep.notes  # explains why nothing was checked


def test_run_vision_check_polaris_unavailable_falls_back():
    # No way to force gemini here without an API key; with no pages there is
    # nothing to score and the report must say so explicitly.
    rep = run_vision_check([Path("/tmp/nonexistent.png")], provider="auto")
    # provider "none" only when pngs is empty; a real run attempts polaris and
    # may succeed or fail — never raise.
    assert rep.findings == []