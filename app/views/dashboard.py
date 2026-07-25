from __future__ import annotations

import time
from datetime import timedelta
from threading import Lock
from typing import Dict, List, Optional, Tuple

from flask import Blueprint, jsonify, current_app
from flask_login import login_required, current_user
from mongoengine.queryset.visitor import Q

from app.models.part import Part
from app.models.artifact import PartFile
from app.models.bom import BOMLink
from app.services.attrs import approval_filter_raw, harvest_part_attrs
from app.services.authorization import require_permission, scope_queryset
from app.services.insights import classify_part
from app.services.timezone_utils import utc_now
from app.views.api_helpers import add_datetime_fields


bp = Blueprint("dashboard_api", __name__, url_prefix="/api/dashboard")

_CACHE: Dict[str, Dict[str, object]] = {}
_CACHE_LOCK = Lock()
_CACHE_TTL = 45.0


def clear_dashboard_cache() -> None:
    with _CACHE_LOCK:
        _CACHE.clear()


def _cache_key() -> str:
    try:
        uid = current_user.get_id() or "anon"
    except Exception:
        uid = "anon"
    return f"summary:{uid}"


def _get_cache(key: str) -> Optional[Dict]:
    now = time.monotonic()
    with _CACHE_LOCK:
        entry = _CACHE.get(key)
        if not entry:
            return None
        if entry.get("expires", 0) <= now:
            _CACHE.pop(key, None)
            return None
        return entry.get("value")  # type: ignore[return-value]


def _set_cache(key: str, value: Dict) -> None:
    now = time.monotonic()
    with _CACHE_LOCK:
        _CACHE[key] = {"expires": now + _CACHE_TTL, "value": value}


def _allowed_q(allowed: Optional[set[Tuple[str, str]]]) -> Optional[Q]:
    if allowed is None:
        return None
    if not allowed:
        return Q(id__in=[])
    q = Q()
    for pn, rev in allowed:
        pn_clean = (pn or "").strip()
        if not pn_clean:
            continue
        if rev:
            q = q | Q(part_number__iexact=pn_clean, revision__iexact=rev)
        else:
            q = q | Q(part_number__iexact=pn_clean)
    return q


def _allowed_match_stage(allowed: Optional[set[Tuple[str, str]]], pn_field: str, rev_field: str) -> Optional[Dict]:
    if allowed is None:
        return None
    pairs = []
    for pn, rev in allowed:
        pn_clean = (pn or "").strip()
        if not pn_clean:
            continue
        pairs.append({pn_field: pn_clean, rev_field: (rev or "")})
    if not pairs:
        return {"$match": {pn_field: "__none__"}}
    return {"$match": {"$or": pairs}}


def _coverage_counts(allowed: Optional[set[Tuple[str, str]]]) -> Dict[str, int]:
    groups = ["pdf", "png", "dxf", "step", "datasheet"]
    match_stage = _allowed_match_stage(allowed, "part_number", "revision")
    pipeline: List[Dict] = []
    if match_stage:
        pipeline.append(match_stage)
    pipeline.extend(
        [
            {"$group": {"_id": {"pn": "$part_number", "rev": "$revision"}, "groups": {"$addToSet": "$ext_group"}}},
            {
                "$project": {
                    "has_pdf": {"$in": ["pdf", "$groups"]},
                    "has_png": {"$in": ["png", "$groups"]},
                    "has_dxf": {"$in": ["dxf", "$groups"]},
                    "has_step": {"$in": ["step", "$groups"]},
                    "has_datasheet": {"$in": ["datasheet", "$groups"]},
                }
            },
            {
                "$group": {
                    "_id": None,
                    "pdf": {"$sum": {"$cond": ["$has_pdf", 1, 0]}},
                    "png": {"$sum": {"$cond": ["$has_png", 1, 0]}},
                    "dxf": {"$sum": {"$cond": ["$has_dxf", 1, 0]}},
                    "step": {"$sum": {"$cond": ["$has_step", 1, 0]}},
                    "datasheet": {"$sum": {"$cond": ["$has_datasheet", 1, 0]}},
                }
            },
        ]
    )
    result = list(PartFile._get_collection().aggregate(pipeline))
    if not result:
        return {k: 0 for k in groups}
    row = result[0]
    return {
        "pdf": int(row.get("pdf", 0)),
        "png": int(row.get("png", 0)),
        "dxf": int(row.get("dxf", 0)),
        "step": int(row.get("step", 0)),
        "datasheet": int(row.get("datasheet", 0)),
    }


