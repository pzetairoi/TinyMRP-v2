from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import current_user
from app.services.acl import permissions_required
from app.services.authorization import (
    authorised_get,
    authorise,
    has_permission,
    scope_queryset,
    uses_portal_presentation,
)
from mongoengine.errors import DoesNotExist, ValidationError
from mongoengine.queryset.visitor import Q

from app.models.customer import Customer
from app.models.job import Job
from app.models.order import Order
from app.models.auth import User
from app.models.common import Address, Contact
from app.services.biz_utils import generate_customer_code

bp = Blueprint("admin_customers", __name__, url_prefix="/admin/customers")

_CUSTOMER_FORM_FIELDS = {
    "csrf_token",
    "code",
    "name",
    "description",
    "status",
    "customer_type",
    "is_company",
    "segment",
    "contact",
    "email",
    "website",
    "phone",
    "tax_id",
    "payment_terms",
    "currency",
    "credit_limit",
    "discount_pct",
    "sales_rep",
    "industry",
    "billing_label",
    "billing_line1",
    "billing_line2",
    "billing_city",
    "billing_state",
    "billing_postal",
    "billing_country",
    "shipping_text",
    "contacts_text",
    "users",
    "tags",
}
_CUSTOMER_FINANCIAL_FORM_FIELDS = {
    "customer_type",
    "segment",
    "tax_id",
    "payment_terms",
    "currency",
    "credit_limit",
    "discount_pct",
    "sales_rep",
    "industry",
    "billing_label",
    "billing_line1",
    "billing_line2",
    "billing_city",
    "billing_state",
    "billing_postal",
    "billing_country",
}


def _require(permission):
    if not authorise(current_user, permission).allowed:
        abort(403)


def _require_customer_form_permissions():
    if set(request.form) - _CUSTOMER_FORM_FIELDS:
        abort(400)
    if set(request.form) & _CUSTOMER_FINANCIAL_FORM_FIELDS:
        _require("customers.financial.update")
    if "users" in request.form:
        _require("customers.portal_users.manage")


@bp.get("/")
@permissions_required("customers.read")
def customers_list():
    cs = scope_queryset(Customer.objects, current_user, "customers")
    q_text = (request.args.get("q") or "").strip()
    code_q = (request.args.get("code_q") or "").strip()
    name_q = (request.args.get("name_q") or "").strip()
    contact_q = (request.args.get("contact_q") or "").strip()
    email_q = (request.args.get("email_q") or "").strip()
    tags_q = (request.args.get("tags_q") or "").strip()
    if q_text and not (code_q or name_q):
        cs = cs.filter(Q(name__icontains=q_text) | Q(code__icontains=q_text))
    if code_q:
        cs = cs.filter(code__icontains=code_q)
    if name_q:
        cs = cs.filter(name__icontains=name_q)
    status = (request.args.get("status") or "").strip()
    if status:
        cs = cs.filter(status=status)
    cust_type = (request.args.get("type") or "").strip()
    if cust_type:
        _require("customers.financial.read")
        cs = cs.filter(customer_type=cust_type)
    if contact_q:
        cs = cs.filter(contact__icontains=contact_q)
    if email_q:
        cs = cs.filter(email__icontains=email_q)
    if tags_q:
        tag_tokens = [t.strip() for t in tags_q.split(",") if t.strip()]
        if tag_tokens:
            cs = cs.filter(tags__in=tag_tokens)
    cs = cs.order_by("name")
    return render_template(
        "admin/customers_list.html",
        customers=cs,
        filters={
            "code_q": code_q,
            "name_q": name_q,
            "status": status,
            "type": cust_type,
            "contact_q": contact_q,
            "email_q": email_q,
            "tags_q": tags_q,
        },
    )

@bp.post("/<cust_id>/delete")
@permissions_required("customers.archive")
def customers_delete(cust_id):
    try:
        c = authorised_get(
            Customer.objects,
            current_user,
            cust_id,
            resource_type="customers",
            permission="customers.archive",
        )
        if not c:
            flash("Customer not found.", "error")
            return redirect(url_for("admin_customers.customers_list"))
        c.status = "inactive"
        c.save()
        flash("Customer archived.", "success")
    except Exception:
        flash("Delete failed.", "error")
    return redirect(url_for("admin_customers.customers_list"))


