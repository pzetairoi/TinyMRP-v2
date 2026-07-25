from __future__ import annotations

from typing import List

from flask import Blueprint, jsonify, request
from mongoengine.queryset.visitor import Q

from app.models.job import Job, JobBOMLine, JobStage
from app.models.customer import Customer
from app.models.part import Part
from app.models.supplier import Supplier
from app.models.auth import User
from app.services.api_auth import api_auth_required
from app.services.authorization import (
    authorised_get,
    authorised_part_pairs,
    scope_queryset,
)
from app.services.biz_utils import generate_job_number, can_transition_job, JOB_STATUS_FLOW
from app.services.field_policies import (
    filter_response_fields,
    response_context,
)
from app.services.part_norm import clean_rev
from app.services.timezone_utils import utc_now
from app.views.api_helpers import (
    add_datetime_fields,
    ensure_permissions,
    get_json,
    json_error,
    parse_datetime_param,
    parse_pagination,
)

bp = Blueprint("jobs_api", __name__, url_prefix="/api/jobs")

_JOB_BASE_FIELDS = {
    "job_number",
    "title",
    "description",
    "part_number",
    "part_revision",
    "qty_ordered",
    "qty_produced",
    "qty_scrapped",
    "status",
    "priority",
    "scheduled_start",
    "scheduled_end",
    "actual_start",
    "actual_end",
    "material_reserved",
    "estimated_hours",
    "actual_hours",
    "order_number",
    "customer_id",
    "customer_code",
    "vendor_ids",
    "participant_ids",
    "stages",
    "bom",
}
_JOB_ASSIGNMENT_FIELDS = {"customer_id", "customer_code", "vendor_ids", "participant_ids"}
_STAGE_FIELDS = {
    "name",
    "sequence",
    "status",
    "assigned_to",
    "department",
    "started_at",
    "completed_at",
    "estimated_hours",
    "actual_hours",
    "note",
}
_BOM_FIELDS = {"pn", "part_number", "rev", "revision", "qty"}


def _invalid_payload_fields(data, allowed):
    unknown = sorted(set(data) - set(allowed))
    if unknown:
        return json_error(
            "invalid_fields",
            "Unsupported field(s) in request.",
            400,
            unknown,
        )
    return None


def _invalid_nested_fields(data):
    for raw in data.get("stages") or []:
        if not isinstance(raw, dict):
            return json_error("invalid_stages", "Job stages must be objects.", 400)
        invalid = _invalid_payload_fields(raw, _STAGE_FIELDS)
        if invalid:
            return invalid
    for raw in data.get("bom") or []:
        if not isinstance(raw, dict):
            return json_error("invalid_bom", "Job BOM lines must be objects.", 400)
        invalid = _invalid_payload_fields(raw, _BOM_FIELDS)
        if invalid:
            return invalid
    return None


def _scoped_job(user, job_number, permission):
    return authorised_get(
        Job.objects(is_deleted=False),
        user,
        job_number,
        resource_type="jobs",
        identifier_field="job_number",
        permission=permission,
    )


def _scoped_customer(user, permission, customer_id="", customer_code=""):
    if customer_id:
        customer = authorised_get(
            Customer.objects,
            user,
            customer_id,
            resource_type="customers",
            permission=permission,
        )
        if customer:
            return customer
    if customer_code:
        return authorised_get(
            Customer.objects,
            user,
            customer_code,
            resource_type="customers",
            identifier_field="code",
            permission=permission,
        )
    return None


def _scoped_suppliers(user, permission, supplier_ids):
    identifiers = [value for value in supplier_ids if value]
    if not identifiers:
        return []
    scoped = scope_queryset(
        Supplier.objects,
        user,
        "suppliers",
        permission=permission,
    )
    suppliers = list(scoped.filter(id__in=identifiers))
    if len({str(item.id) for item in suppliers}) != len({str(item) for item in identifiers}):
        return None
    return suppliers


def _external_user_ids() -> set[str]:
    ids: set[str] = set()
    for c in Customer.objects().only("users"):
        for u in (c.users or []):
            try:
                ids.add(str(u.id))
            except Exception:
                continue
    for s in Supplier.objects().only("users"):
        for u in (s.users or []):
            try:
                ids.add(str(u.id))
            except Exception:
                continue
    return ids

