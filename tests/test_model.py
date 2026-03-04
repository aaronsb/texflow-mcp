"""Tests for the document model."""

import json
import tempfile
from pathlib import Path

from texflow.model import (
    CodeBlock,
    Document,
    DocumentClass,
    Equation,
    Figure,
    HeaderFooter,
    ItemList,
    Layout,
    ListItem,
    Margins,
    Metadata,
    Paragraph,
    RawLatex,
    Section,
    Table,
)


def test_default_document():
    doc = Document()
    assert doc.layout.document_class == DocumentClass.ARTICLE
    assert doc.layout.columns == 1
    assert doc.metadata.title == ""
    assert doc.content == []
    assert doc.bibliography is None


def test_required_packages_minimal():
    doc = Document()
    pkgs = doc.required_packages
    assert "inputenc" in pkgs
    assert "fontenc" in pkgs
    assert "geometry" in pkgs
    assert "hyperref" in pkgs


def test_required_packages_with_figure():
    doc = Document(content=[Figure(path="fig.png")])
    assert "graphicx" in doc.required_packages


def test_required_packages_with_equation():
    doc = Document(content=[Equation(tex="E = mc^2")])
    pkgs = doc.required_packages
    assert "amsmath" in pkgs
    assert "amssymb" in pkgs


def test_required_packages_with_booktabs_table():
    doc = Document(content=[Table(headers=["A", "B"], rows=[["1", "2"]], booktabs=True)])
    assert "booktabs" in doc.required_packages


def test_required_packages_no_booktabs():
    doc = Document(content=[Table(headers=["A"], rows=[["1"]], booktabs=False)])
    assert "booktabs" not in doc.required_packages


def test_required_packages_code():
    doc = Document(content=[CodeBlock(code="print('hello')", language="python")])
    assert "listings" in doc.required_packages


def test_required_packages_multicol():
    doc = Document(layout=Layout(columns=3))
    assert "multicol" in doc.required_packages


def test_required_packages_no_multicol_for_twocol():
    doc = Document(layout=Layout(columns=2))
    assert "multicol" not in doc.required_packages


def test_required_packages_fancyhdr():
    doc = Document(layout=Layout(header=HeaderFooter(left="Title")))
    assert "fancyhdr" in doc.required_packages


def test_required_packages_setspace():
    doc = Document(layout=Layout(line_spacing=1.5))
    assert "setspace" in doc.required_packages


def test_required_packages_nested_in_sections():
    doc = Document(content=[
        Section(title="Intro", level=1, content=[
            Paragraph(text="Hello"),
            Figure(path="fig.png"),
        ]),
    ])
    assert "graphicx" in doc.required_packages


def test_find_section():
    inner = Section(title="Data", level=2, content=[Paragraph(text="data")])
    outer = Section(title="Methods", level=1, content=[inner])
    doc = Document(content=[outer])
    assert doc.find_section("Methods") is outer
    assert doc.find_section("Methods/Data") is inner
    assert doc.find_section("Missing") is None


def test_walk_blocks():
    p1 = Paragraph(text="a")
    p2 = Paragraph(text="b")
    sec = Section(title="S", level=1, content=[p1])
    doc = Document(content=[sec, p2])
    blocks = doc._walk_blocks(doc.content)
    assert sec in blocks
    assert p1 in blocks
    assert p2 in blocks


def test_serialize_deserialize_roundtrip():
    doc = Document(
        metadata=Metadata(title="Test", author="Author", abstract="Abstract text"),
        layout=Layout(
            document_class=DocumentClass.REPORT,
            columns=2,
            font_main="palatino",
            margins=Margins(top="2cm", bottom="2cm", left="1.5cm", right="1.5cm"),
            header=HeaderFooter(left="Title", right="\\thepage"),
            toc=True,
        ),
        content=[
            Section(title="Introduction", level=1, content=[
                Paragraph(text="Hello **world**"),
                Figure(path="fig1.png", caption="A figure", label="fig:one"),
            ]),
            Section(title="Methods", level=1, content=[
                Table(
                    caption="Results",
                    headers=["A", "B"],
                    rows=[["1", "2"]],
                    booktabs=True,
                ),
                CodeBlock(code="x = 1", language="python"),
                Equation(tex="E = mc^2", label="eq:einstein"),
            ]),
        ],
    )

    data = doc.to_dict()
    json_str = json.dumps(data, indent=2)
    restored = Document.from_dict(json.loads(json_str))

    assert restored.metadata.title == "Test"
    assert restored.layout.document_class == DocumentClass.REPORT
    assert restored.layout.columns == 2
    assert restored.layout.font_main == "palatino"
    assert restored.layout.header.left == "Title"
    assert len(restored.content) == 2
    sec0 = restored.content[0]
    assert isinstance(sec0, Section)
    assert sec0.title == "Introduction"
    assert len(sec0.content) == 2
    assert isinstance(sec0.content[0], Paragraph)
    assert isinstance(sec0.content[1], Figure)
    sec1 = restored.content[1]
    assert isinstance(sec1, Section)
    assert isinstance(sec1.content[0], Table)
    assert isinstance(sec1.content[1], CodeBlock)
    assert isinstance(sec1.content[2], Equation)


