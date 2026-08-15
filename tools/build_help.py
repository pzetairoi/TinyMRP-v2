from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

from markdown_it import MarkdownIt


REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = REPO_ROOT / "docs" / "help"
OUTPUT_DIR = REPO_ROOT / "app" / "static" / "help"


def _slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-") or "section"


def _git_commit() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(REPO_ROOT),
            stderr=subprocess.DEVNULL,
        )
        return out.decode("utf-8").strip()
    except Exception:
        return ""


def _read_markdown_files() -> List[Tuple[str, str]]:
    if not DOCS_DIR.exists():
        return []
    files = sorted(p for p in DOCS_DIR.glob("*.md") if p.name != "CONTRIBUTING_HELP.md")
    out = []
    for p in files:
        out.append((p.name, p.read_text(encoding="utf-8")))
    return out


def _extract_ui_routes() -> List[Dict[str, str]]:
    path = REPO_ROOT / "frontend" / "src" / "main.tsx"
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(r"path\s*:\s*['\"]([^'\"]+)['\"]\s*,\s*element\s*:\s*<([A-Za-z0-9_]+)")
    found = pattern.findall(text)
    desc_map = {
        "PartsPage": "Inventory list and search.",
        "PartDetailPage": "Part detail view with files, previews, and doc packs.",
        "BomPage": "BOM tree view for parts and assemblies.",
        "ApiTokensPage": "Create and manage add-in access tokens.",
        "AdminAddinPage": "Admin tools for add-in settings and monitoring.",
        "DashboardPage": "System dashboard and summary metrics.",
        "App": "App shell and navigation.",
    }
    routes = []
    for route, component in found:
        if not route.startswith("/ui/"):
            continue
        perm = "Requires login"
        if "/ui/admin" in route:
            perm = "Admin only"
        routes.append(
            {
                "route": route,
                "component": component,
                "purpose": desc_map.get(component, "See in app."),
                "permission": perm,
            }
        )
    return routes


