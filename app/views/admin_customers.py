from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_security import roles_required
from app.services.acl import permissions_required
from mongoengine.errors import DoesNotExist, ValidationError
from mongoengine.queryset.visitor import Q

from app.models.customer import Customer
from app.models.auth import User
from app.models.common import Address, Contact
from app.services.biz_utils import generate_customer_code

bp = Blueprint("admin_customers", __name__, url_prefix="/admin/customers")


@bp.get("/")
@permissions_required("customers.view")
def customers_list():
    cs = Customer.objects()
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
@permissions_required("customers.manage")
def customers_delete(cust_id):
    try:
        c = Customer.objects.get(id=cust_id)
        c.delete()
        flash("Customer deleted.", "success")
    except Exception:
        flash("Delete failed.", "error")
    return redirect(url_for("admin_customers.customers_list"))


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
@permissions_required("customers.manage")
def customers_new():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Customer name is required.", "error"); return redirect(url_for("admin_customers.customers_new"))
        if Customer.objects(name=name).first():
            flash("Customer already exists.", "error"); return redirect(url_for("admin_customers.customers_new"))
        c = Customer(
            code=(request.form.get("code") or "").strip() or generate_customer_code(),
            name=name,
            description=(request.form.get("description") or "").strip(),
            status=(request.form.get("status") or "active").strip(),
            customer_type=(request.form.get("customer_type") or "oem").strip(),
            is_company=True if request.form.get("is_company") == "on" else False,
            segment=(request.form.get("segment") or "").strip(),
            contact=(request.form.get("contact") or "").strip(),
            email=(request.form.get("email") or "").strip(),
            phone=(request.form.get("phone") or "").strip(),
            tax_id=(request.form.get("tax_id") or "").strip(),
            payment_terms=(request.form.get("payment_terms") or "").strip(),
            currency=(request.form.get("currency") or "USD").strip(),
            credit_limit=_parse_float(request.form.get("credit_limit")),
            discount_pct=_parse_float(request.form.get("discount_pct")),
            sales_rep=(request.form.get("sales_rep") or "").strip(),
            industry=(request.form.get("industry") or "").strip(),
        )
        c.billing_address = _parse_address_from_form("billing")
        shipping = _parse_shipping_text(request.form.get("shipping_text") or "")
        c.shipping_addresses = shipping
        c.default_shipping_label = _default_shipping_label(shipping)
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
        c.tags = [t.strip() for t in (request.form.get("tags") or "").split(",") if t.strip()]
        c.save()
        flash("Customer created.", "success")
        return redirect(url_for("admin_customers.customers_list"))
    users = User.objects().order_by("email")
    return render_template("admin/customers_form.html", users=users, customer=None)


@bp.route("/<cust_id>/edit", methods=["GET","POST"])
@permissions_required("customers.manage")
def customers_edit(cust_id):
    try:
        c = Customer.objects.get(id=cust_id)
    except (DoesNotExist, ValidationError):
        abort(404)
    if request.method == "POST":
        c.name = (request.form.get("name") or c.name).strip()
        c.code = (request.form.get("code") or c.code or "").strip()
        c.description = (request.form.get("description") or "").strip()
        c.status = (request.form.get("status") or c.status or "active").strip()
        c.customer_type = (request.form.get("customer_type") or c.customer_type or "oem").strip()
        c.is_company = True if request.form.get("is_company") == "on" else False
        c.segment = (request.form.get("segment") or "").strip()
        c.contact = (request.form.get("contact") or "").strip()
        c.email = (request.form.get("email") or "").strip()
        c.phone = (request.form.get("phone") or "").strip()
        c.tax_id = (request.form.get("tax_id") or "").strip()
        c.payment_terms = (request.form.get("payment_terms") or "").strip()
        c.currency = (request.form.get("currency") or "USD").strip()
        c.credit_limit = _parse_float(request.form.get("credit_limit"))
        c.discount_pct = _parse_float(request.form.get("discount_pct"))
        c.sales_rep = (request.form.get("sales_rep") or "").strip()
        c.industry = (request.form.get("industry") or "").strip()
        c.billing_address = _parse_address_from_form("billing")
        shipping = _parse_shipping_text(request.form.get("shipping_text") or "")
        c.shipping_addresses = shipping
        c.default_shipping_label = _default_shipping_label(shipping)
        contacts = _parse_contacts_text(request.form.get("contacts_text") or "")
        c.contacts = contacts
        if contacts and not (c.contact or c.email or c.phone):
            primary = _primary_from_contacts(contacts)
            if primary:
                c.contact = primary.name or c.contact
                c.email = primary.email or c.email
                c.phone = primary.phone or c.phone
        c.tags = [t.strip() for t in (request.form.get("tags") or "").split(",") if t.strip()]
        user_ids = request.form.getlist("users")
        c.users = list(User.objects(id__in=user_ids)) if user_ids else []
        c.save()
        flash("Customer updated.", "success")
        return redirect(url_for("admin_customers.customers_list"))
    users = User.objects().order_by("email")
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
    return render_template(
        "admin/customers_form.html",
        users=users,
        customer=c,
        shipping_text=shipping_text,
        contacts_text=contacts_text,
    )
