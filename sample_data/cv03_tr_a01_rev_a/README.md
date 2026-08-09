# CV03 trailer sample dataset

This is TinyMRP's canonical engineering sample for help captures, demo records,
upload/import testing, doc packs, drawing markups, downloads, and 3D previews.
The repository owner selected `CV03-TR-A01` revision `A` and its BOM children
for this purpose on 2026-08-09. Do not add unrelated engineering data here.

`managed/` mirrors the configured TinyMRP deliverables root for the assembly
and all descendants named by its BOM (494 files across 60 exact part/revision
identities). The BOM ZIP is the
owner-supplied export originally placed at
`app/static/misc/CV03-TR-A01_REV_A_2026_07_11_16_41_58.zip`; it contains one
FLATBOM and one TREEBOM file. `manifest.json` records every fixture file's size
and SHA-256 digest so accidental substitutions are detected.

Use `python tools/install_sample_dataset.py --destination <deliverables-root>`
to copy missing files into an isolated development/test deliverables root. The
installer does not overwrite existing files unless `--overwrite` is supplied.
It never modifies MongoDB; the permission-test seeder adds the corresponding
sample part/BOM, approval, review, and business records separately. All sample
family parts are released by `TinyManager` so restricted demo roles can see
the exact items exposed through their linked jobs and orders.
