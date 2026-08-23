"""Tests for variant cloning, shared blocks, and structural validation."""

import tempfile
from pathlib import Path

from texflow.tools.state import set_output_dir, clear_doc, get_doc
from texflow.tools.document import document_tool
from texflow.tools.edit import edit_tool


def setup_function(_):
    clear_doc()
    tmp = Path(tempfile.mkdtemp())
    set_output_dir(tmp)
    globals()["_OUT"] = tmp


def _build_paper():
    document_tool("create", document_class="ieee-conference", title="Deep Models",
                  author="A and B", abstract="We evaluate four models on AUC across tasks.")
    edit_tool("insert", block_type="section", title="Results", level=1)
    edit_tool("insert", block_type="paragraph", section="Results",
              content="Table 1 reports AUC 0.912 for X and 0.887 for Y.")
    edit_tool("insert", block_type="table", section="Results", caption="DeLong p-values",
              headers=["Model", "AUC", "p"], rows=[["X", "0.912", "0.03"], ["Y", "0.887", "0.05"]])


def test_clone_does_not_share_by_default():
    _build_paper()
    assert "Cloned" in document_tool("clone", document_class="ieee-access")
    doc = get_doc()
    assert doc.layout.document_class.value == "ieee-access"
    tbl = doc.content[0].content[1]
    assert tbl.ref == ""  # copy-on-clone, nothing shared


def test_share_then_clone_keeps_ref_and_store():
    _build_paper()
    edit_tool("share", section="Results", position=1, block_id="table:delong")
    document_tool("clone", document_class="ieee-access")
    doc = get_doc()
    tbl = doc.content[0].content[1]
    assert tbl.ref == "table:delong"
    assert "table:delong" in doc.shared
    assert (_OUT / "shared.texflow.json").exists()


def test_share_conflicts_and_type_guard():
    _build_paper()
    edit_tool("share", section="Results", position=1, block_id="table:delong")
    assert "already shared as 'table:delong'" in edit_tool("share", section="Results", position=1, block_id="other:id")
    assert "is Paragraph, not Table or Figure" in edit_tool("share", section="Results", position=0, block_id="blk")


def test_unshare_frees_store_and_detaches():
    _build_paper()
    edit_tool("share", section="Results", position=1, block_id="table:delong")
    assert "Unshared" in edit_tool("unshare", section="Results", position=1)
    doc = get_doc()
    assert doc.content[0].content[1].ref == ""
    assert doc.shared == {}


def test_validate_flags_structural_issues():
    _build_paper()
    assert "Validation clean" in document_tool("validate")
    # introduce a ragged row + empty cell
    edit_tool("insert", block_type="table", section="Results", caption="Ragged",
              headers=["a", "b", "c"], rows=[["1", "2"], ["3", "", "5"]])
    report = document_tool("validate")
    assert "Validation clean" not in report
    assert "cell(s) missing" in report
    assert "empty cell(s)" in report


def test_validate_catches_unit_shift_but_not_pvalues():
    _build_paper()
    edit_tool("insert", block_type="paragraph", section="Results",
              content="Overall accuracy was 91.2 percent in Table 1.")
    report = document_tool("validate")
    # 91.2 (prose) vs 0.912 (table) share significant digits -> flagged
    assert "numeric inconsistency" in report and "91.2" in report
    clear_doc()
    _build_paper()
    # p-values 0.03/0.05 share no significant digits with 0.912/0.887 -> clean
    assert "Validation clean" in document_tool("validate")


def test_list_variants_after_clone():
    _build_paper()
    document_tool("clone", document_class="ieee-access")
    out = document_tool("list_variants")
    assert "ieee-access.texflow.json" in out