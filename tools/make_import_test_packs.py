#!/usr/bin/env python3
"""Build the import-policy exercise packs from the checked-in CV03 sample.

The Import page has three independent policies (Properties, BOM, Files), four
levels each, and an approval rule that cuts across all of them. Reading the
matrix is not the same as seeing it happen, so this generator produces a series
of upload packs that walk one small assembly through a realistic engineering →
manufacturing → purchasing → release → change-request flow. Every pack is a
step in that story, and each step is chosen to make one policy behave visibly
differently from the next.

The part data (descriptions, materials, processes, masses, sheet-metal figures)
and every deliverable byte come from the owner-approved CV03-TR-A01 fixture in
``sample_data/``, so the exercise looks like real engineering data rather than
lorem ipsum. Only the part numbers are renamed, behind a prefix, so running the
exercise on a populated server cannot touch real parts.

Usage::

    python tools/make_import_test_packs.py                # testfiles/import_scenarios
    python tools/make_import_test_packs.py --out C:/tmp/packs --prefix DEMO-

Then upload the numbered ZIPs in order on the Import page. The generated
README.md in the output folder repeats the story and the expected outcome of
each step; the full explanation is in the app help, chapter "Import: what each
policy actually does".
"""

from __future__ import annotations

import argparse
import ast
import json
import shutil
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_ROOT = REPO_ROOT / "sample_data" / "cv03_tr_a01_rev_a" / "managed"
DEFAULT_OUT = REPO_ROOT / "testfiles" / "import_scenarios"

# Fields the first (engineering) release deliberately leaves empty so later
# steps have real blanks to fill. Everything else comes through as authored.
RELEASE_BLANKS = (
    "cost",
    "leadtime",
    "supplier",
    "supplier_partnumber",
    "distributor",
    "design_notes",
    "comments",
)
APPROVAL_KEYS = ("approved", "ApprovedBy", "ApprovedDate")
# Sample columns that are aliases of another column in the same row. Left in,
# every single part would report an alias conflict and drown the interesting
# ones; step 9 puts a deliberate conflict back to show what it looks like.
ALIAS_DUPLICATES = (
    "colour",  # -> finish
    "treatment",  # -> finish
    "Spare part",  # -> spare_part
    "Weight",  # -> mass
    "oem_data_sheet",  # -> datasheet
    "oem_part_number",  # -> oem_partnumber
)


@dataclass(frozen=True)
class PartSpec:
    """One test identity and the real CV03 row its data comes from."""

    key: str
    suffix: str
    revision: str
    source: str
    role: str


# The cast. Small enough to read a whole redline, varied enough to cover an
# assembly, a sub-assembly, fabricated parts, a bought-out part with a
# datasheet, and a bought-out part with NO revision at all.
CAST: tuple[PartSpec, ...] = (
    PartSpec("A01", "A01", "A", "CV03-TR-A01", "Top-level assembly"),
    PartSpec("F01", "F01", "A", "CV03-F01", "Welded sub-assembly"),
    PartSpec("P01", "P01", "B", "CV03-TR-01", "Laser-cut channel"),
    PartSpec("P02", "P02", "B", "CV03-TR-03", "Laser-cut hitch plate"),
    PartSpec("P03", "P03", "B", "CV03-TR-06", "Laser-cut bracket, used twice"),
    PartSpec("B01", "B01", "A", "ADR-HITCH", "Bought-out hitch"),
    PartSpec("B02", "B02", "", "ADR-LED-IND", "Bought-out lamp, no revision"),
)

# Who signs what in step 4. Later steps resend it so that overriding data does
# not silently strip the approval off the part.
STORY_APPROVAL: dict[str, tuple[str, str]] = {
    "P01": ("FQ", "13/10/24"),
    "P02": ("FQ", "13/10/24"),
    "P03": ("FQ", "13/10/24"),
    "F01": ("FQ", "14/10/24"),
    "B01": ("Purchasing", ""),
}


@dataclass
class Pack:
    """One ZIP in the exercise, plus what the operator should expect from it."""

    order: int
    slug: str
    title: str
    story: str
    rows: list[dict[str, Any]]
    tree: list[tuple[str, str, str, float]]
    files: dict[str, bytes] = field(default_factory=dict)
    expectations: list[str] = field(default_factory=list)
    manifest: list[dict[str, str]] = field(default_factory=list)

    @property
    def filename(self) -> str:
        return f"{self.order:02d}_{self.slug}.zip"


