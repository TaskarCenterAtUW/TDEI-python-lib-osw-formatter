# Change log

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