"""Tests for the LaTeX serializer."""

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
from texflow.serializer import escape_latex, serialize, _convert_inline_markup


# --- escape_latex ---


def test_escape_special_chars():
    assert escape_latex("10% off & $5 each") == "10\\% off \\& \\$5 each"


def test_escape_preserves_math():
    assert escape_latex("The value $x_1$ is") == "The value $x_1$ is"


def test_escape_preserves_bold():
    assert escape_latex("This is **bold** text") == "This is **bold** text"


def test_escape_preserves_italic():
    assert escape_latex("This is *italic* text") == "This is *italic* text"


def test_escape_preserves_inline_code():
    assert escape_latex("Use `foo_bar` here") == "Use `foo_bar` here"


def test_escape_preserves_links():
    result = escape_latex("See [here](http://example.com)")
    assert "[here](http://example.com)" in result


def test_escape_mixed():
    text = "Cost is 10% for $x$ items & **bold**"
    result = escape_latex(text)
    assert "10\\%" in result
    assert "$x$" in result
    assert "\\&" in result
    assert "**bold**" in result


# --- inline markup conversion ---


def test_convert_bold():
    assert _convert_inline_markup("**bold**") == "\\textbf{bold}"


def test_convert_italic():
    assert _convert_inline_markup("*italic*") == "\\textit{italic}"


def test_convert_code():
    assert _convert_inline_markup("`code`") == "\\texttt{code}"


def test_convert_link():
    result = _convert_inline_markup("[text](http://example.com)")
    assert result == "\\href{http://example.com}{text}"


def test_convert_math_passthrough():
    assert _convert_inline_markup("$x^2$") == "$x^2$"


# --- Full serialization ---


def test_serialize_minimal():
    doc = Document()
    tex = serialize(doc)
    assert "\\documentclass" in tex
    assert "\\begin{document}" in tex
    assert "\\end{document}" in tex


def test_serialize_article_class():
    doc = Document(layout=Layout(document_class=DocumentClass.ARTICLE))
    tex = serialize(doc)
    assert "\\documentclass[" in tex
    assert "{article}" in tex


def test_serialize_report_class():
    doc = Document(layout=Layout(document_class=DocumentClass.REPORT))
    tex = serialize(doc)
    assert "{report}" in tex


def test_serialize_twocolumn():
    doc = Document(layout=Layout(columns=2))
    tex = serialize(doc)
    assert "twocolumn" in tex
    assert "multicol" not in tex


def test_serialize_multicol():
    doc = Document(
        layout=Layout(columns=3),
        content=[Paragraph(text="hello")],
    )
    tex = serialize(doc)
    assert "\\begin{multicols}{3}" in tex
    assert "\\end{multicols}" in tex


def test_serialize_title_author():
    doc = Document(metadata=Metadata(title="My Paper", author="Alice"))
    tex = serialize(doc)
    assert "\\title{My Paper}" in tex
    assert "\\author{Alice}" in tex
    assert "\\maketitle" in tex


def test_serialize_abstract():
    doc = Document(metadata=Metadata(title="T", abstract="An abstract."))
    tex = serialize(doc)
    assert "\\begin{abstract}" in tex
    assert "An abstract." in tex
    assert "\\end{abstract}" in tex


def test_serialize_toc():
    doc = Document(layout=Layout(toc=True), metadata=Metadata(title="T"))
    tex = serialize(doc)
    assert "\\tableofcontents" in tex


def test_serialize_margins():
    doc = Document(layout=Layout(margins=Margins(top="2cm", bottom="2cm", left="1.5cm", right="1.5cm")))
    tex = serialize(doc)
    assert "top=2cm" in tex
    assert "left=1.5cm" in tex


def test_serialize_header_footer():
    doc = Document(layout=Layout(
        header=HeaderFooter(left="Title", right="\\thepage"),
        footer=HeaderFooter(center="Footer"),
    ))
    tex = serialize(doc)
    assert "\\pagestyle{fancy}" in tex
    assert "\\fancyhead[L]{Title}" in tex
    assert "\\fancyhead[R]{\\thepage}" in tex
    assert "\\fancyfoot[C]{Footer}" in tex


