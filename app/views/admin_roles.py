# app/views/admin_roles.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask import abort
from mongoengine.errors import DoesNotExist, ValidationError
from flask_security import roles_required
from ..models.auth import Role

bp = Blueprint("admin_roles", __name__, url_prefix="/admin/roles")

PERMISSIONS = [
  # Core admin
  "users.manage", "roles.manage", "settings.manage",

  # Items/BOM (existing)
  "items.view", "items.edit",
  "bom.view", "bom.edit",

  # Jobs / Suppliers / Customers / Orders (new granular perms)
  "jobs.view", "jobs.manage",
  "suppliers.view", "suppliers.manage",
  "customers.view", "customers.manage",
  "orders.view", "orders.manage",

  # Work orders / inventory / reports / mrp (placeholders)
  "workorders.view", "workorders.edit", "workorders.close",
  "inventory.issue", "inventory.receive",
  "mrp.run",
  "reports.view",
]

@bp.route("/")
@roles_required("admin")
def roles_list():
    roles = Role.objects().order_by("name")
    return render_template("admin/roles_list.html", roles=roles)

@bp.route("/new", methods=["GET", "POST"])
@roles_required("admin")
def roles_create():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        desc = (request.form.get("description") or "").strip()
        perms = request.form.getlist("permissions")
        if not name:
            flash("Role name is required.", "error")
            return redirect(url_for("admin_roles.roles_create"))
        if Role.objects(name=name).first():
            flash("Role already exists.", "error")
            return redirect(url_for("admin_roles.roles_create"))
        Role(name=name, description=desc, permissions=perms).save()
        flash("Role created.", "success")
        return redirect(url_for("admin_roles.roles_list"))
    return render_template("admin/roles_form.html", permissions=PERMISSIONS, role=None)

@bp.route("/<role_id>/edit", methods=["GET", "POST"])
@roles_required("admin")
def roles_edit(role_id):
    try:
        r = Role.objects.get(id=role_id)
    except (DoesNotExist, ValidationError):
        abort(404)

    if request.method == "POST":
        r.name = (request.form.get("name") or "").strip()
        r.description = (request.form.get("description") or "").strip()
        r.permissions = request.form.getlist("permissions")
        r.save()
        flash("Role updated.", "success")
        return redirect(url_for("admin_roles.roles_list"))
    return render_template("admin/roles_form.html", permissions=PERMISSIONS, role=r)