@bp.get("/<cust_id>")
@permissions_required("customers.read")
def customers_view(cust_id):
    try:
        c = authorised_get(
            Customer.objects,
            current_user,
            cust_id,
            resource_type="customers",
        )
        if not c:
            abort(404)
    except (DoesNotExist, ValidationError):
        abort(404)
    users = (
        User.objects().order_by("email")
        if has_permission(current_user, "customers.portal_users.manage")
        else []
    )
    jobs = list(
        scope_queryset(Job.objects(customer=c), current_user, "jobs").order_by(
            "job_number"
        )
    )
    job_ids = [j.id for j in jobs]
    q_orders = Q(customer=c)
    if job_ids:
        q_orders = q_orders | Q(job__in=job_ids)
    orders = scope_queryset(Order.objects(q_orders), current_user, "orders").order_by(
        "-order_date"
    )
    return render_template(
        "admin/customers_form.html",
        users=users,
        customer=c,
        jobs=jobs,
        orders=orders,
        readonly=True,
        hide_user_links=uses_portal_presentation(
            current_user,
            "customers.read",
            resource_type="customers",
        ),
    )


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


def _parse_shipping_text(text: str):
    addresses = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        label = parts[0] if len(parts) > 0 else ""
        line1 = parts[1] if len(parts) > 1 else ""
        line2 = parts[2] if len(parts) > 2 else ""
        city = parts[3] if len(parts) > 3 else ""
        state = parts[4] if len(parts) > 4 else ""
        postal = parts[5] if len(parts) > 5 else ""
        country = parts[6] if len(parts) > 6 else ""
        default_raw = parts[7] if len(parts) > 7 else ""
        is_default = default_raw.lower() in ("1", "true", "yes", "y", "default")
        if not any([line1, line2, city, state, postal, country]):
            continue
        addresses.append(Address(
            label=label,
            line1=line1,
            line2=line2,
            city=city,
            state=state,
            postal=postal,
            country=country,
            is_default=is_default,
        ))
    return addresses


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


def _default_shipping_label(addresses):
    for addr in addresses or []:
        if addr.is_default and addr.label:
            return addr.label
    return ""


@bp.route("/new", methods=["GET","POST"])
@permissions_required("customers.update")
def customers_new():
    if request.method == "POST":
        _require_customer_form_permissions()
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Customer name is required.", "error"); return redirect(url_for("admin_customers.customers_new"))
        if Customer.objects(name=name).first():
            flash("Customer already exists.", "error"); return redirect(url_for("admin_customers.customers_new"))
        c = Customer(
            code=(request.form.get("code") or "").strip() or generate_customer_code(),
            name=name,
            contact=(request.form.get("contact") or "").strip(),
            email=(request.form.get("email") or "").strip(),
            website=(request.form.get("website") or "").strip(),
            status="active",
        )
        if "description" in request.form:
            c.description = (request.form.get("description") or "").strip()
        if "status" in request.form:
            c.status = (request.form.get("status") or "active").strip()
        if "customer_type" in request.form:
            c.customer_type = (request.form.get("customer_type") or "oem").strip()
        if "is_company" in request.form:
            c.is_company = True if request.form.get("is_company") == "on" else False
        if "segment" in request.form:
            c.segment = (request.form.get("segment") or "").strip()
        if "phone" in request.form:
            c.phone = (request.form.get("phone") or "").strip()
        if "tax_id" in request.form:
            c.tax_id = (request.form.get("tax_id") or "").strip()
        if "payment_terms" in request.form:
            c.payment_terms = (request.form.get("payment_terms") or "").strip()
        if "currency" in request.form:
            c.currency = (request.form.get("currency") or "USD").strip()
        if "credit_limit" in request.form:
            c.credit_limit = _parse_float(request.form.get("credit_limit"))
        if "discount_pct" in request.form:
            c.discount_pct = _parse_float(request.form.get("discount_pct"))
        if "sales_rep" in request.form:
            c.sales_rep = (request.form.get("sales_rep") or "").strip()
        if "industry" in request.form:
            c.industry = (request.form.get("industry") or "").strip()
        c.billing_address = _parse_address_from_form("billing")
        if "shipping_text" in request.form:
            shipping = _parse_shipping_text(request.form.get("shipping_text") or "")
            c.shipping_addresses = shipping
            c.default_shipping_label = _default_shipping_label(shipping)
        if "contacts_text" in request.form:
            contacts = _parse_contacts_text(request.form.get("contacts_text") or "")
            c.contacts = contacts
            if contacts and not (c.contact or c.email or c.phone):
                primary = _primary_from_contacts(contacts)
                if primary:
                    c.contact = primary.name or c.contact
                    c.email = primary.email or c.email
                    c.phone = primary.phone or c.phone
        user_ids = request.form.getlist("users")
        if user_ids:
            c.users = list(User.objects(id__in=user_ids))
        if "tags" in request.form:
            c.tags = [t.strip() for t in (request.form.get("tags") or "").split(",") if t.strip()]
        c.save()
        flash("Customer created.", "success")
        return redirect(url_for("admin_customers.customers_list"))
    users = (
        User.objects().order_by("email")
        if has_permission(current_user, "customers.portal_users.manage")
        else []
    )
    return render_template("admin/customers_form.html", users=users, customer=None)


