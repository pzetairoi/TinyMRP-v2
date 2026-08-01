import secrets
import click
import os
import itertools
import re
import csv
import datetime as dt
from flask.cli import with_appcontext
from flask_security import hash_password

from .models.auth import User, Role
from .models.part import Part
from .models.bom import BOMLink

from flask import current_app

from app.services.attrs import harvest_part_attrs, merge_save_part_attrs
from app.services.part_annotations import bulk_sync_annotation_search_fields
from app.services.part_materialized import rebuild_part_materialized_fields
from app.services.password_policy import validate_admin_password
from app.services.timezone_utils import utc_iso, utc_now




@click.group()
def user():
    """User management commands"""


@click.group()
def role():
    """Role management commands"""


@click.group()
def share():
    """Public-share maintenance commands."""


@share.command("migrate-legacy")
@click.option(
    "--apply",
    is_flag=True,
    help="Backfill only unambiguous legacy share revisions.",
)
@with_appcontext
def migrate_legacy_shares(apply):
    """Report legacy shares without exposing bearer-token material."""

    import json

    from app.services.part_shares import migrate_legacy_part_shares

    click.echo(
        json.dumps(
            migrate_legacy_part_shares(apply=apply),
            indent=2,
            sort_keys=True,
        )
    )


@role.command("list")
@with_appcontext
def list_roles():
    rows = []
    for r in Role.objects.order_by("name"):
        perms = list(r.permissions or [])
        rows.append({
            "name": r.name,
            "permissions_count": len(perms),
        })
    click.echo(rows)

def _get_user(email: str):
    return User.objects(email=str(email or "").strip().lower()).first()

@user.command("create")
@click.option("--email", prompt=True)
@click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
@with_appcontext
def create_user(email, password):
    email = str(email or "").strip().lower()
    if User.objects(email=email).first():
        click.echo("User exists")
        return
    errors = validate_admin_password(password, email=email)
    if errors:
        for error in errors:
            click.echo(error)
        raise SystemExit(1)
    u = User(
        email=email,
        password=hash_password(password),
        fs_uniquifier=secrets.token_hex(16),
        password_changed_at=utc_now(),
        updated_at=utc_now(),
    )
    u.save()
    click.echo("Created user")

@user.command("list")
@with_appcontext
def list_users():
    rows = []
    for u in User.objects.order_by("email"):
        rows.append({
            "email": u.email,
            "active": bool(u.active),
            "roles": [r.name for r in (u.roles or [])],
        })
    click.echo(rows)
    
        
@user.command("grant-admin")
@click.option("--email", prompt=True)
@with_appcontext
def grant_admin(email):
    u = _get_user(email)
    if not u:
        click.echo("User not found")
        raise SystemExit(1)
    r = Role.objects(name="admin").first() or Role(name="admin").save()
    if r not in u.roles:
        u.roles.append(r); u.save()
    click.echo("Granted admin role")    

@user.command("set-password")
@click.option("--email", prompt=True)
@click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
@with_appcontext
def set_password(email, password):
    u = _get_user(email)
    if not u:
        click.echo("User not found")
        raise SystemExit(1)
    errors = validate_admin_password(password, email=u.email or email)
    if errors:
        for error in errors:
            click.echo(error)
        raise SystemExit(1)
    u.password = hash_password(password)
    u.password_changed_at = utc_now()
    u.updated_at = utc_now()
    u.save()
    click.echo("Password updated")

@user.command("grant-role")
@click.option("--email", prompt=True)
@click.option("--role", "role_name", prompt=True)
@with_appcontext
def grant_role(email, role_name):
    u = _get_user(email)
    if not u:
        click.echo("User not found")
        raise SystemExit(1)
    r = Role.objects(name=role_name).first()
    if not r:
        click.echo("Role not found")
        raise SystemExit(1)
    if r not in u.roles:
        u.roles.append(r)
        u.save()
    click.echo("Role granted")

@user.command("revoke-role")
@click.option("--email", prompt=True)
@click.option("--role", "role_name", prompt=True)
@with_appcontext
def revoke_role(email, role_name):
    u = _get_user(email)
    if not u:
        click.echo("User not found")
        raise SystemExit(1)
    r = Role.objects(name=role_name).first()
    if not r:
        click.echo("Role not found")
        raise SystemExit(1)
    if r in (u.roles or []):
        u.roles = [x for x in (u.roles or []) if x != r]
        u.save()
    click.echo("Role revoked")
    
