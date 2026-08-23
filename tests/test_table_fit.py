"""Tests for table fitting / float promotion and figure width rules."""

from texflow.model import Document, DocumentClass, Layout, Metadata, Section, Table, Figure
from texflow.serializer import serialize, _is_wide_figure, _fit_table
from texflow.tools.edit import edit_tool, _RELATIVE_WIDTH_RE


def _doc(cls: DocumentClass, columns: int) -> Document:
    doc = Document(
        layout=Layout(document_class=cls, columns=columns),
        metadata=Metadata(title="T", author="A"),
    )
    doc.content.append(Section(title="S", level=1))
    return doc


def test_wide_figure_promotes_to_figure_star_twocolumn():
    doc = _doc(DocumentClass.IEEE_CONFERENCE, 2)
    fig = Figure(path="img.png", caption="Wide", width="0.8\\textwidth")
    doc.content[0].content.append(fig)
    tex = serialize(doc)
    assert "\\begin{figure*}" in tex
    assert "\\includegraphics[width=0.8\\textwidth]{img.png}" in tex


def test_narrow_figure_stays_single_column():
    doc = _doc(DocumentClass.IEEE_CONFERENCE, 2)
    fig = Figure(path="img.png", caption="Small", width="0.5\\columnwidth")
    doc.content[0].content.append(fig)
    tex = serialize(doc)
    assert "\\begin{figure}" in tex
    assert "\\begin{figure*}" not in tex


def test_wide_figuree_singlecol_does_not_promote():
    # single-column documents keep figure (never figure*)
    doc = _doc(DocumentClass.ARTICLE, 1)
    fig = Figure(path="img.png", caption="Wide", width="0.9\\linewidth")
    doc.content[0].content.append(fig)
    tex = serialize(doc)
    assert "\\begin{figure}" in tex


def test_auto_table_fit_in_twocolumn_promotes():
    doc = _doc(DocumentClass.IEEE_CONFERENCE, 2)
    # ~10-char cells x 6 cols ≈ 73 chars > 45-col-char column budget → table*
    tbl = Table(caption="Big", headers=[f"header-{i}" for i in range(6)],
                rows=[[f"value-0001" for j in range(6)] for _ in range(4)])
    doc.content[0].content.append(tbl)
    tex = serialize(doc)
    assert "\\begin{table*}" in tex
    assert "\\begin{tabular}{" in tex  # fits full width as plain tabular


def test_auto_table_fit_oversized_uses_resizebox():
    doc = _doc(DocumentClass.IEEE_CONFERENCE, 2)
    # ~15-char cells x 6 cols ≈ 103 chars: beyond full width, every cell ≤ 25
    # chars (no tabularx-worthy long text) → resizebox
    tbl = Table(caption="Huge", headers=[f"config-audiograms-v{i}" for i in range(6)],
                rows=[["AUC-0.912345678" for _ in range(6)]])
    doc.content[0].content.append(tbl)
    tex = serialize(doc)
    assert "\\begin{table*}" in tex
    assert "\\resizebox{\\linewidth}{!}{" in tex


def test_long_text_cells_prefer_tabularx():
    doc = _doc(DocumentClass.IEEE_CONFERENCE, 2)
    tbl = Table(caption="Verbatim", headers=[f"header-{i}" for i in range(4)],
                rows=[["calibration-prediction-error-budget" for _ in range(4)]])
    doc.content[0].content.append(tbl)
    tex = serialize(doc)
    assert "\\begin{tabularx}{\\linewidth}{X l l l}" in tex


def test_auto_table_fit_small_stays_in_column():
    doc = _doc(DocumentClass.IEEE_CONFERENCE, 2)
    tbl = Table(caption="Small", headers=["A", "B"], rows=[["1", "2"]])
    doc.content[0].content.append(tbl)
    tex = serialize(doc)
    assert "\\begin{table}" in tex
    assert "\\begin{table*}" not in tex


def test_fit_none_forces_plain_tabular():
    doc = _doc(DocumentClass.IEEE_CONFERENCE, 2)
    tbl = Table(caption="Big", fit="none", headers=[f"H{i}" for i in range(6)],
                rows=[["x"] * 6])
    doc.content[0].content.append(tbl)
    tex = serialize(doc)
    assert "\\begin{table}" in tex  # explicit opt-out: never auto-promotes
    assert "\\begin{tabular}{l l l l l l}" in tex
    assert "\\resizebox" not in tex
    assert "\\adjustbox" not in tex


def test_relative_width_rejects_absolute_units():
    assert _RELATIVE_WIDTH_RE.match("0.8\\textwidth")
    assert _RELATIVE_WIDTH_RE.match("1.0\\linewidth")
    assert not _RELATIVE_WIDTH_RE.match("150px")
    assert not _RELATIVE_WIDTH_RE.match("5cm")
    assert not _RELATIVE_WIDTH_RE.match("12pt")


def test_edit_rejects_absolute_figure_width():
    from texflow.tools.state import set_output_dir, clear_doc
    from texflow.tools.document import document_tool
    import tempfile
    from pathlib import Path
    set_output_dir(Path(tempfile.mkdtemp()))
    clear_doc()
    document_tool("create", title="W", author="A")
    r = edit_tool("insert", block_type="figure", path="img.png", width="5cm")
    assert "Error" in r and "relative" in r.lower()