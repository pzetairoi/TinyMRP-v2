from __future__ import annotations

from datetime import datetime
from typing import List

from flask import Blueprint, jsonify, request
from mongoengine.queryset.visitor import Q

from app.models.job import Job, JobBOMLine, JobStage
from app.models.customer import Customer
from app.models.part import Part
from app.models.supplier import Supplier
from app.models.auth import User
from app.services.api_auth import api_auth_required
from app.services.biz_utils import generate_job_number, can_transition_job, JOB_STATUS_FLOW
from app.services.acl import apply_job_scope
from app.services.part_norm import clean_rev
from app.views.api_helpers import json_error, ensure_permissions, parse_pagination, iso, get_json

bp = Blueprint("jobs_api", __name__, url_prefix="/api/jobs")


def _parse_date(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


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


def _job_to_dict(job: Job):
    return {
        "job_number": job.job_number,
        "title": job.title,
        "description": job.description,
        "part_number": job.part_number,
        "part_revision": job.part_revision,
        "qty_ordered": float(job.qty_ordered or 0.0),
        "qty_produced": float(job.qty_produced or 0.0),
        "qty_scrapped": float(job.qty_scrapped or 0.0),
        "status": job.status,
        "priority": job.priority,
        "scheduled_start": iso(job.scheduled_start),
        "scheduled_end": iso(job.scheduled_end),
        "actual_start": iso(job.actual_start),
        "actual_end": iso(job.actual_end),
        "material_reserved": bool(job.material_reserved),
        "estimated_hours": job.estimated_hours,
        "actual_hours": job.actual_hours,
        "customer": getattr(job.customer, "name", None),
        "customer_id": str(job.customer.id) if job.customer else None,
        "order_number": job.order_number,
        "created_at": iso(job.created_at),
        "updated_at": iso(job.updated_at),
        "stages": [
            {
                "stage_id": s.stage_id,
                "name": s.name,
                "sequence": s.sequence,
                "status": s.status,
                "assigned_to": s.assigned_to,
                "department": s.department,
                "started_at": iso(s.started_at),
                "completed_at": iso(s.completed_at),
                "estimated_hours": s.estimated_hours,
                "actual_hours": s.actual_hours,
                "note": s.note,
            }
            for s in (job.stages or [])
        ],
        "bom": [{"pn": l.pn, "rev": l.rev or "", "qty": float(l.qty or 0.0)} for l in (job.bom or [])],
    }


@bp.get("")
@api_auth_required
def list_jobs():
    user, err = ensure_permissions("jobs.view")
    if err:
        return err

    page, size = parse_pagination()
    q = Job.objects(is_deleted=False)

    status = request.args.get("status")
    if status:
        q = q.filter(status__in=[s.strip() for s in status.split(",") if s.strip()])

    priority = request.args.get("priority")
    if priority:
        q = q.filter(priority__in=[s.strip() for s in priority.split(",") if s.strip()])

    customer = request.args.get("customer")
    if customer:
        cust = Customer.objects(code=customer).first() or Customer.objects(id=customer).first()
        if cust:
            q = q.filter(customer=cust)

    part_number = request.args.get("part_number")
    if part_number:
        q = q.filter(part_number=part_number)

    q_text = request.args.get("q")
    if q_text:
        q = q.filter(Q(job_number__icontains=q_text) | Q(title__icontains=q_text) | Q(description__icontains=q_text))

    date_from = _parse_date(request.args.get("from"))
    date_to = _parse_date(request.args.get("to"))
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

    q = apply_job_scope(q, user)
    total = q.count()
    items = q.order_by(sort_key).skip((page - 1) * size).limit(size)

    return jsonify({
        "ok": True,
        "items": [_job_to_dict(j) for j in items],
        "page": page,
        "page_size": size,
        "total": total,
    })


@bp.post("")
@api_auth_required
def create_job():
    user, err = ensure_permissions("jobs.manage")
    if err:
        return err
    data = get_json()

    job_number = (data.get("job_number") or "").strip() or generate_job_number()
    if Job.objects(job_number=job_number).first():
        return json_error("conflict", "Job number already exists.", 409)

    part_number = (data.get("part_number") or "").strip()
    part_revision = (data.get("part_revision") or "").strip()
    if part_number and not Part.objects(part_number=part_number).first():
        return json_error("invalid_part", "Part number not found.", 400)

    status = (data.get("status") or "draft").strip()
    if status not in ("draft", "released", "in_progress", "on_hold", "completed", "cancelled"):
        return json_error("invalid_status", "Invalid status.", 400)

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
        scheduled_start=_parse_date(data.get("scheduled_start")),
        scheduled_end=_parse_date(data.get("scheduled_end")),
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
        cust = Customer.objects(id=cust_id).first() if cust_id else Customer.objects(code=cust_code).first()
        job.customer = cust

    vendor_ids = data.get("vendor_ids") or []
    if vendor_ids:
        job.vendors = list(Supplier.objects(id__in=vendor_ids))

    participant_ids = data.get("participant_ids") or []
    if participant_ids:
        job.participants = list(User.objects(id__in=participant_ids))

    job.created_at = datetime.utcnow()
    job.updated_at = datetime.utcnow()
    job.save()
    return jsonify({"ok": True, "job": _job_to_dict(job)})


@bp.get("/<job_number>")
@api_auth_required
def get_job(job_number):
    user, err = ensure_permissions("jobs.view")
    if err:
        return err
    job = apply_job_scope(Job.objects(job_number=job_number, is_deleted=False), user).first()
    if not job:
        return json_error("not_found", "Job not found.", 404)
    return jsonify({"ok": True, "job": _job_to_dict(job)})


@bp.put("/<job_number>")
@api_auth_required
def update_job(job_number):
    user, err = ensure_permissions("jobs.manage")
    if err:
        return err
    job = Job.objects(job_number=job_number, is_deleted=False).first()
    if not job:
        return json_error("not_found", "Job not found.", 404)
    data = get_json()

    if "title" in data:
        job.title = (data.get("title") or "").strip()
    if "description" in data:
        job.description = (data.get("description") or "").strip()
    if "part_number" in data:
        pn = (data.get("part_number") or "").strip()
        if pn and not Part.objects(part_number=pn).first():
            return json_error("invalid_part", "Part number not found.", 400)
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
        job.scheduled_start = _parse_date(data.get("scheduled_start"))
    if "scheduled_end" in data:
        job.scheduled_end = _parse_date(data.get("scheduled_end"))
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
        job.customer = Customer.objects(id=cust_id).first() if cust_id else Customer.objects(code=cust_code).first()

    if "vendor_ids" in data:
        job.vendors = list(Supplier.objects(id__in=(data.get("vendor_ids") or [])))
    if "participant_ids" in data:
        job.participants = list(User.objects(id__in=(data.get("participant_ids") or [])))

    job.updated_at = datetime.utcnow()
    job.save()
    return jsonify({"ok": True, "job": _job_to_dict(job)})


@bp.delete("/<job_number>")
@api_auth_required
def delete_job(job_number):
    user, err = ensure_permissions("jobs.manage")
    if err:
        return err
    job = Job.objects(job_number=job_number, is_deleted=False).first()
    if not job:
        return json_error("not_found", "Job not found.", 404)
    if job.status in ("in_progress", "completed"):
        return json_error("invalid_state", "Job cannot be deleted in this status.", 400)
    from app.models.order import Order
    Order.objects(job=job).update(job=None, updated_at=datetime.utcnow())
    job.status = "cancelled"
    job.is_deleted = True
    job.updated_at = datetime.utcnow()
    job.save()
    return jsonify({"ok": True})


@bp.patch("/<job_number>/status")
@api_auth_required
def job_status(job_number):
    user, err = ensure_permissions("jobs.manage")
    if err:
        return err
    job = Job.objects(job_number=job_number, is_deleted=False).first()
    if not job:
        return json_error("not_found", "Job not found.", 404)
    data = get_json()
    new_status = (data.get("status") or "").strip()
    if not new_status:
        return json_error("missing_status", "Status is required.", 400)
    if not can_transition_job(job.status, new_status):
        return json_error("invalid_transition", "Status transition not allowed.", 400)
    if new_status == "released":
        if not job.part_number or not job.scheduled_start or not job.scheduled_end:
            return json_error("invalid_state", "Release requires part number and schedule.", 400)
    if new_status == "completed":
        allow = bool(data.get("allow_override"))
        if (job.qty_produced or 0.0) < (job.qty_ordered or 0.0) and not allow:
            return json_error("qty_incomplete", "Produced quantity is below ordered.", 400)
        job.actual_end = datetime.utcnow()
    if new_status == "in_progress" and not job.actual_start:
        job.actual_start = datetime.utcnow()
    job.status = new_status
    job.updated_at = datetime.utcnow()
    job.save()
    return jsonify({"ok": True, "job": _job_to_dict(job)})


@bp.post("/<job_number>/stages/<stage_id>/complete")
@api_auth_required
def job_stage_complete(job_number, stage_id):
    user, err = ensure_permissions("jobs.manage")
    if err:
        return err
    job = Job.objects(job_number=job_number, is_deleted=False).first()
    if not job:
        return json_error("not_found", "Job not found.", 404)
    for stage in job.stages or []:
        if stage.stage_id == stage_id:
            stage.status = "complete"
            stage.completed_at = datetime.utcnow()
            break
    else:
        return json_error("not_found", "Stage not found.", 404)
    job.updated_at = datetime.utcnow()
    # Auto-complete job if all stages done
    if job.stages and all((s.status == "complete") for s in job.stages):
        job.status = "completed"
        if not job.actual_end:
            job.actual_end = datetime.utcnow()
    job.save()
    return jsonify({"ok": True, "job": _job_to_dict(job)})


@bp.post("/<job_number>/materials/reserve")
@api_auth_required
def job_reserve_materials(job_number):
    user, err = ensure_permissions("jobs.manage")
    if err:
        return err
    job = Job.objects(job_number=job_number, is_deleted=False).first()
    if not job:
        return json_error("not_found", "Job not found.", 404)
    job.material_reserved = True
    job.updated_at = datetime.utcnow()
    job.save()
    return jsonify({"ok": True, "job": _job_to_dict(job)})


@bp.get("/stats")
@api_auth_required
def job_stats():
    user, err = ensure_permissions("jobs.view")
    if err:
        return err
    base = Job.objects(is_deleted=False)
    return jsonify({
        "ok": True,
        "status_counts": {s: base.filter(status=s).count() for s in JOB_STATUS_FLOW.keys()},
        "overdue": base.filter(status__in=["released", "in_progress"], scheduled_end__lt=datetime.utcnow()).count(),
        "active": base.filter(status__in=["released", "in_progress"]).count(),
    })


@bp.get("/dashboard")
@api_auth_required
def job_dashboard():
    user, err = ensure_permissions("jobs.view")
    if err:
        return err
    recent = Job.objects(is_deleted=False).order_by("-created_at").limit(10)
    upcoming = Job.objects(is_deleted=False, status__in=["released", "in_progress"]).order_by("scheduled_end").limit(10)
    return jsonify({
        "ok": True,
        "recent": [_job_to_dict(j) for j in recent],
        "upcoming": [_job_to_dict(j) for j in upcoming],
    })