def _sample_flatbom_rows() -> dict[str, dict[str, Any]]:
    """Real property rows, keyed by part number, from the fixture pack."""

    packs = sorted((SAMPLE_ROOT / "bom").glob("*.zip"))
    if not packs:
        raise SystemExit(f"No sample BOM pack found under {SAMPLE_ROOT / 'bom'}")
    rows: dict[str, dict[str, Any]] = {}
    with zipfile.ZipFile(packs[-1]) as archive:
        name = next(
            item for item in archive.namelist() if item.casefold().endswith("_flatbom.txt")
        )
        text = archive.read(name).decode("utf-8-sig", errors="replace")
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            row = ast.literal_eval(line)
        if isinstance(row, dict) and row.get("partnumber"):
            rows[str(row["partnumber"])] = row
    return rows


def _deliverable(group: str, name: str) -> bytes:
    path = SAMPLE_ROOT / group / name
    if not path.is_file():
        raise SystemExit(f"Sample deliverable missing: {path}")
    return path.read_bytes()


class Builder:
    """Renames the sample rows into the exercise namespace and packs them."""

    def __init__(self, prefix: str) -> None:
        self.prefix = prefix
        self.source_rows = _sample_flatbom_rows()

    # -- identity ---------------------------------------------------------
    def pn(self, key: str) -> str:
        spec = self.spec(key)
        return f"{self.prefix}{spec.suffix}"

    def rev(self, key: str) -> str:
        return self.spec(key).revision

    @staticmethod
    def spec(key: str) -> PartSpec:
        return next(item for item in CAST if item.key == key)

    def stem(self, key: str, revision: str | None = None) -> str:
        """The ``PN_REV_x`` filename stem every managed deliverable must use."""

        rev = self.rev(key) if revision is None else revision
        return f"{self.pn(key)}_REV_{rev}"

    # -- rows -------------------------------------------------------------
    def row(
        self,
        key: str,
        *,
        revision: str | None = None,
        blanks: Iterable[str] = (),
        only: Iterable[str] | None = None,
        **overrides: Any,
    ) -> dict[str, Any]:
        """A FLATBOM row for ``key``.

        ``only`` restricts the row to identity plus the named keys, which is
        how a later step in the story carries just the handful of values that
        department actually owns instead of resending the whole record.
        """

        spec = self.spec(key)
        source = {
            name: value
            for name, value in self.source_rows[spec.source].items()
            if name not in ALIAS_DUPLICATES
        }
        row: dict[str, Any] = {
            **source,
            "partnumber": self.pn(key),
            "revision": self.rev(key) if revision is None else revision,
            # The sample carries absolute authoring paths; the exercise is not
            # about anyone's disk layout.
            "path": "",
            "folder": "",
            "file": f"{self.pn(key)}.SLDPRT",
        }
        for name in APPROVAL_KEYS:
            row[name] = ""
        for name in blanks:
            row[name] = ""
        row.update(overrides)
        if only is not None:
            keep = {"partnumber", "revision", *APPROVAL_KEYS, *only, *overrides}
            row = {name: value for name, value in row.items() if name in keep}
        return row

    def released_row(self, key: str, approver: str, date: str, **overrides: Any) -> dict[str, Any]:
        return self.row(
            key,
            only=(),
            approved="Yes",
            ApprovedBy=approver,
            ApprovedDate=date,
            **overrides,
        )

    def story_row(self, key: str, **overrides: Any) -> dict[str, Any]:
        """A row for a step that runs AFTER the parts were released.

        A row whose approval columns are empty is not "no opinion": under
        Override approved an empty column wins like any other value and strips
        the approval off the part. Steps that only mean to change data
        therefore resend the approval step 4 established. Step 10 is the one
        that deliberately leaves it out, so the damage is visible on purpose.
        """

        approver, date = STORY_APPROVAL.get(key, ("", ""))
        if not approver:
            return self.row(key, only=(), **overrides)
        approval = {"approved": "Yes", "ApprovedBy": approver, "ApprovedDate": date}
        return self.row(key, only=(), **{**approval, **overrides})

    # -- archive ----------------------------------------------------------
    def write(self, pack: Pack, out_dir: Path) -> Path:
        target = out_dir / pack.filename
        stem = f"{self.prefix.rstrip('-')}_{pack.slug}"
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                f"bom/{stem}_FLATBOM.txt",
                "\n".join(json.dumps(row) for row in pack.rows) + "\n",
            )
            if pack.tree:
                lines = ["ITEM NO.\tPART NUMBER\tRevision\tQTY."]
                lines += [
                    f"{item}\t{pn}\t{rev}\t{qty:g}" for item, pn, rev, qty in pack.tree
                ]
                archive.writestr(f"bom/{stem}_TREEBOM.txt", "\n".join(lines) + "\n")
            if pack.manifest:
                archive.writestr(
                    "extra/_manifest.json",
                    json.dumps({"files": pack.manifest}, indent=2),
                )
            for name, payload in pack.files.items():
                archive.writestr(name, payload)
        return target