def _extract_api_endpoints() -> Dict[str, List[Dict[str, str]]]:
    views_dir = REPO_ROOT / "app" / "views"
    if not views_dir.exists():
        return {}
    out: Dict[str, List[Dict[str, str]]] = {}
    method_re = re.compile(r"@bp\.(get|post|put|delete|patch)\(\s*['\"]([^'\"]+)['\"]")
    route_re = re.compile(r"@bp\.route\(\s*['\"]([^'\"]+)['\"](?P<rest>[^)]*)\)")
    methods_re = re.compile(r"methods\s*=\s*\[([^\]]+)\]")
    for path in sorted(views_dir.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        entries: List[Dict[str, str]] = []
        for method, route in method_re.findall(text):
            if "/api" not in route:
                continue
            entries.append({"method": method.upper(), "route": route})
        for match in route_re.finditer(text):
            route = match.group(1)
            if "/api" not in route:
                continue
            rest = match.group("rest") or ""
            methods = methods_re.search(rest)
            if methods:
                raw = methods.group(1)
                cleaned = re.sub(r"[^A-Za-z,]", "", raw)
                for method in [m for m in cleaned.split(",") if m]:
                    entries.append({"method": method.upper(), "route": route})
            else:
                entries.append({"method": "ROUTE", "route": route})
        if entries:
            rel = str(path.relative_to(REPO_ROOT))
            entries = sorted(entries, key=lambda e: (e["route"], e["method"]))
            out[rel] = entries
    return out


def _extract_env_vars() -> List[Dict[str, str]]:
    out: Dict[str, Dict[str, str]] = {}
    for path in sorted(REPO_ROOT.glob(".env*.example")):
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, rest = line.split("=", 1)
            key = key.strip()
            if not key:
                continue
            value = rest.strip()
            comment = ""
            if "#" in value:
                value, comment = value.split("#", 1)
                value = value.strip()
                comment = comment.strip()
            rec = out.setdefault(key, {"key": key, "example": "", "comment": ""})
            if value and not rec["example"]:
                rec["example"] = value
            if comment and not rec["comment"]:
                rec["comment"] = comment
    return sorted(out.values(), key=lambda r: r["key"])


_SCRIPT_GROUPS = (
    ("deploy/community", "Single instance with Docker (Linux, or Windows Docker Desktop)"),
    ("deploy/scripts", "Guided multi-instance VPS with Caddy"),
    ("deploy/windows", "Windows LAN service (nginx + waitress)"),
    ("deploy/windows-restricted", "Windows, restricted host, python run.py"),
    ("tools", "Maintenance and developer utilities"),
)

_SCRIPT_SKIP = {"lib/common.sh", "lib/nextcloud.sh", "lib/update.sh"}


def _script_summary(text: str) -> str:
    """One human sentence describing a script.

    Tried in order: a PowerShell .SYNOPSIS, the header comment, the prose line
    of a usage() heredoc, and finally the Usage line itself. Scripts document
    themselves in all four styles, and a table of "See the script header" would
    be worse than no table.
    """

    synopsis = re.search(r"\.SYNOPSIS\s*\r?\n\s*(.+)", text)
    if synopsis:
        return synopsis.group(1).strip()

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(("#!", "@echo", "setlocal")):
            continue
        if line.startswith("#") or line.startswith("REM "):
            body = line.lstrip("#").removeprefix("REM ").strip(" =-")
            if len(body) > 12 and not body.startswith("shellcheck"):
                return body
            continue
        break

    # The invocation line is the most useful single line for a script whose
    # only documentation is a usage() block, and it is copy-pasteable. Prose
    # from inside the block comes second: picking sentences out of it lands on
    # continuation lines like "(regardless of --continue-on-error)".
    usage = re.search(r"Usage:[ \t]*\r?\n?[ \t]*(\S.*)", text)
    if usage:
        candidate = usage.group(1).strip().strip('"').rstrip("'} ")
        if len(candidate) > 8:
            return candidate

    heredoc = re.search(r"cat <<'?\w+'?\s*\r?\n(.*?)\r?\n\w+\s*$", text, re.DOTALL | re.MULTILINE)
    if heredoc:
        for raw in heredoc.group(1).splitlines():
            line = raw.strip()
            if not line or line.lower().startswith("usage"):
                continue
            if line.startswith(("sudo ", "./", "-", "$", "#", "(")) or line.endswith(":"):
                continue
            if len(line) > 12:
                return line
    return ""


def _script_options(text: str) -> List[str]:
    """Flags a script accepts, from a usage block, a case arm, or param()."""

    options = []
    for match in re.finditer(r"(?m)^\s*(--[a-z][a-z0-9-]*)\)", text):
        options.append(match.group(1))
    for match in re.finditer(r"(?m)^\s*\[(?:switch|string|int|Security\.SecureString)[^\]]*\]\s*\$(\w+)", text):
        options.append("-" + match.group(1))
    for match in re.finditer(r"(?m)^\s*\[(?:Parameter|ValidateSet|ValidateRange)[^\]]*\]\s*\r?\n\s*\[[^\]]+\]\s*\$(\w+)", text):
        options.append("-" + match.group(1))
    seen: List[str] = []
    for option in options:
        if option not in seen and option not in ("-Rest",):
            seen.append(option)
    return seen


def _extract_deploy_scripts() -> List[Tuple[str, List[Dict[str, str]]]]:
    """Catalogue every runnable deployment script, straight from the files.

    Generated rather than hand-written so the help cannot drift from what the
    scripts actually accept - the same reason the env and API tables are
    generated.
    """

    groups: List[Tuple[str, List[Dict[str, str]]]] = []
    for relative, title in _SCRIPT_GROUPS:
        directory = REPO_ROOT / relative
        if not directory.exists():
            continue
        rows: List[Dict[str, str]] = []
        for path in sorted(directory.rglob("*")):
            if path.suffix.lower() not in (".sh", ".ps1", ".cmd"):
                continue
            key = path.relative_to(directory).as_posix()
            if key in _SCRIPT_SKIP:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            options = _script_options(text)
            rows.append(
                {
                    "name": key,
                    "summary": _script_summary(text) or "See the script header.",
                    "options": ", ".join(f"`{o}`" for o in options) if options else "-",
                }
            )
        if rows:
            groups.append((f"{relative} - {title}", rows))
    return groups


def _extract_addin_options() -> List[Dict[str, str]]:
    path = REPO_ROOT / "solidworks-addin" / "TinyMRP.SolidWorksAddin" / "Services" / "PublishOptions.cs"
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    props = re.findall(r"public\s+bool\s+(\w+)\s*\{", text)
    desc = {
        "ExportPngModel": "Export PNG model preview.",
        "ExportStep": "Export STEP model.",
        "ExportEdrawing": "Export eDrawings model.",
        "Export3mf": "Export 3MF model.",
        "ExportPly": "Export PLY model.",
        "ExportStl": "Export STL model.",
        "ExportPngDrawing": "Export drawing PNG (DWG preview).",
        "ExportPdf": "Export drawing PDF.",
        "ExportEdrawingDrawing": "Export eDrawings drawing.",
        "OverwriteFiles": "Overwrite existing files on export.",
        "TopLevelOnly": "Export only the top-level assembly.",
    }
    where = {
        "ExportPngModel": "Publish/BOM tab",
        "ExportStep": "Publish/BOM tab",
        "ExportEdrawing": "Publish/BOM tab",
        "Export3mf": "Publish/BOM tab",
        "ExportPly": "Publish/BOM tab",
        "ExportStl": "Publish/BOM tab",
        "ExportPngDrawing": "Publish/BOM tab",
        "ExportPdf": "Publish/BOM tab",
        "ExportEdrawingDrawing": "Publish/BOM tab",
        "OverwriteFiles": "Publish/BOM tab",
        "TopLevelOnly": "Publish/BOM tab",
    }
    return [
        {
            "name": name,
            "desc": desc.get(name, "Add-in option."),
            "where": where.get(name, "Add-in UI"),
        }
        for name in props
    ]


def _extract_addin_tabs() -> List[Dict[str, str]]:
    path = REPO_ROOT / "solidworks-addin" / "TinyMRP.SolidWorksAddin" / "UI" / "MainPaneControl.cs"
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    tabs = re.findall(r"CreateTabPage\(\"([^\"]+)\"\)", text)
    seen = []
    for t in tabs:
        if t not in seen:
            seen.append(t)
    desc = {
        "Publish/BOM": "Export deliverables and BOMs.",
        "Tools": "Utilities like hide features and unit normalization.",
        "Numbering": "Part numbering schemes and allocation.",
        "Configuration": "Server connection and advanced settings.",
        "Quick Start": "Basic connection settings.",
        "Advanced": "Additional configuration options.",
    }
    return [{"name": t, "desc": desc.get(t, "Add-in tab.")} for t in seen]


def _markdown_table(headers: List[str], rows: List[List[str]]) -> str:
    if not rows:
        return "_No data found._"
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        out.append("| " + " | ".join(row) + " |")
    return "\n".join(out)


def _render_placeholders() -> Dict[str, str]:
    ui_routes = _extract_ui_routes()
    ui_rows = [
        [
            f"`{r['route']}`",
            r["purpose"],
            r["permission"],
        ]
        for r in ui_routes
    ]
    ui_table = _markdown_table(["Route", "What it is for", "Permissions"], ui_rows)

    api_by_module = _extract_api_endpoints()
    api_sections = []
    if api_by_module:
        for module, entries in api_by_module.items():
            api_sections.append(f"### {module}")
            rows = [[e["method"], f"`{e['route']}`"] for e in entries]
            api_sections.append(_markdown_table(["Method", "Path"], rows))
    api_md = "\n\n".join(api_sections) if api_sections else "_No API endpoints found._"

    env_vars = _extract_env_vars()
    env_rows = [[f"`{r['key']}`", f"`{r['example']}`" if r["example"] else "", r["comment"]] for r in env_vars]
    env_md = _markdown_table(["Variable", "Example", "Notes"], env_rows)

    addin_options = _extract_addin_options()
    addin_rows = [[f"`{r['name']}`", r["desc"], r["where"]] for r in addin_options]
    addin_md = _markdown_table(["Option", "What it does", "Where in UI"], addin_rows)

    addin_tabs = _extract_addin_tabs()
    tabs_rows = [[r["name"], r["desc"]] for r in addin_tabs]
    tabs_md = _markdown_table(["Tab", "Purpose"], tabs_rows)

    script_sections = []
    for title, rows in _extract_deploy_scripts():
        script_sections.append(f"**`{title}`**")
        script_sections.append(
            _markdown_table(
                ["Script", "What it does", "Options"],
                [[f"`{r['name']}`", r["summary"], r["options"]] for r in rows],
            )
        )
    scripts_md = "\n\n".join(script_sections) if script_sections else "_No scripts found._"

    return {
        "AUTO_UI_PAGES": ui_table,
        "AUTO_WEB_ROUTES": ui_table,
        "AUTO_API_ENDPOINTS": api_md,
        "AUTO_ENV_VARS": env_md,
        "AUTO_ADDIN_OPTIONS": addin_md,
        "AUTO_ADDIN_TABS": tabs_md,
        "AUTO_DEPLOY_SCRIPTS": scripts_md,
    }


def _replace_placeholders(text: str, values: Dict[str, str]) -> str:
    out = text
    for key, val in values.items():
        out = out.replace("{{" + key + "}}", val)
    return out


def _build_toc(tokens) -> List[Dict[str, Any]]:
    """Return chapters (h1) each holding their sections (h2).

    A flat list of every heading ran to well over a hundred entries, which is
    unusable as navigation. Third-level headings stay addressable by anchor but
    are left out of the tree.
    """

    toc: List[Dict[str, Any]] = []
    slug_counts: Dict[str, int] = {}
    for i, token in enumerate(tokens):
        if token.type != "heading_open":
            continue
        level = int(token.tag[1])
        title = tokens[i + 1].content if i + 1 < len(tokens) else ""
        slug = _slugify(title)
        if slug in slug_counts:
            slug_counts[slug] += 1
            slug = f"{slug}-{slug_counts[slug]}"
        else:
            slug_counts[slug] = 1
        token.attrSet("id", slug)
        if level == 1:
            toc.append({"id": slug, "title": title, "sections": []})
        elif level == 2 and toc:
            toc[-1]["sections"].append({"id": slug, "title": title})
    return toc


_LONE_IMG_RE = re.compile(r'<p>(<img src="([^"]+)" alt="([^"]*)"[^>]*>)</p>')


def _figures(html: str) -> str:
    """Turn a standalone image into a captioned figure.

    The markdown alt text is the caption, so a screenshot always arrives with
    an explanation of what the reader is meant to notice in it.
    """

    def replace(match: "re.Match[str]") -> str:
        img, _src, alt = match.group(1), match.group(2), match.group(3)
        caption = f'<figcaption class="help-figure-caption">{alt}</figcaption>' if alt else ""
        return f'<figure class="help-figure">{img}{caption}</figure>'

    return _LONE_IMG_RE.sub(replace, html)


_H1_RE = re.compile(r"<h1[^>]*>.*?</h1>", re.DOTALL)
_H2_SPLIT_RE = re.compile(r'(<h2 id="[^"]*">.*?</h2>)', re.DOTALL)
_H2_ID_RE = re.compile(r'<h2 id="([^"]*)">(.*?)</h2>', re.DOTALL)


def _collapsible(html: str) -> str:
    """Wrap every h2 section in a <details> so the page reads as an outline.

    Chapters (h1) stay visible as headers; each section below them folds. The
    first section of each chapter starts open so the page never looks empty.
    """

    chapters = [part for part in _H1_RE.split(html)]
    headers = _H1_RE.findall(html)
    out: List[str] = [chapters[0]] if chapters and chapters[0].strip() else []

    for index, header in enumerate(headers):
        body = chapters[index + 1] if index + 1 < len(chapters) else ""
        pieces = _H2_SPLIT_RE.split(body)
        rendered = [f'<section class="help-chapter">{header}']
        if pieces and pieces[0].strip():
            rendered.append(f'<div class="help-intro">{pieces[0]}</div>')
        for position in range(1, len(pieces), 2):
            match = _H2_ID_RE.match(pieces[position])
            if not match:
                continue
            slug, title = match.group(1), match.group(2)
            content = pieces[position + 1] if position + 1 < len(pieces) else ""
            opened = " open" if position == 1 else ""
            rendered.append(
                f'<details class="help-section" id="sec-{slug}"{opened}>'
                f'<summary><span class="help-section-title" id="{slug}">{title}</span></summary>'
                f'<div class="help-section-body">{content}</div>'
                f"</details>"
            )
        rendered.append("</section>")
        out.append("".join(rendered))
    return "".join(out)


def build_help() -> Dict[str, str]:
    md_files = _read_markdown_files()
    combined = "\n\n".join(content for _, content in md_files)
    placeholders = _render_placeholders()
    combined = _replace_placeholders(combined, placeholders)

    md = MarkdownIt("gfm-like", {"html": True})
    md.disable("linkify")
    tokens = md.parse(combined)
    toc = _build_toc(tokens)
    html = _collapsible(_figures(md.renderer.render(tokens, md.options, {})))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    help_html_path = OUTPUT_DIR / "help.html"
    help_toc_path = OUTPUT_DIR / "help_toc.json"

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    commit = _git_commit()

    help_html_path.write_text(html, encoding="utf-8")
    help_toc_path.write_text(
        json.dumps(
            {
                "generated_at": generated_at,
                "commit": commit,
                "items": toc,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    return {
        "help_html": str(help_html_path),
        "help_toc": str(help_toc_path),
        "generated_at": generated_at,
        "commit": commit,
    }


if __name__ == "__main__":
    info = build_help()
    print(json.dumps(info, indent=2))
