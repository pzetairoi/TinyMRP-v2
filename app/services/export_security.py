"""Fail-closed preflight controls for authenticated export generation."""

from __future__ import annotations

import re

from dataclasses import dataclass
from typing import Any, Iterable

from app.models.artifact import PartFile
from app.models.bom import BOMLink
from app.services.authorization import (
    authorised_part_pairs,
    has_permission,
)
from app.services.file_security import (
    FileSecurityError,
    managed_file_read_allowed,
    resolve_managed_path,
)
from app.services.part_norm import clean_rev


class ExportSecurityError(ValueError):
    """A non-disclosing export preflight failure."""


@dataclass(frozen=True)
class ExportPlan:
    pairs: frozenset[tuple[str, str]]
    files: tuple[PartFile, ...] = ()


def _normalized_pairs(
    pairs: Iterable[tuple[Any, Any]],
) -> frozenset[tuple[str, str]]:
    return frozenset(
        (str(part_number or "").strip().casefold(), clean_rev(revision).casefold())
        for part_number, revision in pairs
        if str(part_number or "").strip()
    )


def exact_bom_pairs(
    root_pn: Any,
    root_rev: Any,
    *,
    full: bool = True,
) -> frozenset[tuple[str, str]]:
    """Resolve one exact BOM tree, treating a blank revision as exact."""

    root = (str(root_pn or "").strip(), clean_rev(root_rev))
    if not root[0]:
        raise ExportSecurityError("export unavailable")
    found: set[tuple[str, str]] = {root}
    frontier: list[tuple[str, str]] = [root]
    try:
        # One query per LEVEL, not per node. This walk previously issued a
        # BOMLink query for every part it visited - 1348 of them inside a
        # single doc-pack options call. The parts of a level are all known
        # before any of them is expanded, so they can be asked for together.
        #
        # The result is identical by construction: the same pairs are
        # discovered in the same breadth-first order, and the (pn, rev) match
        # is still exact. Only the number of round trips changes. That matters
        # because this set is the authorisation boundary for an export.
        while frontier:
            parent_names = sorted({pn for pn, _rev in frontier if pn})
            wanted = set(frontier)
            next_frontier: list[tuple[str, str]] = []
            if parent_names:
                for link in BOMLink.objects(parent_pn__in=parent_names).only(
                    "parent_pn", "parent_rev", "child_pn", "child_rev"
                ):
                    parent = (
                        str(getattr(link, "parent_pn", "") or "").strip(),
                        clean_rev(getattr(link, "parent_rev", "")),
                    )
                    # A batched query returns links for every revision of those
                    # part numbers, so the exact pair must still be honoured.
                    if parent not in wanted:
                        continue
                    child_pn = str(getattr(link, "child_pn", "") or "").strip()
                    if not child_pn:
                        continue
                    child = (child_pn, clean_rev(getattr(link, "child_rev", "")))
                    if child in found:
                        continue
                    found.add(child)
                    if full:
                        next_frontier.append(child)
            if not full:
                break
            frontier = next_frontier
    except Exception as exc:
        raise ExportSecurityError("export unavailable") from exc
    return frozenset(found)


def where_used_pairs(root_pn: Any, root_rev: Any) -> frozenset[tuple[str, str]]:
    """Resolve exact immediate where-used parents for an authorised report."""

    pn = str(root_pn or "").strip()
    rev = clean_rev(root_rev)
    if not pn:
        raise ExportSecurityError("export unavailable")
    pairs: set[tuple[str, str]] = set()
    try:
        for link in BOMLink.objects(child_pn=pn, child_rev=rev):
            parent_pn = str(getattr(link, "parent_pn", "") or "").strip()
            if parent_pn:
                pairs.add((parent_pn, clean_rev(getattr(link, "parent_rev", ""))))
    except Exception as exc:
        raise ExportSecurityError("export unavailable") from exc
    return frozenset(pairs)


def require_export_permissions(
    user: Any,
    *permissions: str,
) -> None:
    required = ("exports.run", *permissions)
    if any(not has_permission(user, permission) for permission in required):
        raise ExportSecurityError("export unavailable")


def docpack_file_groups(options: Any) -> set[str] | None:
    """Return included managed groups; ``None`` means every group."""

    groups: set[str] = set()
    if bool(
        getattr(options, "want_excel_bom", False)
        and getattr(options, "excel_all_fields", False)
    ):
        return None
    if bool(getattr(options, "want_excel_bom", False)):
        excel_file_fields = {
            "thumbnail": "png",
            "datasheet": "datasheet",
            "has_pdf": "pdf",
            "has_png": "png",
            "has_dxf": "dxf",
            "has_step": "step",
            "has_edr": "edr",
            "has_3mf": "3mf",
            "has_ply": "ply",
            "has_stl": "stl",
            "has_datasheet": "datasheet",
        }
        groups.update(
            excel_file_fields[field_id]
            for field_id in (
                getattr(options, "excel_field_ids", None) or []
            )
            if field_id in excel_file_fields
        )
    if bool(getattr(options, "want_selected_files", False)):
        selected = {
            str(value or "").strip().lower()
            for value in (getattr(options, "file_types", None) or [])
            if str(value or "").strip()
        }
        if not selected:
            return None
        groups.update(selected)
    if bool(getattr(options, "fabrication_pack", False)):
        groups.update({"pdf", "dxf", "step"})
    if bool(
        getattr(options, "want_pdf_binder", False)
        or getattr(options, "want_index_pdf", False)
    ):
        groups.add("pdf")
        if bool(getattr(options, "binder_add_datasheets", False)):
            groups.add("datasheet")
    wants_binder = bool(getattr(options, "want_pdf_binder", False))
    if bool(
        getattr(options, "want_visual_list", False)
        or getattr(options, "want_cover_page", False)
        or getattr(options, "want_hardware_summary", False)
        or getattr(options, "want_whereused_report", False)
        or (
            wants_binder
            and (
                getattr(options, "binder_add_visual_list", False)
                or getattr(options, "binder_add_cover", False)
                or getattr(options, "binder_add_hardware_summary", False)
                or getattr(options, "binder_add_whereused", False)
            )
        )
    ):
        groups.add("png")
    return groups