@user.command("seed-roles")
@click.option(
    "--dry-run",
    is_flag=True,
    help="Report missing and drifted standard roles without writing changes.",
)
@click.option(
    "--apply",
    is_flag=True,
    help="Replace drifted standard role fields with their canonical definitions.",
)
@with_appcontext
def seed_roles(dry_run, apply):
    import json

    from app.services.standard_roles import reconcile_standard_roles

    if dry_run and apply:
        raise click.UsageError("--dry-run and --apply cannot be used together")
    report = reconcile_standard_roles(dry_run=dry_run, apply=apply)
    click.echo(json.dumps(report, indent=2, sort_keys=True))

@user.command("bootstrap-admin")
@click.option("--email", prompt=True)
@click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
@with_appcontext
def bootstrap_admin(email, password):
    email = str(email or "").strip().lower()
    from app.services.standard_roles import reconcile_standard_roles

    reconcile_standard_roles()
    u = _get_user(email)
    if not u:
        u = User(email=email.lower(), fs_uniquifier=secrets.token_hex(16))
    errors = validate_admin_password(password, email=email)
    if errors:
        for error in errors:
            click.echo(error)
        raise SystemExit(1)
    u.password = hash_password(password)
    u.active = True
    u.password_changed_at = utc_now()
    u.updated_at = utc_now()
    r = Role.objects(name="admin").first() or Role(name="admin").save()
    if r not in (u.roles or []):
        u.roles.append(r)
    u.save()
    click.echo("Admin user ready")

@user.command("seed-combos")
@click.option("--prefix", default="test", show_default=True, help="Email prefix for generated users")
@click.option("--domain", default="test.com", show_default=True, help="Email domain for generated users")
@click.option("--password", default=None, help="Optional fixed password for all users")
@click.option("--max-combos", type=int, default=0, show_default=True, help="0 means no limit")
@click.option("--attach-biz/--no-attach-biz", default=True, show_default=True, help="Attach users to suppliers/customers/jobs if present")
@with_appcontext
def seed_user_combos(prefix, domain, password, max_combos, attach_biz):
    """Create users for every role combination (powerset)."""
    roles = [r for r in Role.objects.order_by("name") if (r.name or "").lower() != "admin"]
    if not roles:
        click.echo("No non-admin roles found; run `flask user seed-roles` first.")
        return

    combos = list(itertools.chain.from_iterable(
        itertools.combinations(roles, r) for r in range(len(roles) + 1)
    ))
    if max_combos and len(combos) > max_combos:
        combos = combos[:max_combos]
        click.echo(f"Truncated role combinations to {max_combos} (use --max-combos 0 for all).")

    out_path = None
    writer = None
    if password is None:
        os.makedirs(current_app.instance_path, exist_ok=True)
        stamp = utc_now().strftime("%Y%m%d_%H%M%S")
        out_path = os.path.join(current_app.instance_path, f"test_users_{stamp}.csv")
        out_file = open(out_path, "w", newline="", encoding="utf-8")
        writer = csv.writer(out_file)
        writer.writerow(["email", "password", "roles"])

    created = 0
    updated = 0
    seeded_users = []
    for idx, combo in enumerate(combos, start=1):
        role_names = [r.name for r in combo]
        label = "none" if not role_names else "-".join(role_names)
        label = re.sub(r"[^a-z0-9-]+", "", label.lower())
        if len(label) > 32 or not label:
            label = f"set{idx:03d}"
        email = f"{prefix}.{label}@{domain}".lower()

        u = User.objects(email=email).first()
        if not u:
            u = User(email=email, fs_uniquifier=secrets.token_hex(16))
            created += 1
            set_password = True
        else:
            updated += 1
            set_password = bool(password)

        if password is None:
            raw = secrets.token_urlsafe(12)
        else:
            raw = password

        if set_password:
            u.password = hash_password(raw)

        u.roles = list(combo)
        u.active = True
        u.save()
        seeded_users.append(u)

        if writer and set_password:
            writer.writerow([email, raw, ",".join(role_names) or "none"])

    if writer:
        writer.writerow([])
        writer.writerow(["note", "Delete this file after use."])
        writer.writerow(["generated_at", utc_iso(utc_now()) or ""])
        writer.writerow(["total_users", len(seeded_users)])
        writer = None
        out_file.close()

    if attach_biz and seeded_users:
        try:
            from app.models.supplier import Supplier
            from app.models.customer import Customer
            from app.models.job import Job
            suppliers = list(Supplier.objects())
            customers = list(Customer.objects())
            jobs = list(Job.objects())

            if suppliers:
                for i, u in enumerate(seeded_users):
                    s = suppliers[i % len(suppliers)]
                    if u not in (s.users or []):
                        s.users.append(u)
                for s in suppliers:
                    s.save()

            if customers:
                for i, u in enumerate(seeded_users):
                    c = customers[i % len(customers)]
                    if u not in (c.users or []):
                        c.users.append(u)
                for c in customers:
                    c.save()

            if jobs:
                for i, u in enumerate(seeded_users):
                    j = jobs[i % len(jobs)]
                    if u not in (j.participants or []):
                        j.participants.append(u)
                for j in jobs:
                    j.save()

        except Exception as exc:
            click.echo(f"Attach to business entities failed: {exc}")

    click.echo({
        "roles": [r.name for r in roles],
        "created": created,
        "updated": updated,
        "users_total": len(seeded_users),
        "password_mode": "random" if password is None else "fixed",
        "password_csv": out_path or "",
    })
