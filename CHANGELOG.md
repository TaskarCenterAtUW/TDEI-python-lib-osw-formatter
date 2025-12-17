# Change log

### 0.3.0
- Update converters to emit OSW 0.3 schema id and support new vegetation features (trees, tree rows, woods).
- Extend OSW normalizers to keep `leaf_cycle` and `leaf_type` where allowed for points, lines, and polygons.
- Add unit coverage for OSW 0.3 natural feature handling.
- Expand OSM normalizer coverage and robustness: preserve non-compliant/unknown tags as `ext:*`, canonicalize JSON ext values, normalize elevation from 3D geometries, tolerate string IDs, and harden edge-case handling with tests.
- OSW→OSM improvements: promote invalid/unknown fields (incl. dict/list) to `ext:*`, set `version="1"` for visible elements, derive `ext:elevation` from Z coords, and keep invalid incline/climb values under `ext:` instead of dropping them.
- OSM→OSW improvements: verify OSW 0.3 `$schema` headers, export tree/tree_row/wood features, and add multi-exterior handling tests for zones/polygons plus line parsing guards.
- Added extensive unit tests for osm/osw normalizers and graph serializers (filters, geojson import/export, zebra crossing mapping, kerb/foot validators, invalid line/polygon/zone branches, ref normalization, etc.).
- Added fixtures for vegetation and 3D elevation scenarios (`tree-test.xml`) and custom-property round-trip checks.

### 0.2.13
- Added default `version="1"` attribute to all nodes, ways, and relations generated during OSW→OSM conversion.
- Introduced unit test coverage to verify version attributes are written for all OSM elements.

### 0.2.12
- Updated OSMTaggedNodeParser to apply the OSW node and point filters with normalization before adding loose tagged nodes, ensuring non-compliant features like crossings are no longer emitted.
- Extended serializer tests to cover the new tagged-node behavior, confirming that compliant kerb features are retained while schema-invalid crossings are skipped.
- Updated GeoJSON node export to normalize IDs, retain full OSM identifiers, and skip non-OSW features so schema-invalid crossings are no longer emitted.
- Ensured only synthetic node IDs have their prefix trimmed, fixing the prior bug where numeric IDs lost the leading digit and caused _id/ext:osm_id mismatches.
- Expanded serializer tests to cover OSW-compliant node export, rejection of non-compliant crossings, and prefix handling for generated point IDs. 
- Refined GeoJSON export to filter nodes using tag-only metadata, preventing schema-invalid features from being emitted.
- Normalized ext:osm_id handling to preserve full numeric identifiers while trimming prefixed synthetic values.


### 0.2.11
- Retain numeric `incline` values and new `length` tags during way normalization
- Recognize any `highway=steps` way as stairs, preserving valid `climb` tags
- Add compliance test verifying `incline` survives OSW→OSM→OSW roundtrips

### 0.2.10
- Removed `climb` tag generation from OSM normalizer

### 0.2.9
- Retain existing `incline` and `climb` tags when converting OSW to OSM
- Add `climb` tag when missing and `incline` is provided
- Expanded unit tests for incline/climb handling

### 0.2.8
- Fixed [BUG 2040](https://dev.azure.com/TDEI-UW/TDEI/_workitems/edit/2040)
- Removing the width tag if the width is not float or integer
- Added unit test cases

### 0.2.7
- Fixed [BUG 1654](https://dev.azure.com/TDEI-UW/TDEI/_workitems/edit/1654)
- Added functionality to retain the `ext` tags
## Unit Tests
- Verified all output files are valid GeoJSON FeatureCollections
- Ensured `nodes` files contain only Point geometries
- Validated that all feature `_id` properties are strings
- Asserted no features are missing geometry or coordinates
- Checked that no duplicate `_id` values exist within any generated file

### 0.2.6
- Added unit test cases
- Added unit test cases pipeline
- Added support to upload test cases results on Azure blob

### 0.2.5
- Fixes XML Parsing issue

### 0.2.4
- Fixes MemoryError issue

### 0.2.3
- Fixes dependencies

### 0.2.2
- Fixes the issues with multiple files generated during the conversion.

### 0.2.1
- Adds support for OSM.XML in addition to OSM.PBF file format


### 0.2.0
- Added internal extensions (lines, zones and polygons)
- Made all OSW files optional
- Filter areas out of edges
- Remove osm_id tag from nodes and points
- Add one character prefix to extension id's to avoid collisions
- Create a zone/polygon entity for each exterior and include interiors of each polygon
- Fix bug in circular ways where edges did not meet end-to-end
- Remove internal nodes which serve no purpose
- Add _id to edges
- Update OSM Normalizer: No need to manipulate tactile_paving, remove OSW generated fields
- Update OSW Normalizer: bring normalizer a step close to being based of schema file, update normalizer to OSW 0.2


### 0.0.3
- Added init files
- Added prefix


### 0.0.2
- Introduces OSW to OSM convertor which converts OSW(geojson) files to OSM(xml) format.
- Added example.py file which demonstrate how to use the package
- Updated README.md file
- Updated CHANGELOG.md file
- Added dependencies to requirements.txt


### 0.0.1
- Introduces OSM to OSW convertor which converts OSM(pbf) file to OSW format.
- Added example.py file which demonstrate how to use the package
- Added unit test cases
- Added README.md file
- Added CHANGELOG.md file
- Added test.pypi pipeline
