import asyncio
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET

from src.osm_osw_reformatter.config import FormatterConfig
from src.osm_osw_reformatter.helpers.osw import OSWHelper
from src.osm_osw_reformatter.helpers.output_validation import (
    EMPTY_OSM_XML_ERROR,
    NO_GENERATED_FILES_ERROR,
)
from src.osm_osw_reformatter.osm2osw.osm2osw import OSM2OSW
from src.osm_osw_reformatter.osw2osm.osw2osm import OSW2OSM
from src.osm_osw_reformatter.serializer.osm.osm_graph import OSMGraph, OSMWayParser


FIXTURE_DIR = Path(__file__).parents[1] / "test_files" / "zero_length_geometry"
OSM_FIXTURE_DIR = FIXTURE_DIR / "osm"
OSW_FIXTURE_DIR = FIXTURE_DIR / "osw"
INPUT_FIXTURE_DIR = FIXTURE_DIR.parent / "input_validation"
ZERO_LENGTH_EDGE_ZIP = INPUT_FIXTURE_DIR / "zero_length_edge.zip"
ZERO_LENGTH_EDGE_ONLY_ZIP = INPUT_FIXTURE_DIR / "zero_length_edge_only.zip"
ZERO_LENGTH_EDGE_TWO_NODES_ZIP = INPUT_FIXTURE_DIR / "zero_length_edge_two_nodes.zip"
ZERO_LENGTH_EDGE_BARE_NODES_ZIP = INPUT_FIXTURE_DIR / "zero_length_edge_bare_nodes.zip"
ZERO_LENGTH_WAY_OSM = INPUT_FIXTURE_DIR / "zero_length_way.xml"
ZERO_LENGTH_WAY_ONLY_OSM = INPUT_FIXTURE_DIR / "zero_length_way_only.xml"
ZERO_LENGTH_WAY_TWO_NODES_OSM = INPUT_FIXTURE_DIR / "zero_length_way_two_nodes.xml"
ZERO_LENGTH_WAY_BARE_NODES_OSM = INPUT_FIXTURE_DIR / "zero_length_way_bare_nodes.xml"

# The fixtures below carry deliberately degenerate geometry, so they are fed
# to the converter with OSW input validation switched off.
NO_INPUT_VALIDATION = FormatterConfig(validate_input=False)
# Zero-length lines are kept by default; these fixtures cover the opt-out path
# where the formatter drops them or collapses them to points instead.
DROP_ZERO_LENGTH_LINES = FormatterConfig(allow_zero_length_lines=False)
DROP_ZERO_LENGTH_LINES_UNVALIDATED = FormatterConfig(
    allow_zero_length_lines=False,
    validate_input=False,
)


def _osm_fixture(filename):
    return str(OSM_FIXTURE_DIR / filename)


def _merge_osw_zip_dataset(zip_filename, output_dir, config=None):
    unzipped_files = OSWHelper.unzip(str(OSW_FIXTURE_DIR / zip_filename), output_dir)
    return OSWHelper.merge(unzipped_files, output_dir, "cleaned", config=config)


def _parse_osm_edges(filename, config=None):
    parser = OSMWayParser(OSWHelper.osw_way_filter, config=config)
    parser.apply_file(_osm_fixture(filename), locations=True)
    return parser.G


def _graph_from_osm(filename, config=None):
    osm_graph = OSMGraph.from_osm_file(
        _osm_fixture(filename),
        OSWHelper.osw_way_filter,
        OSWHelper.osw_node_filter,
        OSWHelper.osw_point_filter,
        OSWHelper.osw_line_filter,
        OSWHelper.osw_zone_filter,
        OSWHelper.osw_polygon_filter,
        config=config,
    )
    osm_graph.construct_geometries(config=config)
    return osm_graph


