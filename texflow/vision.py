"""Vision check: score rendered page PNGs against a fixed defect taxonomy.

The MCP server has no vision of its own, but the local machine does: polaris
(local gemma via ~/PolarisStudio) and gemini-media (Gemini flash-lite) are
both stdio MCP servers. This module spawns them as MCP *clients* via fastmcp
(already a dependency) and asks them to score each page.

Policy (from design review):
- auto: try polaris first (plain file paths, local, no encoding overhead);
  on ANY failure — crash, timeout, non-zero, garbage — fall back to gemini.
- The report always names the provider actually used and every degradation,
  so a flaky local process never silently downgrades the check.
"""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

# Fixed taxonomy the vision pass must score — cheap and specific, not
# open-ended "does this look okay".
VISION_CHECKLIST = (
    "Score this page against exactly these four defect categories:\n"
    "1. overflow — text, table, or figure crossing the margin or column boundary;\n"
    "2. tiny_text — text visibly smaller than body text (fine print, shrunken cells);\n"
    "3. misplaced_float — a float (figure/table) overlapping text, split across pages, "
    "or stranded far from its reference;\n"
    "4. clipped_table — table cells cut off or a table running off the page edge.\n"
    'Reply as compact JSON: {"page": N, "defects": [{"category": "...", "location": "...", "detail": "..."}]}. '
    'Empty list if the page is clean. Do not mention layout that merely differs in style.'
)

# Provider defaults; overridable via environment.
_DEFAULT_POLARIS = ["node", str(Path.home() / "PolarisStudio" / "mcp-server.js")]
_DEFAULT_GEMINI = ["node", str(Path.home() / ".local" / "share" / "gemini-vision-mcp" / "dist" / "index.js")]
_DEFAULT_GEMINI_MODEL = "models/gemini-flash-lite-latest"

_TIMEOUT = 120  # seconds per page


@dataclass
class VisionFinding:
    page: int
    category: str
    location: str = ""
    detail: str = ""


@dataclass
class VisionReport:
    provider_used: str = ""
    notes: list[str] = field(default_factory=list)
    findings: list[VisionFinding] = field(default_factory=list)

    @property
    def degraded(self) -> bool:
        return any(
            "failed" in n or "fallback" in n or "skipped" in n or "ambiguous" in n
            for n in self.notes
        )

    def format(self) -> str:
        lines: list[str] = []
        if self.findings:
            by_page: dict[int, list[VisionFinding]] = {}
            for f in self.findings:
                by_page.setdefault(f.page, []).append(f)
            for page in sorted(by_page):
                lines.append(f"  Page {page}:")
                for f in by_page[page]:
                    loc = f" ({f.location})" if f.location else ""
                    lines.append(f"    - {f.category}{loc}: {f.detail}")
        elif self.degraded:
            lines.append("  Vision degraded — page scan is unreliable. Do not treat as a clean pass;")
            lines.append("  rely on the log defects above and inspect pages via render(action='preview').")
        else:
            lines.append("  No visual defects reported.")
        if self.notes:
            lines.append("")
            for note in self.notes:
                lines.append(f"  note: {note}")
        return "\n".join(lines)


def _provider_cmd(env_key: str, default: list[str]) -> list[str]:
    raw = os.environ.get(env_key)
    if not raw:
        return list(default)
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list) and parsed:
            return [str(x) for x in parsed]
    except json.JSONDecodeError:
        pass
    return [raw]


def _gemini_env() -> dict[str, str] | None:
    key = os.environ.get("TEXFLOW_VISION_GEMINI_KEY")
    if not key:
        key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return None
    return {
        "GEMINI_API_KEY": key,
        "GEMINI_MODEL": os.environ.get("TEXFLOW_VISION_GEMINI_MODEL", _DEFAULT_GEMINI_MODEL),
    }


def _png_data_url(path: Path) -> str:
    b64 = base64.b64encode(path.read_bytes()).decode()
    return f"data:image/png;base64,{b64}"


async def _call_provider(
    cmd: list[str],
    tool: str,
    arguments: dict[str, Any],
    env: dict[str, str] | None = None,
) -> Any:
    """Spawn an MCP stdio server and call one tool. Returns the raw result."""
    transport = StdioTransport(cmd[0], cmd[1:], env=env)
    async with Client(transport) as client:
        result = await client.call_tool(tool, arguments, timeout=_TIMEOUT)
        text = getattr(result, "content", None)
        if text is None:
            text = str(result)
        return text


