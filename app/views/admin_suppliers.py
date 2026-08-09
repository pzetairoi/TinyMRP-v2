from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import current_user
from app.services.acl import permissions_required
from app.services.authorization import (
    authorised_get,
    enforce_permission as _require,
    has_portal_role,
    has_permission,
    scope_queryset,
    uses_portal_presentation,
)
from mongoengine.errors import DoesNotExist, ValidationError
from mongoengine.queryset.visitor import Q

from app.models.supplier import Supplier
from app.models.job import Job
from app.models.order import Order
from app.models.auth import User
from app.services.company_forms import (
    parse_address_from_form as _parse_address_from_form,
    parse_contacts_text as _parse_contacts_text,
    parse_float as _parse_float,
    primary_from_contacts as _primary_from_contacts,
)
from app.services.biz_utils import generate_supplier_code

bp = Blueprint("admin_suppliers", __name__, url_prefix="/admin/suppliers")

_SUPPLIER_FORM_FIELDS = {
    "csrf_token",
    "code",
    "name",
    "description",
    "status",
    "rating",
    "contact",
    "email",
    "phone",
    "website",
    "tax_id",
    "payment_terms",
    "currency",
    "min_order_value",
    "lead_time_days",
    "address_label",
    "address_line1",
    "address_line2",
    "address_city",
    "address_state",
    "address_postal",
    "address_country",
    "billing_label",
    "billing_line1",
    "billing_line2",
    "billing_city",
    "billing_state",
    "billing_postal",
    "billing_country",
    "contacts_text",
    "users",
    "processes",
    "categories",
    "tags",
}
_SUPPLIER_FINANCIAL_FORM_FIELDS = {
    "rating",
    "tax_id",
    "payment_terms",
    "currency",
    "min_order_value",
    "billing_label",
    "billing_line1",
    "billing_line2",
    "billing_city",
    "billing_state",
    "billing_postal",
    "billing_country",
}


def _require_supplier_form_permissions():
    if set(request.form) - _SUPPLIER_FORM_FIELDS:
        abort(400)
    if set(request.form) & _SUPPLIER_FINANCIAL_FORM_FIELDS:
        _require("suppliers.financial.update")
    if "users" in request.form:
        _require("suppliers.portal_users.manage")


def _selected_portal_users() -> list[User]:
    user_ids = request.form.getlist("users")
    users = list(User.objects(id__in=user_ids)) if user_ids else []
    if len(users) != len(set(user_ids)) or any(
        not has_portal_role(user, "supplier") for user in users
    ):
        abort(400)
    return users


@bp.get("/")
@permissions_required("suppliers.read")
def suppliers_list():
    sups = scope_queryset(Supplier.objects, current_user, "suppliers")
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
        _require("suppliers.financial.read")
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
@permissions_required("suppliers.archive")
def suppliers_delete(sup_id):
    try:
        s = authorised_get(
            Supplier.objects,
            current_user,
            sup_id,
            resource_type="suppliers",
            permission="suppliers.archive",
        )
        if not s:
            flash("Supplier not found.", "error")
            return redirect(url_for("admin_suppliers.suppliers_list"))
        s.status = "inactive"
        s.save()
        flash("Supplier archived.", "success")
    except Exception:
        flash("Delete failed.", "error")
    return redirect(url_for("admin_suppliers.suppliers_list"))


@bp.get("/<sup_id>")
@permissions_required("suppliers.read")
def suppliers_view(sup_id):
    try:
        s = authorised_get(
            Supplier.objects,
            current_user,
            sup_id,
            resource_type="suppliers",
        )
        if not s:
            abort(404)
    except (DoesNotExist, ValidationError):
        abort(404)
    users = (
        User.objects().order_by("email")
        if has_permission(current_user, "suppliers.portal_users.manage")
        else []
    )
    orders = scope_queryset(
        Order.objects(supplier=s),
        current_user,
        "orders",
    ).order_by("-order_date")
    jobs = scope_queryset(
        Job.objects(vendors=s),
        current_user,
        "jobs",
    ).order_by("job_number")
    return render_template(
        "admin/suppliers_form.html",
        users=users,
        supplier=s,
        orders=orders,
        jobs=jobs,
        readonly=True,
        hide_user_links=uses_portal_presentation(
            current_user,
            "suppliers.read",
            resource_type="suppliers",
        ),
    )


def _parse_int(value):
    try:
        return int(value)
    except Exception:
        return None


