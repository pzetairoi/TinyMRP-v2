from __future__ import annotations

import io
import stat
import struct
import warnings
import zipfile

import pytest

from app.services.upload_pack import (
    ArchiveLimitError,
    _policy_options,
    parse_import_package,
)


FLATBOM = b"{'partnumber':'LIMIT-1','revision':'A','description':'Safe'}\n"


def _archive(
    entries: list[tuple[str | zipfile.ZipInfo, bytes]],
    *,
    compression: int = zipfile.ZIP_DEFLATED,
) -> bytes:
    payload = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(payload, "w", compression=compression) as archive:
            for name, content in entries:
                archive.writestr(name, content)
    return payload.getvalue()


def _valid_archive(*entries: tuple[str | zipfile.ZipInfo, bytes]) -> bytes:
    return _archive([("bom/LIMIT_FLATBOM.txt", FLATBOM), *entries])


def _parse(app, payload: bytes, **limits):
    with app.app_context():
        app.config.update(limits)
        return parse_import_package(payload, "pack.zip", _policy_options())


def test_rejects_compressed_request_entry_total_and_count_limits(app):
    with pytest.raises(ArchiveLimitError, match="compressed size"):
        _parse(
            app,
            _archive([("large.bin", b"x" * (2 * 1024 * 1024))], compression=zipfile.ZIP_STORED),
            UPLOAD_PACK_MAX_ZIP_MB=1,
        )

    with pytest.raises(ArchiveLimitError, match="entry exceeds"):
        _parse(
            app,
            _valid_archive(("extra/LIMIT-1/A/large.txt", b"x" * (2 * 1024 * 1024))),
            UPLOAD_PACK_MAX_FILE_MB=1,
        )

    with pytest.raises(ArchiveLimitError, match="uncompressed size"):
        _parse(
            app,
            _valid_archive(
                ("extra/LIMIT-1/A/one.txt", b"a" * 600_000),
                ("extra/LIMIT-1/A/two.txt", b"b" * 600_000),
            ),
            UPLOAD_PACK_MAX_TOTAL_MB=1,
            UPLOAD_PACK_MAX_COMPRESSION_RATIO=100_000,
        )

    with pytest.raises(ArchiveLimitError, match="entry count"):
        _parse(
            app,
            _valid_archive(
                ("extra/LIMIT-1/A/one.txt", b"1"),
                ("extra/LIMIT-1/A/two.txt", b"2"),
            ),
            UPLOAD_PACK_MAX_FILES=2,
        )


def test_rejects_high_compression_ratio_without_large_fixture(app):
    payload = _valid_archive(("extra/LIMIT-1/A/repeated.txt", b"A" * 256_000))

    with pytest.raises(ArchiveLimitError, match="compression ratio"):
        _parse(app, payload, UPLOAD_PACK_MAX_COMPRESSION_RATIO=10)


@pytest.mark.parametrize(
    "name",
    [
        "/absolute.txt",
        "C:/windows.txt",
        "extra/LIMIT-1/A/../escape.txt",
        "extra//LIMIT-1/A/empty-segment.txt",
        "extra/LIMIT-1/A/control\nname.txt",
    ],
)
def test_rejects_unsafe_or_ambiguous_paths(app, name):
    with pytest.raises(ValueError, match="unsafe or ambiguous"):
        _parse(app, _valid_archive((name, b"x")))


def test_rejects_long_duplicate_and_case_colliding_paths(app):
    with pytest.raises(ArchiveLimitError, match="path exceeds"):
        _parse(
            app,
            _valid_archive((f"extra/LIMIT-1/A/{'x' * 80}.txt", b"x")),
            UPLOAD_PACK_MAX_PATH_CHARS=40,
        )

    for entries in (
        [("same.txt", b"1"), ("same.txt", b"2")],
        [("Case.txt", b"1"), ("case.txt", b"2")],
    ):
        with pytest.raises(ValueError, match="duplicate or ambiguous"):
            _parse(app, _valid_archive(*entries))


def test_rejects_encrypted_links_and_unsupported_compression(app):
    encrypted = bytearray(_valid_archive())
    local = encrypted.find(b"PK\x03\x04")
    central = encrypted.find(b"PK\x01\x02")
    struct.pack_into("<H", encrypted, local + 6, struct.unpack_from("<H", encrypted, local + 6)[0] | 1)
    struct.pack_into("<H", encrypted, central + 8, struct.unpack_from("<H", encrypted, central + 8)[0] | 1)
    with pytest.raises(ValueError, match="encrypted"):
        _parse(app, bytes(encrypted))

    link = zipfile.ZipInfo("extra/LIMIT-1/A/link.txt")
    link.create_system = 3
    link.external_attr = (stat.S_IFLNK | 0o777) << 16
    with pytest.raises(ValueError, match="links"):
        _parse(app, _valid_archive((link, b"target")))

    with pytest.raises(ValueError, match="compression method"):
        _parse(
            app,
            _archive([("bom/LIMIT_FLATBOM.txt", FLATBOM)], compression=zipfile.ZIP_BZIP2),
        )


@pytest.mark.parametrize(
    ("path", "message"),
    [
        ("deliverables/pdf/LIMIT-1_REV_A.exe", "unsupported file type for pdf"),
        ("extra/LIMIT-1/A/payload.exe", "unsupported file type"),
    ],
)
def test_enforces_managed_and_associated_file_type_policy(app, path, message):
    with pytest.raises(ValueError, match=message):
        _parse(app, _valid_archive((path, b"payload")))


def test_requires_zip_filename(app):
    with app.app_context(), pytest.raises(ValueError, match=r"must be a \.zip"):
        parse_import_package(_valid_archive(), "pack.bin", _policy_options())
