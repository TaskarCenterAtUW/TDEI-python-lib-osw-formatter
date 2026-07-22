import json
import tempfile
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET

from src.osm_osw_reformatter.helpers.osw import OSWHelper
from src.osm_osw_reformatter.osw2osm.osw2osm import OSW2OSM
from src.osm_osw_reformatter.serializer.osm.osm_graph import OSMGraph, OSMWayParser


FIXTURE_DIR = Path(__file__).parents[1] / "test_files" / "zero_length_geometry"
OSM_FIXTURE_DIR = FIXTURE_DIR / "osm"
OSW_FIXTURE_DIR = FIXTURE_DIR / "osw"


def _osm_fixture(filename):
    return str(OSM_FIXTURE_DIR / filename)


def _merge_osw_zip_dataset(zip_filename, output_dir):
    unzipped_files = OSWHelper.unzip(str(OSW_FIXTURE_DIR / zip_filename), output_dir)
    return OSWHelper.merge(unzipped_files, output_dir, "cleaned")


def _parse_osm_edges(filename):
    parser = OSMWayParser(OSWHelper.osw_way_filter)
    parser.apply_file(_osm_fixture(filename), locations=True)
    return parser.G


def _graph_from_osm(filename):
    osm_graph = OSMGraph.from_osm_file(
        _osm_fixture(filename),
        OSWHelper.osw_way_filter,
        OSWHelper.osw_node_filter,
        OSWHelper.osw_point_filter,
        OSWHelper.osw_line_filter,
        OSWHelper.osw_zone_filter,
        OSWHelper.osw_polygon_filter,
    )
    osm_graph.construct_geometries()
    return osm_graph


class TestZeroLengthGeometryCleanup(unittest.TestCase):
    def test_osm2osw_duplicate_node_refs_are_skipped(self):
        graph = _parse_osm_edges("duplicate_node_refs_sidewalk.xml")

        self.assertEqual(len(graph.edges), 0)

    def test_osm2osw_different_node_refs_with_identical_coordinates_are_skipped(self):
        graph = _parse_osm_edges("identical_coordinate_crossing.xml")

        self.assertEqual(len(graph.edges), 0)

    def test_osm2osw_valid_distinct_edge_is_preserved(self):
        graph = _parse_osm_edges("valid_sidewalk_edge.xml")

        self.assertEqual(len(graph.edges), 1)

    def test_osm2osw_collapsed_line_is_skipped(self):
        osm_graph = _graph_from_osm("collapsed_fence_line.xml")

        self.assertNotIn("l700001", osm_graph.get_graph().nodes)

    def test_osm2osw_line_duplicate_consecutive_coordinates_are_cleaned(self):
        osm_graph = _graph_from_osm("tree_row_duplicate_coordinate_line.xml")

        coords = list(osm_graph.get_graph().nodes["l700002"]["geometry"].coords)
        self.assertEqual(coords, [(-122.34028, 47.67851), (-122.3401, 47.67872)])

    def test_osm2osw_zero_length_edge_preserves_tagged_node(self):
        osm_graph = _graph_from_osm("zero_length_edge_orphan_nodes.xml")

        self.assertEqual(len(osm_graph.get_graph().edges), 0)
        self.assertEqual(len(osm_graph.get_graph().nodes), 1)
        node_data = next(iter(osm_graph.get_graph().nodes(data=True)))[1]
        self.assertEqual(node_data.get("ext:highway"), "footway")
        self.assertEqual(node_data.get("ext:footway"), "sidewalk")
        self.assertEqual(node_data.get("ext:surface"), "concrete")

    def test_osm2osw_zero_length_edge_writes_valid_custom_point_geojson(self):
        osm_graph = _graph_from_osm("zero_length_edge_orphan_nodes.xml")
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
            merged_path = _merge_osw_zip_dataset("edge_zero_length.zip", tmpdir)

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
            merged_path = _merge_osw_zip_dataset("line_zero_length.zip", tmpdir)

            with open(merged_path) as f:
                merged = json.load(f)

        self.assertEqual(len(merged["features"]), 1)
        self.assertEqual(merged["features"][0]["geometry"]["type"], "Point")
        self.assertEqual(
            merged["features"][0]["geometry"]["coordinates"],
            [-122.34562, 47.66105],
        )

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

            result = OSW2OSM(zip_file_path=str(zip_path), workdir=tmpdir, prefix="line").convert()

            self.assertTrue(result.status, msg=getattr(result, "error", "Conversion failed"))
            root = ET.parse(result.generated_files).getroot()
            nodes = root.findall(".//node")
            ways = root.findall(".//way")

        self.assertEqual(len(nodes), 1)
        self.assertEqual(len(ways), 0)
        tags = {tag.get("k"): tag.get("v") for tag in nodes[0].findall("tag")}
        self.assertEqual(tags.get("barrier"), "fence")
        self.assertEqual(tags.get("name"), "Aurora Avenue construction fence")


if __name__ == "__main__":
    unittest.main()