def _filter_participant_users(user_ids):
    if not user_ids:
        return []
    external_ids = _external_user_ids()
    users = list(User.objects(id__in=user_ids))
    out = []
    for u in users:
        role_names = {getattr(r, "name", "") for r in (u.roles or [])}
        if role_names & {"customer_viewer", "supplier_viewer"}:
            continue
        if str(u.id) in external_ids:
            continue
        out.append(u)
    return out


def _parse_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def _parse_stages(items) -> List[JobStage]:
    out = []
    for idx, raw in enumerate(items or []):
        name = (raw.get("name") or "").strip()
        if not name:
            continue
        stage = JobStage(
            name=name,
            sequence=int(raw.get("sequence") or (idx + 1)),
            status=raw.get("status") or "pending",
            assigned_to=raw.get("assigned_to") or "",
            department=raw.get("department") or "",
            started_at=parse_datetime_param(raw.get("started_at")),
            completed_at=parse_datetime_param(raw.get("completed_at")),
            estimated_hours=_parse_float(raw.get("estimated_hours"), None),
            actual_hours=_parse_float(raw.get("actual_hours"), None),
            note=raw.get("note") or "",
        )
        out.append(stage)
    out.sort(key=lambda s: s.sequence or 0)
    return out


def _parse_bom(items) -> List[JobBOMLine]:
    out = []
    for raw in items or []:
        pn = (raw.get("pn") or raw.get("part_number") or "").strip()
        if not pn:
            continue
        rev = clean_rev(raw.get("rev") or raw.get("revision") or "")
        qty = _parse_float(raw.get("qty"), 1.0)
        out.append(JobBOMLine(pn=pn, rev=rev, qty=qty))
    return out


def _part_references_allowed(user, pairs) -> bool:
    expected = {
        (
            str(part_number or "").strip().casefold(),
            clean_rev(revision).casefold(),
        )
        for part_number, revision in pairs
        if str(part_number or "").strip()
    }
    if not expected:
        return True
    return authorised_part_pairs(user, pairs) == expected


def _job_to_dict(job: Job, user=None):
    requested_pairs = [
        (line.pn, line.rev or "")
        for line in (job.bom or [])
        if (line.pn or "").strip()
    ]
    if (job.part_number or "").strip():
        requested_pairs.append((job.part_number, job.part_revision or ""))
    allowed_parts = (
        authorised_part_pairs(user, requested_pairs) if user is not None else None
    )

    def can_include(part_number, revision) -> bool:
        if allowed_parts is None:
            return True
        return (
            str(part_number or "").strip().casefold(),
            str(revision or "").strip().casefold(),
        ) in allowed_parts

    primary_allowed = can_include(job.part_number, job.part_revision)
    boundary = response_context("jobs", user)
    stage_payloads = []
    for stage in job.stages or []:
        stage_payload = {
            "stage_id": stage.stage_id,
            "name": stage.name,
            "sequence": stage.sequence,
            "status": stage.status,
            "assigned_to": stage.assigned_to,
            "department": stage.department,
            "estimated_hours": stage.estimated_hours,
            "actual_hours": stage.actual_hours,
            "note": stage.note,
        }
        add_datetime_fields(stage_payload, "started_at", stage.started_at)
        add_datetime_fields(stage_payload, "completed_at", stage.completed_at)
        stage_payloads.append(
            filter_response_fields(
                "job_stage",
                user,
                stage_payload,
                context={"policy_context": boundary, "surface": "embedded"},
            )
        )
    bom_payloads = [
        filter_response_fields(
            "job_bom_line",
            user,
            {"pn": line.pn, "rev": line.rev or "", "qty": float(line.qty or 0.0)},
            context={"policy_context": boundary, "surface": "embedded"},
        )
        for line in (job.bom or [])
        if can_include(line.pn, line.rev or "")
    ]
    payload = {
        "job_number": job.job_number,
        "title": job.title,
        "description": job.description,
        "part_number": job.part_number if primary_allowed else "",
        "part_revision": job.part_revision if primary_allowed else "",
        "qty_ordered": float(job.qty_ordered or 0.0),
        "qty_produced": float(job.qty_produced or 0.0),
        "qty_scrapped": float(job.qty_scrapped or 0.0),
        "status": job.status,
        "priority": job.priority,
        "material_reserved": bool(job.material_reserved),
        "estimated_hours": job.estimated_hours,
        "actual_hours": job.actual_hours,
        "customer": getattr(job.customer, "name", None),
        "customer_id": str(job.customer.id) if job.customer else None,
        "order_number": job.order_number,
        "stages": stage_payloads,
        "bom": bom_payloads,
    }
    for field_name, value in (
        ("scheduled_start", job.scheduled_start),
        ("scheduled_end", job.scheduled_end),
        ("actual_start", job.actual_start),
        ("actual_end", job.actual_end),
        ("created_at", job.created_at),
        ("updated_at", job.updated_at),
    ):
        add_datetime_fields(payload, field_name, value)
    return filter_response_fields(
        "jobs",
        user,
        payload,
        context={"policy_context": boundary},
    )