def _files_for_pairs(
    pairs: Iterable[tuple[str, str]],
    groups: set[str] | None,
) -> tuple[PartFile, ...]:
    # One query for every pair, not one per pair. This ran a PartFile query per
    # part - 1372 of them inside a single doc-pack options call on a 1344-part
    # assembly.
    #
    # The batched query matches on part_number only, so it returns rows for
    # every revision of those numbers. The exact (pn, rev) pair is still
    # enforced in memory below, case-folded exactly as __iexact would - this
    # feeds an export authorisation check, so a row for a revision that was
    # never requested must not slip through.
    wanted: set[tuple[str, str]] = set()
    names: set[str] = set()
    for pn, rev in pairs:
        name = str(pn or "").strip()
        if not name:
            continue
        names.add(name)
        wanted.add((name.casefold(), clean_rev(rev).casefold()))
    if not wanted:
        return ()

    # Case-INSENSITIVE $in, matching the __iexact the per-pair query used.
    # A plain $in is case-sensitive, and swapping it in silently dropped files
    # whose stored part_number differed only in case - including, in the test
    # suite, a path-traversal record that then never reached the safety check
    # and turned a 403 into a 200. Part numbers are matched case-insensitively
    # everywhere in this codebase; an authorisation path is the last place to
    # make an exception.
    query = PartFile.objects(
        __raw__={
            "part_number": {
                "$in": [re.compile(f"^{re.escape(name)}$", re.IGNORECASE) for name in sorted(names)]
            }
        }
    )
    if groups is not None:
        query = query.filter(ext_group__in=sorted(groups))

    files: list[PartFile] = []
    for record in query:
        key = (
            str(getattr(record, "part_number", "") or "").strip().casefold(),
            clean_rev(getattr(record, "revision", "")).casefold(),
        )
        if key in wanted:
            files.append(record)
    return tuple(files)


def preflight_export_plan(
    user: Any,
    pairs: Iterable[tuple[Any, Any]],
    *,
    require_bom: bool = True,
    include_files: bool = False,
    file_groups: set[str] | None = None,
    include_markups: bool = False,
) -> ExportPlan:
    required = ["parts.read"]
    if require_bom:
        required.append("bom.read")
    if include_files:
        required.append("files.read")
    if include_markups:
        required.append("markups.read")
    require_export_permissions(user, *required)

    exact_pairs = _normalized_pairs(pairs)
    if not exact_pairs:
        raise ExportSecurityError("export unavailable")
    if authorised_part_pairs(user, exact_pairs) != exact_pairs:
        raise ExportSecurityError("export unavailable")

    files = _files_for_pairs(exact_pairs, file_groups) if include_files else ()
    for file_record in files:
        # REVERTED 2026-08-08. I removed this per-file check arguing it could
        # not fail - authorised_part_pairs proves the whole pair set above, and
        # _files_for_pairs only returns files for those pairs. The argument was
        # wrong, and test_docpack_preflight_rejects_unsafe_required_file caught
        # it: a PartFile carrying rel_path "../outside.pdf" was accepted where
        # it had been refused with a 403.
        #
        # Keep the full check. The 5592 part queries it costs on a large
        # assembly are recorded in optimizationplan.txt as still open; the
        # answer is to make the check cheap, not to reason it away.
        if not managed_file_read_allowed(user, file_record):
            raise ExportSecurityError("export unavailable")
        try:
            # Existing docpack/binder behaviour treats a safely located but
            # physically missing source as optional and reports the omission.
            resolve_managed_path(file_record, must_exist=False)
        except FileSecurityError as exc:
            raise ExportSecurityError("export unavailable") from exc
    return ExportPlan(exact_pairs, files)


def preflight_docpack(user: Any, options: Any) -> ExportPlan:
    root_pn = str(getattr(options, "root_pn", "") or "").strip()
    root_rev = clean_rev(getattr(options, "root_rev", ""))
    if getattr(options, "flat_override", None) is not None:
        pairs = {
            (str(pn or "").strip(), clean_rev(rev))
            for pn, rev, _qty in (options.flat_override or [])
            if str(pn or "").strip()
        }
    else:
        pairs = set(
            exact_bom_pairs(
                root_pn,
                root_rev,
                full=str(getattr(options, "depth", "full") or "full").lower()
                != "top",
            )
        )
    if root_pn and getattr(options, "flat_override", None) is None:
        pairs.add((root_pn, root_rev))
    if bool(
        getattr(options, "want_whereused_report", False)
        or (
            getattr(options, "want_pdf_binder", False)
            and getattr(options, "binder_add_whereused", False)
        )
    ):
        pairs.update(where_used_pairs(root_pn, root_rev))

    file_groups = docpack_file_groups(options)
    include_files = file_groups is None or bool(file_groups)
    include_markups = bool(
        getattr(options, "want_markup_files", False)
        or getattr(options, "want_markup_report", False)
        or (
            getattr(options, "want_pdf_binder", False)
            and getattr(options, "binder_add_markups", False)
        )
    )
    return preflight_export_plan(
        user,
        pairs,
        require_bom=True,
        include_files=include_files,
        file_groups=file_groups,
        include_markups=include_markups,
    )
