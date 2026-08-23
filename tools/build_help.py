from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import quote, unquote, urlsplit

from markdown_it import MarkdownIt


REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = REPO_ROOT / "docs"
OUTPUT_DIR = REPO_ROOT / "app" / "static" / "help"
REPOSITORY_BLOB_BASE = "https://github.com/pzetairoi/TinyMRP-v2/blob/main"
REPOSITORY_TREE_BASE = "https://github.com/pzetairoi/TinyMRP-v2/tree/main"


# The source files remain ordinary Markdown/text files in the repository.  The
# builder only publishes a navigable, authenticated view of them; it never
# creates a second prose source that can drift away from the originals.
DOCUMENT_GROUPS: Tuple[Dict[str, Any], ...] = (
    {
        "id": "user-guide",
        "title": "User guide",
        "description": "Day-to-day workflows, screens, roles and troubleshooting.",
        "default": True,
    },
    {
        "id": "installation-operations",
        "title": "Installation & operations",
        "description": "Current deployment, configuration, networking, backup and update guidance.",
    },
    {
        "id": "security-governance",
        "title": "Security & governance",
        "description": "Security policy, access intent, dependency triage and risk controls.",
    },
    {
        "id": "product-support",
        "title": "Product & support",
        "description": "Product scope, retention, support and disclosure policies.",
    },
    {
        "id": "engineering-reference",
        "title": "Engineering & reference",
        "description": "Architecture, field design, testing and generated technical reference.",
    },
)

_ROOT_DOCUMENTS = ("README.md", "SECURITY.md", "CHANGELOG.md")
_TECHNICAL_HELP_DOCUMENTS = {
    "docs/help/06b_server_installation.md",
    "docs/help/08_reference_auto.md",
    "docs/help/CONTRIBUTING_HELP.md",
}


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