@bp.get("")
@api_auth_required
def list_jobs():
    user, err = ensure_permissions("jobs.read")
    if err:
        return err

    page, size = parse_pagination()
    q = scope_queryset(Job.objects(is_deleted=False), user, "jobs")

    status = request.args.get("status")
    if status:
        q = q.filter(status__in=[s.strip() for s in status.split(",") if s.strip()])

    priority = request.args.get("priority")
    if priority:
        q = q.filter(priority__in=[s.strip() for s in priority.split(",") if s.strip()])

    customer = request.args.get("customer")
    if customer:
        cust = _scoped_customer(user, "jobs.read", customer, customer)
        if cust:
            q = q.filter(customer=cust)
        else:
            q = q.filter(id__in=[])

    part_number = request.args.get("part_number")
    if part_number:
        q = q.filter(part_number=part_number)

    q_text = request.args.get("q")
    if q_text:
        q = q.filter(Q(job_number__icontains=q_text) | Q(title__icontains=q_text) | Q(description__icontains=q_text))

    date_from = parse_datetime_param(request.args.get("from"))
    date_to = parse_datetime_param(request.args.get("to"), end_of_day=True)
    if date_from:
        q = q.filter(scheduled_start__gte=date_from)
    if date_to:
        q = q.filter(scheduled_end__lte=date_to)

    sort = request.args.get("sort", "job_number")
    direction = request.args.get("direction", "asc").lower()
    sort_map = {
        "job_number": "job_number",
        "created_at": "created_at",
        "scheduled_start": "scheduled_start",
        "priority": "priority",
    }
    sort_key = sort_map.get(sort, "job_number")
    if direction == "desc":
        sort_key = "-" + sort_key

    total = q.count()
    items = q.order_by(sort_key).skip((page - 1) * size).limit(size)

    return jsonify({
        "ok": True,
        "items": [_job_to_dict(j, user) for j in items],
        "page": page,
        "page_size": size,
        "total": total,
    })


