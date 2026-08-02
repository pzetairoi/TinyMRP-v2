from __future__ import annotations

import io
from importlib.metadata import version

import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError

from app.services.docpacks import _merge_pdfs
from app.services.markup_documents import MarkupDocument, combine_markup_documents
from app.services.order_scope import _merge_pdf_bytes, _merge_pdf_paths


def _pdf_bytes(page_count: int, *, outline_title: str | None = None) -> bytes:
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=612, height=792)
    if outline_title:
        writer.add_outline_item(outline_title, 0)
    output = io.BytesIO()
    writer.write(output)
    writer.close()
    return output.getvalue()


def _outline_titles(reader: PdfReader) -> list[str]:
    return [str(item.title) for item in reader.outline if hasattr(item, "title")]


def test_current_pypdf_reader_writer_and_docpack_merge_preserve_outlines(tmp_path):
    assert version("pypdf") == "6.14.2"

    first = tmp_path / "first.pdf"
    crafted = tmp_path / "crafted.pdf"
    second = tmp_path / "second.pdf"
    first.write_bytes(_pdf_bytes(2, outline_title="First document"))
    crafted.write_bytes(b"%PDF-1.7\ntruncated")
    second.write_bytes(_pdf_bytes(1, outline_title="Second document"))

    merged, starts = _merge_pdfs([str(first), str(crafted), str(second)])

    reader = PdfReader(io.BytesIO(merged))
    assert starts == [1, 3]
    assert len(reader.pages) == 3
    assert _outline_titles(reader) == ["First document", "Second document"]


def test_order_path_merge_skips_invalid_pdf_without_offset_drift(tmp_path):
    first = tmp_path / "first.pdf"
    crafted = tmp_path / "crafted.pdf"
    second = tmp_path / "second.pdf"
    first.write_bytes(_pdf_bytes(2))
    crafted.write_bytes(
        b"%PDF-1.7\n1 0 obj\n<< /Length 999999999 /Filter /FlateDecode >>\nstream\nx"
    )
    second.write_bytes(_pdf_bytes(1))

    merged, starts = _merge_pdf_paths([str(first), str(crafted), str(second)])

    assert starts == [1, 3]
    assert len(PdfReader(io.BytesIO(merged)).pages) == 3


def test_order_byte_merge_skips_truncated_pdf_and_keeps_valid_segments():
    merged = _merge_pdf_bytes(
        [
            _pdf_bytes(1),
            b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
            _pdf_bytes(2),
        ]
    )

    assert len(PdfReader(io.BytesIO(merged)).pages) == 3


def test_markup_document_combine_uses_pypdf_reader_writer_with_index():
    documents = [
        MarkupDocument("PART-1", "A", "first.pdf", _pdf_bytes(1)),
        MarkupDocument("PART-2", "B", "second.pdf", _pdf_bytes(2)),
    ]

    merged = combine_markup_documents(documents, include_index=True, root_label="Assembly")
    reader = PdfReader(io.BytesIO(merged))

    assert len(reader.pages) == 4
    assert "Markup Report" in (reader.pages[0].extract_text() or "")


def test_markup_document_combine_rejects_crafted_truncated_pdf():
    crafted = MarkupDocument(
        "PART-BAD",
        "A",
        "crafted.pdf",
        b"%PDF-1.7\n1 0 obj\n<< /Length 999999999 >>\nstream\n",
    )

    with pytest.raises(PdfReadError):
        combine_markup_documents([crafted], include_index=False)
