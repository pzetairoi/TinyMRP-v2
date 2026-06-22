from __future__ import annotations

import re
from typing import Any, Iterable

from mongoengine.queryset.visitor import Q

from app.services.part_norm import clean_rev


MISSING = object()


def terms(value: Any) -> list[str]:
    return [token for token in re.split(r"\s+", str(value or "").strip().lower()) if token]


def filter_value(filters: dict[str, Any], key: str, default: Any = MISSING) -> Any:
    raw = filters.get(key)
    if not isinstance(raw, dict):
        return default
    if "value" in raw:
        return raw.get("value")
    constraints = raw.get("constraints")
    if isinstance(constraints, list):
        for item in constraints:
            if not isinstance(item, dict) or "value" not in item:
                continue
            value = item.get("value")
            if value not in (None, "") or isinstance(value, bool):
                return value
    return default


def flag_enabled(filters: dict[str, Any], key: str) -> bool:
    value = filter_value(filters, key)
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y", "on"}


def or_contains(paths: Iterable[str], term: str) -> Q:
    out = Q()
    for path in paths:
        out = out | Q(**{f"{path}__icontains": term})
    return out


def add_contains_filter(q: Q, paths: Iterable[str], raw_value: Any) -> Q:
    value = str(raw_value or "").strip()
    if not value or value.startswith("__"):
        return q
    for term in terms(value):
        q = q & or_contains(paths, term)
    return q


def pairs_query(pairs: Iterable[tuple[str, str]]) -> Q:
    out = Q()
    for pn, rev in pairs:
        pn_clean = str(pn or "").strip()
        if not pn_clean:
            continue
        out = out | Q(part_number__iexact=pn_clean, revision__iexact=clean_rev(rev))
    return out


def exclude_pairs_query(pairs: Iterable[tuple[str, str]]) -> Q:
    clauses: list[dict[str, object]] = []
    for pn, rev in pairs:
        pn_clean = str(pn or "").strip()
        if not pn_clean:
            continue
        clauses.append(
            {
                "part_number": {"$regex": f"^{re.escape(pn_clean)}$", "$options": "i"},
                "revision": {"$regex": f"^{re.escape(clean_rev(rev))}$", "$options": "i"},
            }
        )
    if not clauses:
        return Q()
    return Q(__raw__={"$nor": clauses})
