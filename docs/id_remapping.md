# ID Remapping (OSW → OSM)

This document explains how IDs are generated and remapped when converting OSW (GeoJSON) to OSM XML.

## Goal
Produce collision-free OSM XML where all node/way/relation IDs are sequential per type (starting at 1) and all references are updated accordingly, while preserving OSW identifiers in `_id` tags.

## Process
1. **Initial IDs from OSW content**
   - Nodes/points/lines/zones/polygons parsed from OSW GeoJSON enter the OSM graph with their OSW `_id`/references.
   - Extension/unknown properties are preserved under `ext:*`; elevation from 3D coordinates becomes `ext:elevation`.

2. **OSW→OSM export**
   - `OSW2OSM.convert()` runs the normal ogr2osm pipeline, writing an OSM XML file.
   - `_ensure_version_attribute` ensures all elements have `version="1"` (visible elements get it if missing).

3. **Sequential remap**
   - After the XML is written, `_remap_ids_to_sequential` rewrites IDs and references:
     - Nodes are renumbered `1..N` in document order; their `_id` tags are updated to the new ID.
     - Ways are renumbered `1..M`; their `_id` tags are updated. All `<nd ref>` values are rewritten to the new node IDs.
     - Relations are renumbered `1..K`; their `_id` tags are updated. All `<member ref>` values are rewritten based on member `type` (node/way/relation) using the new ID maps.
   - The remap runs in-place on the XML so the final output has consistent, collision-free IDs and references.

4. **What remains**
   - Original OSW identifiers survive in other tags (e.g., `ext:osm_id` if provided, other `ext:*`), but `_id` reflects the new sequential OSM ID.

## Notes / rationale
- The remap ensures deterministic, collision-free IDs regardless of source naming schemes (e.g., OSW prefixes, extension data).
- Reference integrity is maintained by rewriting all node refs in ways and member refs in relations.
- Version attributes are normalized before remapping to satisfy OSM validators expecting `version`.

## Minimal example (what the remap does)
Input XML (simplified):
```xml
<osm>
  <node id="10" lat="0" lon="0"><tag k="_id" v="10"/></node>
  <node id="20" lat="1" lon="1"><tag k="_id" v="20"/></node>
  <way id="30">
    <nd ref="10"/><nd ref="20"/>
    <tag k="_id" v="30"/>
  </way>
  <relation id="40">
    <member type="node" ref="20"/>
    <member type="way" ref="30"/>
    <tag k="_id" v="40"/>
  </relation>
</osm>
```

After `_remap_ids_to_sequential`:
```xml
<osm>
  <node id="1" ...><tag k="_id" v="1"/></node>
  <node id="2" ...><tag k="_id" v="2"/></node>
  <way id="1">
    <nd ref="1"/><nd ref="2"/>
    <tag k="_id" v="1"/>
  </way>
  <relation id="1">
    <member type="node" ref="2"/>
    <member type="way" ref="1"/>
    <tag k="_id" v="1"/>
  </relation>
</osm>
```
All IDs now start at 1 per type, and every reference points to the remapped IDs.

## Relevant code
- Entry point: `OSW2OSM.convert()` (`src/osm_osw_reformatter/osw2osm/osw2osm.py`)
  - Calls `_ensure_version_attribute`
  - Calls `_remap_ids_to_sequential`
- Remap implementation: `_remap_ids_to_sequential` in `osw2osm.py` rewrites element IDs and their refs in-place and updates `_id` tags.
