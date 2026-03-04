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
