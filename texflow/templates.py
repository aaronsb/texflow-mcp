"""Template library: load and index .tex template snippets."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

_DATA_DIR = Path(__file__).parent / "data"
_TEMPLATE_DIR = _DATA_DIR / "templates"

_templates: dict[str, Template] | None = None


@dataclass
class Template:
    name: str
    slug: str
    category: str
    description: str
    packages: list[str] = field(default_factory=list)
    preamble: list[str] = field(default_factory=list)
    body: str = ""
    requires_tools: list[str] = field(default_factory=list)
    requires_engine: list[str] = field(default_factory=list)


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split YAML frontmatter from body. Returns (metadata_dict, body).

    Minimal parser — handles flat key: value pairs and list values
    (inline [a, b] or multi-line - item). No PyYAML dependency.
    """
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.DOTALL)
    if not m:
        return {}, text

    meta: dict = {}
    current_list_key: str | None = None

    for line in m.group(1).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # List item under a key
        if stripped.startswith("- "):
            if current_list_key is not None:
                meta.setdefault(current_list_key, []).append(stripped[2:].strip())
            continue

        # Key: value pair
        if ":" in stripped:
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip()

            if val.startswith("[") and val.endswith("]"):
                # Inline list: [a, b, c]
                items = [x.strip().strip("'\"") for x in val[1:-1].split(",") if x.strip()]
                meta[key] = items
                current_list_key = None
            elif val:
                meta[key] = val
                current_list_key = None
            else:
                # Empty value — next lines may be list items
                current_list_key = key
                if key not in meta:
                    meta[key] = []

    return meta, m.group(2)


def _load_templates() -> dict[str, Template]:
    """Glob all .tex files under templates/, parse frontmatter, build index."""
    result: dict[str, Template] = {}
    if not _TEMPLATE_DIR.exists():
        return result

    for tex_file in sorted(_TEMPLATE_DIR.glob("**/*.tex")):
        try:
            text = tex_file.read_text(encoding="utf-8")
        except OSError:
            continue

        meta, body = _parse_frontmatter(text)
        slug = tex_file.stem

        if slug in result:
            continue

        packages = meta.get("packages", [])
        if isinstance(packages, str):
            packages = [packages]
        preamble = meta.get("preamble", [])
        if isinstance(preamble, str):
            preamble = [preamble]
        requires_tools = meta.get("requires_tools", [])
        if isinstance(requires_tools, str):
            requires_tools = [requires_tools]
        requires_engine = meta.get("requires_engine", [])
        if isinstance(requires_engine, str):
            requires_engine = [requires_engine]

        result[slug] = Template(
            name=meta.get("name", slug),
            slug=slug,
            category=meta.get("category", "uncategorized"),
            description=meta.get("description", ""),
            packages=packages,
            preamble=preamble,
            body=body.strip(),
            requires_tools=requires_tools,
            requires_engine=requires_engine,
        )

    return result


def get_templates() -> dict[str, Template]:
    """Return the template index (lazy-loaded, cached)."""
    global _templates
    if _templates is None:
        _templates = _load_templates()
    return _templates


def get_template(slug: str) -> Template | None:
    """Look up a template by slug."""
    return get_templates().get(slug)


def list_templates(category: str | None = None) -> list[Template]:
    """List templates, optionally filtered by category."""
    templates = list(get_templates().values())
    if category:
        templates = [t for t in templates if t.category == category]
    return sorted(templates, key=lambda t: (t.category, t.name))


def list_categories() -> list[str]:
    """Return sorted unique category names."""
    return sorted({t.category for t in get_templates().values()})


def format_template_list(templates: list[Template]) -> str:
    """Format template list for display."""
    if not templates:
        return "No templates available."

    by_category: dict[str, list[Template]] = {}
    for t in templates:
        by_category.setdefault(t.category, []).append(t)

    lines = [f"Templates ({len(templates)} available):"]
    for cat in sorted(by_category):
        lines.append(f"\n  {cat}:")
        for t in sorted(by_category[cat], key=lambda x: x.name):
            lines.append(f"    {t.slug}: {t.name} — {t.description}")
            if t.packages:
                lines.append(f"      packages: {', '.join(t.packages)}")
            if t.requires_tools:
                lines.append(f"      requires tools: {', '.join(t.requires_tools)}")
            if t.requires_engine:
                lines.append(f"      requires engine: {', '.join(t.requires_engine)}")

    return "\n".join(lines)
