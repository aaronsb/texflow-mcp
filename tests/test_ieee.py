"""Tests for IEEE class support: preamble, author blocks, bibliography."""

from texflow.model import (
    Document, DocumentClass, Layout, Metadata, Paragraph, Section, Bibliography, BibEntry,
)
from texflow.serializer import serialize, serialize_bib


def _ieee_doc(cls: DocumentClass, author: str = "Ada Lovelace and Charles Babbage") -> Document:
    doc = Document(
        layout=Layout(document_class=cls, columns=2),
        metadata=Metadata(
            title="A Distributed Difference Engine",
            author=author,
            affiliations=["Analytical Engine Group", "Difference Engine Dept"],
            keywords=["computing", "mechanical"],
            abstract="We generalize the analytical engine.",
        ),
    )
    doc.content.append(Section(title="Introduction", level=1, content=[Paragraph(text="Hello.")]))
    return doc


def test_ieee_access_preamble():
    doc = _ieee_doc(DocumentClass.IEEE_ACCESS)
    tex = serialize(doc)
    # ieeeaccess.cls is its own class (downloaded, not bundled) — the actual
    # IEEE Author Center template form also starts with \documentclass{ieeeaccess}.
    assert "\\documentclass{ieeeaccess}" in tex
    assert "\\IEEEoverridecommandlockouts" in tex
    assert "\\IEEEpubid" in tex and "https://creativecommons.org/licenses/by/4.0/" in tex
    assert "\\usepackage[colorlinks=true" in tex  # hyperref kept for the pubid \href


def test_ieee_access_author_block():
    tex = serialize(_ieee_doc(DocumentClass.IEEE_ACCESS))
    assert "\\IEEEauthorblockN{Ada Lovelace}" in tex
    assert "\\IEEEauthorblockA{\\textit{Analytical Engine Group}}" in tex
    assert "\\and" in tex
    assert "\\IEEEauthorblockN{Charles Babbage}" in tex
    assert "\\markboth{Ada Lovelace}{A Distributed Difference Engine}" in tex
    assert "\\begin{IEEEkeywords}\ncomputing, mechanical\n\\end{IEEEkeywords}" in tex


def test_ieee_uses_bibtex_style_and_bib_file():
    doc = _ieee_doc(DocumentClass.IEEE_CONFERENCE)
    doc.bibliography = Bibliography(style="ieeetran", entries=[BibEntry(key="lovelace", entry_type="article", fields={"title": "Notes"})])
    tex = serialize(doc)
    assert "\\bibliographystyle{IEEEtran}" in tex
    assert "\\bibliography{references}" in tex
    bib = serialize_bib(doc)
    assert "@article{lovelace," in bib


def test_ieee_required_packages():
    doc = _ieee_doc(DocumentClass.IEEE_ACCESS)
    assert "hyperref" in doc.required_packages  # IEEE Access pubid href
    assert "geometry" not in doc.required_packages  # class manages layout
    doc2 = _ieee_doc(DocumentClass.IEEE_CONFERENCE)
    assert "hyperref" not in doc2.required_packages
    # two-column defaults
    assert doc.layout.columns == 2
    assert doc2.layout.columns == 2