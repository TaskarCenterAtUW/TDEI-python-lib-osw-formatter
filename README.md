
# TDEI python lib formatter library  
  
The "OSM to OSW Converter" is a python package designed to convert geospatial data from one format to another. In this case, it converts data from OpenStreetMap (OSM) format to OpenStreetMap Water (OSW) format. Let's break down the key components and processes involved in this converter:  
  

 1. **OpenStreetMap (OSM):** OSM is a collaborative project that creates a free, editable map of the world, often referred to as the "Wikipedia of Maps." It contains a vast amount of geographic data contributed by users worldwide, including information about roads, buildings, parks, rivers, and other features.
 2. **OpenStreetMap Water (OSW):** OSW is a specific format or schema designed for water network data, such as rivers, lakes, reservoirs, and related features. It's a structured format optimized for representing water-related geographic information.
 3. **Converter Purpose:** The OSM to OSW Converter is created to transform data originally stored in OSM format into the specialized OSW format. This conversion allows for more efficient storage, querying, and analysis of water-related features within the geospatial dataset.  
 4. **Input Data:** The converter typically takes OSM data as its input. OSM data can be in the form of OSM files (PBF binary format), which contain geographic elements, their attributes, and relationships.  
 5. **Output Data:** The result of the conversion is OSW data. This output is a representation of geographic features using the OSW schema. The OSW format might have specific attributes and structures points, nodes and edges.  


## System requirements

| Software | Version |
|----------|---------|
| Python   | 3.10.x  |


## What this package does?

- It takes the `pbf` file and output directory path(optional) as input
- Process the pbf file
- Convert the pbf file into edges.geojson, points.geojson and nodes.geojson files at provided output directory path
  

## Starting a new project with template

- Add `osm-osw-reformatter` package as dependency in your `requirements.txt`
- or `pip install osm-osw-reformatter`
- Start using the packages in your code.
  

```python
from osm-osw-reformatter import Formatter

async def main():
    formatter = Formatter(workdir=<OUTPUT_DIR_PATH>, pbf_file=<PBF_FILE_PATH>)
    await formatter.osm2osw()

```


### Testing

The project is configured with `python` to figure out the coverage of the unit tests. All the tests are in `tests`
folder.

- To execute the tests, please follow the commands:

  `pip install -r requirements.txt`

  `python -m unittest discover -v tests/unit_tests`

- To execute the code coverage, please follow the commands:

  `coverage run --source=src -m unittest discover -v tests/unit_tests`

  `coverage html` // Can be run after 1st command

  `coverage report` // Can be run after 1st command

- After the commands are run, you can check the coverage report in `htmlcov/index.html`. Open the file in any browser,
  and it shows complete coverage details
- The terminal will show the output of coverage like this