@bp.post("")
@api_auth_required
def create_job():
    user, err = ensure_permissions("jobs.create")
    if err:
        return err
    data = get_json()
    invalid = _invalid_payload_fields(data, _JOB_BASE_FIELDS)
    if invalid:
        return invalid
    invalid = _invalid_nested_fields(data)
    if invalid:
        return invalid
    if set(data) & _JOB_ASSIGNMENT_FIELDS:
        _, err = ensure_permissions("jobs.assign")
        if err:
            return err
    if data.get("bom"):
        _, err = ensure_permissions("jobs.bom.update")
        if err:
            return err
    if data.get("stages"):
        _, err = ensure_permissions("jobs.stages.update")
        if err:
            return err
    if data.get("material_reserved"):
        _, err = ensure_permissions("jobs.material.issue")
        if err:
            return err

    job_number = (data.get("job_number") or "").strip() or generate_job_number()
    if Job.objects(job_number=job_number).first():
        return json_error("conflict", "Job number already exists.", 409)

    part_number = (data.get("part_number") or "").strip()
    part_revision = (data.get("part_revision") or "").strip()
    requested_pairs = [(part_number, part_revision)] if part_number else []
    requested_pairs.extend(
        (
            str(raw.get("pn") or raw.get("part_number") or "").strip(),
            clean_rev(raw.get("rev") or raw.get("revision") or ""),
        )
        for raw in (data.get("bom") or [])
        if isinstance(raw, dict)
    )
    if not _part_references_allowed(user, requested_pairs):
        return json_error("invalid_part", "Part number not found.", 400)

    status = (data.get("status") or "draft").strip()
    if status not in ("draft", "released", "in_progress", "on_hold", "completed", "cancelled"):
        return json_error("invalid_status", "Invalid status.", 400)
    if status != "draft":
        required = "jobs.cancel" if status == "cancelled" else "jobs.update"
        _, err = ensure_permissions(required)
        if err:
            return err

    job = Job(
        job_number=job_number,
        title=(data.get("title") or "").strip(),
        description=(data.get("description") or "").strip(),
        part_number=part_number,
        part_revision=part_revision,
        qty_ordered=_parse_float(data.get("qty_ordered"), 0.0),
        qty_produced=_parse_float(data.get("qty_produced"), 0.0),
        qty_scrapped=_parse_float(data.get("qty_scrapped"), 0.0),
        status=status,
        priority=(data.get("priority") or "normal").strip(),
        scheduled_start=parse_datetime_param(data.get("scheduled_start")),
        scheduled_end=parse_datetime_param(data.get("scheduled_end")),
        actual_start=parse_datetime_param(data.get("actual_start")),
        actual_end=parse_datetime_param(data.get("actual_end")),
        material_reserved=bool(data.get("material_reserved")),
        estimated_hours=_parse_float(data.get("estimated_hours"), None),
        actual_hours=_parse_float(data.get("actual_hours"), None),
        order_number=(data.get("order_number") or "").strip(),
        stages=_parse_stages(data.get("stages") or []),
        bom=_parse_bom(data.get("bom") or []),
    )

    cust_id = data.get("customer_id") or ""
    cust_code = data.get("customer_code") or ""
    if cust_id or cust_code:
        cust = _scoped_customer(user, "jobs.assign", cust_id, cust_code)
        if not cust:
            return json_error("not_found", "Customer not found.", 404)
        job.customer = cust

    vendor_ids = data.get("vendor_ids") or []
    if vendor_ids:
        vendors = _scoped_suppliers(user, "jobs.assign", vendor_ids)
        if vendors is None:
            return json_error("not_found", "Supplier not found.", 404)
        job.vendors = vendors

    participant_ids = data.get("participant_ids") or []
    if participant_ids:
        participants = _filter_participant_users(participant_ids)
        if len({str(item.id) for item in participants}) != len(
            {str(item) for item in participant_ids}
        ):
            return json_error("not_found", "Participant not found.", 404)
        job.participants = participants

    job.created_at = utc_now()
    job.updated_at = utc_now()
    job.save()
    return jsonify({"ok": True, "job": _job_to_dict(job, user)})


@bp.get("/<job_number>")
@api_auth_required
def get_job(job_number):
    user, err = ensure_permissions("jobs.read")
    if err:
        return err
    job = _scoped_job(user, job_number, "jobs.read")
    if not job:
        return json_error("not_found", "Job not found.", 404)
    return jsonify({"ok": True, "job": _job_to_dict(job, user)})