def test_serialize_section():
    doc = Document(content=[
        Section(title="Introduction", level=1, label="sec:intro"),
    ])
    tex = serialize(doc)
    assert "\\section{Introduction}" in tex
    assert "\\label{sec:intro}" in tex


def test_serialize_subsection():
    doc = Document(content=[
        Section(title="Top", level=1, content=[
            Section(title="Sub", level=2),
        ]),
    ])
    tex = serialize(doc)
    assert "\\section{Top}" in tex
    assert "\\subsection{Sub}" in tex


def test_serialize_paragraph_with_markup():
    doc = Document(content=[
        Paragraph(text="This is **bold** and *italic* with `code`."),
    ])
    tex = serialize(doc)
    assert "\\textbf{bold}" in tex
    assert "\\textit{italic}" in tex
    assert "\\texttt{code}" in tex


def test_serialize_figure():
    doc = Document(content=[
        Figure(path="images/fig1.png", caption="A figure", label="fig:one", width="0.6\\textwidth"),
    ])
    tex = serialize(doc)
    assert "\\begin{figure}" in tex
    assert "\\includegraphics[width=0.6\\textwidth]{images/fig1.png}" in tex
    assert "\\caption{A figure}" in tex
    assert "\\label{fig:one}" in tex
    assert "\\end{figure}" in tex


def test_serialize_table_booktabs():
    doc = Document(content=[
        Table(
            caption="Results",
            headers=["Name", "Value"],
            rows=[["A", "1"], ["B", "2"]],
            booktabs=True,
        ),
    ])
    tex = serialize(doc)
    assert "\\begin{table}" in tex
    assert "\\toprule" in tex
    assert "Name & Value" in tex
    assert "\\midrule" in tex
    assert "A & 1" in tex
    assert "\\bottomrule" in tex
    assert "\\caption{Results}" in tex


def test_serialize_table_no_booktabs():
    doc = Document(content=[
        Table(headers=["X"], rows=[["1"]], booktabs=False),
    ])
    tex = serialize(doc)
    assert "\\toprule" not in tex


def test_serialize_code_block():
    doc = Document(content=[
        CodeBlock(code="def hello():\n    print('hi')", language="python"),
    ])
    tex = serialize(doc)
    assert "\\begin{lstlisting}[language=python]" in tex
    assert "def hello():" in tex
    assert "\\end{lstlisting}" in tex


def test_serialize_ordered_list():
    doc = Document(content=[
        ItemList(ordered=True, items=[
            ListItem(text="First"),
            ListItem(text="Second"),
        ]),
    ])
    tex = serialize(doc)
    assert "\\begin{enumerate}" in tex
    assert "\\item First" in tex
    assert "\\item Second" in tex
    assert "\\end{enumerate}" in tex


def test_serialize_unordered_list():
    doc = Document(content=[
        ItemList(ordered=False, items=[ListItem(text="Bullet")]),
    ])
    tex = serialize(doc)
    assert "\\begin{itemize}" in tex
    assert "\\item Bullet" in tex


def test_serialize_equation_numbered():
    doc = Document(content=[
        Equation(tex="E = mc^2", label="eq:einstein", numbered=True),
    ])
    tex = serialize(doc)
    assert "\\begin{equation}" in tex
    assert "\\label{eq:einstein}" in tex
    assert "E = mc^2" in tex
    assert "\\end{equation}" in tex


def test_serialize_equation_unnumbered():
    doc = Document(content=[
        Equation(tex="a^2 + b^2 = c^2", numbered=False),
    ])
    tex = serialize(doc)
    assert "\\[" in tex
    assert "a^2 + b^2 = c^2" in tex
    assert "\\]" in tex


def test_serialize_raw_latex():
    doc = Document(content=[RawLatex(tex="\\clearpage")])
    tex = serialize(doc)
    assert "\\clearpage" in tex