def build_packs(builder: Builder) -> list[Pack]:
    pn = builder.pn
    rev = builder.rev
    stem = builder.stem

    # The tree used by most steps: A01 → F01 → three fabricated parts, plus two
    # bought-out items hung off the top level. Dotted ITEM NO. is what makes the
    # parent/child links; flat numbering parses but yields no BOM at all.
    full_tree = [
        ("1", pn("A01"), rev("A01"), 1),
        ("1.1", pn("F01"), rev("F01"), 1),
        ("1.1.1", pn("P01"), rev("P01"), 1),
        ("1.1.2", pn("P02"), rev("P02"), 1),
        ("1.1.3", pn("P03"), rev("P03"), 2),
        ("1.2", pn("B01"), rev("B01"), 1),
        ("1.3", pn("B02"), rev("B02"), 2),
    ]

    packs: list[Pack] = []

    # ---------------------------------------------------------------- 01 --
    packs.append(
        Pack(
            order=1,
            slug="engineering_release",
            title="Engineering publishes the first draft",
            story=(
                "The design is finished and published for the first time. Every "
                "part is new, nothing is approved yet, and the commercial fields "
                "(cost, lead time, supplier) are deliberately empty because "
                "engineering does not own them."
            ),
            rows=[
                builder.row("A01", blanks=RELEASE_BLANKS),
                builder.row("F01", blanks=RELEASE_BLANKS),
                builder.row("P01", blanks=RELEASE_BLANKS),
                builder.row("P02", blanks=(*RELEASE_BLANKS, "finish")),
                builder.row("P03", blanks=RELEASE_BLANKS),
                builder.row("B01", blanks=RELEASE_BLANKS),
                builder.row("B02", blanks=RELEASE_BLANKS),
            ],
            tree=full_tree,
            files={
                f"deliverables/png/{stem('A01')}.png": _deliverable("png", "CV03-TR-A01_REV_A.png"),
                f"deliverables/png/{stem('F01')}.png": _deliverable("png", "CV03-F01_REV_A.png"),
                f"deliverables/pdf/{stem('F01')}.pdf": _deliverable("pdf", "CV03-F01_REV_A.pdf"),
                f"deliverables/png/{stem('P01')}.png": _deliverable("png", "CV03-TR-01_REV_B.png"),
                # The drawing screenshot is a SEPARATE identity from the preview.
                f"deliverables/png/{stem('P01')}_DWG.png": _deliverable("png", "CV03-TR-01_REV_B_DWG.png"),
                f"deliverables/pdf/{stem('P01')}.pdf": _deliverable("pdf", "CV03-TR-01_REV_B.pdf"),
                f"deliverables/dxf/{stem('P01')}.dxf": _deliverable("dxf", "CV03-TR-01_REV_B.dxf"),
                f"deliverables/step/{stem('P01')}.step": _deliverable("step", "CV03-TR-01_REV_B.step"),
                f"deliverables/png/{stem('P02')}.png": _deliverable("png", "CV03-TR-03_REV_B.png"),
                f"deliverables/pdf/{stem('P02')}.pdf": _deliverable("pdf", "CV03-TR-03_REV_B.pdf"),
                f"deliverables/png/{stem('P03')}.png": _deliverable("png", "CV03-TR-06_REV_B.png"),
                f"deliverables/png/{stem('B01')}.png": _deliverable("png", "ADR-HITCH_REV_A.png"),
                # Blank revision: the stem still carries the _REV_ marker.
                f"deliverables/png/{stem('B02')}.png": _deliverable("png", "ADR-LED-IND_REV_.png"),
                f"extra/{pn('F01')}/{rev('F01')}/weld-procedure-WPS-01.pdf": _deliverable(
                    "pdf", "CV03-F01_REV_A.pdf"
                ),
            },
            manifest=[
                {
                    "pn": pn("F01"),
                    "rev": rev("F01"),
                    "name": "weld-procedure-WPS-01.pdf",
                    "label": "Weld procedure WPS-01",
                }
            ],
            expectations=[
                "Every part is New, so Fill only creates all 7 parts, the BOM and every file.",
                "Required permissions: parts.create, bom.update, files.add, imports.execute_low_risk.",
                "An Engineering user can run this step; nothing here needs the override.",
                f"{pn('P01')} gets two PNG rows: the preview and the _DWG drawing screenshot.",
                f"{pn('B02')} has no revision — that blank revision is its identity from now on.",
            ],
        )
    )

    # ---------------------------------------------------------------- 02 --
    packs.append(
        Pack(
            order=2,
            slug="manufacturing_fills_blanks",
            title="Manufacturing fills in what it owns",
            story=(
                "Process engineering sets the lead times, gives one part the "
                "finish that was left empty, and wants to correct the material "
                "and description of another. The parts are still drafts, so this "
                "is where Fill only and Update drafts stop behaving the same."
            ),
            rows=[
                builder.row(
                    "P01",
                    only=("description", "material", "finish", "leadtime"),
                    # Blank in step 1 → any policy above Skip fills this.
                    leadtime="10",
                    # NOT blank in step 1 → only Update drafts replaces these.
                    finish="zinc plate",
                    material="MS PLATE GRADE 250",
                    description="75x50x4 CHANNEL 1925 A (rolled)",
                ),
                builder.row(
                    "P02",
                    # Step 1 left P02 with no finish at all, so this one fills.
                    only=("finish", "leadtime"),
                    finish="powdercoat",
                    leadtime="10",
                ),
                builder.row("P03", only=("leadtime",), leadtime="7"),
                builder.row("F01", only=("finish",), finish="paint"),
            ],
            tree=full_tree,
            expectations=[
                "Fill only: every lead time is added and P02 gets its finish; the new "
                "material, description and P01/F01's finish are skipped because those "
                "fields already hold a value.",
                "Update drafts: the same blanks are filled AND material, description and "
                "finish are replaced — which needs imports.execute_approved, so plain "
                "Engineering cannot run it.",
                "The BOM is identical to step 1, so the BOM section reports 'unchanged'.",
                "No files travel in this pack; with Files on anything but Skip the plan "
                "still lists the deliverables it re-discovered in storage.",
                "'Finish' also covers the treatment and colour columns — one logical field, "
                "several column names.",
            ],
        )
    )

    # ---------------------------------------------------------------- 03 --
    supplier_datasheet = f"{pn('B01')}-datasheet.pdf"
    packs.append(
        Pack(
            order=3,
            slug="purchasing_supplier_data",
            title="Purchasing adds supplier data and datasheets",
            story=(
                "Procurement fills the commercial fields on the two bought-out "
                "items, attaches the supplier datasheet, and re-sends a lead time "
                "that disagrees with manufacturing's. It also brings a second copy "
                "of a drawing PDF whose file name differs only in letter case."
            ),
            rows=[
                builder.row(
                    "B01",
                    only=("supplier", "supplier_partnumber", "distributor", "cost", "leadtime", "datasheet"),
                    supplier="ADR Towing Pty Ltd",
                    supplier_partnumber="ADR-HITCH-50",
                    distributor="Trailer Parts Direct",
                    cost="184.50",
                    leadtime="21",
                    datasheet=supplier_datasheet,
                ),
                builder.row(
                    "B02",
                    only=("supplier", "supplier_partnumber", "cost", "leadtime"),
                    supplier="LumaTech",
                    supplier_partnumber="LT-LED-24",
                    cost="12.80",
                    leadtime="14",
                ),
                # Disagrees with step 2 on purpose: 21 vs 10 days.
                builder.row("P01", only=("leadtime", "cost"), leadtime="21", cost="63.40"),
            ],
            tree=full_tree,
            files={
                f"deliverables/datasheet/{supplier_datasheet}": _deliverable(
                    "pdf", "CV03-TR-A01_REV_A.pdf"
                ),
                # Same part, same group, same extension once case is folded:
                # one identity, so this REPLACES the step-1 PDF rather than
                # adding a second one, even though the file name is different.
                f"deliverables/pdf/{stem('P01')}.PDF": _deliverable("pdf", "CV03-TR-03_REV_B.pdf"),
                # Associated files are identified by their name, so this lands
                # beside the weld procedure instead of replacing anything.
                f"extra/{pn('B01')}/{rev('B01')}/supplier-quote-Q-2291.pdf": _deliverable(
                    "pdf", "CV03-TR-06_REV_B.pdf"
                ),
            },
            manifest=[
                {
                    "pn": pn("B01"),
                    "rev": rev("B01"),
                    "name": "supplier-quote-Q-2291.pdf",
                    "label": "Supplier quote Q-2291",
                }
            ],
            expectations=[
                "Supplier, supplier part number, distributor and cost are blank, so every "
                "policy above Skip adds them.",
                f"Lead time on {pn('P01')} is already 10 from step 2: Fill only keeps 10, "
                "Update drafts overwrites it with 21.",
                "The datasheet PDF is matched to its owner through the datasheet attribute, "
                "not through its file name.",
                f"deliverables/pdf/{stem('P01')}.PDF is the SAME file identity as the step-1 "
                "PDF: Fill only skips it, Update drafts replaces it.",
                "The supplier quote in extra/ is a new associated file, not a replacement.",
            ],
        )
    )

    # ---------------------------------------------------------------- 04 --
    packs.append(
        Pack(
            order=4,
            slug="engineering_release_approved",
            title="Engineering releases: approval arrives",
            story=(
                "The drawings are signed off. The same identities come back "
                "carrying an approver and an approval date. This is the step that "
                "makes everything afterwards behave differently."
            ),
            rows=[
                builder.released_row("P01", "FQ", "13/10/24"),
                builder.released_row("P02", "FQ", "13/10/24"),
                builder.released_row("P03", "FQ", "13/10/24"),
                builder.released_row("F01", "FQ", "14/10/24"),
                # No status column at all — an approver name alone approves it.
                builder.row("B01", only=(), ApprovedBy="Purchasing"),
                # Stays a draft: explicit "No" beats everything else.
                builder.row("A01", only=(), approved="No"),
            ],
            tree=full_tree,
            expectations=[
                "Fill only leaves approval alone: the approval rows read 'skipped — Approval "
                "policy preserves existing approval fields'.",
                "Update drafts applies the approval, because these targets are still drafts.",
                f"{pn('B01')} shows that an approver name with no status column still counts "
                "as approved.",
                f"{pn('A01')} stays a draft: an explicit No wins over anything else in the row.",
                "After applying this with Update drafts, four parts are approved and the rest "
                "of the exercise needs the override.",
            ],
        )
    )

    # ---------------------------------------------------------------- 05 --
    packs.append(
        Pack(
            order=5,
            slug="new_revision_line",
            title="A new revision supersedes an approved part",
            story=(
                f"{pn('P01')} is revised to C and already carries its approval. "
                "The revision is a brand-new identity, so creating it is not an "
                "override — but pointing the sub-assembly at it is a BOM change on "
                "an approved parent."
            ),
            rows=[
                builder.row(
                    "P01",
                    revision="C",
                    approved="Yes",
                    ApprovedBy="FQ",
                    ApprovedDate="03/02/26",
                    description="75x50x4 CHANNEL 1925 A (rev C, longer slots)",
                    material="MS PLATE GRADE 350",
                    finish="zinc plate",
                ),
                # F01 is approved by now and this step only means to change its
                # BOM, so it resends the approval it expects to find.
                builder.story_row("F01"),
            ],
            tree=[
                ("1", pn("F01"), rev("F01"), 1),
                ("1.1", pn("P01"), "C", 1),
                ("1.2", pn("P02"), rev("P02"), 1),
                ("1.3", pn("P03"), rev("P03"), 2),
            ],
            files={
                f"deliverables/png/{stem('P01', 'C')}.png": _deliverable("png", "CV03-TR-01_REV_B.png"),
                f"deliverables/pdf/{stem('P01', 'C')}.pdf": _deliverable("pdf", "CV03-TR-01_REV_B.pdf"),
                f"deliverables/dxf/{stem('P01', 'C')}.dxf": _deliverable("dxf", "CV03-TR-01_REV_B.dxf"),
            },
            expectations=[
                f"{pn('P01')} REV C is New, so any uploader may create it — approved and all.",
                f"REV B of {pn('P01')} is not touched: a revision is a separate part.",
                f"The BOM belongs to {pn('F01')}, which step 4 approved, so Fill only and "
                "Update drafts both report the BOM as blocked.",
                "Override approved is what lets the sub-assembly swap REV B for REV C.",
            ],
        )
    )

    # ---------------------------------------------------------------- 06 --
    packs.append(
        Pack(
            order=6,
            slug="change_request_on_approved",
            title="A change request against approved parts",
            story=(
                "A workshop change request re-cuts an approved part, redraws its "
                "PDF and bumps a quantity. Every single effect here lands on an "
                "approved target, which is exactly what the override exists for."
            ),
            rows=[
                # Re-signed by engineering as part of the change request, which
                # is also what keeps the override from wiping the approval.
                builder.story_row(
                    "P01",
                    ApprovedDate="05/02/26",
                    description="75x50x4 CHANNEL 1925 A (CR-118 gusset)",
                    material="MS PLATE GRADE 350",
                    thickness="5",
                    mass="9.8",
                ),
                builder.story_row("F01"),
                builder.story_row("P02"),
                builder.story_row("P03"),
            ],
            tree=[
                ("1", pn("F01"), rev("F01"), 1),
                ("1.1", pn("P01"), rev("P01"), 1),
                ("1.2", pn("P02"), rev("P02"), 1),
                # Was 2 in every earlier step.
                ("1.3", pn("P03"), rev("P03"), 3),
            ],
            files={
                f"deliverables/pdf/{stem('P01')}.pdf": _deliverable("pdf", "CV03-TR-06_REV_B.pdf"),
            },
            expectations=[
                "With Fill only or Update drafts everything is blocked and the import is "
                "still allowed to run — it simply changes nothing.",
                "Override approved (Admin) applies all of it: properties, the quantity and "
                "the replaced PDF.",
                "Required permissions include imports.override_approved, so Engineering "
                "Manager or Administrator.",
                "The redline's 'Modified approved' tab is the review list for this step.",
            ],
        )
    )

    # ---------------------------------------------------------------- 07 --
    packs.append(
        Pack(
            order=7,
            slug="bom_only_reimport",
            title="BOM-only re-import picks up files from storage",
            story=(
                "This is what the add-in's Create BOM actually produces: two text "
                "files and nothing else. The deliverables already live in the "
                "storage root, so the import reconciles the file records by "
                "scanning storage instead of carrying bytes."
            ),
            rows=[builder.story_row(key) for key in ("A01", "F01", "P01", "P02", "P03", "B01", "B02")],
            tree=full_tree,
            expectations=[
                "No file travels in this pack, so every file row is 'found in storage'.",
                "Copy the out_of_band/ files into the deliverables root first: they appear "
                "as new file records without any file policy allowing an overwrite.",
                "Record reconciliation is not an overwrite, so it happens even on approved "
                "parts — but setting Files to Skip turns the storage scan off entirely.",
                "Re-running this pack unchanged is the normal idempotent case: the redline "
                "reports no property changes and the run is flagged as a repeat.",
            ],
        )
    )

    # ---------------------------------------------------------------- 08 --
    packs.append(
        Pack(
            order=8,
            slug="bom_restructure",
            title="The BOM is restructured",
            story=(
                "The sub-assembly drops a part, doubles another and picks up a "
                "bought-out item. The BOM policy is whole-BOM: there is no such "
                "thing as merging one row in."
            ),
            rows=[
                builder.story_row("F01"),
                builder.story_row("P01"),
                builder.story_row("P03"),
                builder.story_row("B02"),
            ],
            tree=[
                ("1", pn("F01"), rev("F01"), 1),
                ("1.1", pn("P01"), rev("P01"), 1),
                # P02 is gone, P03 goes 2 → 4, B02 is new here.
                ("1.2", pn("P03"), rev("P03"), 4),
                ("1.3", pn("B02"), rev("B02"), 1),
            ],
            expectations=[
                f"Fill only reports 'Fill if empty never merges into an existing BOM' — "
                f"{pn('F01')} already has one.",
                "Update drafts replaces the whole BOM when the parent is a draft; after step "
                "4 the parent is approved, so it is blocked instead.",
                "Override approved deletes the old rows and writes these three.",
                "Removing a row from the BOM never deletes the part itself.",
            ],
        )
    )

    # ---------------------------------------------------------------- 09 --
    packs.append(
        Pack(
            order=9,
            slug="messy_pack",
            title="A messy pack: duplicates, orphans and conflicts",
            story=(
                "Real exports are not tidy. This pack carries a virtual component "
                "that collapses onto an existing part number, a deliverable for a "
                "part that is not in the BOM, a file name the importer cannot "
                "resolve, and a row whose approval columns contradict each other."
            ),
            rows=[
                builder.story_row("P02", description="HITCH PLATE A"),
                # SolidWorks exports virtual components as PN^parent; both rows
                # resolve to the same identity, so the operator picks a winner.
                builder.story_row(
                    "P02",
                    partnumber=f"{pn('P02')}^{pn('F01')}",
                    description="HITCH PLATE A (virtual copy)",
                ),
                # approved=Yes and is_approved=No cannot both be true.
                builder.story_row("P03", is_approved="No"),
                # Two aliases of the same logical field disagreeing.
                builder.story_row("P01", mass="9.2", Weight="11.4"),
                builder.story_row("F01"),
            ],
            tree=[
                ("1", pn("F01"), rev("F01"), 1),
                ("1.1", pn("P01"), rev("P01"), 1),
                ("1.2", pn("P02"), rev("P02"), 1),
                ("1.3", pn("P03"), rev("P03"), 2),
            ],
            files={
                # No BOM row for P99 → reported and skipped, never invented.
                f"deliverables/png/{builder.prefix}P99_REV_A.png": _deliverable(
                    "png", "CV03-TR-06_REV_B.png"
                ),
                # No _REV_ marker → the importer cannot tell whose file it is.
                "deliverables/png/general-arrangement.png": _deliverable(
                    "png", "CV03-F01_REV_A.png"
                ),
                # Everything after _REV_ is the revision, so this is a file for a
                # revision that does not exist rather than a second sheet.
                f"deliverables/pdf/{stem('P01')}_SHEET2.pdf": _deliverable(
                    "pdf", "CV03-TR-03_REV_B.pdf"
                ),
            },
            expectations=[
                "The preview keeps the first duplicate row, warns about the clash and "
                "offers a chooser; pick the other row and preview again to see it swap.",
                "Three warnings appear: an orphan deliverable, an unresolvable file name and "
                "a file whose revision does not exist.",
                f"{pn('P03')} shows 'Incoming approval aliases conflict' and its approval is "
                "blocked under every policy.",
                f"{pn('P01')} keeps the first mass value and reports the ignored alias.",
            ],
        )
    )

    # ---------------------------------------------------------------- 10 --
    packs.append(
        Pack(
            order=10,
            slug="blank_approval_columns",
            title="The trap: blank approval columns under Override",
            story=(
                "The same parts, re-exported from a CAD file whose approval "
                "properties were never written back, so every approval column "
                "is empty. Under Fill only and Update drafts that is harmless. "
                "Under Override approved an empty column wins like any other "
                "value — and the approval is stripped off the part."
            ),
            rows=[
                builder.row(key, only=("description",))
                for key in ("P01", "P02", "P03", "F01")
            ],
            tree=[
                ("1", pn("F01"), rev("F01"), 1),
                ("1.1", pn("P01"), rev("P01"), 1),
                ("1.2", pn("P02"), rev("P02"), 1),
                ("1.3", pn("P03"), rev("P03"), 2),
            ],
            expectations=[
                "Preview with Fill only: the approval rows read 'skipped'. Nothing at risk.",
                "Preview with Update drafts: the approval rows read 'blocked', because the "
                "targets are approved.",
                "Preview with Override approved: 'Approved' changes to No and the approver "
                "and date are cleared. Read those rows before applying anything.",
                "If you do apply it, re-run step 4 with Update drafts to sign the parts "
                "again — they are drafts now, so that is allowed.",
                "The lesson: an override run is only as safe as the columns in the pack.",
            ],
        )
    )

    return packs