@user.command("seed-parts")
@with_appcontext
def seed_parts():
    if Part.objects.count():
        click.echo("Parts already exist"); return
    samples = [
        dict(part_number="ASM-1001", revision="A", description="Widget Assembly", category="Assembly", uom="EA", status="active"),
        dict(part_number="CMP-2002", revision="B", description="Gizmo Component", category="Component", uom="EA", manufacturer="Acme", mfr_part="AC-2002", status="active"),
        dict(part_number="MAT-3003", revision="A", description="Aluminium Sheet 2mm", category="Material", uom="SHT", status="active"),
        dict(part_number="CMP-2004", revision="C", description="Bearing 6202ZZ", category="Component", uom="EA", manufacturer="SKF", mfr_part="6202ZZ", status="obsolete"),
    ]
    for s in samples: Part(**s).save()
    click.echo("Seeded sample parts")

@user.command("seed-bom")
@with_appcontext
def seed_bom():
    if not Part.objects(part_number="ASM-1001"):
        click.echo("Run seed-parts first"); return
    if BOMLink.objects(parent_pn="ASM-1001"):
        click.echo("BOM already seeded"); return
    BOMLink(parent_pn="ASM-1001", child_pn="CMP-2002", qty=2).save()
    BOMLink(parent_pn="ASM-1001", child_pn="MAT-3003", qty=4, uom="SHT").save()
    BOMLink(parent_pn="CMP-2002", child_pn="CMP-2004", qty=1).save()
    click.echo("Seeded demo BOM links")









##########################seed generation commands##########################
# app/cli.py (append at bottom, below existing imports / groups)
import random, string, datetime as dt
from mongoengine.errors import NotUniqueError
from flask.cli import with_appcontext
import click

from .models.part import Part
from .models.bom import BOMLink

def _now():
    return utc_now()

def _pn(prefix: str, n: int) -> str:
    return f"{prefix}-{n:04d}"

def _choose_many(pool, kmin, kmax):
    k = random.randint(kmin, kmax)
    return random.sample(pool, min(k, len(pool)))

def _upsert_part(pn, **kw):
    p = Part.objects(part_number=pn).first()
    if not p:
        p = Part(part_number=pn)
    # sane defaults
    p.revision    = kw.get("revision", "A")
    p.description = kw.get("description", "")
    p.category    = kw.get("category", "")
    p.uom         = kw.get("uom", "EA")
    p.manufacturer= kw.get("manufacturer", "")
    p.mfr_part    = kw.get("mfr_part", "")
    p.status      = kw.get("status", "active")
    attrs         = kw.get("attrs") or {}
    p.attrs       = {**(p.attrs or {}), **attrs}
    p.updated_at  = _now()
    p.save()
    return p