def _write_zip_dataset(output_dir, dataset_name, feature_collection):
    geojson_path = Path(output_dir) / f"{dataset_name}.geojson"
    with open(geojson_path, "w") as f:
        json.dump(feature_collection, f)
    zip_path = Path(output_dir) / f"{dataset_name}.zip"
    with zipfile.ZipFile(zip_path, "w") as zip_file:
        zip_file.write(geojson_path, arcname=f"{dataset_name}.geojson")
    geojson_path.unlink()
    return zip_path


class TestZeroLengthGeometryCleanup(unittest.TestCase):
    def test_osm2osw_duplicate_node_refs_are_skipped(self):
        graph = _parse_osm_edges("duplicate_node_refs_sidewalk.xml", config=DROP_ZERO_LENGTH_LINES)

        self.assertEqual(len(graph.edges), 0)

    def test_osm2osw_different_node_refs_with_identical_coordinates_are_skipped(self):
        graph = _parse_osm_edges("identical_coordinate_crossing.xml", config=DROP_ZERO_LENGTH_LINES)

        self.assertEqual(len(graph.edges), 0)

    def test_osm2osw_allow_zero_length_lines_preserves_zero_length_edge(self):
        config = FormatterConfig(allow_zero_length_lines=True)

        graph = _parse_osm_edges("identical_coordinate_crossing.xml", config=config)

        self.assertEqual(len(graph.edges), 1)

    def test_osm2osw_zero_length_edge_is_preserved_by_default(self):
        graph = _parse_osm_edges("identical_coordinate_crossing.xml")

        self.assertEqual(len(graph.edges), 1)

    def test_osm2osw_valid_distinct_edge_is_preserved(self):
        graph = _parse_osm_edges("valid_sidewalk_edge.xml")

        self.assertEqual(len(graph.edges), 1)

    def test_osm2osw_collapsed_line_is_skipped(self):
        osm_graph = _graph_from_osm("collapsed_fence_line.xml", config=DROP_ZERO_LENGTH_LINES)

        self.assertNotIn("l700001", osm_graph.get_graph().nodes)

    def test_osm2osw_line_duplicate_consecutive_coordinates_are_cleaned(self):
        osm_graph = _graph_from_osm("tree_row_duplicate_coordinate_line.xml")

        coords = list(osm_graph.get_graph().nodes["l700002"]["geometry"].coords)
        self.assertEqual(coords, [(-122.34028, 47.67851), (-122.3401, 47.67872)])

    def test_osm2osw_zero_length_edge_preserves_tagged_node(self):
        osm_graph = _graph_from_osm("zero_length_edge_orphan_nodes.xml", config=DROP_ZERO_LENGTH_LINES)

        self.assertEqual(len(osm_graph.get_graph().edges), 0)
        self.assertEqual(len(osm_graph.get_graph().nodes), 1)
        node_data = next(iter(osm_graph.get_graph().nodes(data=True)))[1]
        self.assertEqual(node_data.get("ext:highway"), "footway")
        self.assertEqual(node_data.get("ext:footway"), "sidewalk")
        self.assertEqual(node_data.get("ext:surface"), "concrete")

    def test_osm2osw_zero_length_edge_writes_valid_custom_point_geojson(self):
        osm_graph = _graph_from_osm("zero_length_edge_orphan_nodes.xml", config=DROP_ZERO_LENGTH_LINES)
        with tempfile.TemporaryDirectory() as tmpdir:
            nodes_path = Path(tmpdir) / "nodes.geojson"
            edges_path = Path(tmpdir) / "edges.geojson"
            points_path = Path(tmpdir) / "points.geojson"
            lines_path = Path(tmpdir) / "lines.geojson"
            zones_path = Path(tmpdir) / "zones.geojson"
            polygons_path = Path(tmpdir) / "polygons.geojson"

            osm_graph.to_geojson(
                nodes_path,
                edges_path,
                points_path,
                lines_path,
                zones_path,
                polygons_path,
            )

            self.assertFalse(nodes_path.exists())
            with open(points_path) as f:
                points = json.load(f)

        self.assertEqual(len(points["features"]), 1)
        self.assertEqual(points["features"][0]["geometry"]["type"], "Point")
        self.assertNotIn("highway", points["features"][0]["properties"])
        self.assertNotIn("footway", points["features"][0]["properties"])
        self.assertNotIn("surface", points["features"][0]["properties"])
        self.assertEqual(points["features"][0]["properties"].get("ext:highway"), "footway")
        self.assertEqual(points["features"][0]["properties"].get("ext:footway"), "sidewalk")

    def test_osm2osw_collapsed_polygon_is_skipped(self):
        osm_graph = _graph_from_osm("collapsed_building_polygon.xml")

        polygon_nodes = [
            data for _, data in osm_graph.get_graph().nodes(data=True)
            if data.get("building") == "yes"
        ]
        self.assertEqual(polygon_nodes, [])

    def test_osm2osw_collapsed_zone_is_skipped(self):
        osm_graph = _graph_from_osm("collapsed_pedestrian_zone.xml")

        zone_nodes = [
            data for _, data in osm_graph.get_graph().nodes(data=True)
            if data.get("highway") == "pedestrian"
        ]
        self.assertEqual(zone_nodes, [])

    def test_osm2osw_allow_zero_length_lines_does_not_apply_to_zones(self):
        config = FormatterConfig(allow_zero_length_lines=True)

        osm_graph = _graph_from_osm("collapsed_pedestrian_zone.xml", config=config)

        zone_nodes = [
            data for _, data in osm_graph.get_graph().nodes(data=True)
            if data.get("highway") == "pedestrian"
        ]
        self.assertEqual(zone_nodes, [])

    def test_osw2osm_edge_duplicate_consecutive_coordinates_are_cleaned(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            merged_path = _merge_osw_zip_dataset("edge_duplicate_coordinates.zip", tmpdir)

            with open(merged_path) as f:
                merged = json.load(f)

        self.assertEqual(
            merged["features"][0]["geometry"]["coordinates"],
            [[-122.33581, 47.60972], [-122.33542, 47.60994]],
        )

    def test_osw2osm_zero_length_edge_is_converted_to_point(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            merged_path = _merge_osw_zip_dataset(
                "edge_zero_length.zip", tmpdir, config=DROP_ZERO_LENGTH_LINES
            )

            with open(merged_path) as f:
                merged = json.load(f)

        self.assertEqual(len(merged["features"]), 1)
        self.assertEqual(merged["features"][0]["geometry"]["type"], "Point")
        self.assertEqual(
            merged["features"][0]["geometry"]["coordinates"],
            [-122.33702, 47.61018],
        )

    def test_osw2osm_zero_length_line_is_converted_to_point(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            merged_path = _merge_osw_zip_dataset(
                "line_zero_length.zip", tmpdir, config=DROP_ZERO_LENGTH_LINES
            )

            with open(merged_path) as f:
                merged = json.load(f)

        self.assertEqual(len(merged["features"]), 1)
        self.assertEqual(merged["features"][0]["geometry"]["type"], "Point")
        self.assertEqual(
            merged["features"][0]["geometry"]["coordinates"],
            [-122.34562, 47.66105],
        )

    def test_osw2osm_allow_zero_length_lines_preserves_zero_length_line(self):
        config = FormatterConfig(allow_zero_length_lines=True)
        with tempfile.TemporaryDirectory() as tmpdir:
            merged_path = _merge_osw_zip_dataset(
                "line_zero_length.zip",
                tmpdir,
                config=config,
            )

            with open(merged_path) as f:
                merged = json.load(f)

        self.assertEqual(len(merged["features"]), 1)
        self.assertEqual(merged["features"][0]["geometry"]["type"], "LineString")

    def test_osw2osm_zero_length_line_is_preserved_by_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            merged_path = _merge_osw_zip_dataset("line_zero_length.zip", tmpdir)

            with open(merged_path) as f:
                merged = json.load(f)

        self.assertEqual(len(merged["features"]), 1)
        self.assertEqual(merged["features"][0]["geometry"]["type"], "LineString")

    def test_osw2osm_zero_area_polygon_is_converted_to_point(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            merged_path = _merge_osw_zip_dataset("polygon_zero_area.zip", tmpdir)

            with open(merged_path) as f:
                merged = json.load(f)

        self.assertEqual(len(merged["features"]), 1)
        self.assertEqual(merged["features"][0]["geometry"]["type"], "Point")
        self.assertEqual(
            merged["features"][0]["geometry"]["coordinates"],
            [-122.32070, 47.61201],
        )

    def test_osw2osm_zero_area_zone_is_converted_to_point(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            merged_path = _merge_osw_zip_dataset("zone_zero_area.zip", tmpdir)

            with open(merged_path) as f:
                merged = json.load(f)

        self.assertEqual(len(merged["features"]), 1)
        self.assertEqual(merged["features"][0]["geometry"]["type"], "Point")
        self.assertEqual(
            merged["features"][0]["geometry"]["coordinates"],
            [-122.33612, 47.60892],
        )

    def test_osw2osm_allow_zero_length_lines_does_not_apply_to_zones(self):
        config = FormatterConfig(allow_zero_length_lines=True)
        with tempfile.TemporaryDirectory() as tmpdir:
            merged_path = _merge_osw_zip_dataset(
                "zone_zero_area.zip",
                tmpdir,
                config=config,
            )

            with open(merged_path) as f:
                merged = json.load(f)

        self.assertEqual(len(merged["features"]), 1)
        self.assertEqual(merged["features"][0]["geometry"]["type"], "Point")

    def test_osw2osm_point_features_are_not_affected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            merged_path = _merge_osw_zip_dataset("point_valid.zip", tmpdir)

            with open(merged_path) as f:
                merged = json.load(f)

        self.assertEqual(len(merged["features"]), 1)
        self.assertEqual(merged["features"][0]["geometry"]["type"], "Point")

    def test_osw2osm_zero_length_line_zip_generates_osm_node_with_tags(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source_zip = OSW_FIXTURE_DIR / "line_zero_length.zip"
            zip_path = Path(tmpdir) / "line_zero_length.zip"
            with open(source_zip, "rb") as source, open(zip_path, "wb") as target:
                target.write(source.read())

            result = OSW2OSM(
                zip_file_path=str(zip_path),
                workdir=tmpdir,
                prefix="line",
                config=DROP_ZERO_LENGTH_LINES_UNVALIDATED,
            ).convert()

            self.assertTrue(result.status, msg=getattr(result, "error", "Conversion failed"))
            root = ET.parse(result.generated_files).getroot()
            nodes = root.findall(".//node")
            ways = root.findall(".//way")

        self.assertEqual(len(nodes), 1)
        self.assertEqual(len(ways), 0)
        tags = {tag.get("k"): tag.get("v") for tag in nodes[0].findall("tag")}
        self.assertEqual(tags.get("barrier"), "fence")
        self.assertEqual(tags.get("name"), "Aurora Avenue construction fence")

    def test_osm2osw_no_generated_files_returns_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = asyncio.run(
                OSM2OSW(
                    prefix="empty",
                    osm_file=_osm_fixture("collapsed_fence_line.xml"),
                    workdir=tmpdir,
                    config=DROP_ZERO_LENGTH_LINES,
                ).convert()
            )

        self.assertFalse(result.status)
        self.assertEqual(result.generated_files, [])
        self.assertEqual(result.error, NO_GENERATED_FILES_ERROR)

    def test_osw2osm_empty_osm_xml_returns_error(self):
        fc = {
            "$schema": "https://sidewalks.washington.edu/opensidewalks/0.3/schema.json",
            "type": "FeatureCollection",
            "features": [],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = _write_zip_dataset(tmpdir, "points", fc)

            result = OSW2OSM(
                zip_file_path=str(zip_path),
                workdir=tmpdir,
                prefix="empty",
                config=NO_INPUT_VALIDATION,
            ).convert()

        self.assertFalse(result.status)
        self.assertEqual(result.generated_files, None)
        self.assertEqual(result.error, EMPTY_OSM_XML_ERROR)

    def test_osw2osm_rejects_input_above_configured_coordinate_precision(self):
        fc = {
            "$schema": "https://sidewalks.washington.edu/opensidewalks/0.3/schema.json",
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [-122.33702012, 47.61018012],
                    },
                    "properties": {
                        "_id": "p-precision",
                        "barrier": "bollard",
                    },
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = _write_zip_dataset(tmpdir, "points", fc)

            result = OSW2OSM(
                zip_file_path=str(zip_path),
                workdir=tmpdir,
                prefix="precision",
            ).convert()

        self.assertFalse(result.status)
        self.assertIn("decimal places", result.error)

    def test_osw2osm_input_coordinate_precision_is_configurable(self):
        fc = {
            "$schema": "https://sidewalks.washington.edu/opensidewalks/0.3/schema.json",
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [-122.33702012, 47.61018012],
                    },
                    "properties": {
                        "_id": "p-precision",
                        "barrier": "bollard",
                    },
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = _write_zip_dataset(tmpdir, "points", fc)

            result = OSW2OSM(
                zip_file_path=str(zip_path),
                workdir=tmpdir,
                prefix="precision",
                config=FormatterConfig(coordinate_precision=8),
            ).convert()

        self.assertTrue(result.status, msg=result.error)

    def test_osw2osm_lone_zero_length_edge_becomes_exactly_one_node_and_one_way(self):
        """OSW e1 = (n0, n0), and nothing else, converts to OSM w1 = [n0, n0]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = OSW2OSM(
                zip_file_path=str(ZERO_LENGTH_EDGE_ONLY_ZIP),
                workdir=tmpdir,
                prefix="only",
            ).convert()

            self.assertTrue(result.status, msg=result.error)
            root = ET.parse(result.generated_files).getroot()

        nodes = root.findall(".//node")
        ways = root.findall(".//way")
        self.assertEqual(len(nodes), 1)
        self.assertEqual(len(ways), 1)

        refs = [nd.get("ref") for nd in ways[0].findall("nd")]
        self.assertEqual(refs, [nodes[0].get("id"), nodes[0].get("id")])

    def test_osw2osm_zero_length_edge_between_co_located_nodes_keeps_both(self):
        """e1 = (n0, n1) where n0 and n1 share a location stays w1 = [n0, n1]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = OSW2OSM(
                zip_file_path=str(ZERO_LENGTH_EDGE_TWO_NODES_ZIP),
                workdir=tmpdir,
                prefix="two_nodes",
            ).convert()

            self.assertTrue(result.status, msg=result.error)
            root = ET.parse(result.generated_files).getroot()

        nodes = root.findall(".//node")
        ways = root.findall(".//way")
        self.assertEqual(len(nodes), 2)
        self.assertEqual(len(ways), 1)

        # Identical geometry, so only the tags tell the two nodes apart.
        coordinates = {(node.get("lat"), node.get("lon")) for node in nodes}
        self.assertEqual(len(coordinates), 1)

        tags_by_id = {
            node.get("id"): {t.get("k"): t.get("v") for t in node.findall("tag")}
            for node in nodes
        }
        kerbs = [i for i, tags in tags_by_id.items() if tags.get("barrier") == "kerb"]
        self.assertEqual(len(kerbs), 1)
        self.assertEqual(tags_by_id[kerbs[0]].get("kerb"), "flush")

        # The way runs between the two distinct nodes, not twice through one.
        refs = [nd.get("ref") for nd in ways[0].findall("nd")]
        self.assertEqual(len(refs), 2)
        self.assertEqual(set(refs), set(tags_by_id))
        self.assertEqual(refs[0], kerbs[0], "The edge starts at the kerb node")

    def test_osw2osm_zero_length_edge_between_untagged_co_located_nodes_keeps_both(self):
        """e1 = (n0, n1) where both nodes are untagged and share a location."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = OSW2OSM(
                zip_file_path=str(ZERO_LENGTH_EDGE_BARE_NODES_ZIP),
                workdir=tmpdir,
                prefix="bare_nodes",
            ).convert()

            self.assertTrue(result.status, msg=result.error)
            root = ET.parse(result.generated_files).getroot()

        nodes = root.findall(".//node")
        ways = root.findall(".//way")
        self.assertEqual(len(nodes), 2)
        self.assertEqual(len(ways), 1)

        # Same location and nothing to tell them apart but their identity.
        coordinates = {(node.get("lat"), node.get("lon")) for node in nodes}
        self.assertEqual(len(coordinates), 1)

        node_ids = [node.get("id") for node in nodes]
        self.assertEqual(len(set(node_ids)), 2)

        refs = [nd.get("ref") for nd in ways[0].findall("nd")]
        self.assertEqual(len(refs), 2)
        self.assertEqual(set(refs), set(node_ids))

    def test_osw2osm_zero_length_edge_becomes_a_two_node_way(self):
        """OSW e1 = (n0, n0) must convert to OSM w1 = [n0, n0]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = OSW2OSM(
                zip_file_path=str(ZERO_LENGTH_EDGE_ZIP),
                workdir=tmpdir,
                prefix="zero_edge",
            ).convert()

            self.assertTrue(result.status, msg=result.error)
            root = ET.parse(result.generated_files).getroot()

        self_looping = [
            way for way in root.findall(".//way")
            if len({nd.get("ref") for nd in way.findall("nd")}) == 1
        ]
        self.assertEqual(len(self_looping), 1)

        refs = [nd.get("ref") for nd in self_looping[0].findall("nd")]
        self.assertEqual(len(refs), 2, "A zero-length way must keep both node references")
        self.assertEqual(refs[0], refs[1])

        tags = {tag.get("k"): tag.get("v") for tag in self_looping[0].findall("tag")}
        self.assertEqual(tags.get("highway"), "footway")
        self.assertEqual(tags.get("footway"), "sidewalk")

    def test_osw2osm_zero_length_edge_becomes_a_point_when_disallowed(self):
        """With zero-length lines disallowed the edge collapses to one node."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = OSW2OSM(
                zip_file_path=str(ZERO_LENGTH_EDGE_ZIP),
                workdir=tmpdir,
                prefix="zero_edge",
                config=FormatterConfig(
                    allow_zero_length_lines=False,
                    validate_input=False,
                ),
            ).convert()

            self.assertTrue(result.status, msg=result.error)
            root = ET.parse(result.generated_files).getroot()

        self_looping = [
            way for way in root.findall(".//way")
            if len({nd.get("ref") for nd in way.findall("nd")}) == 1
        ]
        self.assertEqual(self_looping, [], "The collapsed edge should not remain a way")

    def test_restore_zero_length_way_refs_leaves_normal_ways_alone(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            xml_path = Path(tmpdir, "ways.osm.xml")
            xml_path.write_text(
                """<osm version="0.6">
  <node id="1" lat="0" lon="0"/>
  <node id="2" lat="1" lon="1"/>
  <way id="10"><nd ref="1"/></way>
  <way id="11"><nd ref="1"/><nd ref="2"/></way>
</osm>"""
            )

            OSW2OSM._restore_zero_length_way_refs(xml_path)

            root = ET.parse(xml_path).getroot()

        refs = {
            way.get("id"): [nd.get("ref") for nd in way.findall("nd")]
            for way in root.findall(".//way")
        }
        self.assertEqual(refs["10"], ["1", "1"])
        self.assertEqual(refs["11"], ["1", "2"])

    def test_osm2osw_lone_zero_length_way_becomes_exactly_one_node_and_one_edge(self):
        """OSM w1 = [n0, n0], and nothing else, converts to OSW e1 = (n0, n0)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = asyncio.run(
                OSM2OSW(
                    prefix="only",
                    osm_file=str(ZERO_LENGTH_WAY_ONLY_OSM),
                    workdir=tmpdir,
                ).convert()
            )
            self.assertTrue(result.status, msg=result.error)

            datasets = {}
            for file_path in result.generated_files:
                name = Path(file_path).name.split(".")[-2]
                with open(file_path) as f:
                    datasets[name] = json.load(f)["features"]

        self.assertEqual(set(datasets), {"nodes", "edges"})
        self.assertEqual(len(datasets["nodes"]), 1)
        self.assertEqual(len(datasets["edges"]), 1)

        node = datasets["nodes"][0]
        edge = datasets["edges"][0]
        self.assertEqual(edge["properties"]["_u_id"], node["properties"]["_id"])
        self.assertEqual(edge["properties"]["_v_id"], node["properties"]["_id"])

        coordinates = edge["geometry"]["coordinates"]
        self.assertEqual(len(coordinates), 2)
        self.assertEqual(coordinates[0], coordinates[1])
        self.assertEqual(coordinates[0], node["geometry"]["coordinates"])

    def test_osm2osw_zero_length_way_between_co_located_nodes_keeps_both(self):
        """OSM w1 = [n0, n1] with n0 and n1 at one location stays e1 = (n0, n1)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = asyncio.run(
                OSM2OSW(
                    prefix="two_nodes",
                    osm_file=str(ZERO_LENGTH_WAY_TWO_NODES_OSM),
                    workdir=tmpdir,
                ).convert()
            )
            self.assertTrue(result.status, msg=result.error)

            datasets = {}
            for file_path in result.generated_files:
                name = Path(file_path).name.split(".")[-2]
                with open(file_path) as f:
                    datasets[name] = json.load(f)["features"]

        self.assertEqual(set(datasets), {"nodes", "edges"})
        self.assertEqual(len(datasets["nodes"]), 2)
        self.assertEqual(len(datasets["edges"]), 1)

        # Identical geometry, so only the tags tell the two nodes apart.
        coordinates = {tuple(node["geometry"]["coordinates"]) for node in datasets["nodes"]}
        self.assertEqual(len(coordinates), 1)

        kerbs = [
            node for node in datasets["nodes"]
            if node["properties"].get("barrier") == "kerb"
        ]
        self.assertEqual(len(kerbs), 1)
        self.assertEqual(kerbs[0]["properties"].get("kerb"), "flush")

        edge = datasets["edges"][0]
        node_ids = {node["properties"]["_id"] for node in datasets["nodes"]}
        self.assertNotEqual(edge["properties"]["_u_id"], edge["properties"]["_v_id"])
        self.assertEqual(
            {edge["properties"]["_u_id"], edge["properties"]["_v_id"]},
            node_ids,
        )

    def test_osm2osw_zero_length_way_between_untagged_co_located_nodes_keeps_both(self):
        """OSM w1 = [n0, n1] with two untagged nodes at one location."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = asyncio.run(
                OSM2OSW(
                    prefix="bare_nodes",
                    osm_file=str(ZERO_LENGTH_WAY_BARE_NODES_OSM),
                    workdir=tmpdir,
                ).convert()
            )
            self.assertTrue(result.status, msg=result.error)

            datasets = {}
            for file_path in result.generated_files:
                name = Path(file_path).name.split(".")[-2]
                with open(file_path) as f:
                    datasets[name] = json.load(f)["features"]

        self.assertEqual(set(datasets), {"nodes", "edges"})
        self.assertEqual(len(datasets["nodes"]), 2)
        self.assertEqual(len(datasets["edges"]), 1)

        coordinates = {tuple(node["geometry"]["coordinates"]) for node in datasets["nodes"]}
        self.assertEqual(len(coordinates), 1)

        node_ids = {node["properties"]["_id"] for node in datasets["nodes"]}
        self.assertEqual(len(node_ids), 2)

        edge = datasets["edges"][0]
        self.assertNotEqual(edge["properties"]["_u_id"], edge["properties"]["_v_id"])
        self.assertEqual(
            {edge["properties"]["_u_id"], edge["properties"]["_v_id"]},
            node_ids,
        )

    def test_osm2osw_zero_length_way_becomes_one_node_and_one_edge(self):
        """OSM w1 = [n0, n0] must convert back to OSW e1 = (n0, n0)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = asyncio.run(
                OSM2OSW(prefix="zero", osm_file=str(ZERO_LENGTH_WAY_OSM), workdir=tmpdir).convert()
            )
            self.assertTrue(result.status, msg=result.error)

            datasets = {}
            for file_path in result.generated_files:
                name = Path(file_path).name.split(".")[-2]
                with open(file_path) as f:
                    datasets[name] = json.load(f)["features"]

        zero_length = [
            edge for edge in datasets["edges"]
            if edge["properties"]["_u_id"] == edge["properties"]["_v_id"]
        ]
        self.assertEqual(len(zero_length), 1)
        edge = zero_length[0]

        # The edge starts and ends at one node that is present in nodes.geojson.
        node_ids = {node["properties"]["_id"] for node in datasets["nodes"]}
        self.assertIn(edge["properties"]["_u_id"], node_ids)
        node = next(
            n for n in datasets["nodes"]
            if n["properties"]["_id"] == edge["properties"]["_u_id"]
        )

        coordinates = edge["geometry"]["coordinates"]
        self.assertEqual(len(coordinates), 2)
        self.assertEqual(coordinates[0], coordinates[1])
        self.assertEqual(coordinates[0], node["geometry"]["coordinates"])

    def test_osm2osw_zero_length_way_collapses_to_a_point_when_disallowed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = asyncio.run(
                OSM2OSW(
                    prefix="zero",
                    osm_file=str(ZERO_LENGTH_WAY_OSM),
                    workdir=tmpdir,
                    config=DROP_ZERO_LENGTH_LINES,
                ).convert()
            )
            self.assertTrue(result.status, msg=result.error)

            edges = []
            for file_path in result.generated_files:
                if file_path.endswith("edges.geojson"):
                    with open(file_path) as f:
                        edges = json.load(f)["features"]

        self.assertEqual(
            [e for e in edges if e["properties"]["_u_id"] == e["properties"]["_v_id"]],
            [],
            "The collapsed edge should not remain an edge",
        )

    def test_simplify_keeps_a_self_looping_node(self):
        """A self-loop is not a degree-2 continuation and must survive simplify."""
        with tempfile.TemporaryDirectory() as tmpdir:
            osm_graph = OSMGraph.from_osm_file(
                str(ZERO_LENGTH_WAY_OSM),
                OSWHelper.osw_way_filter,
                OSWHelper.osw_node_filter,
                OSWHelper.osw_point_filter,
                OSWHelper.osw_line_filter,
                OSWHelper.osw_zone_filter,
                OSWHelper.osw_polygon_filter,
            )
            def self_loop_refs(graph):
                return [
                    d["ndref"] for u, v, d in graph.edges(data=True)
                    if u == v
                ]

            before = self_loop_refs(osm_graph.get_graph())
            osm_graph.simplify()
            after = self_loop_refs(osm_graph.get_graph())

        self.assertEqual(before, [[1, 1]])
        # Splicing the node into its own way would grow this to [1, 1, 1] and
        # then delete it as an internal node.
        self.assertEqual(after, [[1, 1]])


if __name__ == "__main__":
    unittest.main()