def _top_processes(allowed: Optional[set[Tuple[str, str]]]) -> List[Dict[str, object]]:
    match_stage = _allowed_match_stage(allowed, "part_number", "revision")
    pipeline: List[Dict] = []
    if match_stage:
        pipeline.append(match_stage)
    pipeline.extend(
        [
            {"$unwind": "$processes"},
            {"$match": {"processes": {"$ne": ""}}},
            {"$group": {"_id": "$processes", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 6},
        ]
    )
    out = []
    try:
        for row in Part._get_collection().aggregate(pipeline):
            out.append({"process": row.get("_id") or "", "count": int(row.get("count", 0))})
    except Exception:
        pass
    return out


def _top_hardware_usage(allowed: Optional[set[Tuple[str, str]]]) -> List[Dict[str, object]]:
    pipeline: List[Dict] = []
    if allowed is not None:
        child_pairs = [
            {"child_pn": pn, "child_rev": rev}
            for pn, rev in allowed
            if pn
        ]
        parent_pairs = [
            {"parent_pn": pn, "parent_rev": rev}
            for pn, rev in allowed
            if pn
        ]
        if not child_pairs or not parent_pairs:
            return []
        pipeline.append(
            {
                "$match": {
                    "$and": [
                        {"$or": child_pairs},
                        {"$or": parent_pairs},
                    ]
                }
            }
        )
    pipeline.extend(
        [
            {
                "$group": {
                    "_id": {"pn": "$child_pn", "rev": "$child_rev"},
                    "total_qty": {"$sum": "$qty"},
                    "parents": {"$addToSet": {"pn": "$parent_pn", "rev": "$parent_rev"}},
                }
            },
            {
                "$project": {
                    "total_qty": 1,
                    "where_used_count": {"$size": "$parents"},
                }
            },
            {"$sort": {"total_qty": -1}},
            {"$limit": 200},
        ]
    )
    rows = list(BOMLink._get_collection().aggregate(pipeline))
    if not rows:
        return []

    pairs = [(r.get("_id", {}).get("pn") or "", r.get("_id", {}).get("rev") or "") for r in rows]
    pn_list = list({pn for pn, _ in pairs if pn})
    parts = Part.objects(part_number__in=pn_list).only("part_number", "revision", "description", "attrs", "processes", "category")
    part_map: Dict[Tuple[str, str], Part] = {}
    for p in parts:
        part_map[(p.part_number, p.revision or "")] = p

    meta = current_app.config.get("PROCESS_META", {})
    out = []
    for row in rows:
        pn = row.get("_id", {}).get("pn") or ""
        rev = row.get("_id", {}).get("rev") or ""
        p = part_map.get((pn, rev))
        if not p:
            continue
        attrs = harvest_part_attrs(p)
        classification = classify_part(attrs, list(p.processes or []), meta, category=p.category or "")
        if classification != "hardware":
            continue
        out.append(
            {
                "part_number": pn,
                "revision": rev,
                "description": p.description or attrs.get("description") or "",
                "where_used_count": int(row.get("where_used_count", 0)),
                "total_qty": float(row.get("total_qty", 0.0)),
            }
        )
        if len(out) >= 12:
            break
    return out


@bp.get("/summary")
@login_required
@require_permission("parts.read")
def dashboard_summary():
    cache_key = _cache_key()
    cached = _get_cache(cache_key)
    if cached is not None:
        return jsonify(cached)

    base = scope_queryset(Part.objects, current_user, "parts")
    allowed = {
        (str(pn or "").strip(), str(rev or "").strip())
        for pn, rev in base.scalar("part_number", "revision")
    }

    total_parts = base.count()
    if not allowed:
        empty = {
            "counts": {"total_parts": 0, "updated_7d": 0, "approved": 0},
            "doc_coverage": {"pdf": 0, "png": 0, "dxf": 0, "step": 0, "datasheet": 0},
            "data_health": {"missing_material": 0, "missing_process": 0, "missing_description": 0},
            "top_processes": [],
            "recent_parts": [],
            "top_hardware": [],
        }
        _set_cache(cache_key, empty)
        return jsonify(empty)

    since = utc_now() - timedelta(days=7)
    updated_7d = base.filter(updated_at__gte=since).count()

    missing_material_raw = {
        "$or": [
            {"canonical.material": {"$exists": False}},
            {"canonical.material": ""},
            {"canonical.material": None},
        ]
    }
    missing_description_raw = {
        "$and": [
            {"$or": [{"description": {"$exists": False}}, {"description": ""}, {"description": None}]},
            {"$or": [{"attrs.description": {"$exists": False}}, {"attrs.description": ""}, {"attrs.description": None}]},
        ]
    }
    missing_process_raw = {
        "$or": [{"processes": {"$exists": False}}, {"processes": {"$size": 0}}],
    }
    approved_raw = approval_filter_raw(approved=True)

    missing_material = base.filter(__raw__=missing_material_raw).count()
    missing_description = base.filter(__raw__=missing_description_raw).count()
    missing_process = base.filter(__raw__=missing_process_raw).count()
    approved_count = base.filter(__raw__=approved_raw).count()

    doc_coverage = _coverage_counts(allowed)
    top_processes = _top_processes(allowed)
    top_hardware = _top_hardware_usage(allowed)

    recent_parts = []
    for p in base.order_by("-updated_at").only("part_number", "revision", "description", "attrs", "updated_at").limit(10):
        attrs = harvest_part_attrs(p)
        rev = (attrs.get("revision") or p.revision or "").strip()
        desc = p.description or attrs.get("description") or ""
        recent_parts.append(
            {
                "part_number": p.part_number,
                "revision": rev,
                "description": desc,
            }
        )
        add_datetime_fields(recent_parts[-1], "updated_at", p.updated_at)

    payload = {
        "counts": {"total_parts": total_parts, "updated_7d": updated_7d, "approved": approved_count},
        "doc_coverage": doc_coverage,
        "data_health": {
            "missing_material": missing_material,
            "missing_process": missing_process,
            "missing_description": missing_description,
        },
        "top_processes": top_processes,
        "recent_parts": recent_parts,
        "top_hardware": top_hardware,
    }
    _set_cache(cache_key, payload)
    return jsonify(payload)
