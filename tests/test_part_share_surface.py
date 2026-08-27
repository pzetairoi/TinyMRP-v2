"""Every share option, audited against everything a public link can reach.

The per-option tests elsewhere check one endpoint at a time. This one drives a
full assembly through the whole public surface at once, because the defects
that reached users were never a single wrong answer - they were one endpoint
disagreeing with another. The BOM tree returned five children whose rows were
all blank; the Files tab appeared on links that granted no files; the child
grant resolved correctly in scope and still showed nothing on screen.
"""

import uuid

from app.models.artifact import PartFile
from app.models.auth import Role, User
from app.models.bom import BOMLink
from app.models.extra_file import PartExtraFile
from app.models.part import Part
from app.services.permissions import PERMISSION_REGISTRY


ROOT = "SURF-ROOT"
CHILD = "SURF-CHILD"
REV = "A"

# One file of every group a level can gate, on both parts.
FILE_SPECS = (
    ("png", False),
    ("png", True),
    ("ply", False),
    ("pdf", False),
    ("step", False),
    ("dxf", False),
    ("edr", False),
    ("datasheet", False),
)


def _admin(client, email):
    role = (
        Role.objects(name="administrator").first()
        or Role(name="administrator", permissions=sorted(PERMISSION_REGISTRY)).save()
    )
    user = User(
        email=email,
        password="test-password-123",
        active=True,
        fs_uniquifier=str(uuid.uuid4()),
        roles=[role],
    ).save()
    with client.session_transaction() as sess:
        sess["_user_id"] = user.get_id()
        sess["_fresh"] = True
    return user


def _assembly(app, tmp_path):
    app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
    app.config["FILE_SOURCES"] = [{"local_root": str(tmp_path)}]
    app.config["EXTRA_FILES_ROOT"] = str(tmp_path)

    for pn, desc in ((ROOT, "Shared assembly"), (CHILD, "Shared component")):
        Part(
            part_number=pn,
            revision=REV,
            description=desc,
            attrs={"material": "Steel", "finish": "Painted", "mass": "3.5"},
        ).save()
        for group, is_dwg in FILE_SPECS:
            name = group + ("-dwg" if is_dwg else "")
            rel = f"{pn}/{name}.{group}"
            abs_path = tmp_path / rel
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            abs_path.write_bytes(f"{pn}-{name}".encode())
            PartFile(
                part_number=pn,
                revision=REV,
                ext_group=group,
                ext=group,
                is_dwg=is_dwg,
                rel_path=rel,
                path=str(abs_path),
            ).save()

    BOMLink(
        parent_pn=ROOT, parent_rev=REV, child_pn=CHILD, child_rev=REV, qty=2
    ).save()

    upload = tmp_path / "extra" / "costing.xlsx"
    upload.parent.mkdir(parents=True, exist_ok=True)
    upload.write_bytes(b"costing")
    PartExtraFile(
        part_number=ROOT,
        revision=REV,
        original_name="costing.xlsx",
        rel_path="extra/costing.xlsx",
        source="upload",
    ).save()
    # Never shared at any level - the source term alone disqualifies it.
    internal = tmp_path / "extra" / "margins.xlsx"
    internal.write_bytes(b"margins")
    PartExtraFile(
        part_number=ROOT,
        revision=REV,
        original_name="margins.xlsx",
        rel_path="extra/margins.xlsx",
        source="internal",
    ).save()


def _surface(app, created):
    """Everything one public link exposes, read the way a browser reads it."""

    public = app.test_client()
    base = f"/api/share/part/{created['share_id']}/{created['share_token']}"
    detail = public.get(f"{base}/part_detail?pn={ROOT}&rev={REV}").get_json()
    overview = public.get(f"{base}/files_overview?pn={ROOT}&rev={REV}").get_json()
    rows = overview["current_revision"]["files"]
    root_nodes = public.get(f"{base}/bom_tree?pn={ROOT}&rev={REV}").get_json()
    kids = public.get(
        f"{base}/bom_tree?parent={ROOT}&parent_rev={REV}"
    ).get_json()
    flat = public.get(f"{base}/bom_flat?pn={ROOT}&rev={REV}").get_json()
    options = public.get(
        f"{base}/docpacks/options?pn={ROOT}&rev={REV}&depth=top"
    )
    return {
        "images": len(detail["images"]),
        "drawings": len(detail["drawing_urls"]),
        "groups": sorted(g for g, files in detail["files"].items() if files),
        "attributes": sorted(detail["part"]["attributes"]),
        "datasheet_field": bool(detail["part"]["field_values"].get("datasheet")),
        "preview_images": len(
            public.get(
                f"{base}/part_images?pn={ROOT}&rev={REV}&mode=preview"
            ).get_json()
        ),
        "drawing_images": len(
            public.get(
                f"{base}/part_images?pn={ROOT}&rev={REV}&mode=drawing"
            ).get_json()
        ),
        "listed_managed": sorted(
            row["ext_group"] for row in rows if row["kind"] == "scanned"
        ),
        "listed_extra": sorted(
            row["name"] for row in rows if row["kind"] == "extra"
        ),
        "bom_roots": len(root_nodes),
        "bom_root_named": [node["data"].get("pn") for node in root_nodes],
        "bom_children": [node["data"].get("pn") for node in kids],
        "bom_child_desc": [node["data"].get("desc") for node in kids],
        "bom_flat": len(flat),
        "child_reachable": public.get(
            f"{base}/part_detail?pn={CHILD}&rev={REV}"
        ).status_code,
        "docpack_options": options.status_code,
        "docpack_types": (
            sorted(options.get_json()["file_types"])
            if options.status_code == 200
            else None
        ),
    }


