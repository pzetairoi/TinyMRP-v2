from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_security import roles_required
from app.services.acl import permissions_required
from mongoengine.errors import DoesNotExist, ValidationError
from mongoengine.queryset.visitor import Q

from app.models.supplier import Supplier
from app.models.job import Job
from app.models.order import Order
from app.models.auth import User
from app.models.common import Address, Contact
from app.services.biz_utils import generate_supplier_code

bp = Blueprint("admin_suppliers", __name__, url_prefix="/admin/suppliers")


@bp.get("/")
@permissions_required("suppliers.view")
def suppliers_list():
    sups = Supplier.objects()
    q_text = (request.args.get("q") or "").strip()
    code_q = (request.args.get("code_q") or "").strip()
    name_q = (request.args.get("name_q") or "").strip()
    contact_q = (request.args.get("contact_q") or "").strip()
    email_q = (request.args.get("email_q") or "").strip()
    rating_q = (request.args.get("rating") or "").strip()
    if q_text and not (code_q or name_q):
        sups = sups.filter(Q(name__icontains=q_text) | Q(code__icontains=q_text))
    if code_q:
        sups = sups.filter(code__icontains=code_q)
    if name_q:
        sups = sups.filter(name__icontains=name_q)
    status = (request.args.get("status") or "").strip()
    if status:
        sups = sups.filter(status=status)
    category = (request.args.get("category") or "").strip()
    if category:
        sups = sups.filter(categories__in=[category])
    if contact_q:
        sups = sups.filter(contact__icontains=contact_q)
    if email_q:
        sups = sups.filter(email__icontains=email_q)
    if rating_q:
        try:
            sups = sups.filter(rating=int(rating_q))
        except Exception:
            pass
    sups = sups.order_by("name")
    return render_template(
        "admin/suppliers_list.html",
        suppliers=sups,
        filters={
            "code_q": code_q,
            "name_q": name_q,
            "status": status,
            "rating": rating_q,
            "contact_q": contact_q,
            "email_q": email_q,
            "category": category,
        },
    )

@bp.post("/<sup_id>/delete")
@permissions_required("suppliers.manage")
def suppliers_delete(sup_id):
    try:
        s = Supplier.objects.get(id=sup_id)
        Job.objects(vendors=s).update(pull__vendors=s)
        Order.objects(supplier=s).update(supplier=None)
        s.delete()
        flash("Supplier deleted.", "success")
    except Exception:
        flash("Delete failed.", "error")
    return redirect(url_for("admin_suppliers.suppliers_list"))


def _parse_int(value):
    try:
        return int(value)
    except Exception:
        return None


def _parse_float(value):
    try:
        return float(value)
    except Exception:
        return None


def _parse_address_from_form(prefix: str):
    label = (request.form.get(f"{prefix}_label") or "").strip()
    line1 = (request.form.get(f"{prefix}_line1") or "").strip()
    line2 = (request.form.get(f"{prefix}_line2") or "").strip()
    city = (request.form.get(f"{prefix}_city") or "").strip()
    state = (request.form.get(f"{prefix}_state") or "").strip()
    postal = (request.form.get(f"{prefix}_postal") or "").strip()
    country = (request.form.get(f"{prefix}_country") or "").strip()
    if not any([line1, line2, city, state, postal, country]):
        return None
    return Address(
        label=label,
        line1=line1,
        line2=line2,
        city=city,
        state=state,
        postal=postal,
        country=country,
    )


def _parse_contacts_text(text: str):
    contacts = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        name = parts[0] if len(parts) > 0 else ""
        title = parts[1] if len(parts) > 1 else ""
        email = parts[2] if len(parts) > 2 else ""
        phone = parts[3] if len(parts) > 3 else ""
        primary_raw = parts[4] if len(parts) > 4 else ""
        is_primary = primary_raw.lower() in ("1", "true", "yes", "y", "primary")
        if not name:
            continue
        contacts.append(Contact(
            name=name,
            title=title,
            email=email,
            phone=phone,
            is_primary=is_primary,
        ))
    return contacts


def _primary_from_contacts(contacts):
    for c in contacts or []:
        if c.is_primary:
            return c
    return contacts[0] if contacts else None


