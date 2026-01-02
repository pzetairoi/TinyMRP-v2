from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_security import roles_required
from app.services.acl import permissions_required
from mongoengine.errors import DoesNotExist, ValidationError

from app.models.customer import Customer
from app.models.auth import User

bp = Blueprint("admin_customers", __name__, url_prefix="/admin/customers")


@bp.get("/")
@permissions_required("customers.view")
def customers_list():
    cs = Customer.objects().order_by("name")
    return render_template("admin/customers_list.html", customers=cs)

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
            name=name,
            description=(request.form.get("description") or "").strip(),
            contact=(request.form.get("contact") or "").strip(),
            email=(request.form.get("email") or "").strip(),
            phone=(request.form.get("phone") or "").strip(),
            address=(request.form.get("address") or "").strip(),
        )
        user_ids = request.form.getlist("users")
        if user_ids:
            c.users = list(User.objects(id__in=user_ids))
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
        c.description = (request.form.get("description") or "").strip()
        c.contact = (request.form.get("contact") or "").strip()
        c.email = (request.form.get("email") or "").strip()
        c.phone = (request.form.get("phone") or "").strip()
        c.address = (request.form.get("address") or "").strip()
        user_ids = request.form.getlist("users")
        c.users = list(User.objects(id__in=user_ids)) if user_ids else []
        c.save()
        flash("Customer updated.", "success")
        return redirect(url_for("admin_customers.customers_list"))
    users = User.objects().order_by("email")
    return render_template("admin/customers_form.html", users=users, customer=c)