def _out_of_band_files(builder: Builder) -> dict[str, bytes]:
    """Files to drop straight into the deliverables root for step 7."""

    return {
        f"step/{builder.stem('P02')}.step": _deliverable("step", "CV03-TR-03_REV_B.step"),
        f"3mf/{builder.stem('P03')}.3mf": _deliverable("3mf", "CV03-TR-06_REV_B.3mf"),
    }


def _readme(builder: Builder, packs: list[Pack]) -> str:
    lines = [
        "# Import policy exercise packs",
        "",
        "Generated by `tools/make_import_test_packs.py` from the CV03-TR-A01 sample",
        f"fixture. Every part number is prefixed `{builder.prefix}` so the exercise",
        "cannot collide with real data.",
        "",
        "Upload them **in order** on the Import page, previewing before every apply.",
        "The full explanation of what each policy does lives in the app help,",
        "chapter *Import: what each policy actually does*.",
        "",
        "| Step | Pack | What it is |",
        "| --- | --- | --- |",
    ]
    for pack in packs:
        lines.append(f"| {pack.order} | `{pack.filename}` | {pack.title} |")
    lines += [
        "",
        "## Cast",
        "",
        "| Part | Revision | Role | Data from |",
        "| --- | --- | --- | --- |",
    ]
    for spec in CAST:
        lines.append(
            f"| `{builder.pn(spec.key)}` | {spec.revision or '(none)'} | {spec.role} | {spec.source} |"
        )
    lines += ["", "## Steps", ""]
    for pack in packs:
        lines += [f"### {pack.order}. {pack.title}", "", pack.story, ""]
        lines += [f"- {item}" for item in pack.expectations]
        lines.append("")
    lines += [
        "## out_of_band/",
        "",
        "Copy this folder's contents into the deliverables root (`FILES_LOCAL_ROOT`,",
        "keeping the group sub-folders) **before** step 7. It stands in for a file a",
        "supplier emailed you and someone dropped on the share: step 7 finds it by",
        "scanning storage and creates the file record for it.",
        "",
        "## Cleaning up",
        "",
        f"Every part created by this exercise starts with `{builder.prefix}`. Search that",
        "prefix in Inventory to review or remove them when you are done.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--prefix",
        default="IMPTEST-",
        help="Part-number prefix that keeps the exercise away from real data.",
    )
    parser.add_argument("--clean", action="store_true", help="Empty the output folder first.")
    args = parser.parse_args()

    builder = Builder(args.prefix)
    out_dir: Path = args.out
    if args.clean and out_dir.exists():
        shutil.rmtree(out_dir)
    (out_dir / "out_of_band").mkdir(parents=True, exist_ok=True)

    packs = build_packs(builder)
    written = []
    for pack in packs:
        path = builder.write(pack, out_dir)
        written.append({"pack": path.name, "bytes": path.stat().st_size, "title": pack.title})

    for name, payload in _out_of_band_files(builder).items():
        target = out_dir / "out_of_band" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)

    (out_dir / "README.md").write_text(_readme(builder, packs), encoding="utf-8")
    (out_dir / "index.json").write_text(
        json.dumps(
            {
                "prefix": builder.prefix,
                "parts": [
                    {
                        "part_number": builder.pn(spec.key),
                        "revision": spec.revision,
                        "role": spec.role,
                        "source": spec.source,
                    }
                    for spec in CAST
                ],
                "packs": [
                    {
                        "order": pack.order,
                        "file": pack.filename,
                        "title": pack.title,
                        "story": pack.story,
                        "expectations": pack.expectations,
                    }
                    for pack in packs
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps({"out": str(out_dir), "packs": written}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
