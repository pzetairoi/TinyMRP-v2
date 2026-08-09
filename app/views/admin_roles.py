from __future__ import annotations

import re

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_security import current_user
from mongoengine.errors import DoesNotExist, ValidationError

from app.models.auth import Role, User
from app.services.app_settings import (
    permission_test_data_enabled,
    set_permission_test_data_enabled,
)
from app.services.audit import log_action
from app.services.authorization import require_permission
from app.services.permissions import (
    CANONICAL_PERMISSION_GROUPS,
)
from app.services.rls_demo import (
    reset_permission_test_environment,
    seed_permission_test_environment,
)
from app.services.session_lifecycle import revoke_role_sessions
from app.services.standard_roles import (
    STANDARD_ROLES,
    reconcile_standard_roles,
)


bp = Blueprint("admin_roles", __name__, url_prefix="/admin/roles")

GROUP_LABELS = {
    "security_and_administration": "Security & administration",
    "parts_bom_and_files": "Parts, BOM & files",
    "imports": "Imports",
    "comments_markups_and_reviews": "Comments, markups & reviews",
    "jobs": "Jobs",
    "orders": "Orders",
    "customers": "Customers",
    "suppliers": "Suppliers",
}

NOUN_LABELS = {
    "assignments": "assignments",
    "audit": "audit records",
    "bom": "BOM",
    "comments": "comments",
    "config": "configuration",
    "customers": "customers",
    "exports": "exports",
    "files": "files",
    "imports": "imports",
    "jobs": "jobs",
    "markups": "markups",
    "numbering": "part numbers",
    "orders": "orders",
    "parts": "parts",
    "reviews": "reviews",
    "roles": "roles",
    "shares": "shares",
    "storage": "storage",
    "suppliers": "suppliers",
    "system": "system",
    "tokens": "tokens",
    "users": "users",
}

ACTION_LABELS = {
    "add": "Add",
    "allocate": "Allocate",
    "approve": "Approve",
    "archive": "Archive",
    "assign": "Assign",
    "cancel": "Cancel",
    "create": "Create",
    "execute": "Execute",
    "fulfil": "Fulfil",
    "issue": "Issue",
    "manage": "Manage",
    "moderate": "Moderate",
    "preview": "Preview",
    "purge": "Purge",
    "read": "Read",
    "receive": "Receive",
    "replace": "Replace",
    "restore": "Restore",
    "revise": "Revise",
    "revoke": "Revoke",
    "rollback": "Roll back",
    "run": "Run",
    "ship": "Ship",
    "submit": "Submit",
    "update": "Update",
    "write": "Write",
}


def _permission_label(permission: str) -> str:
    pieces = permission.split(".")
    action = pieces[-1]
    subjects = pieces[:-1]
    if permission == "imports.execute_low_risk":
        return "Execute low-risk imports"
    if permission == "imports.execute_approved":
        return "Execute approved imports"
    if permission == "imports.override_approved":
        return "Override approved import data"
    if len(subjects) == 2 and subjects[0] == "security":
        subject = NOUN_LABELS.get(subjects[1], subjects[1].replace("_", " "))
    elif "financial" in subjects:
        owner = NOUN_LABELS.get(subjects[0], subjects[0].replace("_", " "))
        subject = f"{owner.rstrip('s')} financial data"
    elif subjects[:2] == ["parts", "release"]:
        subject = "part release"
    elif subjects[:2] == ["customers", "portal_users"]:
        subject = "customer portal users"
    elif subjects[:2] == ["suppliers", "portal_users"]:
        subject = "supplier portal users"
    elif len(subjects) > 1:
        subject = " ".join(
            NOUN_LABELS.get(piece, piece.replace("_", " ")) for piece in subjects
        )
    else:
        subject = NOUN_LABELS.get(
            subjects[0] if subjects else "",
            (subjects[0] if subjects else permission).replace("_", " "),
        )
    verb = ACTION_LABELS.get(action, action.replace("_", " ").title())
    return f"{verb} {subject}".strip()


def _permission_action(permission: str) -> str:
    if permission.endswith(".purge"):
        return "Destructive"
    if ".financial." in permission:
        return "Financial"
    if permission.endswith(".approve") or "approve_" in permission:
        return "Approval"
    if (
        permission.endswith(".read")
        or permission.endswith(".view")
        or permission.rsplit(".", 1)[-1].startswith("read_")
    ):
        return "Read"
    if permission.startswith(("security.", "system.")) or permission == "audit.read":
        return "Administration"
    return "Write"