def test_serialize_raw_tikz_includes_package():
    """RawLatex with tikzpicture triggers \\usepackage{tikz} in preamble."""
    doc = Document(content=[RawLatex(tex="\\begin{tikzpicture}\\draw (0,0) circle (1);\\end{tikzpicture}")])
    tex = serialize(doc)
    assert "\\usepackage{tikz}" in tex


def test_serialize_raw_preamble_lines():
    """RawLatex preamble lines are emitted in the document preamble."""
    doc = Document(content=[RawLatex(
        tex="\\begin{tikzpicture}\\end{tikzpicture}",
        preamble=["\\usetikzlibrary{arrows.meta,positioning}"],
    )])
    tex = serialize(doc)
    assert "\\usetikzlibrary{arrows.meta,positioning}" in tex
    assert tex.index("\\usetikzlibrary") < tex.index("\\begin{document}")


def test_serialize_raw_preamble_deduplication():
    """Duplicate preamble lines from multiple blocks are emitted once."""
    doc = Document(content=[
        RawLatex(tex="a", preamble=["\\usetikzlibrary{positioning}"]),
        RawLatex(tex="b", preamble=["\\usetikzlibrary{positioning}"]),
    ])
    tex = serialize(doc)
    assert tex.count("\\usetikzlibrary{positioning}") == 1


def test_serialize_font_packages():
    doc = Document(layout=Layout(font_main="palatino"))
    tex = serialize(doc)
    assert "\\usepackage{palatino}" in tex


def test_serialize_line_spacing():
    doc = Document(layout=Layout(line_spacing=1.5))
    tex = serialize(doc)
    assert "\\onehalfspacing" in tex


def test_serialize_double_spacing():
    doc = Document(layout=Layout(line_spacing=2.0))
    tex = serialize(doc)
    assert "\\doublespacing" in tex


def test_serialize_special_chars_in_paragraph():
    doc = Document(content=[Paragraph(text="Price is 10% off: $5 & up")])
    tex = serialize(doc)
    assert "10\\%" in tex
    assert "\\&" in tex


def test_serialize_complete_document():
    """Integration test: a realistic document produces valid-looking LaTeX."""
    doc = Document(
        metadata=Metadata(
            title="A Research Paper",
            author="Jane Doe",
            abstract="This paper presents novel results.",
        ),
        layout=Layout(
            document_class=DocumentClass.ARTICLE,
            columns=2,
            font_main="palatino",
            font_size="11pt",
            paper_size="letterpaper",
            margins=Margins(top="1in", bottom="1in", left="0.75in", right="0.75in"),
            header=HeaderFooter(left="Doe", right="\\thepage"),
            toc=True,
        ),
        content=[
            Section(title="Introduction", level=1, label="sec:intro", content=[
                Paragraph(text="We present a **novel** approach to the problem."),
                Figure(path="figures/overview.png", caption="System overview", label="fig:overview"),
            ]),
            Section(title="Methods", level=1, content=[
                Paragraph(text="Our method uses the formula $E = mc^2$."),
                Equation(tex="F = ma", label="eq:newton"),
                Table(
                    caption="Experimental results",
                    headers=["Trial", "Result"],
                    rows=[["1", "0.95"], ["2", "0.97"]],
                ),
            ]),
            Section(title="Conclusion", level=1, content=[
                Paragraph(text="In conclusion, this approach works *remarkably* well."),
            ]),
        ],
    )

    tex = serialize(doc)

    # Structural checks
    assert "\\documentclass" in tex
    assert "\\begin{document}" in tex
    assert "\\end{document}" in tex
    assert tex.index("\\begin{document}") < tex.index("\\end{document}")

    # Layout
    assert "twocolumn" in tex
    assert "11pt" in tex
    assert "letterpaper" in tex
    assert "palatino" in tex

    # Content
    assert "\\section{Introduction}" in tex
    assert "\\section{Methods}" in tex
    assert "\\section{Conclusion}" in tex
    assert "\\textbf{novel}" in tex
    assert "$E = mc^2$" in tex
    assert "\\begin{equation}" in tex
    assert "\\begin{table}" in tex
    assert "\\begin{figure}" in tex