async def _score_pages(pngs: list[Path], provider: str) -> VisionReport:
    """Score all pages with the chosen provider ('' = none available)."""
    report = VisionReport()
    prompt = VISION_CHECKLIST

    if provider == "polaris":
        report.provider_used = "polaris"
        cmd = _provider_cmd("TEXFLOW_VISION_POLARIS_CMD", _DEFAULT_POLARIS)
        try:
            for png in pngs:
                raw = await _call_provider(cmd, "describe_image", {
                    "image": str(png),
                    "prompt": prompt,
                })
                _absorb(raw, png, report)
        except Exception as e:
            report.notes.append(f"polaris failed ({type(e).__name__}: {e}) — fallback to gemini")
            return await _score_pages_gemini(pngs, report)
        return report

    if provider == "gemini":
        return await _score_pages_gemini(pngs, report)

    report.notes.append("vision skipped: no provider available")
    return report


async def _score_pages_gemini(pngs: list[Path], report: VisionReport) -> VisionReport:
    """Score pages with gemini-media, sharing the caller's report object."""
    env = _gemini_env()
    if env is None:
        report.notes.append(
            "gemini skipped: no GEMINI_API_KEY (set TEXFLOW_VISION_GEMINI_KEY) "
            "and no PIL to downscale pages below the provider payload limit"
        )
        return report

    report.provider_used = "gemini"
    cmd = _provider_cmd("TEXFLOW_VISION_GEMINI_CMD", _DEFAULT_GEMINI)
    try:
        for png in pngs:
            raw = await _call_provider(cmd, "analyze_image", {
                "imageUrls": [_png_data_url(png)],
                "prompt": VISION_CHECKLIST,
            }, env=env)
            _absorb(raw, png, report)
    except Exception as e:
        report.notes.append(f"gemini failed ({type(e).__name__}: {e})")
    return report


def _absorb(raw: Any, png: Path, report: VisionReport) -> None:
    """Parse a provider response (JSON-ish text or content list) into findings."""
    text = ""
    if isinstance(raw, list):
        for item in raw:
            d = getattr(item, "text", None) if not isinstance(item, dict) else item.get("text")
            if isinstance(d, str):
                text += d + "\n"
    elif isinstance(raw, str):
        text = raw

    findings = _extract_json_defects(text)
    if findings is None:
        report.notes.append(f"{png.name}: provider response not machine-readable, forwarding as text")
        snippet = text.strip().replace("\n", " ")[:200]
        if snippet:
            report.notes.append(f"  raw: {snippet}")
        return
    if not findings and text and "clean" not in text.lower():
        # Neither empty JSON nor an explicit clean verdict — surface it.
        report.notes.append(f"{png.name}: ambiguous vision response: {text.strip()[:200]}")
    report.findings.extend(findings)


def _extract_json_defects(text: str) -> list[VisionFinding] | None:
    """Pull a {defects: [...]} object out of provider text. None if unparseable."""
    m = None
    start = text.find("{")
    if start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    m = text[start:i + 1]
                    break
    if m is None:
        return None
    try:
        data = json.loads(m)
    except json.JSONDecodeError:
        return None
    page = data.get("page") or 0
    defects = data.get("defects", [])
    if not isinstance(defects, list):
        return None
    result: list[VisionFinding] = []
    for d in defects:
        if isinstance(d, dict) and d.get("category"):
            result.append(VisionFinding(
                page=page,
                category=str(d["category"]),
                location=str(d.get("location", "")),
                detail=str(d.get("detail", "")),
            ))
    return result


def run_vision_check(pngs: list[Path], provider: str = "auto") -> VisionReport:
    """Public entry: score pages, applying the auto fallback policy.

    provider: "auto" (polaris → gemini), "polaris", "gemini", or "none".
    """
    import asyncio

    if provider == "none" or not pngs:
        report = VisionReport(provider_used="none")
        if not pngs:
            report.notes.append("no page previews to check")
        return report

    if provider == "polaris":
        return asyncio.run(_score_pages(pngs, "polaris"))
    if provider == "gemini":
        return asyncio.run(_score_pages(pngs, "gemini"))

    # auto: polaris first; _score_pages falls back internally on failure
    return asyncio.run(_score_pages(pngs, "polaris"))