def _permission_item(permission: str) -> dict[str, str]:
    return {
        "id": permission,
        "label": _permission_label(permission),
        "action": _permission_action(permission),
    }


def _canonical_catalogue() -> list[dict[str, object]]:
    return [
        {
            "slug": slug,
            "label": GROUP_LABELS.get(slug, slug.replace("_", " ").title()),
            "permissions": [_permission_item(value) for value in permissions],
        }
        for slug, permissions in CANONICAL_PERMISSION_GROUPS.items()
    ]


def _submitted_permissions() -> list[str]:
    """Return the posted permissions, de-duplicated in first-seen order.

    A checkbox offered by more than one catalogue section posts the same value
    repeatedly; that is a form artefact, not a role the operator should have to
    repair by hand.
    """

    seen: set[str] = set()
    unique: list[str] = []
    for permission in request.form.getlist("permissions"):
        if permission in seen:
            continue
        seen.add(permission)
        unique.append(permission)
    return unique


def _permission_group_summary(permissions: list[str]) -> list[dict[str, object]]:
    selected = set(permissions or [])
    summary = []
    for slug, group_permissions in CANONICAL_PERMISSION_GROUPS.items():
        count = len(selected.intersection(group_permissions))
        if count:
            summary.append(
                {
                    "label": GROUP_LABELS.get(
                        slug,
                        slug.replace("_", " ").title(),
                    ),
                    "count": count,
                }
            )
    return summary


def _standard_status_report() -> dict[str, object]:
    report = reconcile_standard_roles(dry_run=True)
    return {
        **report,
        "current_count": len(report["unchanged"]),
        "missing_count": len(report["missing"]),
        "drifted_count": len(report["drifted"]),
        "invalid_count": len(report["invalid_permissions"]),
    }


def _role_rows(
    report: dict[str, object],
    *,
    query: str = "",
    role_filter: str = "all",
) -> list[dict[str, object]]:
    drifted = {
        item["slug"]: item["fields"]
        for item in report.get("drifted", [])
    }
    invalid = {
        item["slug"]: item
        for item in report.get("invalid_permissions", [])
    }
    rows: list[dict[str, object]] = []
    existing_slugs: set[str] = set()
    for role in Role.objects().order_by("name"):
        existing_slugs.add(role.name)
        definition = STANDARD_ROLES.get(role.name)
        invalid_detail = invalid.get(role.name)
        drift_fields = drifted.get(role.name, [])
        if invalid_detail:
            status = "Invalid permissions"
            tone = "danger"
        elif definition and drift_fields:
            status = "Customised/drifted"
            tone = "warning"
        elif definition:
            status = "Current"
            tone = "active"
        else:
            status = "Custom"
            tone = "neutral"
        rows.append(
            {
                "role": role,
                "slug": role.name,
                "display_name": (
                    role.display_name
                    or (definition.display_name if definition else "")
                    or role.name.replace("_", " ").title()
                ),
                "description": role.description or (
                    definition.description if definition else ""
                ),
                "is_standard": bool(definition),
                "is_missing": False,
                "permission_count": len(role.permissions or []),
                "assigned_count": User.objects(roles=role).count(),
                "status": status,
                "status_tone": tone,
                "drift_fields": drift_fields,
                "invalid": invalid_detail,
                "permission_summary": _permission_group_summary(role.permissions or []),
                "permissions": list(role.permissions or []),
            }
        )
    for slug, definition in STANDARD_ROLES.items():
        if slug in existing_slugs:
            continue
        rows.append(
            {
                "role": None,
                "slug": slug,
                "display_name": definition.display_name,
                "description": definition.description,
                "is_standard": True,
                "is_missing": True,
                "permission_count": len(definition.permissions),
                "assigned_count": 0,
                "status": "Missing",
                "status_tone": "warning",
                "drift_fields": [],
                "invalid": None,
                "permission_summary": _permission_group_summary(
                    list(definition.permissions)
                ),
                "permissions": list(definition.permissions),
            }
        )

    query_text = query.casefold()
    if query_text:
        rows = [
            row
            for row in rows
            if query_text
            in " ".join(
                [
                    str(row["display_name"]),
                    str(row["slug"]),
                    str(row["description"]),
                    " ".join(row["permissions"]),
                ]
            ).casefold()
        ]
    filters = {
        "standard": lambda row: row["is_standard"],
        "custom": lambda row: not row["is_standard"],
        "drifted": lambda row: row["status"] == "Customised/drifted",
        "invalid": lambda row: row["status"] == "Invalid permissions",
    }
    if role_filter in filters:
        rows = [row for row in rows if filters[role_filter](row)]
    return sorted(
        rows,
        key=lambda row: (
            not bool(row["is_standard"]),
            str(row["display_name"]).casefold(),
        ),
    )


