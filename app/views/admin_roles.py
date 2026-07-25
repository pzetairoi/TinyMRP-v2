# app/views/admin_roles.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask import abort
from mongoengine.errors import DoesNotExist, ValidationError
from flask_security import current_user
from app.services.authorization import require_permission
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
  "numbering.manage",
  # Tools / imports
  "tools.view",
  "import.bom",
]

@bp.route("/")
@require_permission("security.roles.read")
def roles_list():
    roles = Role.objects().order_by("name")
    return render_template("admin/roles_list.html", roles=roles)

@bp.route("/new", methods=["GET", "POST"])
@require_permission("security.roles.manage")
def roles_create():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        desc = (request.form.get("description") or "").strip()
        perms = request.form.getlist("permissions")
        if name == "admin" and not current_user.has_role("admin"):
            abort(403)
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
@require_permission("security.roles.manage")
def roles_edit(role_id):
    try:
        r = Role.objects.get(id=role_id)
    except (DoesNotExist, ValidationError):
        abort(404)

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        permissions = request.form.getlist("permissions")
        assigned_to_actor = any(
            str(role.id) == str(r.id)
            for role in (getattr(current_user, "roles", None) or [])
        )
        if assigned_to_actor and (
            name != r.name or set(permissions) - set(r.permissions or [])
        ):
            abort(403)
        if name == "admin" and r.name != "admin" and not current_user.has_role("admin"):
            abort(403)
        r.name = name
        r.description = (request.form.get("description") or "").strip()
        r.permissions = permissions
        r.save()
        flash("Role updated.", "success")
        return redirect(url_for("admin_roles.roles_list"))
    return render_template("admin/roles_form.html", permissions=PERMISSIONS, role=r)
