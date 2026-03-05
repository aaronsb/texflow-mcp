"""Tests for LaTeX file ingestion (.tex → Document model)."""

from texflow.model import (
    CodeBlock,
    Document,
    Equation,
    Figure,
    ItemList,
    Layout,
    ListItem,
    Metadata,
    Paragraph,
    RawLatex,
    Section,
    Table,
)
from texflow.serializer import serialize
from texflow.tex_ingestion import (
    _convert_line,
    _latex_inline_to_markdown,
    _unescape_latex,
    ingest_tex,
)


# --- Inline markup reversal ---


class TestInlineMarkup:
    def test_textbf_to_bold(self):
        assert _latex_inline_to_markdown("\\textbf{hello}") == "**hello**"

    def test_textit_to_italic(self):
        assert _latex_inline_to_markdown("\\textit{hello}") == "*hello*"

    def test_texttt_to_code(self):
        assert _latex_inline_to_markdown("\\texttt{hello}") == "`hello`"

    def test_href_to_link(self):
        assert _latex_inline_to_markdown("\\href{http://x.com}{click}") == "[click](http://x.com)"

    def test_mixed_inline(self):
        result = _latex_inline_to_markdown("See \\textbf{bold} and \\textit{italic}")
        assert result == "See **bold** and *italic*"


class TestUnescape:
    def test_basic_escapes(self):
        assert _unescape_latex("\\&") == "&"
        assert _unescape_latex("\\%") == "%"
        assert _unescape_latex("\\$") == "$"
        assert _unescape_latex("\\#") == "#"
        assert _unescape_latex("\\_") == "_"

    def test_special_escapes(self):
        assert _unescape_latex("\\textasciitilde{}") == "~"
        assert _unescape_latex("\\textasciicircum{}") == "^"
        assert _unescape_latex("\\textbackslash{}") == "\\"

    def test_convert_line(self):
        result = _convert_line("Hello \\textbf{world} \\& friends")
        assert result == "Hello **world** & friends"


# --- Preamble parsing ---


class TestPreambleParsing:
    def test_documentclass(self):
        tex = "\\documentclass[12pt,a4paper]{article}\n\\begin{document}\n\\end{document}"
        doc = ingest_tex(tex)
        assert doc.layout.font_size == "12pt"
        assert doc.layout.paper == "a4paper"

    def test_metadata(self):
        tex = (
            "\\documentclass{article}\n"
            "\\title{My Title}\n"
            "\\author{Alice}\n"
            "\\date{2026}\n"
            "\\begin{document}\n\\end{document}"
        )
        doc = ingest_tex(tex)
        assert doc.metadata.title == "My Title"
        assert doc.metadata.author == "Alice"
        assert doc.metadata.date == "2026"

    def test_geometry_margins(self):
        tex = (
            "\\documentclass{article}\n"
            "\\usepackage[top=2in,bottom=1.5in,left=1in,right=1in]{geometry}\n"
            "\\begin{document}\n\\end{document}"
        )
        doc = ingest_tex(tex)
        assert doc.layout.margins.top == "2in"
        assert doc.layout.margins.bottom == "1.5in"

    def test_documentclass_no_options(self):
        tex = "\\documentclass{report}\n\\begin{document}\n\\end{document}"
        doc = ingest_tex(tex)
        assert doc.layout.document_class.value == "report"

    def test_twocolumn(self):
        tex = "\\documentclass[12pt,a4paper,twocolumn]{article}\n\\begin{document}\n\\end{document}"
        doc = ingest_tex(tex)
        assert doc.layout.columns == 2

    def test_line_spacing(self):
        tex = "\\documentclass{article}\n\\onehalfspacing\n\\begin{document}\n\\end{document}"
        doc = ingest_tex(tex)
        assert doc.layout.line_spacing == 1.5


# --- Body parsing ---


class TestSections:
    def test_single_section(self):
        tex = "\\begin{document}\n\\section{Intro}\nHello.\n\\end{document}"
        doc = ingest_tex(tex)
        assert len(doc.content) == 1
        sec = doc.content[0]
        assert isinstance(sec, Section)
        assert sec.title == "Intro"
        assert sec.level == 1

    def test_nested_sections(self):
        tex = (
            "\\begin{document}\n"
            "\\section{Top}\n"
            "\\subsection{Sub}\n"
            "Content.\n"
            "\\section{Next}\n"
            "\\end{document}"
        )
        doc = ingest_tex(tex)
        assert len(doc.content) == 2
        assert doc.content[0].title == "Top"
        assert len(doc.content[0].content) == 1  # subsection
        sub = doc.content[0].content[0]
        assert isinstance(sub, Section)
        assert sub.title == "Sub"
        assert sub.level == 2
        assert doc.content[1].title == "Next"

    def test_section_label(self):
        tex = "\\begin{document}\n\\section{Labeled}\n\\label{sec:labeled}\nText.\n\\end{document}"
        doc = ingest_tex(tex)
        sec = doc.content[0]
        assert sec.label == "sec:labeled"