def test_save_and_load():
    doc = Document(
        metadata=Metadata(title="Saved Doc"),
        content=[Paragraph(text="hello")],
    )
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = Path(f.name)

    try:
        doc.save(path)
        loaded = Document.load(path)
        assert loaded.metadata.title == "Saved Doc"
        assert len(loaded.content) == 1
        assert isinstance(loaded.content[0], Paragraph)
        assert loaded.content[0].text == "hello"
        assert loaded.save_path == path
    finally:
        path.unlink(missing_ok=True)


def test_list_block():
    lst = ItemList(
        ordered=True,
        start=1,
        items=[
            ListItem(text="First"),
            ListItem(text="Second", children=[Paragraph(text="Detail")]),
        ],
    )
    doc = Document(content=[lst])
    blocks = doc._walk_blocks(doc.content)
    # Should find the list, and the paragraph nested in the second item
    assert any(isinstance(b, ItemList) for b in blocks)
    assert any(isinstance(b, Paragraph) and b.text == "Detail" for b in blocks)


# --- Raw LaTeX package detection ---


def test_required_packages_raw_tikz():
    doc = Document(content=[RawLatex(tex="\\begin{tikzpicture}\n\\draw (0,0) -- (1,1);\n\\end{tikzpicture}")])
    assert "tikz" in doc.required_packages


def test_required_packages_raw_minted():
    doc = Document(content=[RawLatex(tex="\\begin{minted}{python}\nprint('hi')\n\\end{minted}")])
    assert "minted" in doc.required_packages


def test_required_packages_raw_includegraphics():
    doc = Document(content=[RawLatex(tex="\\includegraphics[width=5cm]{img.png}")])
    assert "graphicx" in doc.required_packages


def test_required_packages_raw_multirow():
    doc = Document(content=[RawLatex(tex="\\multirow{2}{*}{cell}")])
    assert "multirow" in doc.required_packages


def test_required_packages_raw_algorithm():
    doc = Document(content=[RawLatex(tex="\\begin{algorithm}\n\\caption{Sort}\n\\end{algorithm}")])
    assert "algorithm2e" in doc.required_packages


def test_required_packages_raw_landscape():
    doc = Document(content=[RawLatex(tex="\\begin{landscape}\nwide content\n\\end{landscape}")])
    assert "pdflscape" in doc.required_packages


def test_required_packages_raw_longtable():
    doc = Document(content=[RawLatex(tex="\\begin{longtable}{|c|c|}\nA & B\n\\end{longtable}")])
    assert "longtable" in doc.required_packages


def test_required_packages_raw_subfigure():
    doc = Document(content=[RawLatex(tex="\\begin{subfigure}{0.5\\textwidth}\n\\end{subfigure}")])
    assert "subcaption" in doc.required_packages


def test_required_packages_raw_booktabs():
    doc = Document(content=[RawLatex(tex="\\toprule\nA & B \\\\\n\\midrule\n1 & 2 \\\\\n\\bottomrule")])
    assert "booktabs" in doc.required_packages


def test_required_packages_raw_xcolor():
    doc = Document(content=[RawLatex(tex="\\textcolor{red}{warning}")])
    assert "xcolor" in doc.required_packages


def test_required_packages_raw_no_match():
    """Plain raw LaTeX without recognizable patterns adds no extra packages."""
    doc = Document(content=[RawLatex(tex="\\newpage")])
    base = Document().required_packages
    assert doc.required_packages == base


def test_required_packages_raw_multiple_packages():
    """A single RawLatex block can trigger multiple packages."""
    doc = Document(content=[RawLatex(tex="\\begin{tikzpicture}\n\\includegraphics{x.png}\n\\end{tikzpicture}")])
    pkgs = doc.required_packages
    assert "tikz" in pkgs
    assert "graphicx" in pkgs


def test_required_packages_raw_nested_in_section():
    """RawLatex inside a section is still detected via _walk_blocks."""
    doc = Document(content=[
        Section(title="Diagrams", level=1, content=[
            RawLatex(tex="\\begin{tikzpicture}\\end{tikzpicture}")
        ])
    ])
    assert "tikz" in doc.required_packages
