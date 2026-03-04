"""System capability detection for LaTeX environments.

Probes for installed engines, packages, and tools, then caches results
for the session. Used to warn before cryptic compilation failures.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field


@dataclass
class SystemCapabilities:
    """Detected LaTeX system capabilities."""

    engines: dict[str, bool] = field(default_factory=dict)
    tools: dict[str, bool] = field(default_factory=dict)
    packages: dict[str, bool] = field(default_factory=dict)
    tex_distribution: str = ""


_cached: SystemCapabilities | None = None

_ENGINES = ["xelatex", "pdflatex", "lualatex"]
_TOOLS = ["biber", "bibtex", "pygmentize", "pdftoppm", "kpsewhich"]


def _detect_engines() -> dict[str, bool]:
    return {eng: shutil.which(eng) is not None for eng in _ENGINES}


def _detect_tools() -> dict[str, bool]:
    return {tool: shutil.which(tool) is not None for tool in _TOOLS}


def _detect_packages(packages: list[str]) -> dict[str, bool]:
    """Check package availability via kpsewhich (batch call)."""
    if not shutil.which("kpsewhich"):
        return {pkg: False for pkg in packages}

    result: dict[str, bool] = {}
    for pkg in packages:
        try:
            proc = subprocess.run(
                ["kpsewhich", f"{pkg}.sty"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            result[pkg] = proc.returncode == 0
        except (subprocess.TimeoutExpired, OSError):
            result[pkg] = False
    return result


def _detect_distribution() -> str:
    """Identify the TeX distribution."""
    try:
        proc = subprocess.run(
            ["kpsewhich", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if proc.returncode == 0:
            first_line = proc.stdout.strip().splitlines()[0]
            return first_line
    except (subprocess.TimeoutExpired, OSError, IndexError):
        pass
    return "unknown"


def check_capabilities(packages: list[str] | None = None) -> SystemCapabilities:
    """Probe system capabilities with session-level caching.

    On first call, detects engines, tools, and distribution.
    Package checks are additive — new packages are probed and merged
    into the cached result.
    """
    global _cached

    if _cached is None:
        _cached = SystemCapabilities(
            engines=_detect_engines(),
            tools=_detect_tools(),
            tex_distribution=_detect_distribution(),
        )

    if packages:
        new_pkgs = [p for p in packages if p not in _cached.packages]
        if new_pkgs:
            _cached.packages.update(_detect_packages(new_pkgs))

    return _cached


def reset_cache() -> None:
    """Clear cached capabilities (for testing)."""
    global _cached
    _cached = None


def format_missing_warnings(caps: SystemCapabilities, needed_packages: list[str] | None = None) -> list[str]:
    """Return human-readable warnings for missing capabilities."""
    warnings: list[str] = []

    missing_engines = [e for e, ok in caps.engines.items() if not ok]
    if missing_engines:
        warnings.append(f"Missing LaTeX engines: {', '.join(missing_engines)}")

    missing_tools = [t for t, ok in caps.tools.items() if not ok]
    if missing_tools:
        warnings.append(f"Missing tools: {', '.join(missing_tools)}")

    if needed_packages:
        missing_pkgs = [p for p in needed_packages if not caps.packages.get(p, False)]
        if missing_pkgs:
            warnings.append(f"Missing LaTeX packages: {', '.join(missing_pkgs)}")

    return warnings


def format_capabilities(caps: SystemCapabilities) -> str:
    """Format capabilities for display."""
    lines = [f"TeX Distribution: {caps.tex_distribution}", ""]

    lines.append("Engines:")
    for eng, ok in sorted(caps.engines.items()):
        status = "installed" if ok else "not found"
        lines.append(f"  {eng}: {status}")
    lines.append("")

    lines.append("Tools:")
    for tool, ok in sorted(caps.tools.items()):
        status = "installed" if ok else "not found"
        lines.append(f"  {tool}: {status}")

    if caps.packages:
        lines.append("")
        lines.append("Packages:")
        for pkg, ok in sorted(caps.packages.items()):
            status = "available" if ok else "not found"
            lines.append(f"  {pkg}: {status}")

    return "\n".join(lines)
