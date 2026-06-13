# Field Customization Design

## Goal

Allow TinyMRP to:

- map key application fields to either core part fields or imported `attrs` fields
- let admins control which fields are available and which defaults are active per screen/export
- let users choose the fields they want to see within the admin-defined limits
- keep a code-level default preset that can always be restored

## Comparison Baseline

This design follows the common pattern used by comparable systems:

- OpenBOM separates the product data model from user-defined views and export choices.
- Arena centers controlled item/BOM data and consistent field presentation across downstream outputs.
- Odoo separates administrator view configuration from user-level optional columns and export selection.

The practical conclusion is that field customization should not be hard-coded inside each page or export. It should be managed from one schema/config layer, then consumed by tables, detail pages, and exports.

## Implemented Model

### 1. System defaults

`app/services/field_config.py` defines:

- the built-in field catalog
- default source mappings
- default per-context allowed/default field sets

These defaults are immutable in code and can be restored through the admin reset action.

### 2. Admin configuration

Admins can manage:

- field labels
- source paths such as `part.description` or `attrs.material`
- custom fields
- allowed fields per context
- default fields per context

Current contexts:

- `parts_list`
- `part_detail_summary`
- `bom_tree`
- `where_used`
- `excel_bom`

### 3. User preferences

Users can choose visible fields for each context, but only from the admin-allowed set.

This keeps governance with the admin while still allowing practical per-user views.

## Export Behavior

- Doc pack logic now reads configurable key fields such as description/material/finish/mass from the shared resolver.
- Excel BOM export accepts a selected field list and falls back to the admin default preset when none is chosen.

## Why This Shape

This avoids three common problems:

1. duplicated field logic across parts/BOM/export code paths
2. breaking exports when imported JSON schemas evolve
3. losing a stable fallback when admins experiment with mappings

The result is one field schema, one admin control plane, one reset path, and multiple consumers.