def _link(parent_pn, child_pn, qty=1.0, uom="EA", alt_group="", phantom=False, scrap_rate=0.0,
          eff_from=None, eff_to=None):
    # Avoid exact duplicate link
    existing = BOMLink.objects(parent_pn=parent_pn, child_pn=child_pn).first()
    if existing:
        # update minor fields if needed
        existing.qty = qty
        existing.uom = uom
        if alt_group: existing.alt_group = alt_group
        existing.phantom = phantom
        existing.scrap_rate = scrap_rate
        existing.effective_from = eff_from
        existing.effective_to = eff_to
        existing.updated_at = _now()
        existing.save()
        return existing
    return BOMLink(
        parent_pn=parent_pn, child_pn=child_pn, qty=qty, uom=uom,
        alt_group=alt_group, phantom=phantom, scrap_rate=scrap_rate,
        effective_from=eff_from, effective_to=eff_to, updated_at=_now()
    ).save()

@click.group()
def data():
    """Data generation commands (demo parts & BOM)"""

@data.command("clear-demo")
@click.option("--tag", default="demo", help="Seed tag to clear (attrs.seed)")
@with_appcontext
def clear_demo(tag):
    """Delete all parts and BOM links that were seeded with a given tag."""
    q = {"attrs__seed": tag}
    parts = Part.objects(**q).only("part_number")
    pns = [p.part_number for p in parts]
    deleted_parts = parts.delete()
    deleted_links = 0
    if pns:
        deleted_links = BOMLink.objects(parent_pn__in=pns).delete() + BOMLink.objects(child_pn__in=pns).delete()
    click.echo(f"Deleted parts={deleted_parts}, bom_links={deleted_links} for seed tag '{tag}'")

