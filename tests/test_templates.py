"""Tests for the template library."""

from texflow.templates import (
    Template,
    _parse_frontmatter,
    get_template,
    get_templates,
    list_categories,
    list_templates,
    format_template_list,
)


class TestParseFrontmatter:
    def test_with_frontmatter(self):
        text = "---\nname: Test\ncategory: cat\n---\nbody here"
        meta, body = _parse_frontmatter(text)
        assert meta["name"] == "Test"
        assert meta["category"] == "cat"
        assert body == "body here"

    def test_no_frontmatter(self):
        text = "just body"
        meta, body = _parse_frontmatter(text)
        assert meta == {}
        assert body == "just body"

    def test_inline_list(self):
        text = "---\npackages: [tikz, graphicx]\n---\nbody"
        meta, body = _parse_frontmatter(text)
        assert meta["packages"] == ["tikz", "graphicx"]

    def test_multiline_list(self):
        text = "---\npackages:\n  - tikz\n  - graphicx\n---\nbody"
        meta, body = _parse_frontmatter(text)
        assert meta["packages"] == ["tikz", "graphicx"]

    def test_empty_list(self):
        text = "---\npreamble: []\n---\nbody"
        meta, body = _parse_frontmatter(text)
        assert meta["preamble"] == []

    def test_description_field(self):
        text = "---\ndescription: A cool template\n---\nbody"
        meta, body = _parse_frontmatter(text)
        assert meta["description"] == "A cool template"


class TestTemplateLoading:
    def test_get_templates_returns_dict(self):
        templates = get_templates()
        assert isinstance(templates, dict)

    def test_templates_loaded(self):
        templates = get_templates()
        assert len(templates) >= 8  # We created 8 templates

    def test_tikz_diagram_loaded(self):
        tmpl = get_template("tikz-diagram")
        assert tmpl is not None
        assert tmpl.name == "TikZ Diagram"
        assert tmpl.category == "diagrams"
        assert "tikz" in tmpl.packages
        assert "tikzpicture" in tmpl.body

    def test_longtable_loaded(self):
        tmpl = get_template("longtable")
        assert tmpl is not None
        assert "longtable" in tmpl.packages

    def test_nonexistent_template(self):
        assert get_template("nonexistent") is None

    def test_list_templates_all(self):
        templates = list_templates()
        assert len(templates) >= 8
        # Should be sorted by (category, name)
        categories = [t.category for t in templates]
        assert categories == sorted(categories)

    def test_list_templates_by_category(self):
        diagrams = list_templates(category="diagrams")
        assert len(diagrams) >= 2
        assert all(t.category == "diagrams" for t in diagrams)

    def test_list_categories(self):
        cats = list_categories()
        assert "diagrams" in cats
        assert "tables" in cats
        assert "math" in cats

    def test_format_empty(self):
        result = format_template_list([])
        assert "No templates" in result

    def test_format_with_templates(self):
        templates = [Template(name="Test", slug="test", category="cat", description="A test")]
        result = format_template_list(templates)
        assert "test" in result
        assert "cat" in result

    def test_format_shows_packages(self):
        templates = [Template(name="T", slug="t", category="c", description="d", packages=["tikz"])]
        result = format_template_list(templates)
        assert "tikz" in result

    def test_templates_expanded(self):
        """ADR-202: template count grew from 8 to ~30."""
        templates = get_templates()
        assert len(templates) >= 28

    def test_new_categories_exist(self):
        cats = list_categories()
        for cat in ["references", "callouts", "charts"]:
            assert cat in cats, f"Missing category: {cat}"

    def test_pgfplots_lineplot_loaded(self):
        tmpl = get_template("pgfplots-lineplot")
        assert tmpl is not None
        assert tmpl.category == "diagrams"
        assert "pgfplots" in tmpl.packages
        assert "axis" in tmpl.body

    def test_theorem_proof_loaded(self):
        tmpl = get_template("theorem-proof")
        assert tmpl is not None
        assert "amsthm" in tmpl.packages
        assert len(tmpl.preamble) >= 1
        assert "newtheorem" in tmpl.preamble[0]

    def test_biblatex_citations_loaded(self):
        tmpl = get_template("biblatex-citations")
        assert tmpl is not None
        assert "biblatex" in tmpl.packages
        assert "biber" in tmpl.requires_tools

    def test_minted_requires_tools(self):
        tmpl = get_template("minted-listing")
        assert tmpl is not None
        assert "pygmentize" in tmpl.requires_tools

    def test_frontmatter_requires_tools_parsing(self):
        text = "---\nname: T\nrequires_tools:\n  - biber\n  - pygmentize\n---\nbody"
        meta, body = _parse_frontmatter(text)
        assert meta["requires_tools"] == ["biber", "pygmentize"]

    def test_frontmatter_requires_engine_parsing(self):
        text = "---\nname: T\nrequires_engine: [xelatex]\n---\nbody"
        meta, body = _parse_frontmatter(text)
        assert meta["requires_engine"] == ["xelatex"]

    def test_format_shows_requires_tools(self):
        templates = [Template(name="T", slug="t", category="c", description="d",
                              requires_tools=["pygmentize"])]
        result = format_template_list(templates)
        assert "requires tools: pygmentize" in result

    def test_format_shows_requires_engine(self):
        templates = [Template(name="T", slug="t", category="c", description="d",
                              requires_engine=["xelatex"])]
        result = format_template_list(templates)
        assert "requires engine: xelatex" in result

    def test_algorithm_pseudocode_loaded(self):
        tmpl = get_template("algorithm-pseudocode")
        assert tmpl is not None
        assert "algorithm" in tmpl.packages
        assert "algpseudocode" in tmpl.packages

    def test_tcolorbox_note_loaded(self):
        tmpl = get_template("tcolorbox-note")
        assert tmpl is not None
        assert "tcolorbox" in tmpl.packages

    def test_gantt_chart_loaded(self):
        tmpl = get_template("gantt-chart")
        assert tmpl is not None
        assert "pgfgantt" in tmpl.packages

    def test_figure_local_image_loaded(self):
        tmpl = get_template("figure-local-image")
        assert tmpl is not None
        assert "graphicx" in tmpl.packages
