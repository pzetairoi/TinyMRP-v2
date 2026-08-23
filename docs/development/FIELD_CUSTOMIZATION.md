# Field customisation architecture

## Goal

TinyMRP maps application fields to core part fields or imported attributes,
lets administrators control the fields available to each screen/export, and
lets users choose within those limits. Code defaults always provide a stable
reset point.

## Implemented model

`app/services/field_config.py` owns the built-in field catalogue, default source
mappings and per-context defaults. Administrators can manage labels, source
paths, custom fields and the allowed/default sets. Users can choose visible
fields only from the administrator-approved set.

Current contexts are:

- `parts_list`
- `part_detail_summary`
- `bom_tree`
- `where_used`
- `excel_bom`

Doc packs resolve configured description, material, finish and mass fields
through the same layer. Excel BOM export accepts a selected field list and
falls back to the administrator default.

## Design constraint

Do not duplicate field-resolution logic in individual pages or exports. New
consumers use the shared schema/configuration layer so imported schemas can
evolve without breaking presentation or exports.