@bp.route("/new", methods=["GET","POST"])
@permissions_required("suppliers.manage")
def suppliers_new():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Supplier name is required.", "error")
            return redirect(url_for("admin_suppliers.suppliers_new"))
        if Supplier.objects(name=name).first():
            flash("Supplier already exists.", "error")
            return redirect(url_for("admin_suppliers.suppliers_new"))
        s = Supplier(
            code=(request.form.get("code") or "").strip() or generate_supplier_code(),
            name=name,
            description=(request.form.get("description") or "").strip(),
            status=(request.form.get("status") or "active").strip(),
            rating=_parse_int(request.form.get("rating")),
            contact=(request.form.get("contact") or "").strip(),
            email=(request.form.get("email") or "").strip(),
            phone=(request.form.get("phone") or "").strip(),
            website=(request.form.get("website") or "").strip(),
            tax_id=(request.form.get("tax_id") or "").strip(),
            payment_terms=(request.form.get("payment_terms") or "").strip(),
            currency=(request.form.get("currency") or "USD").strip(),
            min_order_value=_parse_float(request.form.get("min_order_value")),
            lead_time_days=_parse_int(request.form.get("lead_time_days")),
        )
        s.address = _parse_address_from_form("address")
        s.billing_address = _parse_address_from_form("billing")
        contacts = _parse_contacts_text(request.form.get("contacts_text") or "")
        s.contacts = contacts
        if contacts and not (s.contact or s.email or s.phone):
            primary = _primary_from_contacts(contacts)
            if primary:
                s.contact = primary.name or s.contact
                s.email = primary.email or s.email
                s.phone = primary.phone or s.phone
        user_ids = request.form.getlist("users")
        if user_ids:
            s.users = list(User.objects(id__in=user_ids))
        s.processes = [p.strip() for p in (request.form.get("processes") or "").split(",") if p.strip()]
        s.categories = [c.strip() for c in (request.form.get("categories") or "").split(",") if c.strip()]
        s.tags = [t.strip() for t in (request.form.get("tags") or "").split(",") if t.strip()]
        s.save()
        flash("Supplier created.", "success")
        return redirect(url_for("admin_suppliers.suppliers_list"))
    users = User.objects().order_by("email")
    return render_template("admin/suppliers_form.html", users=users, supplier=None)


@bp.route("/<sup_id>/edit", methods=["GET","POST"])
@permissions_required("suppliers.manage")
def suppliers_edit(sup_id):
    try:
        s = Supplier.objects.get(id=sup_id)
    except (DoesNotExist, ValidationError):
        abort(404)
    if request.method == "POST":
        s.name = (request.form.get("name") or s.name).strip()
        s.code = (request.form.get("code") or s.code or "").strip()
        s.description = (request.form.get("description") or "").strip()
        s.status = (request.form.get("status") or s.status or "active").strip()
        s.rating = _parse_int(request.form.get("rating"))
        s.contact = (request.form.get("contact") or "").strip()
        s.email = (request.form.get("email") or "").strip()
        s.phone = (request.form.get("phone") or "").strip()
        s.website = (request.form.get("website") or "").strip()
        s.tax_id = (request.form.get("tax_id") or "").strip()
        s.payment_terms = (request.form.get("payment_terms") or "").strip()
        s.currency = (request.form.get("currency") or "USD").strip()
        s.min_order_value = _parse_float(request.form.get("min_order_value"))
        s.lead_time_days = _parse_int(request.form.get("lead_time_days"))
        s.address = _parse_address_from_form("address")
        s.billing_address = _parse_address_from_form("billing")
        contacts = _parse_contacts_text(request.form.get("contacts_text") or "")
        s.contacts = contacts
        if contacts and not (s.contact or s.email or s.phone):
            primary = _primary_from_contacts(contacts)
            if primary:
                s.contact = primary.name or s.contact
                s.email = primary.email or s.email
                s.phone = primary.phone or s.phone
        user_ids = request.form.getlist("users")
        s.users = list(User.objects(id__in=user_ids)) if user_ids else []
        s.processes = [p.strip() for p in (request.form.get("processes") or "").split(",") if p.strip()]
        s.categories = [c.strip() for c in (request.form.get("categories") or "").split(",") if c.strip()]
        s.tags = [t.strip() for t in (request.form.get("tags") or "").split(",") if t.strip()]
        s.save()
        flash("Supplier updated.", "success")
        return redirect(url_for("admin_suppliers.suppliers_list"))
    users = User.objects().order_by("email")
    contacts_text = ""
    if s.contacts:
        lines = []
        for c in s.contacts:
            line = "|".join([
                c.name or "",
                c.title or "",
                c.email or "",
                c.phone or "",
                "1" if c.is_primary else "0",
            ])
            lines.append(line)
        contacts_text = "\n".join(lines)
    return render_template("admin/suppliers_form.html", users=users, supplier=s, contacts_text=contacts_text)
