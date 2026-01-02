from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_security import roles_required
from app.services.acl import permissions_required
from mongoengine.errors import DoesNotExist, ValidationError

from app.models.supplier import Supplier
from app.models.auth import User

bp = Blueprint("admin_suppliers", __name__, url_prefix="/admin/suppliers")


@bp.get("/")
@permissions_required("suppliers.view")
def suppliers_list():
    sups = Supplier.objects().order_by("name")
    return render_template("admin/suppliers_list.html", suppliers=sups)

@bp.post("/<sup_id>/delete")
@permissions_required("suppliers.manage")
def suppliers_delete(sup_id):
    try:
        s = Supplier.objects.get(id=sup_id)
        s.delete()
        flash("Supplier deleted.", "success")
    except Exception:
        flash("Delete failed.", "error")
    return redirect(url_for("admin_suppliers.suppliers_list"))


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
            name=name,
            description=(request.form.get("description") or "").strip(),
            contact=(request.form.get("contact") or "").strip(),
            email=(request.form.get("email") or "").strip(),
            phone=(request.form.get("phone") or "").strip(),
        )
        user_ids = request.form.getlist("users")
        if user_ids:
            s.users = list(User.objects(id__in=user_ids))
        s.processes = [p.strip() for p in (request.form.get("processes") or "").split(",") if p.strip()]
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
        s.description = (request.form.get("description") or "").strip()
        s.contact = (request.form.get("contact") or "").strip()
        s.email = (request.form.get("email") or "").strip()
        s.phone = (request.form.get("phone") or "").strip()
        user_ids = request.form.getlist("users")
        s.users = list(User.objects(id__in=user_ids)) if user_ids else []
        s.processes = [p.strip() for p in (request.form.get("processes") or "").split(",") if p.strip()]
        s.save()
        flash("Supplier updated.", "success")
        return redirect(url_for("admin_suppliers.suppliers_list"))
    users = User.objects().order_by("email")
    return render_template("admin/suppliers_form.html", users=users, supplier=s)
