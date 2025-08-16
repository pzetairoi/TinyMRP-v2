import secrets
import click
from flask.cli import with_appcontext
from flask_security import hash_password

from .models.auth import User, Role
from .models.part import Part
from .models.bom import BOMLink

@click.group()
def user():
    """User management commands"""

@user.command("create")
@click.option("--email", prompt=True)
@click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
@with_appcontext
def create_user(email, password):
    if User.objects(email=email).first():
        click.echo("User exists")
        return
    u = User(email=email, password=hash_password(password), fs_uniquifier=secrets.token_hex(16))
    u.save()
    click.echo("Created user")
    
        
@user.command("grant-admin")
@click.option("--email", prompt=True)
@with_appcontext
def grant_admin(email):
    u = User.objects(email=email.lower()).first()
    if not u:
        click.echo("User not found"); return
    r = Role.objects(name="admin").first() or Role(name="admin").save()
    if r not in u.roles:
        u.roles.append(r); u.save()
    click.echo("Granted admin role")    
    
@user.command("seed-roles")
@with_appcontext
def seed_roles():
    from .views.admin_roles import PERMISSIONS
    from .models.auth import Role
    def upsert(name, desc, perms):
        r = Role.objects(name=name).first()
        if not r: r = Role(name=name)
        r.description = desc; r.permissions = perms; r.save()
    upsert("admin", "Full access", PERMISSIONS)
    upsert("planner", "Plan and run MRP", ["items.view","bom.view","workorders.view","mrp.run","reports.view"])
    upsert("operator", "Execute work orders", ["workorders.view","workorders.edit","workorders.close","inventory.issue","inventory.receive"])
    upsert("viewer", "Read-only", ["items.view","bom.view","workorders.view","reports.view"])
    click.echo("Seeded roles.")

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


def init_app(app):
    app.cli.add_command(user)
    
    