@bp.put("/<job_number>")
@api_auth_required
def update_job(job_number):
    user, err = ensure_permissions("jobs.update")
    if err:
        return err
    data = get_json()
    invalid = _invalid_payload_fields(data, _JOB_BASE_FIELDS - {"job_number", "status"})
    if invalid:
        return invalid
    invalid = _invalid_nested_fields(data)
    if invalid:
        return invalid
    if set(data) & _JOB_ASSIGNMENT_FIELDS:
        _, err = ensure_permissions("jobs.assign")
        if err:
            return err
    if "bom" in data:
        _, err = ensure_permissions("jobs.bom.update")
        if err:
            return err
    if "stages" in data:
        _, err = ensure_permissions("jobs.stages.update")
        if err:
            return err
    if "material_reserved" in data:
        _, err = ensure_permissions("jobs.material.issue")
        if err:
            return err
    job = _scoped_job(user, job_number, "jobs.update")
    if not job:
        return json_error("not_found", "Job not found.", 404)

    target_part_number = (
        str(data.get("part_number") or "").strip()
        if "part_number" in data
        else str(job.part_number or "").strip()
    )
    target_part_revision = (
        clean_rev(data.get("part_revision"))
        if "part_revision" in data
        else clean_rev(job.part_revision)
    )
    requested_pairs = (
        [(target_part_number, target_part_revision)]
        if target_part_number
        else []
    )
    if "bom" in data:
        requested_pairs.extend(
            (
                str(raw.get("pn") or raw.get("part_number") or "").strip(),
                clean_rev(raw.get("rev") or raw.get("revision") or ""),
            )
            for raw in (data.get("bom") or [])
            if isinstance(raw, dict)
        )
    if not _part_references_allowed(user, requested_pairs):
        return json_error("invalid_part", "Part number not found.", 400)

    if "title" in data:
        job.title = (data.get("title") or "").strip()
    if "description" in data:
        job.description = (data.get("description") or "").strip()
    if "part_number" in data:
        pn = (data.get("part_number") or "").strip()
        job.part_number = pn
    if "part_revision" in data:
        job.part_revision = (data.get("part_revision") or "").strip()
    if "qty_ordered" in data:
        job.qty_ordered = _parse_float(data.get("qty_ordered"), 0.0)
    if "qty_produced" in data:
        job.qty_produced = _parse_float(data.get("qty_produced"), 0.0)
    if "qty_scrapped" in data:
        job.qty_scrapped = _parse_float(data.get("qty_scrapped"), 0.0)
    if "priority" in data:
        job.priority = (data.get("priority") or "normal").strip()
    if "scheduled_start" in data:
        job.scheduled_start = parse_datetime_param(data.get("scheduled_start"))
    if "scheduled_end" in data:
        job.scheduled_end = parse_datetime_param(data.get("scheduled_end"))
    if "actual_start" in data:
        job.actual_start = parse_datetime_param(data.get("actual_start"))
    if "actual_end" in data:
        job.actual_end = parse_datetime_param(data.get("actual_end"))
    if "material_reserved" in data:
        job.material_reserved = bool(data.get("material_reserved"))
    if "estimated_hours" in data:
        job.estimated_hours = _parse_float(data.get("estimated_hours"), None)
    if "actual_hours" in data:
        job.actual_hours = _parse_float(data.get("actual_hours"), None)
    if "order_number" in data:
        job.order_number = (data.get("order_number") or "").strip()
    if "stages" in data:
        job.stages = _parse_stages(data.get("stages") or [])
    if "bom" in data:
        job.bom = _parse_bom(data.get("bom") or [])

    if "customer_id" in data or "customer_code" in data:
        cust_id = data.get("customer_id") or ""
        cust_code = data.get("customer_code") or ""
        if not cust_id and not cust_code:
            job.customer = None
        else:
            customer = _scoped_customer(user, "jobs.assign", cust_id, cust_code)
            if not customer:
                return json_error("not_found", "Customer not found.", 404)
            job.customer = customer

    if "vendor_ids" in data:
        vendors = _scoped_suppliers(user, "jobs.assign", data.get("vendor_ids") or [])
        if vendors is None:
            return json_error("not_found", "Supplier not found.", 404)
        job.vendors = vendors
    if "participant_ids" in data:
        participant_ids = data.get("participant_ids") or []
        participants = _filter_participant_users(participant_ids)
        if len({str(item.id) for item in participants}) != len(
            {str(item) for item in participant_ids}
        ):
            return json_error("not_found", "Participant not found.", 404)
        job.participants = participants

    job.updated_at = utc_now()
    job.save()
    return jsonify({"ok": True, "job": _job_to_dict(job, user)})


@bp.delete("/<job_number>")
@api_auth_required
def delete_job(job_number):
    user, err = ensure_permissions("jobs.archive", "orders.update")
    if err:
        return err
    job = _scoped_job(user, job_number, "jobs.archive")
    if not job:
        return json_error("not_found", "Job not found.", 404)
    if job.status in ("in_progress", "completed"):
        return json_error("invalid_state", "Job cannot be deleted in this status.", 400)
    from app.models.order import Order
    related_orders = Order.objects(job=job)
    scoped_orders = scope_queryset(
        related_orders,
        user,
        "orders",
        permission="orders.update",
    )
    if scoped_orders.count() != related_orders.count():
        return json_error("not_found", "Related order not found.", 404)
    scoped_orders.update(job=None, updated_at=utc_now())
    job.status = "cancelled"
    job.is_deleted = True
    job.updated_at = utc_now()
    job.save()
    return jsonify({"ok": True})