@bp.route("/new", methods=["GET","POST"])
@permissions_required("suppliers.update")
def suppliers_new():
    if request.method == "POST":
        _require_supplier_form_permissions()
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
            contact=(request.form.get("contact") or "").strip(),
            email=(request.form.get("email") or "").strip(),
            website=(request.form.get("website") or "").strip(),
            status="active",
        )
        if "description" in request.form:
            s.description = (request.form.get("description") or "").strip()
        if "status" in request.form:
            s.status = (request.form.get("status") or "active").strip()
        if "rating" in request.form:
            s.rating = _parse_int(request.form.get("rating"))
        if "phone" in request.form:
            s.phone = (request.form.get("phone") or "").strip()
        if "tax_id" in request.form:
            s.tax_id = (request.form.get("tax_id") or "").strip()
        if "payment_terms" in request.form:
            s.payment_terms = (request.form.get("payment_terms") or "").strip()
        if "currency" in request.form:
            s.currency = (request.form.get("currency") or "USD").strip()
        if "min_order_value" in request.form:
            s.min_order_value = _parse_float(request.form.get("min_order_value"))
        if "lead_time_days" in request.form:
            s.lead_time_days = _parse_int(request.form.get("lead_time_days"))
        if any(k in request.form for k in ("address_label","address_line1","address_line2","address_city","address_state","address_postal","address_country")):
            s.address = _parse_address_from_form("address")
        if "billing_label" in request.form:
            s.billing_address = _parse_address_from_form("billing")
        if "contacts_text" in request.form:
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
            s.users = _selected_portal_users()
        if "processes" in request.form:
            s.processes = [p.strip() for p in (request.form.get("processes") or "").split(",") if p.strip()]
        if "categories" in request.form:
            s.categories = [c.strip() for c in (request.form.get("categories") or "").split(",") if c.strip()]
        if "tags" in request.form:
            s.tags = [t.strip() for t in (request.form.get("tags") or "").split(",") if t.strip()]
        s.save()
        flash("Supplier created.", "success")
        return redirect(url_for("admin_suppliers.suppliers_list"))
    users = (
        User.objects().order_by("email")
        if has_permission(current_user, "suppliers.portal_users.manage")
        else []
    )
    return render_template("admin/suppliers_form.html", users=users, supplier=None)


@bp.route("/<sup_id>/edit", methods=["GET","POST"])
@permissions_required("suppliers.update")
def suppliers_edit(sup_id):
    try:
        s = authorised_get(
            Supplier.objects,
            current_user,
            sup_id,
            resource_type="suppliers",
            permission="suppliers.update",
        )
        if not s:
            abort(404)
    except (DoesNotExist, ValidationError):
        abort(404)
    if request.method == "POST":
        _require_supplier_form_permissions()
        if "name" in request.form:
            s.name = (request.form.get("name") or s.name).strip()
        if "code" in request.form:
            s.code = (request.form.get("code") or s.code or "").strip()
        if "description" in request.form:
            s.description = (request.form.get("description") or "").strip()
        if "status" in request.form:
            s.status = (request.form.get("status") or s.status or "active").strip()
        if "rating" in request.form:
            s.rating = _parse_int(request.form.get("rating"))
        if "contact" in request.form:
            s.contact = (request.form.get("contact") or "").strip()
        if "email" in request.form:
            s.email = (request.form.get("email") or "").strip()
        if "phone" in request.form:
            s.phone = (request.form.get("phone") or "").strip()
        if "website" in request.form:
            s.website = (request.form.get("website") or "").strip()
        if "tax_id" in request.form:
            s.tax_id = (request.form.get("tax_id") or "").strip()
        if "payment_terms" in request.form:
            s.payment_terms = (request.form.get("payment_terms") or "").strip()
        if "currency" in request.form:
            s.currency = (request.form.get("currency") or "USD").strip()
        if "min_order_value" in request.form:
            s.min_order_value = _parse_float(request.form.get("min_order_value"))
        if "lead_time_days" in request.form:
            s.lead_time_days = _parse_int(request.form.get("lead_time_days"))
        if any(k in request.form for k in ("address_label","address_line1","address_line2","address_city","address_state","address_postal","address_country")):
            s.address = _parse_address_from_form("address")
        if "billing_label" in request.form:
            s.billing_address = _parse_address_from_form("billing")
        if "contacts_text" in request.form:
            contacts = _parse_contacts_text(request.form.get("contacts_text") or "")
            s.contacts = contacts
            if contacts and not (s.contact or s.email or s.phone):
                primary = _primary_from_contacts(contacts)
                if primary:
                    s.contact = primary.name or s.contact
                    s.email = primary.email or s.email
                    s.phone = primary.phone or s.phone
        if "users" in request.form:
            s.users = _selected_portal_users()
        if "processes" in request.form:
            s.processes = [p.strip() for p in (request.form.get("processes") or "").split(",") if p.strip()]
        if "categories" in request.form:
            s.categories = [c.strip() for c in (request.form.get("categories") or "").split(",") if c.strip()]
        if "tags" in request.form:
            s.tags = [t.strip() for t in (request.form.get("tags") or "").split(",") if t.strip()]
        s.save()
        flash("Supplier updated.", "success")
        return redirect(url_for("admin_suppliers.suppliers_list"))
    users = (
        User.objects().order_by("email")
        if has_permission(current_user, "suppliers.portal_users.manage")
        else []
    )
    orders = scope_queryset(
        Order.objects(supplier=s),
        current_user,
        "orders",
    ).order_by("-order_date")
    jobs = scope_queryset(
        Job.objects(vendors=s),
        current_user,
        "jobs",
    ).order_by("job_number")
    return render_template(
        "admin/suppliers_form.html",
        users=users,
        supplier=s,
        orders=orders,
        jobs=jobs,
    )