class TestParagraphs:
    def test_simple_paragraph(self):
        tex = "\\begin{document}\nHello world.\n\\end{document}"
        doc = ingest_tex(tex)
        assert len(doc.content) == 1
        assert isinstance(doc.content[0], Paragraph)
        assert doc.content[0].text == "Hello world."

    def test_paragraph_with_inline_markup(self):
        tex = "\\begin{document}\nSee \\textbf{bold} and \\textit{italic}.\n\\end{document}"
        doc = ingest_tex(tex)
        p = doc.content[0]
        assert isinstance(p, Paragraph)
        assert "**bold**" in p.text
        assert "*italic*" in p.text

    def test_multiple_paragraphs(self):
        tex = "\\begin{document}\nFirst para.\n\nSecond para.\n\\end{document}"
        doc = ingest_tex(tex)
        assert len(doc.content) == 2
        assert doc.content[0].text == "First para."
        assert doc.content[1].text == "Second para."


class TestEquations:
    def test_numbered_equation(self):
        tex = "\\begin{document}\n\\begin{equation}\nE = mc^2\n\\end{equation}\n\\end{document}"
        doc = ingest_tex(tex)
        eq = doc.content[0]
        assert isinstance(eq, Equation)
        assert eq.tex == "E = mc^2"
        assert eq.numbered is True

    def test_unnumbered_equation(self):
        tex = "\\begin{document}\n\\[\nE = mc^2\n\\]\n\\end{document}"
        doc = ingest_tex(tex)
        eq = doc.content[0]
        assert isinstance(eq, Equation)
        assert eq.tex == "E = mc^2"
        assert eq.numbered is False

    def test_equation_with_label(self):
        tex = "\\begin{document}\n\\begin{equation}\n\\label{eq:emc}\nE = mc^2\n\\end{equation}\n\\end{document}"
        doc = ingest_tex(tex)
        eq = doc.content[0]
        assert eq.label == "eq:emc"


class TestFigures:
    def test_basic_figure(self):
        tex = (
            "\\begin{document}\n"
            "\\begin{figure}[htbp]\n"
            "\\centering\n"
            "\\includegraphics[width=0.8\\textwidth]{image.png}\n"
            "\\caption{A figure}\n"
            "\\label{fig:test}\n"
            "\\end{figure}\n"
            "\\end{document}"
        )
        doc = ingest_tex(tex)
        fig = doc.content[0]
        assert isinstance(fig, Figure)
        assert fig.path == "image.png"
        assert fig.caption == "A figure"
        assert fig.label == "fig:test"
        assert fig.width == "0.8\\textwidth"


class TestTables:
    def test_basic_table(self):
        tex = (
            "\\begin{document}\n"
            "\\begin{table}[htbp]\n"
            "\\centering\n"
            "\\begin{tabular}{l c r}\n"
            "\\toprule\n"
            "Name & Value & Unit \\\\\n"
            "\\midrule\n"
            "Mass & 10 & kg \\\\\n"
            "Speed & 5 & m/s \\\\\n"
            "\\bottomrule\n"
            "\\end{tabular}\n"
            "\\caption{Test table}\n"
            "\\end{table}\n"
            "\\end{document}"
        )
        doc = ingest_tex(tex)
        tbl = doc.content[0]
        assert isinstance(tbl, Table)
        assert tbl.headers == ["Name", "Value", "Unit"]
        assert len(tbl.rows) == 2
        assert tbl.rows[0] == ["Mass", "10", "kg"]
        assert tbl.booktabs is True
        assert tbl.caption == "Test table"


class TestCodeBlocks:
    def test_basic_code(self):
        tex = (
            "\\begin{document}\n"
            "\\begin{lstlisting}[language=Python, caption={Hello}]\n"
            "print('hello')\n"
            "\\end{lstlisting}\n"
            "\\end{document}"
        )
        doc = ingest_tex(tex)
        code = doc.content[0]
        assert isinstance(code, CodeBlock)
        assert code.language == "Python"
        assert code.caption == "Hello"
        assert "print('hello')" in code.code


class TestLists:
    def test_unordered_list(self):
        tex = (
            "\\begin{document}\n"
            "\\begin{itemize}\n"
            "\\item First\n"
            "\\item Second\n"
            "\\end{itemize}\n"
            "\\end{document}"
        )
        doc = ingest_tex(tex)
        lst = doc.content[0]
        assert isinstance(lst, ItemList)
        assert lst.ordered is False
        assert len(lst.items) == 2
        assert lst.items[0].text == "First"

    def test_ordered_list(self):
        tex = (
            "\\begin{document}\n"
            "\\begin{enumerate}\n"
            "\\item Alpha\n"
            "\\item Beta\n"
            "\\end{enumerate}\n"
            "\\end{document}"
        )
        doc = ingest_tex(tex)
        lst = doc.content[0]
        assert isinstance(lst, ItemList)
        assert lst.ordered is True