```shell

>  coverage run --source=src -m unittest discover -v tests/unit_tests
test_construct_geometries (helpers.test_osm.TestOSMHelper) ... ok
test_count_entities_with_nodes_counter (helpers.test_osm.TestOSMHelper) ... ok
test_count_entities_with_points_counter (helpers.test_osm.TestOSMHelper) ... ok
test_count_entities_with_ways_counter (helpers.test_osm.TestOSMHelper) ... ok
test_get_osm_graph (helpers.test_osm.TestOSMHelper) ... ok
test_osw_node_filter (helpers.test_osm.TestOSMHelper) ... ok
test_osw_point_filter (helpers.test_osm.TestOSMHelper) ... ok
test_osw_way_filter (helpers.test_osm.TestOSMHelper) ... ok
test_simplify_og (helpers.test_osm.TestOSMHelper) ... ok
test_construct_geometries (helpers.test_osw.TestOSWHelper) ... ok
test_count_entities_with_nodes_counter (helpers.test_osw.TestOSWHelper) ... ok
test_count_entities_with_points_counter (helpers.test_osw.TestOSWHelper) ... ok
test_count_entities_with_ways_counter (helpers.test_osw.TestOSWHelper) ... ok
test_count_nodes (helpers.test_osw.TestOSWHelper) ... ok
test_count_points (helpers.test_osw.TestOSWHelper) ... ok
test_count_ways (helpers.test_osw.TestOSWHelper) ... ok
test_get_osm_graph (helpers.test_osw.TestOSWHelper) ... ok
test_osw_node_filter (helpers.test_osw.TestOSWHelper) ... ok
test_osw_point_filter (helpers.test_osw.TestOSWHelper) ... ok
test_osw_way_filter (helpers.test_osw.TestOSWHelper) ... ok
test_simplify_og (helpers.test_osw.TestOSWHelper) ... ok
test_osm2osw_error (test_formatter.TestFormatter) ... Estimating number of ways, nodes and points in datasets...
Open failed for 'test.pbf': No such file or directory
ok
test_osm2osw_successful (test_formatter.TestFormatter) ... Estimating number of ways, nodes and points in datasets...
Creating networks from region extracts...
Created OSW files!
ok
test_workdir_already_exists (test_formatter.TestFormatter) ... ok
test_workdir_creation (test_formatter.TestFormatter) ... ok
test_convert_error (test_osm2osw.test_osm2osw.TestOSM2OSW) ... Estimating number of ways, nodes and points in datasets...
Open failed for 'test.pbf': No such file or directory
ok
test_convert_successful (test_osm2osw.test_osm2osw.TestOSM2OSW) ... Estimating number of ways, nodes and points in datasets...
Creating networks from region extracts...
Created OSW files!
ok
test_crossing (test_serializer.test_osw_normalizer.TestCommonFunctions) ... ok
test_crossing_markings (test_serializer.test_osw_normalizer.TestCommonFunctions) ... ok
test_incline (test_serializer.test_osw_normalizer.TestCommonFunctions) ... ok
test_surface (test_serializer.test_osw_normalizer.TestCommonFunctions) ... ok
test_tactile_paving (test_serializer.test_osw_normalizer.TestCommonFunctions) ... ok
test_is_kerb (test_serializer.test_osw_normalizer.TestOSWNodeNormalizer) ... ok
test_is_kerb_invalid (test_serializer.test_osw_normalizer.TestOSWNodeNormalizer) ... ok
test_normalize_invalid_node (test_serializer.test_osw_normalizer.TestOSWNodeNormalizer) ... ok
test_normalize_kerb (test_serializer.test_osw_normalizer.TestOSWNodeNormalizer) ... ok
test_is_powerpole (test_serializer.test_osw_normalizer.TestOSWPointNormalizer) ... ok
test_is_powerpole_invalid (test_serializer.test_osw_normalizer.TestOSWPointNormalizer) ... ok
test_normalize_invalid_point (test_serializer.test_osw_normalizer.TestOSWPointNormalizer) ... ok
test_normalize_powerpole (test_serializer.test_osw_normalizer.TestOSWPointNormalizer) ... ok
test_is_crossing (test_serializer.test_osw_normalizer.TestOSWWayNormalizer) ... ok
test_is_cycleway (test_serializer.test_osw_normalizer.TestOSWWayNormalizer) ... ok
test_is_footway (test_serializer.test_osw_normalizer.TestOSWWayNormalizer) ... ok
test_is_living_street (test_serializer.test_osw_normalizer.TestOSWWayNormalizer) ... ok
test_is_path (test_serializer.test_osw_normalizer.TestOSWWayNormalizer) ... ok
test_is_pedestrian (test_serializer.test_osw_normalizer.TestOSWWayNormalizer) ... ok
test_is_sidewalk (test_serializer.test_osw_normalizer.TestOSWWayNormalizer) ... ok
test_is_stairs (test_serializer.test_osw_normalizer.TestOSWWayNormalizer) ... ok
test_is_traffic_island (test_serializer.test_osw_normalizer.TestOSWWayNormalizer) ... ok
test_normalize_crossing (test_serializer.test_osw_normalizer.TestOSWWayNormalizer) ... ok
test_normalize_invalid_way (test_serializer.test_osw_normalizer.TestOSWWayNormalizer) ... ok
test_normalize_sidewalk (test_serializer.test_osw_normalizer.TestOSWWayNormalizer) ... ok

----------------------------------------------------------------------
Ran 52 tests in 12.610s

OK

```