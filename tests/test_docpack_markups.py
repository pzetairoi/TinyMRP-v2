import io
import zipfile

from PIL import Image
from PyPDF2 import PdfReader

from app.models.artifact import PartFile
from app.models.part import Part
from app.models.part_drawing_markup import PartDrawingMarkup
from app.services.docpacks import DocPackOptions, build_docpack
from app.services.markup_documents import markup_documents_for_pairs
from app.services.part_drawing_markups import source_fingerprint_for


def _markup_source(tmp_path):
    part = Part(part_number="MK-100", revision="A", description="Marked drawing").save()
    image_path = tmp_path / "MK-100.png"
    Image.new("RGB", (320, 180), "white").save(image_path)
    source = PartFile(
        part_number=part.part_number,
        revision=part.revision,
        ext_group="png",
        ext="png",
        is_dwg=True,
        rel_path="drawings/MK-100.png",
        path=str(image_path),
        sha256="markup-source-sha",
        size=float(image_path.stat().st_size),
    ).save()
    PartDrawingMarkup(
        part_number=part.part_number,
        revision=part.revision,
        source_file_id=str(source.id),
        source_rel_path=source.rel_path,
        source_fingerprint=source_fingerprint_for(source),
        canvas_json={
            "version": "7.4.0",
            "objects": [
                {
                    "type": "Rect",
                    "tmObjectId": "review-box",
                    "left": 50,
                    "top": 40,
                    "width": 100,
                    "height": 60,
                    "stroke": "#dc2626",
                    "strokeWidth": 4,
                    "fill": "",
                }
            ],
        },
        version=1,
    ).save()
    return part


def _options(**changes):
    values = {
        "root_pn": "MK-100",
        "root_rev": "A",
        "flat_override": [],
        "want_selected_files": False,
        "binder_add_cover": False,
        "binder_add_index": False,
        "binder_add_visual_list": False,
        "binder_add_hardware_summary": False,
        "binder_add_whereused": False,
        "binder_add_datasheets": False,
        "binder_page_numbers": False,
    }
    values.update(changes)
    return DocPackOptions(**values)


def test_markup_document_renderer_produces_a_pdf(app, tmp_path):
    _markup_source(tmp_path)
    with app.app_context():
        documents = markup_documents_for_pairs([("MK-100", "A")])

    assert len(documents) == 1
    assert documents[0].filename.endswith(".pdf")
    assert documents[0].pdf_bytes.startswith(b"%PDF")
    assert len(PdfReader(io.BytesIO(documents[0].pdf_bytes)).pages) == 1


def test_docpack_places_markup_documents_in_the_markups_folder(app, tmp_path):
    _markup_source(tmp_path)
    with app.test_request_context("/"):
        name, payload, mimetype = build_docpack(_options(want_markup_files=True))

    assert name.endswith(".zip")
    assert mimetype == "application/zip"
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        markup_names = [item for item in archive.namelist() if item.startswith("markups/")]
        assert len(markup_names) == 1
        assert archive.read(markup_names[0]).startswith(b"%PDF")


def test_docpack_can_return_markup_only_report_or_binder(app, tmp_path):
    _markup_source(tmp_path)
    with app.test_request_context("/"):
        report_name, report, report_type = build_docpack(_options(want_markup_report=True))
        binder_name, binder, binder_type = build_docpack(
            _options(want_pdf_binder=True, binder_add_markups=True)
        )

    assert "MarkupReport" in report_name
    assert report_type == "application/pdf"
    # The report leads with a binder-style index page listing the parts,
    # followed by one page per marked-up drawing.
    report_pages = PdfReader(io.BytesIO(report)).pages
    assert len(report_pages) == 2
    index_text = report_pages[0].extract_text() or ""
    assert "Markup Report" in index_text
    assert "MK-100" in index_text
    assert binder_name.endswith(".pdf")
    assert binder_type == "application/pdf"
    assert len(PdfReader(io.BytesIO(binder)).pages) == 1