def _source_key(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _document_group(path: Path) -> str:
    rel = _source_key(path)
    if rel.startswith("docs/help/") and rel not in _TECHNICAL_HELP_DOCUMENTS:
        return "user-guide"
    if rel.startswith("docs/deployment/") or rel == "docs/help/06b_server_installation.md":
        return "installation-operations"
    if rel == "SECURITY.md" or rel.startswith("docs/security/"):
        return "security-governance"
    if rel.startswith("docs/commercial/"):
        return "product-support"
    if rel == "CHANGELOG.md" or rel.startswith("docs/planning/") or rel in {
        "docs/PRODUCTION_HARDENING_BASELINE.md",
        "docs/UPDATING_PRODUCTION.md",
    }:
        return "history"
    return "engineering-reference"


def _source_sort_key(path: Path) -> Tuple[int, str]:
    """Put directory indexes before their detail pages, then sort naturally."""

    rel = _source_key(path)
    return (0 if path.name.lower() == "readme.md" else 1, rel.lower())


def _documentation_sources() -> List[Path]:
    files = [
        path
        for path in DOCS_DIR.rglob("*")
        if path.is_file() and path.suffix.lower() in {".md", ".txt"}
    ]
    files.extend(REPO_ROOT / name for name in _ROOT_DOCUMENTS if (REPO_ROOT / name).is_file())
    # Planning archives, changelogs and point-in-time production evidence stay
    # in the repository for developers. They are deliberately not published in
    # the end-user Help UI.
    return sorted((path for path in files if _document_group(path) != "history"), key=_source_sort_key)


def _document_id(path: Path) -> str:
    rel = path.relative_to(REPO_ROOT).with_suffix("").as_posix()
    if rel.startswith("docs/"):
        rel = rel[5:]
    return "doc-" + _slugify(rel.replace("/", " "))


def _fallback_title(path: Path) -> str:
    return path.stem.replace("_", " ").replace("-", " ").strip().title()


def _read_document(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() == ".txt":
        return (
            f"# {_fallback_title(path)}\n\n"
            "> Historical plain-text archive. Treat this as evidence, not current instructions.\n\n"
            "## Archived text\n\n```text\n"
            + text
            + "\n```"
        )
    if not re.search(r"(?m)^#\s+\S", text):
        text = f"# {_fallback_title(path)}\n\n{text}"
    return text


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


def _build_toc(
    tokens,
    *,
    document_id: str | None = None,
    used_ids: set[str] | None = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """Return chapters (h1) each holding their sections (h2).

    A flat list of every heading ran to well over a hundred entries, which is
    unusable as navigation. Third-level headings stay addressable by anchor but
    are left out of the tree. Repository-reference documents get a document
    prefix so repeated headings such as "Overview" cannot collide. The user
    guide keeps its established public anchors because screens deep-link to it.
    """

    toc: List[Dict[str, Any]] = []
    heading_targets: Dict[str, str] = {}
    occupied = used_ids if used_ids is not None else set()
    first_h1 = True
    for i, token in enumerate(tokens):
        if token.type != "heading_open":
            continue
        level = int(token.tag[1])
        title = tokens[i + 1].content if i + 1 < len(tokens) else ""
        source_slug = _slugify(title)
        if document_id and level == 1 and first_h1:
            candidate = document_id
        elif document_id:
            candidate = f"{document_id}--{source_slug}"
        else:
            candidate = source_slug
        slug = candidate
        suffix = 2
        while slug in occupied:
            slug = f"{candidate}-{suffix}"
            suffix += 1
        occupied.add(slug)
        token.attrSet("id", slug)
        heading_targets.setdefault(source_slug, slug)
        if level == 1:
            toc.append({"id": slug, "title": title, "sections": []})
            first_h1 = False
        elif level == 2 and toc:
            toc[-1]["sections"].append({"id": slug, "title": title})
    return toc, heading_targets


def _walk_link_tokens(tokens):
    for token in tokens:
        if token.type == "link_open":
            yield token
        if token.children:
            yield from _walk_link_tokens(token.children)


def _repository_url(path: Path) -> str:
    try:
        rel = path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return ""
    base = REPOSITORY_TREE_BASE if path.is_dir() else REPOSITORY_BLOB_BASE
    return f"{base}/{quote(rel, safe='/')}"


def _rewrite_document_links(
    tokens,
    *,
    source: Path,
    record_by_path: Dict[Path, Dict[str, Any]],
    group_by_directory: Dict[Path, str],
    heading_targets: Dict[str, str],
) -> None:
    """Make repository-relative Markdown links work inside the one-page UI."""

    for token in _walk_link_tokens(tokens):
        href = token.attrGet("href") or ""
        parsed = urlsplit(href)
        if parsed.scheme or parsed.netloc or href.startswith(("/", "mailto:", "tel:")):
            continue

        fragment = unquote(parsed.fragment or "")
        if not parsed.path:
            if fragment:
                token.attrSet("href", "#" + heading_targets.get(_slugify(fragment), _slugify(fragment)))
            continue

        target = (source.parent / unquote(parsed.path)).resolve()
        if target.is_dir() and (target / "README.md").resolve() in record_by_path:
            target = (target / "README.md").resolve()

        target_record = record_by_path.get(target)
        if target_record:
            target_id = target_record["document_id"]
            if fragment:
                target_id = target_record["heading_targets"].get(_slugify(fragment), target_id)
            token.attrSet("href", "#" + target_id)
            continue

        group_id = group_by_directory.get(target)
        if group_id:
            token.attrSet("href", "#help-group-" + group_id)
            continue

        repo_url = _repository_url(target)
        if repo_url:
            if fragment:
                repo_url += "#" + quote(fragment, safe="-_")
            token.attrSet("href", repo_url)


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
    placeholders = _render_placeholders()
    md = MarkdownIt("gfm-like", {"html": True})
    md.disable("linkify")

    records: List[Dict[str, Any]] = []
    record_by_path: Dict[Path, Dict[str, Any]] = {}
    user_guide_ids: set[str] = set()
    reference_ids: set[str] = set()

    # Parse and assign every anchor first. Relative links can then be rewritten
    # to their final in-page target even when they point to a later document.
    for source in _documentation_sources():
        group_id = _document_group(source)
        source_text = _replace_placeholders(_read_document(source), placeholders)
        tokens = md.parse(source_text)
        generated_document_id = _document_id(source)
        toc, heading_targets = _build_toc(
            tokens,
            document_id=None if group_id == "user-guide" else generated_document_id,
            used_ids=user_guide_ids if group_id == "user-guide" else reference_ids,
        )
        if not toc:
            raise ValueError(f"documentation source has no chapter heading: {_source_key(source)}")
        for chapter in toc:
            chapter["source"] = _source_key(source)
            chapter["source_url"] = _repository_url(source)
        record = {
            "path": source.resolve(),
            "source": _source_key(source),
            "source_url": _repository_url(source),
            "group_id": group_id,
            "document_id": toc[0]["id"],
            "heading_targets": heading_targets,
            "tokens": tokens,
            "toc": toc,
        }
        records.append(record)
        record_by_path[source.resolve()] = record

    group_by_directory: Dict[Path, str] = {}
    for directory in [path for path in DOCS_DIR.rglob("*") if path.is_dir()]:
        child_groups = {
            record["group_id"]
            for record in records
            if directory.resolve() in record["path"].parents
        }
        if len(child_groups) == 1:
            group_by_directory[directory.resolve()] = child_groups.pop()

    group_defs = {group["id"]: dict(group) for group in DOCUMENT_GROUPS}
    group_html: Dict[str, List[str]] = {group["id"]: [] for group in DOCUMENT_GROUPS}
    group_toc: Dict[str, List[Dict[str, Any]]] = {group["id"]: [] for group in DOCUMENT_GROUPS}

    for record in records:
        _rewrite_document_links(
            record["tokens"],
            source=record["path"],
            record_by_path=record_by_path,
            group_by_directory=group_by_directory,
            heading_targets=record["heading_targets"],
        )
        rendered = _collapsible(
            _figures(md.renderer.render(record["tokens"], md.options, {}))
        )
        group_html[record["group_id"]].append(
            '<article class="help-document" data-help-source="{}">'
            '<div class="help-source">Canonical source: '
            '<a href="{}" target="_blank" rel="noopener noreferrer"><code>{}</code></a>'
            '</div>{}</article>'.format(
                escape(record["source"], quote=True),
                escape(record["source_url"], quote=True),
                escape(record["source"]),
                rendered,
            )
        )
        group_toc[record["group_id"]].extend(record["toc"])

    toc: List[Dict[str, Any]] = []
    rendered_groups: List[str] = []
    for group in DOCUMENT_GROUPS:
        group_id = group["id"]
        chapters = group_toc[group_id]
        if not chapters:
            continue
        toc_group = dict(group_defs[group_id])
        toc_group["chapters"] = chapters
        toc.append(toc_group)
        rendered_groups.append(
            '<section class="help-group" data-help-group="{}" id="help-group-{}">'
            '<header class="help-group-header"><h2>{}</h2><p>{}</p></header>{}</section>'.format(
                escape(group_id, quote=True),
                escape(group_id, quote=True),
                escape(group["title"]),
                escape(group["description"]),
                "".join(group_html[group_id]),
            )
        )

    help_html = "".join(rendered_groups)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    help_html_path = OUTPUT_DIR / "help.html"
    help_toc_path = OUTPUT_DIR / "help_toc.json"

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    commit = _git_commit()

    help_html_path.write_text(help_html, encoding="utf-8")
    help_toc_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "generated_at": generated_at,
                "commit": commit,
                "source_count": len(records),
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