def _render_roles_page(
    *,
    permission_test_result: dict[str, object] | None = None,
    status_code: int = 200,
):
    report = _standard_status_report()
    query = (request.args.get("q") or "").strip()
    role_filter = (request.args.get("filter") or "all").strip().lower()
    if role_filter not in {"all", "standard", "custom", "drifted", "invalid"}:
        role_filter = "all"
    response = make_response(
        render_template(
            "admin/roles_list.html",
            role_rows=_role_rows(report, query=query, role_filter=role_filter),
            standard_report=report,
            query=query,
            role_filter=role_filter,
            permission_test_enabled=permission_test_data_enabled(),
            permission_test_result=permission_test_result,
        ),
        status_code,
    )
    if permission_test_result:
        response.headers["Cache-Control"] = "private, no-store"
    return response


def _role_form_context(
    role: Role | None,
    *,
    selected_permissions: list[str] | None = None,
    submitted: dict[str, str] | None = None,
    deletion_error: str = "",
) -> dict[str, object]:
    definition = STANDARD_ROLES.get(role.name) if role else None
    assigned_count = User.objects(roles=role).count() if role else 0
    drift_fields = []
    if role and definition:
        if role.display_name != definition.display_name:
            drift_fields.append("display_name")
        if role.description != definition.description:
            drift_fields.append("description")
        if tuple(role.permissions or ()) != definition.permissions:
            drift_fields.append("permissions")
    return {
        "role": role,
        "standard_definition": definition,
        "assigned_count": assigned_count,
        "deletion_error": deletion_error,
        "drift_fields": drift_fields,
        "canonical_groups": _canonical_catalogue(),
        "selected_permissions": (
            selected_permissions
            if selected_permissions is not None
            else list(role.permissions or [])
            if role
            else []
        ),
        "submitted": submitted or {},
    }


@bp.get("/")
@require_permission("security.roles.read")
def roles_list():
    return _render_roles_page()


@bp.post("/standard-roles/seed")
@require_permission("security.roles.manage")
def standard_roles_seed():
    report = reconcile_standard_roles()
    log_action(
        "admin.roles.seed_standard",
        resource_type="role",
        resource="standard_roles",
        meta={"created": list(report["created"])},
    )
    if report["created"]:
        flash(
            f"Seeded {len(report['created'])} missing standard role(s).",
            "success",
        )
    else:
        flash("All standard roles already exist. No changes were made.", "info")
    return redirect(url_for("admin_roles.roles_list"))


@bp.post("/standard-roles/restore")
@require_permission("security.roles.manage")
def standard_roles_restore():
    report = reconcile_standard_roles(apply=True)
    log_action(
        "admin.roles.restore_standard",
        resource_type="role",
        resource="standard_roles",
        meta={"updated": list(report["updated"])},
    )
    if report["updated"]:
        flash(
            f"Restored {len(report['updated'])} standard role definition(s).",
            "success",
        )
    else:
        flash("No standard role drift was found.", "info")
    return redirect(url_for("admin_roles.roles_list"))