class TestAbstract:
    def test_abstract_to_metadata(self):
        tex = (
            "\\documentclass{article}\n"
            "\\title{Test}\n"
            "\\begin{document}\n"
            "\\begin{abstract}\n"
            "This is the abstract.\n"
            "\\end{abstract}\n"
            "\\section{Intro}\nContent.\n"
            "\\end{document}"
        )
        doc = ingest_tex(tex)
        assert doc.metadata.abstract == "This is the abstract."
        # Abstract should not appear as a block
        assert all(not isinstance(b, RawLatex) for b in doc.content)


class TestGracefulDegradation:
    def test_unknown_env_becomes_raw(self):
        tex = (
            "\\begin{document}\n"
            "\\begin{tikzpicture}\n"
            "\\draw (0,0) -- (1,1);\n"
            "\\end{tikzpicture}\n"
            "\\end{document}"
        )
        doc = ingest_tex(tex)
        raw = doc.content[0]
        assert isinstance(raw, RawLatex)
        assert "tikzpicture" in raw.tex
        assert "\\draw" in raw.tex

    def test_no_begin_document(self):
        # Source without \begin{document} — treated as body
        tex = "\\section{Intro}\nHello.\n"
        doc = ingest_tex(tex)
        assert len(doc.content) == 1
        assert doc.content[0].title == "Intro"


class TestLayoutFlags:
    def test_toc_detected(self):
        tex = "\\begin{document}\n\\tableofcontents\n\\section{Intro}\nHi.\n\\end{document}"
        doc = ingest_tex(tex)
        assert doc.layout.toc is True

    def test_skip_maketitle(self):
        tex = "\\begin{document}\n\\maketitle\n\\section{Intro}\nHi.\n\\end{document}"
        doc = ingest_tex(tex)
        # maketitle should not create a block
        assert len(doc.content) == 1
        assert isinstance(doc.content[0], Section)


# --- Round-trip test ---


class TestRoundTrip:
    def test_basic_round_trip(self):
        """Serialize a document, ingest the .tex, verify model is equivalent."""
        original = Document(
            metadata=Metadata(title="Round Trip", author="Test", date="2026"),
            layout=Layout(),
            content=[
                Section(title="Introduction", level=1, content=[
                    Paragraph(text="Hello **bold** and *italic* world."),
                    Paragraph(text="Second paragraph with `code`."),
                ]),
                Section(title="Methods", level=1, content=[
                    Section(title="Data", level=2, content=[
                        Paragraph(text="Some data description."),
                    ]),
                ]),
                Section(title="Results", level=1, content=[
                    Equation(tex="E = mc^2", numbered=True),
                ]),
            ],
        )
        tex = serialize(original)
        restored = ingest_tex(tex)

        assert restored.metadata.title == "Round Trip"
        assert restored.metadata.author == "Test"
        assert len(restored.content) == 3
        assert restored.content[0].title == "Introduction"
        assert restored.content[1].title == "Methods"
        assert restored.content[2].title == "Results"

        # Check nested section
        methods = restored.content[1]
        assert len(methods.content) == 1
        assert methods.content[0].title == "Data"

        # Check paragraphs preserved inline markup
        intro = restored.content[0]
        assert len(intro.content) == 2
        p1 = intro.content[0]
        assert isinstance(p1, Paragraph)
        assert "**bold**" in p1.text
        assert "*italic*" in p1.text

    def test_round_trip_with_table(self):
        original = Document(
            metadata=Metadata(title="Table Test"),
            content=[
                Table(
                    headers=["A", "B"],
                    rows=[["1", "2"], ["3", "4"]],
                    caption="My table",
                    booktabs=True,
                ),
            ],
        )
        tex = serialize(original)
        restored = ingest_tex(tex)
        tbl = restored.content[0]
        assert isinstance(tbl, Table)
        assert tbl.headers == ["A", "B"]
        assert tbl.rows == [["1", "2"], ["3", "4"]]
        assert tbl.booktabs is True

    def test_round_trip_with_code(self):
        original = Document(
            metadata=Metadata(title="Code Test"),
            content=[
                CodeBlock(code="x = 1", language="Python", caption="Example"),
            ],
        )
        tex = serialize(original)
        restored = ingest_tex(tex)
        code = restored.content[0]
        assert isinstance(code, CodeBlock)
        assert "x = 1" in code.code
        assert code.language == "Python"

    def test_round_trip_with_list(self):
        original = Document(
            metadata=Metadata(title="List Test"),
            content=[
                ItemList(
                    items=[ListItem(text="First"), ListItem(text="Second")],
                    ordered=True,
                ),
            ],
        )
        tex = serialize(original)
        restored = ingest_tex(tex)
        lst = restored.content[0]
        assert isinstance(lst, ItemList)
        assert lst.ordered is True
        assert len(lst.items) == 2
        assert lst.items[0].text == "First"

    def test_round_trip_table_then_list(self):
        """Regression: nested envs (tabular inside table) must not swallow subsequent envs."""
        original = Document(
            metadata=Metadata(title="Mixed Test"),
            content=[
                Section(title="Results", level=1, content=[
                    Table(headers=["X"], rows=[["1"]], booktabs=True),
                    ItemList(
                        items=[ListItem(text="A"), ListItem(text="B")],
                        ordered=False,
                    ),
                ]),
            ],
        )
        tex = serialize(original)
        restored = ingest_tex(tex)
        results = restored.content[0]
        assert len(results.content) == 2
        assert isinstance(results.content[0], Table)
        assert isinstance(results.content[1], ItemList)
        assert len(results.content[1].items) == 2


