"""Tests for the style presets system."""

from texflow.model import Document, Layout, Paragraph, Section
from texflow.serializer import serialize
from texflow.styles import (
    Style,
    format_style_list,
    get_style,
    get_styles,
    list_styles,
    resolve_style_stack,
)


class TestStyleLoading:
    def test_get_styles_returns_dict(self):
        styles = get_styles()
        assert isinstance(styles, dict)

    def test_all_styles_loaded(self):
        styles = get_styles()
        # 6 original + 5 background-colored styles
        assert len(styles) >= 11
        # Verify background styles are present
        for slug in ("dark-academia", "midnight", "soft-rose", "ocean-depth", "sunbeam"):
            assert slug in styles, f"Missing style: {slug}"

    def test_modern_blue_loaded(self):
        s = get_style("modern-blue")
        assert s is not None
        assert s.name == "Modern Blue"
        assert "titlesec" in s.packages
        assert "xcolor" in s.packages
        assert any("heading" in line for line in s.preamble)

    def test_nonexistent_style(self):
        assert get_style("nonexistent") is None

    def test_list_styles_sorted_by_name(self):
        styles = list_styles()
        names = [s.name for s in styles]
        assert names == sorted(names)

    def test_all_styles_have_packages(self):
        for slug, style in get_styles().items():
            assert style.packages, f"Style {slug} has no packages"
            assert style.preamble, f"Style {slug} has no preamble"


class TestStyleStack:
    def test_single_style(self):
        pkgs, preamble = resolve_style_stack(["modern-blue"])
        assert "titlesec" in pkgs
        assert "xcolor" in pkgs
        assert len(preamble) > 0

    def test_empty_stack(self):
        pkgs, preamble = resolve_style_stack([])
        assert pkgs == set()
        assert preamble == []

    def test_unknown_style_ignored(self):
        pkgs, preamble = resolve_style_stack(["nonexistent"])
        assert pkgs == set()
        assert preamble == []

    def test_stacking_merges_packages(self):
        pkgs, _ = resolve_style_stack(["modern-blue", "newsletter"])
        assert "titlesec" in pkgs
        assert "lettrine" in pkgs  # Only in newsletter

    def test_preamble_order_preserved(self):
        _, preamble = resolve_style_stack(["minimal", "modern-blue"])
        # Both define heading color — minimal's comes first, modern-blue's second
        heading_defs = [l for l in preamble if "definecolor{heading}" in l]
        assert len(heading_defs) == 2
        assert "333333" in heading_defs[0]  # minimal
        assert "1A5276" in heading_defs[1]  # modern-blue (wins)

    def test_deduplicate_identical_preamble(self):
        # Stacking a style with itself shouldn't duplicate lines
        _, preamble = resolve_style_stack(["modern-blue", "modern-blue"])
        heading_defs = [l for l in preamble if "definecolor{heading}" in l]
        assert len(heading_defs) == 1