@bp.post("/permission-test/toggle")
@require_permission("security.roles.manage")
@require_permission("security.users.manage")
@require_permission("security.assignments.manage")
@require_permission("system.maintenance")
def permission_test_toggle():
    """Turn the permission-test environment on or off without editing a file.

    Guarded by exactly the permissions that seeding already required, so this
    cannot become a cheaper route to the same capability: anyone able to flip
    the switch was already able to seed and reset the environment.
    """
    desired = str(request.form.get("enabled") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    set_permission_test_data_enabled(desired)
    log_action(
        "admin.permission_test.toggle",
        resource_type="system",
        resource="permission_test_environment",
        meta={"enabled": desired},
    )
    flash(
        "Permission test environment enabled."
        if desired
        else "Permission test environment disabled.",
        "success" if desired else "info",
    )
    return redirect(url_for("admin_roles.roles_list"))


@bp.post("/permission-test/seed")
@require_permission("security.roles.manage")
@require_permission("security.users.manage")
@require_permission("security.assignments.manage")
@require_permission("system.maintenance")
def permission_test_seed():
    if not permission_test_data_enabled():
        abort(403)
    domain = str(
        current_app.config.get("PERMISSION_TEST_DATA_DOMAIN") or "demo.com"
    )
    result = seed_permission_test_environment(domain=domain)
    log_action(
        "admin.permission_test.seed",
        resource_type="system",
        resource="permission_test_environment",
        meta={
            "users_created": int(result["counts"]["users_created"]),
            "users_updated": int(result["counts"]["users_updated"]),
            "domain": result["domain"],
        },
    )
    return _render_roles_page(permission_test_result={"seed": result})


@bp.post("/permission-test/reset")
@require_permission("security.roles.manage")
@require_permission("security.users.manage")
@require_permission("security.assignments.manage")
@require_permission("system.maintenance")
def permission_test_reset():
    if not permission_test_data_enabled():
        abort(403)
    domain = str(
        current_app.config.get("PERMISSION_TEST_DATA_DOMAIN") or "demo.com"
    )
    result = reset_permission_test_environment(domain=domain)
    log_action(
        "admin.permission_test.reset",
        resource_type="system",
        resource="permission_test_environment",
        meta={"removed": dict(result)},
    )
    return _render_roles_page(permission_test_result={"reset": result})


@bp.route("/new", methods=["GET", "POST"])
@require_permission("security.roles.manage")
def roles_create():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        display_name = (request.form.get("display_name") or "").strip()
        description = (request.form.get("description") or "").strip()
        permissions = _submitted_permissions()
        submitted = {
            "name": name,
            "display_name": display_name,
            "description": description,
        }
        if name == "administrator" and not current_user.has_role("administrator"):
            abort(403)
        if not re.fullmatch(r"[a-z0-9][a-z0-9_]*", name):
            flash(
                "Machine slug must use lowercase letters, numbers and underscores.",
                "error",
            )
            return (
                render_template(
                    "admin/roles_form.html",
                    **_role_form_context(
                        None,
                        selected_permissions=permissions,
                        submitted=submitted,
                    ),
                ),
                400,
            )
        if name in STANDARD_ROLES:
            flash(
                "Use Seed missing standard roles for catalogue role slugs.",
                "error",
            )
            return (
                render_template(
                    "admin/roles_form.html",
                    **_role_form_context(
                        None,
                        selected_permissions=permissions,
                        submitted=submitted,
                    ),
                ),
                400,
            )
        if Role.objects(name=name).first():
            flash("Role already exists.", "error")
            return redirect(url_for("admin_roles.roles_create"))
        role = Role(
            name=name,
            display_name=display_name,
            description=description,
            permissions=permissions,
        )
        try:
            role.save()
        except ValidationError as exc:
            flash(str(exc), "error")
            return (
                render_template(
                    "admin/roles_form.html",
                    **_role_form_context(
                        None,
                        selected_permissions=permissions,
                        submitted=submitted,
                    ),
                ),
                400,
            )
        log_action(
            "admin.role.create",
            resource_type="role",
            resource=role.name,
        )
        flash("Custom role created.", "success")
        return redirect(url_for("admin_roles.roles_list"))
    return render_template(
        "admin/roles_form.html",
        **_role_form_context(None),
    )


@bp.route("/<role_id>/edit", methods=["GET", "POST"])
@require_permission("security.roles.manage")
def roles_edit(role_id):
    try:
        role = Role.objects.get(id=role_id)
    except (DoesNotExist, ValidationError):
        abort(404)

    if request.method == "POST":
        definition = STANDARD_ROLES.get(role.name)
        previous_name = role.name
        previous_permissions = set(role.permissions or [])
        name = role.name if definition else (request.form.get("name") or "").strip()
        display_name = (request.form.get("display_name") or "").strip()
        description = (request.form.get("description") or "").strip()
        permissions = _submitted_permissions()
        submitted = {
            "name": name,
            "display_name": display_name,
            "description": description,
        }
        assigned_to_actor = any(
            str(assigned.id) == str(role.id)
            for assigned in (getattr(current_user, "roles", None) or [])
        )
        if assigned_to_actor and (
            name != role.name
            or set(permissions) - set(role.permissions or [])
        ):
            abort(403)
        if (
            name == "administrator"
            and role.name != "administrator"
            and not current_user.has_role("administrator")
        ):
            abort(403)
        if not definition and not re.fullmatch(r"[a-z0-9][a-z0-9_]*", name):
            flash(
                "Machine slug must use lowercase letters, numbers and underscores.",
                "error",
            )
            return (
                render_template(
                    "admin/roles_form.html",
                    **_role_form_context(
                        role,
                        selected_permissions=permissions,
                        submitted=submitted,
                    ),
                ),
                400,
            )
        role.name = name
        role.display_name = display_name
        role.description = description
        role.permissions = permissions
        try:
            role.save()
        except ValidationError as exc:
            flash(str(exc), "error")
            return (
                render_template(
                    "admin/roles_form.html",
                    **_role_form_context(
                        role,
                        selected_permissions=permissions,
                        submitted=submitted,
                    ),
                ),
                400,
            )
        security_changed = (
            role.name != previous_name
            or set(role.permissions or []) != previous_permissions
        )
        revoked_sessions = (
            revoke_role_sessions(role, reason="role_definition_changed")
            if security_changed
            else 0
        )
        log_action(
            "admin.role.update",
            resource_type="role",
            resource=role.name,
            meta={"revoked_browser_sessions": revoked_sessions},
        )
        message = "Role updated."
        if revoked_sessions:
            message += f" Signed out {revoked_sessions} assigned user(s)."
        flash(message, "success")
        return redirect(url_for("admin_roles.roles_list"))
    return render_template(
        "admin/roles_form.html",
        **_role_form_context(role),
    )


@bp.post("/<role_id>/delete")
@require_permission("security.roles.manage")
def roles_delete(role_id):
    try:
        role = Role.objects.get(id=role_id)
    except (DoesNotExist, ValidationError):
        abort(404)

    # Standard roles are protected because deleting one breaks the canonical
    # model. A role named "admin" used to be protected too, from when that name
    # bypassed the permission system; it carries no special meaning now, so it
    # is deletable like any other custom role.
    if role.name in STANDARD_ROLES:
        abort(403)

    assigned_count = User.objects(roles=role).count()
    if assigned_count:
        message = (
            f"This role is still assigned to {assigned_count} user(s). "
            "Review and remove those assignments before deleting the role."
        )
        log_action(
            "admin.role.delete_blocked",
            resource_type="role",
            resource=role.name,
            meta={"assigned_users": assigned_count},
        )
        return (
            render_template(
                "admin/roles_form.html",
                **_role_form_context(role, deletion_error=message),
            ),
            409,
        )

    role_name = role.name
    role.delete()
    log_action(
        "admin.role.delete",
        resource_type="role",
        resource=role_name,
    )
    flash("Custom role deleted.", "success")
    return redirect(url_for("admin_roles.roles_list"))


@bp.post("/permission-test/impersonate")
@require_permission("security.users.manage")
@require_permission("security.assignments.manage")
def permission_test_impersonate():
    """Act as a seeded permission-test user without logging out.

    Every guard lives in the service: the posted email is only honoured when it
    resolves to an active ``permtest.*`` account on the configured domain and
    the instance enables permission-test data.
    """
    from flask_security.utils import login_user

    from app.services import impersonation

    target = impersonation.resolve_target(current_user, request.form.get("email"))
    if target is None:
        abort(403)

    actor_email = str(getattr(current_user, "email", "") or "")
    log_action(
        "admin.permission_test.impersonate",
        resource_type="user",
        resource=str(target.email),
        meta={"impersonator": actor_email},
    )
    impersonation.begin(current_user)
    login_user(target)
    return redirect(url_for("main.app_home"))


@bp.post("/permission-test/impersonate/stop")
def permission_test_impersonate_stop():
    """Return to the administrator who started the swap.

    Deliberately unguarded by permission: the impersonated session holds the
    test user's (lower) permissions, so requiring admin rights here would trap
    the operator in the swapped identity.
    """
    from flask_security.utils import login_user

    from app.services import impersonation

    original = impersonation.real_user()
    impersonation.end()
    if original is None:
        abort(403)
    log_action(
        "admin.permission_test.impersonate.stop",
        resource_type="user",
        resource=str(getattr(current_user, "email", "") or ""),
        meta={"impersonator": str(original.email or "")},
    )
    login_user(original)
    return redirect(url_for("admin_roles.roles_list"))
