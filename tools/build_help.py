from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

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

    return {
        "AUTO_UI_PAGES": ui_table,
        "AUTO_WEB_ROUTES": ui_table,
        "AUTO_API_ENDPOINTS": api_md,
        "AUTO_ENV_VARS": env_md,
        "AUTO_ADDIN_OPTIONS": addin_md,
        "AUTO_ADDIN_TABS": tabs_md,
    }


def _replace_placeholders(text: str, values: Dict[str, str]) -> str:
    out = text
    for key, val in values.items():
        out = out.replace("{{" + key + "}}", val)
    return out


def _build_toc(tokens) -> List[Dict[str, str]]:
    toc = []
    slug_counts: Dict[str, int] = {}
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.type == "heading_open":
            level = int(token.tag[1])
            if i + 1 < len(tokens):
                title = tokens[i + 1].content
            else:
                title = ""
            slug = _slugify(title)
            if slug in slug_counts:
                slug_counts[slug] += 1
                slug = f"{slug}-{slug_counts[slug]}"
            else:
                slug_counts[slug] = 1
            token.attrSet("id", slug)
            if level >= 2:
                toc.append({"id": slug, "title": title, "level": level})
        i += 1
    return toc


def build_help() -> Dict[str, str]:
    md_files = _read_markdown_files()
    combined = "\n\n".join(content for _, content in md_files)
    placeholders = _render_placeholders()
    combined = _replace_placeholders(combined, placeholders)

    md = MarkdownIt("gfm-like", {"html": True})
    md.disable("linkify")
    tokens = md.parse(combined)
    toc = _build_toc(tokens)
    html = md.renderer.render(tokens, md.options, {})

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
