"""Style presets: document-level visual identity bundles."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .templates import _parse_frontmatter

_DATA_DIR = Path(__file__).parent / "data"
_STYLE_DIR = _DATA_DIR / "styles"

_styles: dict[str, Style] | None = None


@dataclass
class Style:
    name: str
    slug: str
    description: str
    packages: list[str] = field(default_factory=list)
    preamble: list[str] = field(default_factory=list)


def _load_styles() -> dict[str, Style]:
    """Load all .yaml style files from data/styles/."""
    result: dict[str, Style] = {}
    if not _STYLE_DIR.exists():
        return result

    for style_file in sorted(_STYLE_DIR.glob("*.yaml")):
        try:
            text = style_file.read_text(encoding="utf-8")
        except OSError:
            continue

        meta, _ = _parse_frontmatter(text)
        slug = style_file.stem

        if slug in result:
            continue

        packages = meta.get("packages", [])
        if isinstance(packages, str):
            packages = [packages]
        preamble = meta.get("preamble", [])
        if isinstance(preamble, str):
            preamble = [preamble]

        result[slug] = Style(
            name=meta.get("name", slug),
            slug=slug,
            description=meta.get("description", ""),
            packages=packages,
            preamble=preamble,
        )

    return result


def get_styles() -> dict[str, Style]:
    """Return the style index (lazy-loaded, cached)."""
    global _styles
    if _styles is None:
        _styles = _load_styles()
    return _styles


def get_style(slug: str) -> Style | None:
    """Look up a style by slug."""
    return get_styles().get(slug)


def list_styles() -> list[Style]:
    """List all available styles."""
    return sorted(get_styles().values(), key=lambda s: s.name)


def resolve_style_stack(slugs: list[str]) -> tuple[set[str], list[str]]:
    """Resolve an ordered list of style slugs into packages and preamble lines.

    Returns (packages, preamble_lines). Packages are deduplicated.
    Preamble lines are ordered: earlier styles first, later styles last
    (later wins on conflicts since LaTeX uses last-defined).
    """
    packages: set[str] = set()
    preamble: list[str] = []
    seen_preamble: set[str] = set()

    for slug in slugs:
        style = get_style(slug)
        if style is None:
            continue
        packages.update(style.packages)
        for line in style.preamble:
            if line not in seen_preamble:
                seen_preamble.add(line)
                preamble.append(line)

    return packages, preamble


def format_style_list(styles: list[Style]) -> str:
    """Format style list for display."""
    if not styles:
        return "No styles available."

    lines = [f"Styles ({len(styles)} available):"]
    for s in styles:
        lines.append(f"\n  {s.slug}: {s.name}")
        lines.append(f"    {s.description}")
        if s.packages:
            lines.append(f"    packages: {', '.join(s.packages)}")

    return "\n".join(lines)