@data.command("seed-demo")
@click.option("--scale", type=click.Choice(["small","medium","large"], case_sensitive=False), default="medium")
@click.option("--tag", default="demo", help="Seed tag to mark generated docs (attrs.seed)")
@click.option("--random-seed", type=int, default=42, help="Deterministic RNG seed")
@with_appcontext
def seed_demo(scale, tag, random_seed):
    """
    Generate a multi-level BOM dataset with overlaps/alternates/phantoms.
    Re-run with the same random-seed for reproducible data.
    """
    random.seed(random_seed)

    cfg = {
        "small":  dict(n_common=10, n_comp=120, n_sub=30, n_top=6, depth=3, fan_min=2, fan_max=6),
        "medium": dict(n_common=20, n_comp=300, n_sub=80, n_top=12, depth=4, fan_min=3, fan_max=8),
        "large":  dict(n_common=40, n_comp=800, n_sub=200, n_top=25, depth=4, fan_min=4, fan_max=10),
    }[scale]

    # Vocab
    CATEGORIES = ["Component","Material","Fastener","PCB","IC","Resistor","Capacitor","Assembly","Subassembly"]
    UOMS = ["EA","EA","EA","EA","SHT","M","KG"]  # weighted to EA
    MFRS = ["ACME","SKF","Vishay","TI","NXP","Infineon","ST","Omron","Panasonic","Murata"]
    STATUSES = ["active"]*9 + ["obsolete"]  # 10% obsolete

    # ---------- 1) Parts ----------
    click.echo(f"Seeding parts for tag='{tag}' …")
    created = 0
    # Common components (heavily reused)
    common_pns = []
    for i in range(1, cfg["n_common"]+1):
        pn = _pn("CMP", 1000+i)
        common_pns.append(pn)
        _upsert_part(
            pn,
            description=f"Common Component {i}",
            category=random.choice(["Component","Fastener","Resistor","Capacitor"]),
            uom=random.choice(UOMS),
            manufacturer=random.choice(MFRS),
            mfr_part=f"{random.choice(MFRS)}-{1000+i}",
            status=random.choice(STATUSES),
            attrs={"seed": tag}
        ); created += 1

    # Regular components/materials
    comp_pns = []
    for i in range(1, cfg["n_comp"]+1):
        prefix = random.choice(["CMP","MAT","CMP","CMP","PCB","IC"])
        pn = _pn(prefix, 2000+i)
        comp_pns.append(pn)
        cat = random.choice(["Component","Material","PCB","IC","Resistor","Capacitor","Fastener"])
        _upsert_part(
            pn,
            description=f"{cat} {i}",
            category=cat,
            uom=random.choice(UOMS),
            manufacturer=random.choice(MFRS) if cat in ["IC","PCB","Resistor","Capacitor","Component"] else "",
            mfr_part=f"{random.choice(MFRS)}-{2000+i}" if cat in ["IC","PCB","Resistor","Capacitor","Component"] else "",
            status=random.choice(STATUSES),
            attrs={"seed": tag}
        ); created += 1

    # Subassemblies (no children yet)
    sub_pns = []
    for i in range(1, cfg["n_sub"]+1):
        pn = _pn("SUB", 3000+i)
        sub_pns.append(pn)
        _upsert_part(
            pn,
            description=f"Subassembly {i}",
            category="Subassembly",
            uom="EA",
            status="active",
            attrs={"seed": tag}
        ); created += 1

    # Top-level assemblies
    top_pns = []
    for i in range(1, cfg["n_top"]+1):
        pn = _pn("ASM", 4000+i)
        top_pns.append(pn)
        _upsert_part(
            pn,
            description=f"Top Assembly {i}",
            category="Assembly",
            uom="EA",
            status="active",
            attrs={"seed": tag}
        ); created += 1

    click.echo(f"Parts created/updated: {created}")

    # ---------- 2) BOM Links ----------
    click.echo("Seeding BOM links …")

    def make_children(parent, level, max_level):
        """Attach children to parent: mix of components, common components, maybe subassemblies, alternates, phantom."""
        # Base fanout
        kids = []

        # Always add some common components for overlap
        common_pick = _choose_many(common_pns, 1, min(3, len(common_pns)))
        kids.extend([(c, random.randint(1,5), "EA", "") for c in common_pick])

        # Mix in regular parts
        pool_parts = comp_pns[:]
        # Occasionally attach a subassembly if we are not too deep
        if level < max_level-1 and sub_pns:
            pool_parts = pool_parts + random.sample(sub_pns, min( max(1, len(sub_pns)//5), len(sub_pns)))

        # random unique picks
        others = _choose_many(pool_parts, cfg["fan_min"], cfg["fan_max"])
        for ch in others:
            qty = random.choice([1,1,2,3,4,5])
            uom = "EA" if ch.startswith(("CMP","SUB","ASM","IC","PCB")) else random.choice(UOMS)
            kids.append((ch, qty, uom, ""))

        # Some alternates: pick 1–2 groups of 2–3 items and mark same alt_group
        if len(others) >= 4:
            group_count = random.choice([0,1,1,2])
            for g in range(group_count):
                group_id = "ALT-" + ''.join(random.choices(string.ascii_uppercase+string.digits, k=4))
                alt_members = random.sample(others, k=min(3, len(others)))
                for ch in alt_members:
                    idx = next(i for i,t in enumerate(kids) if t[0]==ch)
                    kids[idx] = (kids[idx][0], kids[idx][1], kids[idx][2], group_id)

        # Occasionally insert a phantom subassembly layer
        if level < max_level-1 and random.random() < 0.25:
            ph = _pn("SUB", 8000+random.randint(1, 9999))
            _upsert_part(ph, description="Phantom Subassembly", category="Subassembly", attrs={"seed": tag})
            _link(parent, ph, qty=1, uom="EA", phantom=True)
            # Phantom carries some of the kids
            carry = random.sample(kids, k=min(len(kids)//2 or 1, len(kids)))
            for ch, qty, uom, alt_group in carry:
                _link(ph, ch, qty=qty, uom=uom, alt_group=alt_group)
            # and keep remaining directly under parent
            for ch, qty, uom, alt_group in [k for k in kids if k not in carry]:
                _link(parent, ch, qty=qty, uom=uom, alt_group=alt_group)
        else:
            for ch, qty, uom, alt_group in kids:
                _link(parent, ch, qty=qty, uom=uom, alt_group=alt_group)

    # Build from subassemblies up (so SUB can also have SUB children)
    # Level 1: subassemblies get components
    for p in sub_pns:
        make_children(p, level=1, max_level=cfg["depth"])

    # Level 2: subassemblies may include other subassemblies to increase depth/cross-links
    for p in random.sample(sub_pns, k=max(1, len(sub_pns)//2)):
        # attach a few other SUBs as children to deepen the tree
        attach = random.sample([x for x in sub_pns if x != p], k=min(3, len(sub_pns)-1))
        for ch in attach:
            _link(p, ch, qty=random.randint(1,3))
        make_children(p, level=2, max_level=cfg["depth"])

    # Top-level: assemblies reference subassemblies + components
    for a in top_pns:
        # ensure some SUBs
        subs = _choose_many(sub_pns, 2, min(6, len(sub_pns)))
        for s in subs:
            _link(a, s, qty=random.randint(1,3))
        make_children(a, level=3, max_level=cfg["depth"])

    # Some effective date toys: mark a few links as expired or future-dated
    all_links = list(BOMLink.objects())
    for l in random.sample(all_links, k=min( max(1, len(all_links)//20), len(all_links) )):
        r = random.random()
        if r < 0.5:
            l.effective_to = _now() - dt.timedelta(days=random.randint(30, 400))
        else:
            l.effective_from = _now() + dt.timedelta(days=random.randint(30, 180))
        l.save()

    # Stats
    n_parts = Part.objects(attrs__seed=tag).count()
    n_links = BOMLink.objects().count()
    # Heavily used components (where-used stress)
    counter = {}
    for l in BOMLink.objects().only("child_pn"):
        counter[l.child_pn] = counter.get(l.child_pn, 0) + 1
    hot = sorted(counter.items(), key=lambda kv: kv[1], reverse=True)[:10]

    click.echo(f"Done. Seed tag='{tag}' "
               f"parts={n_parts}, bom_links={n_links}, common/top where-used: {hot[:5]}")
    
    
###########################################
## Import utilities for ZIP uploads

@click.group()
def importcmd():
    """Import utilities"""

@importcmd.command("zip")
@click.option("--file", "path", required=True, help="Path to ZIP file")
@click.option("--tag", default="upload-cli")
@click.option("--data-mode", default="fill_blanks", show_default=True)
@click.option("--bom-mode", default="fill_if_empty", show_default=True)
@click.option("--file-mode", default="add_missing", show_default=True)
@click.option("--approval-mode", default="preserve", show_default=True)
@click.option("--dry-run", is_flag=True, default=False)
@with_appcontext
def import_zip_cmd(path, tag, data_mode, bom_mode, file_mode, approval_mode, dry_run):
    from app.services.upload_pack import import_upload_pack

    with open(path, "rb") as f:
        result = import_upload_pack(
            f.read(),
            path,
            seed_tag=tag,
            dry_run=dry_run,
            allow_extra=False,
            data_mode=data_mode,
            bom_mode=bom_mode,
            file_mode=file_mode,
            approval_mode=approval_mode,
        )
    summary = result["plan"]["summary"]
    click.echo(
        f"zip={result['zip']} root={result['root']} rev={result['root_rev']} "
        f"dry_run={result['dry_run']} parts={summary['parts']} "
        f"changed={summary['changed']} blocked={summary['blocked']} "
        f"metrics={result['metrics']}"
    )

    
    
################################################################
#File discovery commands

import click, os
from flask.cli import with_appcontext
from flask import current_app
from app.services.filescan import discover_part_files, upsert_part_files
from app.models.artifact import PartFile

@click.group()
def files():
    """File utilities"""

@files.command("scan-one")
@click.option("--pn", required=True)
@click.option("--rev", required=True)
@with_appcontext
def scan_one(pn, rev):
    recs = discover_part_files(pn, rev)
    ins = upsert_part_files(recs)
    from app.services.thumbs_gen import generate_thumbs_for_parts
    n_thumbs = generate_thumbs_for_parts([(pn, rev)])
    click.echo({"found": len(recs), "inserted": ins, "thumbnails_generated": n_thumbs})

@files.command("backfill-rel")
@with_appcontext
def backfill_rel():
    """Compute rel_path for docs missing it (based on FILE_ROOT_LOCAL)."""
    root = (current_app.config.get("FILE_ROOT_LOCAL") or "").strip()
    if not root:
        click.echo("FILE_ROOT_LOCAL not set"); return
    base = os.path.abspath(root)
    n = 0
    for d in PartFile.objects():
        if getattr(d, "rel_path", None): continue
        p = getattr(d, "path", "")
        if not p: continue
        try:
            rp = os.path.relpath(p, base)
            if rp.startswith(".."): continue
            d.rel_path = rp.replace("\\", "/")
            d.save(); n += 1
        except Exception:
            continue
    click.echo({"rel_paths_added": n})


import click
from flask.cli import with_appcontext
from app.services.thumbs_gen import generate_thumbs_for_parts
from app.models.part import Part
from app.services.timezone_utils import utc_now

@click.group()
def thumbs():
    """Thumbnail utilities"""

@thumbs.command("rebuild-one")
@click.option("--pn", required=True)
@click.option("--rev", default=None, help='Revision string, use "" to target empty, omit for all')
@with_appcontext
def rebuild_one(pn, rev):
    num = generate_thumbs_for_parts([(pn, rev)])
    click.echo({"rebuilt": num})

@thumbs.command("rebuild-all")
@with_appcontext
def rebuild_all():
    pairs = []
    for p in Part.objects.only("part_number","revision"):
        pairs.append((p.part_number, p.revision or ""))
    num = generate_thumbs_for_parts(pairs)
    click.echo({"rebuilt": num})


@click.group()
def attrs():
    """Attribute utilities"""

@attrs.command("backfill")
@with_appcontext
def attrs_backfill():
    """Ensure all Parts have full attribute dict with defaults."""
    fixed = 0
    for p in Part.objects():
        before = dict(getattr(p, "props", {}) or {})
        attrs = harvest_part_attrs(p)
        # If something changed (missing defaults added), save back
        if attrs != before or p.description != attrs.get("description","") or p.revision != attrs.get("revision","") or p.category != attrs.get("category",""):
            merge_save_part_attrs(p, attrs)
            fixed += 1
    click.echo({"updated": fixed})


@click.group()
def attrs():
    """Attribute utils"""

@attrs.command("backfill")
@with_appcontext
def attrs_backfill():
    count = 0
    for p in Part.objects():
        norm = harvest_part_attrs(p)
        # Save only if we would change stored attrs or mirrors
        changed = (norm != (p.attrs or {})) \
            or (p.description != norm.get("description","")) \
            or (p.revision != norm.get("revision","")) \
            or (p.category != norm.get("category",""))
        if changed:
            merge_save_part_attrs(p, norm)
            count += 1
    click.echo({"updated": count})


@click.group()
def annotations():
    """Part notes/comments utilities"""


@annotations.command("backfill")
@with_appcontext
def annotations_backfill():
    result = bulk_sync_annotation_search_fields(Part.objects())
    click.echo(result)


@click.group()
def parts():
    """Part search/materialized field utilities"""


@parts.command("rebuild-search-fields")
@with_appcontext
def parts_rebuild_search_fields():
    report = rebuild_part_materialized_fields()
    click.echo(report)



def init_app(app):
    # ... your existing CLI registrations ...
    app.cli.add_command(attrs)
    app.cli.add_command(thumbs)
    app.cli.add_command(importcmd, "import")
    app.cli.add_command(files)
    app.cli.add_command(user)
    app.cli.add_command(role)
    app.cli.add_command(share)
    app.cli.add_command(data)
    app.cli.add_command(attrs)
    app.cli.add_command(annotations)
    app.cli.add_command(parts)

    # Audit diagnostics group
    import click
    from app.models.audit import AuditLog
    from mongoengine import get_connection
    from flask import current_app

    @click.group()
    def audit():
        """Audit log diagnostics"""

    @audit.command("write-test")
    @with_appcontext
    def audit_write_test():
        """Write a test audit entry and print its id."""
        from app.services.audit import log_action
        inserted = log_action("cli.audit.test", resource_type="system", resource="cli")
        # best effort: if not returned, fetch most recent
        if not inserted:
            doc = AuditLog.objects(action="cli.audit.test").order_by("-ts").first()
            inserted = str(getattr(doc, 'id', 'unknown')) if doc else 'unknown'
        click.echo({"inserted_id": inserted})

    @audit.command("count")
    @with_appcontext
    def audit_count():
        click.echo({"audit_logs": AuditLog.objects.count()})

    @audit.command("tail")
    @click.option("--n", default=5, help="How many entries to show")
    @with_appcontext
    def audit_tail(n):
        rows = AuditLog.objects.order_by("-ts").limit(max(1, min(n, 100)))
        out = [dict(ts=str(r.ts), email=r.email, action=r.action, resource=r.resource) for r in rows]
        click.echo(out)

    @audit.command("diag")
    @with_appcontext
    def audit_diag():
        alias = current_app.config.get("MONGODB_ALIAS", "tinymrp-v2")
        uri = current_app.config.get("MONGO_URI")
        ok = True
        err = None
        try:
            client = get_connection(alias=alias)
            client.admin.command('ping')
        except Exception as e:
            ok = False; err = str(e)
        click.echo({"alias": alias, "uri": uri, "ping": ok, "error": err})

    app.cli.add_command(audit)

    # ---- Help documentation ----
    import sys
    import subprocess

    @click.group(name="help")
    def helpcmd():
        """Help documentation utilities."""

    @helpcmd.command("build")
    @with_appcontext
    def help_build():
        """Generate the static help HTML and TOC files."""
        root = os.path.abspath(os.path.join(current_app.root_path, os.pardir))
        script = os.path.join(root, "tools", "build_help.py")
        if not os.path.isfile(script):
            click.echo("tools/build_help.py not found.")
            raise SystemExit(1)
        try:
            out = subprocess.check_output([sys.executable, script], cwd=root)
            click.echo(out.decode("utf-8").strip())
        except subprocess.CalledProcessError as exc:
            click.echo(f"Help build failed: {exc}")
            raise SystemExit(1)

    app.cli.add_command(helpcmd)

    # ---- Business demo seeding (jobs, suppliers, customers, orders) ----
    import click

    @click.group()
    def biz():
        """Business data utilities (jobs/suppliers/customers/orders)."""

    @biz.command("seed")
    @with_appcontext
    def biz_seed():
        """Seed sample suppliers, customers, a job with BOM, and a purchase order."""
        from app.models.supplier import Supplier
        from app.models.customer import Customer
        from app.models.job import Job, JobBOMLine
        from app.models.order import Order, OrderLine
        from app.models.auth import User, Role

        def _upsert_supplier(name, **kw):
            s = Supplier.objects(name=name).first() or Supplier(name=name)
            for k,v in kw.items(): setattr(s, k, v)
            s.save(); return s
        def _upsert_customer(name, **kw):
            c = Customer.objects(name=name).first() or Customer(name=name)
            for k,v in kw.items(): setattr(c, k, v)
            c.save(); return c
        def _find_admin_user():
            try:
                r = Role.objects(name="admin").first()
                if r:
                    u = User.objects(roles=r).first()
                    return u
            except Exception:
                pass
            return User.objects().first()

        acme = _upsert_supplier("ACME Fabrication", contact="A. Smith", email="contact@acmefab.test", processes=["welding","laser"])
        mworks = _upsert_supplier("MetalWorks Ltd", contact="B. Jones", email="sales@metalworks.test", processes=["machine"]) 
        contoso = _upsert_customer("Contoso", contact="C. Adams", email="projects@contoso.test")
        fabrikam = _upsert_customer("Fabrikam", contact="D. Baker", email="ops@fabrikam.test")

        demo_user = _find_admin_user()
        if demo_user and demo_user not in (acme.users or []):
            acme.users.append(demo_user); acme.save()
        if demo_user and demo_user not in (contoso.users or []):
            contoso.users.append(demo_user); contoso.save()

        job = Job.objects(job_number="JOB-1001").first()
        if not job:
            job = Job(job_number="JOB-1001", description="Demo Project", customer=contoso)
            if demo_user:
                job.participants = [demo_user]
            job.vendors = [acme]
            job.bom = [
                JobBOMLine(pn="ASM-1001", rev="A", qty=1.0),
                JobBOMLine(pn="CMP-2002", rev="B", qty=2.0),
            ]
            job.save()

        po = Order.objects(order_number="PO-1001").first()
        if not po:
            po = Order(order_number="PO-1001", description="Initial buy", kind="purchase",
                       job=job, supplier=acme, customer=contoso,
                       lines=[
                           OrderLine(pn="CMP-2002", rev="B", qty=10, uom="EA", note="Wave 1"),
                           OrderLine(pn="MAT-3003", rev="A", qty=5, uom="SHT", note="Stock-up"),
                       ])
            po.save()

        click.echo({
            "suppliers": [s.name for s in Supplier.objects().only("name")],
            "customers": [c.name for c in Customer.objects().only("name")],
            "jobs": [j.job_number for j in Job.objects().only("job_number")],
            "orders": [o.order_number for o in Order.objects().only("order_number")],
        })

    @biz.command("clear")
    @with_appcontext
    def biz_clear():
        """Delete all Jobs, Orders, Suppliers, Customers (dangerous)."""
        from app.models.order import Order
        from app.models.job import Job
        from app.models.supplier import Supplier
        from app.models.customer import Customer
        n_orders = Order.objects.delete()
        n_jobs = Job.objects.delete()
        n_sup = Supplier.objects.delete()
        n_cust = Customer.objects.delete()
        click.echo({"orders": n_orders, "jobs": n_jobs, "suppliers": n_sup, "customers": n_cust})

    app.cli.add_command(biz)