def _make(client, **payload):
    resp = client.post(
        f"/api/parts/{ROOT}/shares",
        json={"rev": REV, "expires_in_days": 30, **payload},
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    return resp.get_json()


def test_preview_level_surface(client, app, tmp_path):
    """The floor: an image and a mesh, and nothing that hints at more."""

    _admin(client, "surface-preview@example.com")
    _assembly(app, tmp_path)
    s = _surface(app, _make(client, tier="preview"))

    assert s["images"] == 1
    assert s["preview_images"] == 1
    assert s["drawings"] == 0 and s["drawing_images"] == 0
    assert s["groups"] == ["ply"]
    assert s["listed_managed"] == ["ply", "png"]
    assert s["listed_extra"] == []
    assert s["attributes"] == []
    assert s["datasheet_field"] is False
    # No child grant means no BOM at all, not a heading over one blank row.
    assert s["bom_roots"] == 0
    assert s["bom_children"] == []
    assert s["bom_flat"] == 0
    assert s["child_reachable"] == 404
    assert s["docpack_options"] == 403


def test_review_level_surface(client, app, tmp_path):
    """Drawings, datasheet and attributes appear; the CAD models do not."""

    _admin(client, "surface-review@example.com")
    _assembly(app, tmp_path)
    s = _surface(app, _make(client, tier="review"))

    assert s["images"] == 1 and s["drawings"] == 1
    assert s["drawing_images"] == 1
    assert s["groups"] == ["datasheet", "pdf", "ply"]
    assert s["listed_managed"] == ["datasheet", "pdf", "ply", "png", "png"]
    assert s["listed_extra"] == []
    assert "material" in s["attributes"] and "finish" in s["attributes"]
    assert s["datasheet_field"] is True
    assert "step" not in s["groups"] and "dxf" not in s["groups"]
    assert s["bom_roots"] == 0
    assert s["docpack_options"] == 403


def test_supplier_level_surface(client, app, tmp_path):
    """Everything, including the BOM - and the internal upload still never."""

    _admin(client, "surface-supplier@example.com")
    _assembly(app, tmp_path)
    s = _surface(app, _make(client, tier="supplier", allow_children=True))

    assert s["images"] == 1 and s["drawings"] == 1
    assert s["groups"] == ["datasheet", "dxf", "edr", "pdf", "ply", "step"]
    assert s["listed_extra"] == ["costing.xlsx"], "margins.xlsx is source=internal"
    assert s["child_reachable"] == 200

    # The defect that made the child grant look broken: five children whose
    # rows were every one of them blank, because the node data had been run
    # through an authenticated field policy with no user behind it.
    assert s["bom_roots"] == 1
    assert s["bom_root_named"] == [ROOT]
    assert s["bom_children"] == [CHILD]
    assert s["bom_child_desc"] == ["Shared component"]
    assert s["bom_flat"] == 1

    assert s["docpack_options"] == 200
    assert "step" in s["docpack_types"]


def test_children_grant_is_independent_of_the_level(client, app, tmp_path):
    """Which PARTS a link reaches is a separate axis from what it shows."""

    _admin(client, "surface-axes@example.com")
    _assembly(app, tmp_path)

    preview_with_children = _surface(
        app, _make(client, tier="preview", allow_children=True)
    )
    assert preview_with_children["bom_root_named"] == [ROOT]
    assert preview_with_children["bom_children"] == [CHILD]
    assert preview_with_children["child_reachable"] == 200
    # ...but the level still governs what each of those parts shows.
    assert preview_with_children["groups"] == ["ply"]
    assert preview_with_children["drawings"] == 0

    supplier_no_children = _surface(app, _make(client, tier="supplier"))
    assert supplier_no_children["bom_roots"] == 0
    assert supplier_no_children["child_reachable"] == 404
    assert "step" in supplier_no_children["groups"]


def test_every_grant_moves_exactly_one_thing(client, app, tmp_path):
    """Turn each grant on alone and pin what it - and only it - adds."""

    _admin(client, "surface-single@example.com")
    _assembly(app, tmp_path)
    floor = _surface(app, _make(client, tier="preview"))

    drawings = _surface(app, _make(client, tier="preview", allow_drawings=True))
    assert drawings["drawings"] == 1 and drawings["drawing_images"] == 1
    assert drawings["groups"] == ["pdf", "ply"]
    assert drawings["attributes"] == floor["attributes"]

    cad = _surface(app, _make(client, tier="preview", allow_neutral_cad=True))
    assert cad["groups"] == ["dxf", "edr", "ply", "step"]
    assert cad["drawings"] == 0, "neutral CAD must not leak the drawing"

    datasheets = _surface(
        app, _make(client, tier="preview", allow_datasheets=True)
    )
    assert datasheets["groups"] == ["datasheet", "ply"]
    assert datasheets["datasheet_field"] is True
    assert datasheets["listed_extra"] == [], "a datasheet is not an upload"

    all_files = _surface(app, _make(client, tier="preview", allow_all_files=True))
    assert all_files["listed_extra"] == ["costing.xlsx"]
    assert all_files["groups"] == floor["groups"], "uploads are not a managed group"

    attributes = _surface(
        app, _make(client, tier="preview", allow_attributes=True)
    )
    assert "material" in attributes["attributes"]
    assert attributes["groups"] == floor["groups"]

    docpacks = _surface(app, _make(client, tier="preview", allow_docpacks=True))
    assert docpacks["docpack_options"] == 200
    # No "png": the pack builder cannot tell a preview PNG from a drawing PNG,
    # so a link that withholds drawings withholds PNGs from packs entirely.
    assert docpacks["docpack_types"] == ["ply"], "only what this link shows"