class TestSerializerIntegration:
    def test_style_packages_in_output(self):
        doc = Document(
            layout=Layout(styles=["modern-blue"]),
            content=[Paragraph(text="Hello")],
        )
        tex = serialize(doc)
        assert "\\usepackage{titlesec}" in tex
        assert "\\usepackage{xcolor}" in tex
        assert "\\usepackage{parskip}" in tex

    def test_style_preamble_in_output(self):
        doc = Document(
            layout=Layout(styles=["modern-blue"]),
            content=[Paragraph(text="Hello")],
        )
        tex = serialize(doc)
        assert "\\definecolor{heading}{HTML}{1A5276}" in tex
        assert "\\titleformat" in tex

    def test_style_preamble_before_block_preamble(self):
        from texflow.model import RawLatex
        doc = Document(
            layout=Layout(styles=["modern-blue"]),
            content=[RawLatex(tex="test", preamble=["\\usetikzlibrary{arrows}"])],
        )
        tex = serialize(doc)
        heading_pos = tex.index("\\definecolor{heading}")
        tikz_pos = tex.index("\\usetikzlibrary{arrows}")
        assert heading_pos < tikz_pos

    def test_hyperref_style_aware(self):
        # With style: only colorlinks=true, no hardcoded colors
        doc_styled = Document(
            layout=Layout(styles=["modern-blue"]),
            content=[Paragraph(text="Hello")],
        )
        tex = serialize(doc_styled)
        assert "colorlinks=true]" in tex or "colorlinks=true}" in tex
        assert "linkcolor=blue" not in tex

        # Without style: full hardcoded colors
        doc_plain = Document(content=[Paragraph(text="Hello")])
        tex_plain = serialize(doc_plain)
        assert "linkcolor=blue" in tex_plain

    def test_no_style_no_change(self):
        doc = Document(content=[Paragraph(text="Hello")])
        tex = serialize(doc)
        assert "titlesec" not in tex
        assert "\\definecolor" not in tex


class TestLayoutRoundtrip:
    def test_styles_serialized(self):
        doc = Document(layout=Layout(styles=["modern-blue", "minimal"]))
        data = doc.to_dict()
        restored = Document.from_dict(data)
        assert restored.layout.styles == ["modern-blue", "minimal"]

    def test_empty_styles_roundtrip(self):
        doc = Document(layout=Layout(styles=[]))
        data = doc.to_dict()
        restored = Document.from_dict(data)
        assert restored.layout.styles == []


class TestBackgroundStyles:
    """Test styles that use pagecolor for colored backgrounds."""

    def test_dark_academia_has_pagecolor(self):
        s = get_style("dark-academia")
        assert s is not None
        assert any("\\pagecolor" in line for line in s.preamble)
        assert any("\\color{bodyText}" in line for line in s.preamble)

    def test_midnight_has_pagecolor(self):
        s = get_style("midnight")
        assert s is not None
        assert any("\\pagecolor" in line for line in s.preamble)

    def test_background_styles_compile(self):
        """Background styles include pagecolor + color in preamble."""
        for slug in ("dark-academia", "midnight", "soft-rose", "ocean-depth", "sunbeam"):
            s = get_style(slug)
            assert s is not None, f"Missing: {slug}"
            assert any("\\pagecolor" in line for line in s.preamble), (
                f"{slug} missing \\pagecolor"
            )

    def test_background_style_serializes(self):
        doc = Document(
            layout=Layout(styles=["dark-academia"]),
            content=[Paragraph(text="Hello darkness")],
        )
        tex = serialize(doc)
        assert "\\pagecolor{pageBg}" in tex
        assert "\\color{bodyText}" in tex


class TestLayoutToolValidation:
    """Test style validation in the layout tool."""

    def test_invalid_style_returns_error(self):
        from texflow.tools import state as st
        from texflow.tools.layout import layout_tool
        st.set_doc(Document(content=[Paragraph(text="test")]))
        result = layout_tool(style="nonexistent-style")
        assert "Error" in result
        assert "nonexistent-style" in result
        assert "modern-blue" in result  # Should list available styles

    def test_valid_style_accepted(self):
        from texflow.tools import state as st
        from texflow.tools.layout import layout_tool
        st.set_doc(Document(content=[Paragraph(text="test")]))
        result = layout_tool(style="modern-blue")
        assert "Error" not in result
        assert "modern-blue" in result


class TestFormatting:
    def test_format_empty(self):
        result = format_style_list([])
        assert "No styles" in result

    def test_format_with_styles(self):
        styles = [Style(name="Test", slug="test", description="A test style")]
        result = format_style_list(styles)
        assert "test" in result
        assert "A test style" in result

    def test_format_shows_packages(self):
        styles = [Style(name="T", slug="t", description="d", packages=["titlesec"])]
        result = format_style_list(styles)
        assert "titlesec" in result
