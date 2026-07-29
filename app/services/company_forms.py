"""Address and contact parsing shared by the customer and supplier surfaces.

Customers and suppliers carry the same embedded address and contact shapes, so
both the HTML form handlers and the JSON APIs read them through here rather
than keeping four copies in step by hand.
"""

from __future__ import annotations

from typing import Any, List

from flask import request

from app.models.common import Address, Contact
from app.services.field_policies import filter_response_fields

ADDRESS_FIELDS = {
    "label",
    "line1",
    "line2",
    "city",
    "state",
    "postal",
    "country",
    "is_default",
}
CONTACT_FIELDS = {"name", "title", "email", "phone", "is_primary"}


def parse_float(value) -> float | None:
    try:
        return float(value)
    except Exception:
        return None


def parse_address_from_form(prefix: str) -> Address | None:
    """Build an address from ``<prefix>_*`` form fields, or None if empty."""

    parts = {
        field: (request.form.get(f"{prefix}_{field}") or "").strip()
        for field in ("label", "line1", "line2", "city", "state", "postal", "country")
    }
    if not any(value for field, value in parts.items() if field != "label"):
        return None
    return Address(**parts)


def parse_contacts_text(text: str) -> List[Contact]:
    """Parse the ``name | title | email | phone | primary`` textarea format."""

    contacts: List[Contact] = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        parts += [""] * (5 - len(parts))
        name, title, email, phone, primary = parts[:5]
        if not name:
            continue
        contacts.append(
            Contact(
                name=name,
                title=title,
                email=email,
                phone=phone,
                is_primary=primary.lower() in ("1", "true", "yes", "y", "primary"),
            )
        )
    return contacts


def primary_from_contacts(contacts):
    for contact in contacts or []:
        if contact.is_primary:
            return contact
    return contacts[0] if contacts else None


def parse_address(data) -> Address | None:
    if not data:
        return None
    return Address(
        label=data.get("label") or "",
        line1=data.get("line1") or "",
        line2=data.get("line2") or "",
        city=data.get("city") or "",
        state=data.get("state") or "",
        postal=data.get("postal") or "",
        country=data.get("country") or "",
        is_default=bool(data.get("is_default")),
    )


def parse_contacts(items) -> List[Contact]:
    out: List[Contact] = []
    for raw in items or []:
        name = (raw.get("name") or "").strip()
        if not name:
            continue
        out.append(
            Contact(
                name=name,
                title=raw.get("title") or "",
                email=raw.get("email") or "",
                phone=raw.get("phone") or "",
                is_primary=bool(raw.get("is_primary")),
            )
        )
    return out


def _embedded(kind: str, value: Any, user, boundary, fields):
    return filter_response_fields(
        kind,
        user,
        {field: getattr(value, field, None) for field in fields},
        context={"policy_context": boundary, "surface": "embedded"},
    )


def address_to_dict(value, user, boundary):
    if value is None:
        return None
    return _embedded("address", value, user, boundary, ADDRESS_FIELDS)


def contact_to_dict(value, user, boundary):
    return _embedded("contact", value, user, boundary, CONTACT_FIELDS)