@bp.route("/<cust_id>/edit", methods=["GET","POST"])
@permissions_required("customers.update")
def customers_edit(cust_id):
    try:
        c = authorised_get(
            Customer.objects,
            current_user,
            cust_id,
            resource_type="customers",
            permission="customers.update",
        )
        if not c:
            abort(404)
    except (DoesNotExist, ValidationError):
        abort(404)
    if request.method == "POST":
        _require_customer_form_permissions()
        if "name" in request.form:
            c.name = (request.form.get("name") or c.name).strip()
        if "code" in request.form:
            c.code = (request.form.get("code") or c.code or "").strip()
        if "description" in request.form:
            c.description = (request.form.get("description") or "").strip()
        if "status" in request.form:
            c.status = (request.form.get("status") or c.status or "active").strip()
        if "customer_type" in request.form:
            c.customer_type = (request.form.get("customer_type") or c.customer_type or "oem").strip()
        if "is_company" in request.form:
            c.is_company = True if request.form.get("is_company") == "on" else False
        if "segment" in request.form:
            c.segment = (request.form.get("segment") or "").strip()
        if "contact" in request.form:
            c.contact = (request.form.get("contact") or "").strip()
        if "email" in request.form:
            c.email = (request.form.get("email") or "").strip()
        if "website" in request.form:
            c.website = (request.form.get("website") or "").strip()
        if "phone" in request.form:
            c.phone = (request.form.get("phone") or "").strip()
        if "tax_id" in request.form:
            c.tax_id = (request.form.get("tax_id") or "").strip()
        if "payment_terms" in request.form:
            c.payment_terms = (request.form.get("payment_terms") or "").strip()
        if "currency" in request.form:
            c.currency = (request.form.get("currency") or "USD").strip()
        if "credit_limit" in request.form:
            c.credit_limit = _parse_float(request.form.get("credit_limit"))
        if "discount_pct" in request.form:
            c.discount_pct = _parse_float(request.form.get("discount_pct"))
        if "sales_rep" in request.form:
            c.sales_rep = (request.form.get("sales_rep") or "").strip()
        if "industry" in request.form:
            c.industry = (request.form.get("industry") or "").strip()
        if any(k in request.form for k in ("billing_label","billing_line1","billing_line2","billing_city","billing_state","billing_postal","billing_country")):
            c.billing_address = _parse_address_from_form("billing")
        if "shipping_text" in request.form:
            shipping = _parse_shipping_text(request.form.get("shipping_text") or "")
            c.shipping_addresses = shipping
            c.default_shipping_label = _default_shipping_label(shipping)
        if "contacts_text" in request.form:
            contacts = _parse_contacts_text(request.form.get("contacts_text") or "")
            c.contacts = contacts
            if contacts and not (c.contact or c.email or c.phone):
                primary = _primary_from_contacts(contacts)
                if primary:
                    c.contact = primary.name or c.contact
                    c.email = primary.email or c.email
                    c.phone = primary.phone or c.phone
        if "tags" in request.form:
            c.tags = [t.strip() for t in (request.form.get("tags") or "").split(",") if t.strip()]
        if "users" in request.form:
            user_ids = request.form.getlist("users")
            c.users = list(User.objects(id__in=user_ids)) if user_ids else []
        c.save()
        flash("Customer updated.", "success")
        return redirect(url_for("admin_customers.customers_list"))
    users = (
        User.objects().order_by("email")
        if has_permission(current_user, "customers.portal_users.manage")
        else []
    )
    shipping_text = ""
    if c.shipping_addresses:
        lines = []
        for a in c.shipping_addresses:
            line = "|".join([
                a.label or "",
                a.line1 or "",
                a.line2 or "",
                a.city or "",
                a.state or "",
                a.postal or "",
                a.country or "",
                "1" if a.is_default else "0",
            ])
            lines.append(line)
        shipping_text = "\n".join(lines)
    contacts_text = ""
    if c.contacts:
        lines = []
        for ct in c.contacts:
            line = "|".join([
                ct.name or "",
                ct.title or "",
                ct.email or "",
                ct.phone or "",
                "1" if ct.is_primary else "0",
            ])
            lines.append(line)
        contacts_text = "\n".join(lines)
    jobs = list(
        scope_queryset(Job.objects(customer=c), current_user, "jobs").order_by(
            "job_number"
        )
    )
    job_ids = [j.id for j in jobs]
    q_orders = Q(customer=c)
    if job_ids:
        q_orders = q_orders | Q(job__in=job_ids)
    orders = scope_queryset(Order.objects(q_orders), current_user, "orders").order_by(
        "-order_date"
    )
    return render_template(
        "admin/customers_form.html",
        users=users,
        customer=c,
        shipping_text=shipping_text,
        contacts_text=contacts_text,
        jobs=jobs,
        orders=orders,
    )
