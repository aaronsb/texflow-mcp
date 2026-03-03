"""Reference tool: LaTeX documentation search and help."""

from __future__ import annotations

import json
import re
from pathlib import Path

_DATA_DIR = Path(__file__).parent.parent / "data"
_REF_DIR = _DATA_DIR / "latex_reference"

# Lazy-loaded databases
_commands_db: dict | None = None
_symbols_db: dict | None = None
_packages_db: dict | None = None
_errors_db: dict | None = None


def _load_json(filepath: Path) -> dict:
    if filepath.exists():
        try:
            return json.loads(filepath.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _load_dir(dirpath: Path) -> dict:
    result = {}
    if dirpath.exists():
        for f in dirpath.glob("*.json"):
            result.update(_load_json(f))
    return result


def _commands() -> dict:
    global _commands_db
    if _commands_db is None:
        _commands_db = _load_dir(_REF_DIR / "commands")
    return _commands_db


def _symbols() -> dict:
    global _symbols_db
    if _symbols_db is None:
        _symbols_db = _load_dir(_REF_DIR / "symbols")
    return _symbols_db


def _packages() -> dict:
    global _packages_db
    if _packages_db is None:
        _packages_db = {}
        pkg_dir = _REF_DIR / "packages"
        if pkg_dir.exists():
            for f in pkg_dir.glob("*.json"):
                data = _load_json(f)
                _packages_db[f.stem] = data
    return _packages_db


def _errors() -> dict:
    global _errors_db
    if _errors_db is None:
        _errors_db = _load_json(_REF_DIR / "errors" / "patterns.json")
    return _errors_db


def reference_tool(
    action: str,
    query: str | None = None,
    description: str | None = None,
    name: str | None = None,
    error: str | None = None,
    topic: str | None = None,
    path: str | None = None,
) -> str:
    """Search LaTeX documentation, symbols, packages, and error solutions.

    Actions:
    - search: Search for LaTeX commands or general topics.
    - symbol: Find symbols by description (e.g., "approximately equal").
    - package: Get information about a LaTeX package.
    - check_style: Analyze a .tex file for best practices.
    - error_help: Get help for LaTeX error messages.
    - example: Get working examples for a topic.
    """
    match action:
        case "search":
            return _search(query)
        case "symbol":
            return _find_symbol(description)
        case "package":
            return _package_info(name)
        case "check_style":
            return _check_style(path)
        case "error_help":
            return _error_help(error)
        case "example":
            return _get_example(topic)
        case _:
            return f"Unknown action: {action}. Valid: search, symbol, package, check_style, error_help, example"


def _search(query: str | None) -> str:
    if not query:
        return "Error: 'query' is required for search."

    q = query.lower()
    results: list[str] = []

    # Search commands
    for cmd_name, info in _commands().items():
        if (q in cmd_name.lower()
                or q in info.get("description", "").lower()
                or q in info.get("category", "").lower()):
            line = f"  {cmd_name}"
            if info.get("syntax"):
                line += f"  {info['syntax']}"
            line += f"\n    {info.get('description', '')}"
            if info.get("package"):
                line += f" (package: {info['package']})"
            results.append(line)

    # Search symbols
    for sym_name, info in _symbols().items():
        if (q in sym_name.lower()
                or q in info.get("description", "").lower()):
            cmd = info.get("command", sym_name)
            desc = info.get("description", "")
            pkg = info.get("package", "")
            line = f"  {sym_name}: {cmd}"
            if desc:
                line += f" — {desc}"
            if pkg:
                line += f" (package: {pkg})"
            results.append(line)

    if not results:
        return f"No results for '{query}'."

    results = results[:20]
    header = f"Found {len(results)} results for '{query}':\n"
    return header + "\n".join(results)


def _find_symbol(description: str | None) -> str:
    if not description:
        return "Error: 'description' is required for symbol search."

    words = description.lower().split()
    matches: list[tuple[int, str]] = []

    for sym_name, info in _symbols().items():
        sym_desc = info.get("description", "").lower()
        score = sum(1 for w in words if w in sym_desc)
        if score > 0:
            cmd = info.get("command", sym_name)
            desc = info.get("description", "")
            pkg = info.get("package", "built-in")
            line = f"  {cmd}  {desc}  (package: {pkg})"
            matches.append((score, line))

    matches.sort(key=lambda m: m[0], reverse=True)

    if not matches:
        return f"No symbols matching '{description}'."

    lines = [f"Found {len(matches)} symbols matching '{description}':"]
    for _, line in matches[:15]:
        lines.append(line)
    return "\n".join(lines)


def _package_info(name: str | None) -> str:
    if not name:
        return "Error: 'name' is required for package lookup."

    pkg_name = name.lower()
    pkgs = _packages()

    if pkg_name not in pkgs:
        similar = [p for p in pkgs if pkg_name in p]
        if similar:
            return f"Package '{pkg_name}' not found. Similar: {', '.join(similar[:5])}"
        return f"Package '{pkg_name}' not found."

    info = pkgs[pkg_name]
    lines = [f"Package: {pkg_name}"]
    if info.get("description"):
        lines.append(f"  {info['description']}")
    lines.append(f"  Usage: {info.get('usage', f'\\usepackage{{{pkg_name}}}')}")

    if info.get("options"):
        lines.append("  Options:")
        for opt in info["options"][:10]:
            if isinstance(opt, dict):
                lines.append(f"    {opt.get('name', '')}: {opt.get('description', '')}")
            else:
                lines.append(f"    {opt}")

    if info.get("commands"):
        lines.append("  Commands:")
        for cmd in info["commands"][:10]:
            if isinstance(cmd, dict):
                lines.append(f"    {cmd.get('name', '')}: {cmd.get('description', '')}")
            else:
                lines.append(f"    {cmd}")

    if info.get("examples"):
        lines.append("  Examples:")
        for ex in info["examples"][:3]:
            lines.append(f"    {ex}")

    return "\n".join(lines)


def _check_style(path: str | None) -> str:
    if not path:
        return "Error: 'path' is required for style check."

    filepath = Path(path)
    if not filepath.exists():
        return f"File not found: {filepath}"

    try:
        content = filepath.read_text(encoding="utf-8")
    except OSError as e:
        return f"Failed to read file: {e}"

    warnings: list[str] = []

    for line_num, line in enumerate(content.split("\n"), 1):
        # Math operators without backslash
        for op in ("sin", "cos", "tan", "log", "ln", "exp", "min", "max", "lim"):
            if re.search(rf"(?<!\\){op}\s*\(", line):
                warnings.append(f"  Line {line_num}: Use \\{op} instead of {op}")

        # Deprecated commands
        deprecated = {
            "\\rm": "\\textrm", "\\bf": "\\textbf", "\\it": "\\textit",
            "\\sc": "\\textsc", "\\tt": "\\texttt",
        }
        for old, new in deprecated.items():
            if old in line:
                warnings.append(f"  Line {line_num}: '{old}' is deprecated, use '{new}'")

        if "\\\\\\\\" in line:
            warnings.append(f"  Line {line_num}: Multiple line breaks; use \\vspace{{}} instead")

    if not warnings:
        return f"Style check passed: no issues found in {filepath.name}."

    return f"Style check: {len(warnings)} warnings in {filepath.name}:\n" + "\n".join(warnings)


def _error_help(error_msg: str | None) -> str:
    if not error_msg:
        return "Error: 'error' is required."

    error_lower = error_msg.lower()
    solutions: list[str] = []

    for pattern, solution in _errors().items():
        if pattern.lower() in error_lower or _safe_match(pattern, error_msg):
            lines = [f"  Pattern: {pattern}"]
            if solution.get("explanation"):
                lines.append(f"  Explanation: {solution['explanation']}")
            if solution.get("solution"):
                lines.append(f"  Solution: {solution['solution']}")
            if solution.get("common_causes"):
                lines.append("  Common causes:")
                for cause in solution["common_causes"]:
                    lines.append(f"    - {cause}")
            solutions.append("\n".join(lines))

    if not solutions:
        generic = _generic_error_help(error_msg)
        if generic:
            solutions.append(generic)

    if not solutions:
        return f"No solutions found for: {error_msg}"

    return f"Help for '{error_msg}':\n\n" + "\n\n".join(solutions)


def _safe_match(pattern: str, text: str) -> bool:
    try:
        return bool(re.search(pattern, text, re.IGNORECASE))
    except re.error:
        return False


def _generic_error_help(error_msg: str) -> str | None:
    el = error_msg.lower()

    if "undefined control sequence" in el:
        match = re.search(r"\\(\w+)", error_msg)
        cmd = match.group(1) if match else "command"
        return (
            f"  Undefined control sequence: \\{cmd}\n"
            "  Common causes:\n"
            "    - Typo in command name\n"
            "    - Missing \\usepackage{} declaration\n"
            "    - Command from an unloaded package"
        )

    if "missing $ inserted" in el:
        return (
            "  Missing $ inserted\n"
            "  Math content found outside math environment.\n"
            "  Solution: Wrap math in $...$ or \\[...\\]\n"
            "  Common causes:\n"
            "    - Using ^ or _ outside math mode\n"
            "    - Math commands like \\frac outside math mode"
        )

    if "file not found" in el:
        return (
            "  File not found\n"
            "  Common causes:\n"
            "    - Incorrect path in \\input or \\include\n"
            "    - Missing image file for \\includegraphics\n"
            "    - Package not installed"
        )

    return None


_EXAMPLES = {
    "table": (
        "Basic table:\n"
        "  \\begin{tabular}{|l|c|r|}\n"
        "  \\hline\n"
        "  Left & Center & Right \\\\\n"
        "  \\hline\n"
        "  1 & 2 & 3 \\\\\n"
        "  \\hline\n"
        "  \\end{tabular}"
    ),
    "equation": (
        "Numbered equation:\n"
        "  \\begin{equation}\n"
        "  E = mc^2\n"
        "  \\end{equation}"
    ),
    "figure": (
        "Figure with caption:\n"
        "  \\begin{figure}[htbp]\n"
        "  \\centering\n"
        "  \\includegraphics[width=0.8\\textwidth]{image.png}\n"
        "  \\caption{Figure caption}\n"
        "  \\label{fig:example}\n"
        "  \\end{figure}"
    ),
    "list": (
        "Itemized list:\n"
        "  \\begin{itemize}\n"
        "  \\item First item\n"
        "  \\item Second item\n"
        "  \\end{itemize}\n"
        "\n"
        "Enumerated list:\n"
        "  \\begin{enumerate}\n"
        "  \\item First item\n"
        "  \\item Second item\n"
        "  \\end{enumerate}"
    ),
    "code": (
        "Code listing (requires listings package):\n"
        "  \\begin{lstlisting}[language=Python]\n"
        "  def hello():\n"
        "      print('Hello, world!')\n"
        "  \\end{lstlisting}"
    ),
}


def _get_example(topic: str | None) -> str:
    if not topic:
        return "Error: 'topic' is required."

    t = topic.lower()
    matches = [(name, ex) for name, ex in _EXAMPLES.items() if t in name]

    if not matches:
        available = ", ".join(_EXAMPLES.keys())
        return f"No examples for '{topic}'. Available topics: {available}"

    parts = [f"Examples for '{topic}':"]
    for name, ex in matches:
        parts.append(f"\n{ex}")
    return "\n".join(parts)
