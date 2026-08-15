import io
import json
import zipfile

from app.services.import_practice_packs import Builder, build_bundle_bytes, build_packs


def test_build_packs_is_eleven_sequential_steps_with_unique_names():
    builder = Builder("IMPTEST-")
    packs = build_packs(builder)

    assert [pack.order for pack in packs] == list(range(1, 12))
    assert len({pack.filename for pack in packs}) == len(packs)
    for pack in packs:
        assert pack.filename == f"{pack.order:02d}_{pack.slug}.zip"


def test_a_custom_prefix_reaches_every_row_and_never_the_default():
    builder = Builder("DEMO-")
    packs = build_packs(builder)

    for pack in packs:
        for row in pack.rows:
            assert row["partnumber"].startswith("DEMO-")
            assert "IMPTEST-" not in row["partnumber"]


def test_build_bundle_bytes_is_a_complete_zip_of_zips():
    """The bundle the help download serves must open, and every pack in it
    must itself be a valid ZIP with real FLATBOM content."""

    data = build_bundle_bytes("IMPTEST-")
    bundle = zipfile.ZipFile(io.BytesIO(data))
    assert bundle.testzip() is None

    names = bundle.namelist()
    pack_names = [name for name in names if name.endswith(".zip")]
    assert len(pack_names) == 11

    index = json.loads(bundle.read("index.json"))
    assert index["prefix"] == "IMPTEST-"
    assert len(index["packs"]) == 11

    first = zipfile.ZipFile(io.BytesIO(bundle.read("01_engineering_release.zip")))
    assert first.testzip() is None
    flatbom = next(name for name in first.namelist() if name.endswith("_FLATBOM.txt"))
    rows = [json.loads(line) for line in first.read(flatbom).decode("utf-8").splitlines() if line.strip()]
    assert rows and all(row["partnumber"].startswith("IMPTEST-") for row in rows)