# --- Citation and bibliography tests ---

from texflow.tex_ingestion import parse_bib_file, _latex_inline_to_markdown


class TestCitationReversal:
    def test_cite_to_bracket(self):
        result = _latex_inline_to_markdown("See \\cite{smith2024}.")
        assert result == "See [@smith2024]."

    def test_cite_with_option(self):
        result = _latex_inline_to_markdown("See \\cite[p. 42]{smith2024}.")
        assert result == "See [@smith2024, p. 42]."

    def test_textcite_to_bracket(self):
        result = _latex_inline_to_markdown("\\textcite{jones2023} argues")
        assert result == "[@jones2023] argues"

    def test_parencite_to_bracket(self):
        result = _latex_inline_to_markdown("results \\parencite{doe2022}")
        assert result == "results [@doe2022]"

    def test_multiple_cites(self):
        result = _latex_inline_to_markdown("\\cite{a} and \\cite{b}")
        assert "[@a]" in result
        assert "[@b]" in result


class TestBibFileParsing:
    def test_single_entry(self):
        bib = """@article{smith2024,
  author = {John Smith},
  title = {A Great Paper},
  year = {2024}
}"""
        entries = parse_bib_file(bib)
        assert len(entries) == 1
        assert entries[0].key == "smith2024"
        assert entries[0].entry_type == "article"
        assert entries[0].fields["author"] == "John Smith"
        assert entries[0].fields["title"] == "A Great Paper"
        assert entries[0].fields["year"] == "2024"

    def test_multiple_entries(self):
        bib = """@book{a,
  title = {Book A}
}

@inproceedings{b,
  title = {Paper B},
  year = {2023}
}"""
        entries = parse_bib_file(bib)
        assert len(entries) == 2
        assert entries[0].key == "a"
        assert entries[1].key == "b"
        assert entries[1].entry_type == "inproceedings"

    def test_empty_bib(self):
        entries = parse_bib_file("")
        assert len(entries) == 0

    def test_nested_braces(self):
        bib = "@article{rna, title = {The {RNA} Polymerase}, author = {Jane {van der Berg}}}"
        entries = parse_bib_file(bib)
        assert len(entries) == 1
        assert entries[0].fields["title"] == "The {RNA} Polymerase"
        assert entries[0].fields["author"] == "Jane {van der Berg}"


class TestCitationRoundTrip:
    def test_serialize_then_ingest(self):
        from texflow.model import BibEntry, Bibliography
        from texflow.serializer import serialize

        original = Document(
            metadata=Metadata(title="Cite Test"),
            content=[Paragraph(text="See [@smith2024, p. 5].")],
            bibliography=Bibliography(
                style="numeric",
                entries=[BibEntry(key="smith2024", entry_type="article", fields={"title": "T"})],
            ),
        )
        tex = serialize(original)
        restored = ingest_tex(tex)
        p = restored.content[0]
        assert isinstance(p, Paragraph)
        assert "[@smith2024, p. 5]" in p.text


class TestBiblatexPreambleIngestion:
    def test_biblatex_style_detected(self):
        tex = "\\documentclass{article}\n\\usepackage[style=numeric,backend=biber]{biblatex}\n\\begin{document}\n\\end{document}"
        doc = ingest_tex(tex)
        assert doc.bibliography is not None
        assert doc.bibliography.style == "numeric"

    def test_printbibliography_skipped(self):
        tex = "\\begin{document}\nSome text.\n\\printbibliography\n\\end{document}"
        doc = ingest_tex(tex)
        # printbibliography should not appear as content
        assert len(doc.content) == 1
        assert isinstance(doc.content[0], Paragraph)