@bp.patch("/<job_number>/status")
@api_auth_required
def job_status(job_number):
    data = get_json()
    invalid = _invalid_payload_fields(data, {"status", "allow_override"})
    if invalid:
        return invalid
    new_status = (data.get("status") or "").strip()
    if not new_status:
        return json_error("missing_status", "Status is required.", 400)
    permission = "jobs.cancel" if new_status == "cancelled" else "jobs.update"
    user, err = ensure_permissions(permission)
    if err:
        return err
    job = _scoped_job(user, job_number, permission)
    if not job:
        return json_error("not_found", "Job not found.", 404)
    if not can_transition_job(job.status, new_status):
        return json_error("invalid_transition", "Status transition not allowed.", 400)
    if new_status == "released":
        if not job.part_number or not job.scheduled_start or not job.scheduled_end:
            return json_error("invalid_state", "Release requires part number and schedule.", 400)
    if new_status == "completed":
        allow = bool(data.get("allow_override"))
        if (job.qty_produced or 0.0) < (job.qty_ordered or 0.0) and not allow:
            return json_error("qty_incomplete", "Produced quantity is below ordered.", 400)
        job.actual_end = utc_now()
    if new_status == "in_progress" and not job.actual_start:
        job.actual_start = utc_now()
    job.status = new_status
    job.updated_at = utc_now()
    job.save()
    return jsonify({"ok": True, "job": _job_to_dict(job, user)})


@bp.post("/<job_number>/stages/<stage_id>/complete")
@api_auth_required
def job_stage_complete(job_number, stage_id):
    user, err = ensure_permissions("jobs.stages.update")
    if err:
        return err
    job = _scoped_job(user, job_number, "jobs.stages.update")
    if not job:
        return json_error("not_found", "Job not found.", 404)
    for stage in job.stages or []:
        if stage.stage_id == stage_id:
            stage.status = "complete"
            stage.completed_at = utc_now()
            break
    else:
        return json_error("not_found", "Stage not found.", 404)
    job.updated_at = utc_now()
    # Auto-complete job if all stages done
    if job.stages and all((s.status == "complete") for s in job.stages):
        job.status = "completed"
        if not job.actual_end:
            job.actual_end = utc_now()
    job.save()
    return jsonify({"ok": True, "job": _job_to_dict(job, user)})


@bp.post("/<job_number>/materials/reserve")
@api_auth_required
def job_reserve_materials(job_number):
    user, err = ensure_permissions("jobs.material.issue")
    if err:
        return err
    job = _scoped_job(user, job_number, "jobs.material.issue")
    if not job:
        return json_error("not_found", "Job not found.", 404)
    job.material_reserved = True
    job.updated_at = utc_now()
    job.save()
    return jsonify({"ok": True, "job": _job_to_dict(job, user)})


@bp.get("/stats")
@api_auth_required
def job_stats():
    user, err = ensure_permissions("jobs.read")
    if err:
        return err
    base = scope_queryset(Job.objects(is_deleted=False), user, "jobs")
    return jsonify(
        filter_response_fields(
            "job_stats",
            user,
            {
                "ok": True,
                "status_counts": {
                    status: base.filter(status=status).count()
                    for status in JOB_STATUS_FLOW
                },
                "overdue": base.filter(
                    status__in=["released", "in_progress"],
                    scheduled_end__lt=utc_now(),
                ).count(),
                "active": base.filter(
                    status__in=["released", "in_progress"]
                ).count(),
            },
            context={"policy_context": response_context("jobs", user)},
        )
    )


@bp.get("/dashboard")
@api_auth_required
def job_dashboard():
    user, err = ensure_permissions("jobs.read")
    if err:
        return err
    base = scope_queryset(Job.objects(is_deleted=False), user, "jobs")
    recent = base.order_by("-created_at").limit(10)
    upcoming = base.filter(status__in=["released", "in_progress"]).order_by("scheduled_end").limit(10)
    return jsonify({
        "ok": True,
        "recent": [_job_to_dict(j, user) for j in recent],
        "upcoming": [_job_to_dict(j, user) for j in upcoming],
    })
